"""
WebSocket 实时语音转写路由
"""
import json
import uuid
import asyncio
import tempfile
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from pydantic import BaseModel

from app.services.asr_service import transcribe_audio_streaming
from app.utils.auth import decode_access_token, TokenData
from app.services.db.postgres import get_conn

router = APIRouter()

# 活跃的WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)

manager = ConnectionManager()

class ASRSession:
    """ASR 会话：管理单次录音的转写过程"""
    def __init__(self, session_id: str, user_id: str, config: dict):
        self.session_id = session_id
        self.user_id = user_id
        self.config = config
        self.audio_chunks: list[bytes] = []
        self.full_transcript = ""
        self.start_time = datetime.now()
        self.is_active = True
        self.temp_audio_file: Optional[Path] = None
        
        # 实时转录相关
        self.realtime_enabled = config.get("realtime", False)
        self.realtime_processor = None
        
        if self.realtime_enabled:
            from app.services.asr_realtime import RealtimeASRProcessor
            self.realtime_processor = RealtimeASRProcessor(
                session_id=session_id,
                language=config.get("language", "zh"),
                chunk_duration_ms=config.get("chunk_duration_ms", 3000),
                min_chunk_size_bytes=config.get("min_chunk_size_bytes", 50000),
                overlap_duration_ms=config.get("overlap_duration_ms", 500),
                context_window=config.get("context_window", 3),
                on_transcript=None  # 将在WebSocket中设置
            )
    
    def add_audio_chunk(self, chunk: bytes):
        """添加音频数据块"""
        if self.is_active:
            self.audio_chunks.append(chunk)
            # 如果启用实时转录，也添加到实时处理器
            if self.realtime_enabled and self.realtime_processor:
                self.realtime_processor.add_audio_chunk(chunk)
    
    def get_duration(self) -> float:
        """获取录音时长（秒）"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_full_audio(self) -> bytes:
        """获取完整音频数据"""
        return b''.join(self.audio_chunks)
    
    async def start_realtime(self):
        """启动实时转录"""
        if self.realtime_processor:
            self.realtime_processor.start()
    
    async def stop_realtime(self):
        """停止实时转录"""
        if self.realtime_processor:
            await self.realtime_processor.stop()
            # 获取实时转录的完整文本
            self.full_transcript = self.realtime_processor.get_full_transcript()

# 活跃的ASR会话
active_sessions: Dict[str, ASRSession] = {}

@router.websocket("/ws/asr")
async def websocket_asr_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket 实时语音转写端点
    
    客户端需要发送:
    1. Token 作为查询参数进行认证
    2. 音频数据块 (binary)
    3. 控制命令 (JSON)
       - {"action": "start", "config": {...}}
       - {"action": "stop"}
       - {"action": "pause"}
    
    服务端发送:
    1. 转写片段 {"type": "transcript", "text": "...", "is_partial": true}
    2. 最终结果 {"type": "final", "recording_id": "...", "full_transcript": "..."}
    3. 错误 {"type": "error", "message": "..."}
    4. 状态 {"type": "status", "message": "..."}
    """
    # 认证
    try:
        token_data: TokenData = decode_access_token(token)
        user_id = token_data.user_id
    except Exception as e:
        await websocket.close(code=1008, reason="Authentication failed")
        return
    
    # 创建会话ID
    session_id = f"asr_{uuid.uuid4().hex[:12]}"
    
    await manager.connect(session_id, websocket)
    
    try:
        await manager.send_message(session_id, {
            "type": "status",
            "message": "Connected to ASR service",
            "session_id": session_id
        })
        
        asr_session: Optional[ASRSession] = None
        
        while True:
            # 接收消息（可能是音频数据或控制命令）
            try:
                message = await websocket.receive()
                
                # 处理文本消息（控制命令）
                if "text" in message:
                    data = json.loads(message["text"])
                    action = data.get("action")
                    
                    if action == "start":
                        # 开始录音
                        config = data.get("config", {})
                        asr_session = ASRSession(session_id, user_id, config)
                        active_sessions[session_id] = asr_session
                        
                        # 如果启用实时转录，设置回调并启动
                        if asr_session.realtime_enabled and asr_session.realtime_processor:
                            # 设置实时回调
                            async def on_transcript_callback(transcript):
                                await manager.send_message(session_id, {
                                    "type": "transcript",
                                    "text": transcript.text,
                                    "is_final": transcript.is_final,
                                    "chunk_id": transcript.chunk_id,
                                    "timestamp": transcript.timestamp
                                })
                            
                            asr_session.realtime_processor.on_transcript = on_transcript_callback
                            await asr_session.start_realtime()
                            
                            await manager.send_message(session_id, {
                                "type": "status",
                                "message": "实时转录已启动 - 即录即转模式",
                                "session_id": session_id,
                                "realtime": True
                            })
                        else:
                            await manager.send_message(session_id, {
                                "type": "status",
                                "message": "Recording started - transcription will be done when you finish",
                                "session_id": session_id,
                                "realtime": False
                            })
                    
                    elif action == "stop":
                        # 停止录音
                        if asr_session:
                            # 停止实时转录（如果启用）
                            if asr_session.realtime_enabled:
                                await asr_session.stop_realtime()
                            await finalize_recording(session_id, asr_session, websocket)
                            asr_session = None
                        break
                    
                    elif action == "pause":
                        if asr_session:
                            asr_session.is_active = False
                            await manager.send_message(session_id, {
                                "type": "status",
                                "message": "Recording paused"
                            })
                
                # 处理音频数据
                elif "bytes" in message:
                    if asr_session and asr_session.is_active:
                        audio_data = message["bytes"]
                        asr_session.add_audio_chunk(audio_data)
                        
                        # 实时模式下，音频已经自动添加到realtime_processor
                        # 无需额外操作
            
            except WebSocketDisconnect:
                break
            except Exception as e:
                await manager.send_message(session_id, {
                    "type": "error",
                    "message": f"Error: {str(e)}"
                })
                break
    
    finally:
        # 清理
        manager.disconnect(session_id)
        if session_id in active_sessions:
            del active_sessions[session_id]

