"""
ASR实时转录服务
支持即录即转（边录边转）
"""
import asyncio
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass

from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RealtimeTranscript:
    """实时转录结果"""
    text: str
    is_final: bool
    timestamp: float
    chunk_id: int


class RealtimeASRProcessor:
    """
    实时ASR处理器
    
    特点：
    1. 支持音频流分块处理
    2. 自动累积小块音频到合适大小再转录（避免频繁调用API）
    3. 支持并发控制（避免显存溢出）
    4. 提供实时回调通知转录结果
    """
    
    def __init__(
        self,
        session_id: str,
        language: str = "zh",
        chunk_duration_ms: int = 3000,  # 每3秒转录一次
        min_chunk_size_bytes: int = 50000,  # 最小50KB才触发转录
        overlap_duration_ms: int = 500,  # 重叠500ms用于上下文
        context_window: int = 3,  # 保留最近3段转录作为上下文
        on_transcript: Optional[Callable[[RealtimeTranscript], None]] = None,
    ):
        """
        Args:
            session_id: 会话ID
            language: 语言代码
            chunk_duration_ms: 分块时长（毫秒）
            min_chunk_size_bytes: 最小分块大小（字节）
            overlap_duration_ms: 音频块重叠时长（用于上下文连贯性）
            context_window: 保留多少段转录作为上下文
            on_transcript: 转录结果回调函数
        """
        self.session_id = session_id
        self.language = language
        self.chunk_duration_ms = chunk_duration_ms
        self.min_chunk_size_bytes = min_chunk_size_bytes
        self.overlap_duration_ms = overlap_duration_ms
        self.context_window = context_window
        self.on_transcript = on_transcript
        
        # 音频缓冲区
        self.audio_buffer: List[bytes] = []
        self.buffer_size = 0
        
        # 上下文管理：保留前一块音频用于重叠
        self.previous_audio_tail: Optional[bytes] = None
        
        # 状态
        self.is_active = False
        self.chunk_counter = 0
        self.start_time = None
        self.last_process_time = None
        
        # 转录历史
        self.transcripts: List[RealtimeTranscript] = []
        
        # 处理任务
        self.process_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"[实时ASR] 初始化 session={session_id} chunk_duration={chunk_duration_ms}ms "
            f"overlap={overlap_duration_ms}ms context_window={context_window}"
        )
    
    def start(self):
        """开始处理"""
        if not self.is_active:
            self.is_active = True
            self.start_time = datetime.now()
            self.last_process_time = datetime.now()
            # 启动后台处理任务
            self.process_task = asyncio.create_task(self._background_processor())
            logger.info(f"[实时ASR] 已启动 session={self.session_id}")
    
    async def stop(self):
        """停止处理"""
        if self.is_active:
            self.is_active = False
            # 处理剩余缓冲区
            if self.buffer_size > 0:
                await self._process_buffer(is_final=True)
            # 取消后台任务
            if self.process_task:
                self.process_task.cancel()
                try:
                    await self.process_task
                except asyncio.CancelledError:
                    pass
            logger.info(f"[实时ASR] 已停止 session={self.session_id}")
    
    def add_audio_chunk(self, audio_data: bytes):
        """添加音频数据块"""
        if self.is_active:
            self.audio_buffer.append(audio_data)
            self.buffer_size += len(audio_data)
    
    async def _background_processor(self):
        """后台处理任务：定期检查并处理缓冲区"""
        while self.is_active:
            try:
                # 检查是否需要处理
                now = datetime.now()
                time_since_last = (now - self.last_process_time).total_seconds() * 1000
                
                should_process = (
                    self.buffer_size >= self.min_chunk_size_bytes or
                    (time_since_last >= self.chunk_duration_ms and self.buffer_size > 0)
                )
                
                if should_process:
                    await self._process_buffer(is_final=False)
                    self.last_process_time = now
                
                # 等待一小段时间
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"[实时ASR] 后台处理错误 session={self.session_id}: {e}")
                await asyncio.sleep(1)
    
    async def _process_buffer(self, is_final: bool = False):
        """处理缓冲区中的音频（带上下文）"""
        if not self.audio_buffer:
            return
        
        # 获取缓冲区数据
        current_audio = b''.join(self.audio_buffer)
        chunk_id = self.chunk_counter
        self.chunk_counter += 1
        
        # 添加前一块的尾部作为上下文（音频重叠）
        if self.previous_audio_tail and not is_final:
            # 计算重叠部分大小（约占500ms）
            # 假设16kHz采样率，16位，单声道：16000 * 2 bytes/s = 32000 bytes/s
            overlap_bytes = int(32000 * self.overlap_duration_ms / 1000)
            audio_with_context = self.previous_audio_tail[-overlap_bytes:] + current_audio
        else:
            audio_with_context = current_audio
        
        # 保存当前音频的尾部用于下次重叠
        if not is_final and len(current_audio) > 10000:  # 至少10KB
            self.previous_audio_tail = current_audio
        
        # 清空缓冲区
        self.audio_buffer = []
        self.buffer_size = 0
        
        logger.info(
            f"[实时ASR] 处理音频块 session={self.session_id} chunk_id={chunk_id} "
            f"size={len(current_audio)} bytes context_size={len(audio_with_context)-len(current_audio)} "
            f"is_final={is_final}"
        )
        
        try:
            # 获取上下文文本（最近几段转录）
            context_text = self._get_context_text()
            
            # 使用并发控制进行转录
            from .asr_concurrency import execute_asr_with_concurrency_control
            
            async def do_transcription():
                return await self._transcribe_chunk(audio_with_context, context_text)
            
            # 执行转录（带并发控制和重试）
            text = await execute_asr_with_concurrency_control(
                do_transcription,
                task_id=f"{self.session_id}_chunk_{chunk_id}"
            )
            
            if text and text.strip():
                # 创建转录结果
                transcript = RealtimeTranscript(
                    text=text.strip(),
                    is_final=is_final,
                    timestamp=datetime.now().timestamp(),
                    chunk_id=chunk_id
                )
                
                self.transcripts.append(transcript)
                
                # 回调通知
                if self.on_transcript:
                    try:
                        self.on_transcript(transcript)
                    except Exception as e:
                        logger.error(f"[实时ASR] 回调错误: {e}")
                
                logger.info(
                    f"[实时ASR] 转录成功 session={self.session_id} chunk_id={chunk_id} "
                    f"text_length={len(text)}"
                )
            else:
                logger.debug(f"[实时ASR] 空转录结果 session={self.session_id} chunk_id={chunk_id}")
        
        except Exception as e:
            logger.error(
                f"[实时ASR] 转录失败 session={self.session_id} chunk_id={chunk_id}: {e}",
                exc_info=True
            )
    
    def _get_context_text(self) -> str:
        """获取上下文文本（最近几段转录）"""
        if not self.transcripts:
            return ""
        
        # 获取最近的转录片段
        recent_transcripts = self.transcripts[-self.context_window:]
        context = " ".join(t.text for t in recent_transcripts if t.text)
        
        # 限制上下文长度（避免太长）
        max_context_length = 200
        if len(context) > max_context_length:
            context = context[-max_context_length:]
        
        return context
    
    def _post_process_with_context(self, current_text: str, context_text: str) -> str:
        """
        基于上下文对当前转录结果进行后处理
        
        主要优化：
        1. 去除重复内容（音频重叠导致）
        2. 句子连接优化
        3. 标点符号修正
        """
        if not current_text or not context_text:
            return current_text
        
        current_text = current_text.strip()
        context_text = context_text.strip()
        
        # 1. 去除重复内容
        # 检查当前文本开头是否与上下文结尾重复
        overlap_found = False
        for overlap_len in range(min(50, len(current_text), len(context_text)), 5, -1):
            context_end = context_text[-overlap_len:]
            current_start = current_text[:overlap_len]
            
            # 计算相似度（允许轻微差异）
            if self._calculate_similarity(context_end, current_start) > 0.8:
                # 找到重复部分，去除
                current_text = current_text[overlap_len:].strip()
                overlap_found = True
                logger.debug(
                    f"[实时ASR] 检测到重叠 session={self.session_id} "
                    f"overlap_length={overlap_len} removed='{context_end}'"
                )
                break
        
        # 2. 句子连接优化
        if not overlap_found and current_text:
            # 如果上一句没有结束标点，当前句首字母可能需要小写（英文）
            # 或者需要添加连接词
            pass
        
        return current_text
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（简单的字符匹配）
        返回：0.0-1.0的相似度分数
        """
        if not text1 or not text2:
            return 0.0
        
        # 去除空格和标点符号
        import re
        text1_cleaned = re.sub(r'[^\w]', '', text1.lower())
        text2_cleaned = re.sub(r'[^\w]', '', text2.lower())
        
        if not text1_cleaned or not text2_cleaned:
            return 0.0
        
        # 计算字符级别的匹配度
        matches = sum(c1 == c2 for c1, c2 in zip(text1_cleaned, text2_cleaned))
        max_len = max(len(text1_cleaned), len(text2_cleaned))
        
        return matches / max_len if max_len > 0 else 0.0
    
    async def _transcribe_chunk(self, audio_data: bytes, context_text: str = "") -> str:
        """转录音频块"""
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        temp_file.write(audio_data)
        temp_file.close()
        temp_path = temp_file.name
        
        # 转换为WAV
        wav_path = temp_path.replace('.webm', '.wav')
        
        try:
            # 使用ffmpeg转换
            cmd = [
                'ffmpeg', '-y', '-i', temp_path,
                '-ar', '16000',  # 16kHz采样率
                '-ac', '1',      # 单声道
                '-f', 'wav',
                wav_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10
            )
            
            # 检查输出文件
            if not Path(wav_path).exists() or Path(wav_path).stat().st_size < 1000:
                logger.warning(f"[实时ASR] FFmpeg输出无效 session={self.session_id}")
                return ""
            
            # 调用ASR服务
            from .asr_service import transcribe_audio
            with open(wav_path, 'rb') as f:
                wav_data = f.read()
            
            text, _ = await transcribe_audio(
                audio_data=wav_data,
                filename="chunk.wav",
                language=self.language
            )
            
            # 如果有上下文，进行后处理优化
            if context_text and text:
                text = self._post_process_with_context(text, context_text)
            
            return text
            
        except subprocess.TimeoutExpired:
            logger.error(f"[实时ASR] FFmpeg超时 session={self.session_id}")
            return ""
        except subprocess.CalledProcessError as e:
            logger.error(f"[实时ASR] FFmpeg失败 session={self.session_id}: {e}")
            return ""
        except Exception as e:
            logger.error(f"[实时ASR] 转录失败 session={self.session_id}: {e}")
            return ""
        finally:
            # 清理临时文件
            Path(temp_path).unlink(missing_ok=True)
            if Path(wav_path).exists():
                Path(wav_path).unlink(missing_ok=True)
    
    def get_full_transcript(self) -> str:
        """获取完整转录文本"""
        return " ".join(t.text for t in self.transcripts if t.text)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "session_id": self.session_id,
            "is_active": self.is_active,
            "chunks_processed": self.chunk_counter,
            "transcripts_count": len(self.transcripts),
            "buffer_size": self.buffer_size,
            "full_text_length": len(self.get_full_transcript())
        }