async def transcribe_chunk(audio_data: bytes, config: dict) -> str:
    """
    转写单个音频块
    使用ffmpeg将音频转换为wav格式
    """
    import subprocess
    import logging
    
    logger = logging.getLogger(__name__)
    
    # 检查音频数据大小，太小则跳过
    if len(audio_data) < 10000:  # 小于10KB则跳过
        logger.warning(f"Audio chunk too small: {len(audio_data)} bytes, skipping")
        return ""
    
    # 检测可能的音频格式
    file_ext = '.webm'  # 默认格式
    
    # 简单的格式检测（通过文件头）
    if audio_data[:4] == b'OggS':
        file_ext = '.ogg'
    elif audio_data[:4] == b'ftyp' or audio_data[4:8] == b'ftyp':
        file_ext = '.m4a'
    elif audio_data[:4] == b'RIFF':
        file_ext = '.wav'
    
    # 保存原始音频到临时文件
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
        temp_file.write(audio_data)
        temp_input_path = temp_file.name
    
    # 创建wav输出文件路径
    temp_wav_path = temp_input_path.replace(file_ext, '.wav')
    
    try:
        # 使用ffmpeg转换为wav (16kHz, 单声道)
        cmd = [
            'ffmpeg', '-y', '-i', temp_input_path,
            '-ar', '16000',  # 采样率16kHz
            '-ac', '1',      # 单声道
            '-f', 'wav',     # wav格式
            temp_wav_path
        ]
        
        # 运行ffmpeg，隐藏输出
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True,
            timeout=10
        )
        
        # 检查输出文件是否存在且大小合理
        if not Path(temp_wav_path).exists() or Path(temp_wav_path).stat().st_size < 1000:
            logger.error(f"FFmpeg output invalid: {temp_wav_path}")
            return ""
        
        # 使用转换后的wav文件进行转写
        transcript, _ = await transcribe_audio_streaming(
            Path(temp_wav_path),
            language=config.get("language", "zh")
        )
        return transcript.strip()
        
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout")
        return ""
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr.decode() if e.stderr else 'unknown'}")
        return ""
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return ""
        
    finally:
        # 删除临时文件
        Path(temp_input_path).unlink(missing_ok=True)
        if Path(temp_wav_path).exists():
            Path(temp_wav_path).unlink(missing_ok=True)

async def background_transcribe(recording_id: str, audio_path: str, language: str = "zh"):
    """
    后台任务：转写音频并更新数据库
    
    注意：并发控制已在 call_remote_asr_api 层面实现，此处无需重复包装
    """
    import subprocess
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting background transcription for {recording_id}")
        
        # 使用ffmpeg转换为wav
        webm_path = audio_path
        wav_path = webm_path.replace('.webm', '.wav')
        cmd = [
            'ffmpeg', '-y', '-i', webm_path,
            '-ar', '16000', '-ac', '1', '-f', 'wav',
            wav_path
        ]
        
        logger.info(f"Converting audio to WAV: {webm_path} -> {wav_path}")
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                      check=True, timeout=60)
        
        try:
            # 转写（内部已有并发控制）
            logger.info(f"Calling ASR service for {recording_id}")
            from app.services.asr_service import transcribe_audio
            with open(wav_path, 'rb') as f:
                audio_data = f.read()
            
            transcript, _ = await transcribe_audio(
                audio_data=audio_data,
                filename="recording.wav",
                language=language
            )
            
            transcript = transcript.strip()
            word_count = len(transcript)
            
            logger.info(f"Transcription completed for {recording_id}: {word_count} characters")
            
            # 更新数据库
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE voice_recordings 
                        SET transcript = %s, word_count = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (transcript, word_count, recording_id))
                conn.commit()
            
        finally:
            # 清理临时文件
            Path(wav_path).unlink(missing_ok=True)
        
        logger.info(f"Background transcription completed for {recording_id}")
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"FFmpeg timeout for {recording_id}: audio file may be too long")
        # 更新数据库状态为失败
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE voice_recordings 
                        SET import_status = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, ("failed", recording_id))
                conn.commit()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Background transcription failed for {recording_id}: {e}", exc_info=True)
        # 更新数据库状态为失败
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE voice_recordings 
                        SET import_status = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, ("failed", recording_id))
                conn.commit()
        except Exception:
            pass


async def finalize_recording(session_id: str, asr_session: ASRSession, websocket: WebSocket):
    """
    完成录音并保存到数据库（快速保存，后台转写）
    """
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # 获取完整音频
        full_audio = asr_session.get_full_audio()
        duration = int(asr_session.get_duration())
        
        # 生成recording_id
        recording_id = f"rec_{uuid.uuid4().hex[:12]}"
        
        # 保存音频文件到磁盘
        from app.config import get_settings
        settings = get_settings()
        audio_dir = Path(settings.APP_DATA_DIR) / "recordings"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        audio_filename = f"{recording_id}.webm"
        audio_path = audio_dir / audio_filename
        audio_path.write_bytes(full_audio)
        
        # 快速保存到数据库（不等待转写完成）
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO voice_recordings (
                        id, user_id, title, filename, duration, file_size,
                        audio_format, transcript, word_count, audio_path,
                        import_status, keep_audio, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    recording_id,
                    asr_session.user_id,
                    f"录音_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    audio_filename,
                    duration,
                    len(full_audio),
                    "webm",
                    "",  # 转写文本为空，后台处理
                    0,   # 字数为0
                    str(audio_path),
                    "pending",
                    True  # 保留音频文件
                ))
            conn.commit()
        
        # 立即发送结果给前端（不等待转写）
        await manager.send_message(session_id, {
            "type": "final",
            "recording_id": recording_id,
            "full_transcript": "",
            "duration": duration,
            "word_count": 0,
            "session_id": session_id
        })
        
        # 启动后台任务进行转写
        if len(full_audio) > 10000:  # 至少10KB
            asyncio.create_task(
                background_transcribe(recording_id, str(audio_path), asr_session.config.get("language", "zh"))
            )
        
    except Exception as e:
        logger.error(f"Failed to save recording: {e}")
        await manager.send_message(session_id, {
            "type": "error",
            "message": f"Failed to save recording: {str(e)}"
        })

