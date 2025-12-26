"""
音频转文字（ASR）服务 - 使用远程 API
支持：
- 远程 Whisper API（可配置多个接口）
- 音频预处理（降噪、音量标准化）
- 实时流式转写（WebSocket）
"""
import io
import logging
import os
import tempfile
import warnings
import asyncio
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import librosa
import numpy as np
import soundfile as sf
# pydub removed - no longer needed for remote ASR API

from ..config import get_settings

logger = logging.getLogger(__name__)

# 抑制一些不必要的警告
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# 导入远程API服务
from .asr_api_service import call_remote_asr_api
from .db.postgres import get_conn

SUPPORTED_AUDIO_FORMATS = {
    ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a",
    ".wav", ".webm", ".ogg", ".flac"
}


def is_audio_file(filename: str) -> bool:
    """检查文件是否为支持的音频格式"""
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_AUDIO_FORMATS


def _get_default_asr_config() -> Optional[Dict[str, Any]]:
    """获取默认的ASR API配置"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, api_url, api_key, model_name, response_format, extra_params
                    FROM asr_configs
                    WHERE is_active = TRUE AND is_default = TRUE
                    LIMIT 1
                """)
                row = cur.fetchone()
                
                if not row:
                    # 如果没有默认配置，使用第一个激活的配置
                    cur.execute("""
                        SELECT id, name, api_url, api_key, model_name, response_format, extra_params
                        FROM asr_configs
                        WHERE is_active = TRUE
                        ORDER BY created_at
                        LIMIT 1
                    """)
                    row = cur.fetchone()
                
                if row:
                    return {
                        "id": row[0],
                        "name": row[1],
                        "api_url": row[2],
                        "api_key": row[3],
                        "model_name": row[4] or "whisper",
                        "response_format": row[5] or "verbose_json",
                        "extra_params": row[6] or {}
                    }
                
                return None
    
    except Exception as e:
        logger.error(f"Failed to get ASR config: {e}")
        return None


def _get_whisper_model_DEPRECATED():
    """获取或初始化 Whisper 模型（单例模式）"""
    global _whisper_model
    
    if _whisper_model is not None:
        return _whisper_model
    
    settings = get_settings()
    
    if not settings.ASR_ENABLED:
        raise ValueError("ASR 功能未启用，请设置 ASR_ENABLED=true")
    
    try:
        from faster_whisper import WhisperModel
        
        device = settings.ASR_DEVICE
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        
        logger.info(
            "Loading Whisper model=%s device=%s compute_type=%s",
            settings.ASR_MODEL,
            device,
            settings.ASR_COMPUTE_TYPE,
        )
        
        # 设置 HuggingFace 国内镜像（加速下载）
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        
        # 使用持久化目录存储模型
        download_root = os.getenv('WHISPER_MODEL_DIR', '/app/data/whisper_models')
        
        _whisper_model = WhisperModel(
            settings.ASR_MODEL,
            device=device,
            compute_type=settings.ASR_COMPUTE_TYPE,
            download_root=download_root,
        )
        
        logger.info("Whisper model loaded successfully")
        return _whisper_model
        
    except Exception as exc:
        logger.error("Failed to load Whisper model: %s", exc)
        raise RuntimeError(f"无法加载 Whisper 模型: {exc}") from exc


def _get_diarization_pipeline():
    """获取或初始化说话人识别管道（单例模式）"""
    global _diarization_pipeline
    
    if _diarization_pipeline is not None:
        return _diarization_pipeline
    
    settings = get_settings()
    
    if not settings.ASR_ENABLE_DIARIZATION:
        return None
    
    if not settings.ASR_HF_TOKEN:
        logger.warning(
            "说话人识别需要 HuggingFace Token，请设置 ASR_HF_TOKEN。"
            "获取方式：https://huggingface.co/settings/tokens"
        )
        return None
    
    try:
        from pyannote.audio import Pipeline
        
        logger.info("Loading speaker diarization pipeline...")
        
        _diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=settings.ASR_HF_TOKEN,
        )
        
        # 尝试使用 GPU
        device = settings.ASR_DEVICE
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        
        if device == "cuda":
            try:
                import torch
                _diarization_pipeline.to(torch.device("cuda"))
                logger.info("Diarization pipeline loaded on GPU")
            except Exception as exc:
                logger.warning("Failed to move diarization to GPU: %s", exc)
        else:
            logger.info("Diarization pipeline loaded on CPU")
        
        return _diarization_pipeline
        
    except Exception as exc:
        logger.error("Failed to load diarization pipeline: %s", exc)
        return None


def preprocess_audio(
    audio_path: str,
    reduce_noise: bool = True,
    normalize: bool = True,
) -> str:
    """
    音频预处理：降噪和音量标准化
    
    Args:
        audio_path: 音频文件路径
        reduce_noise: 是否降噪
        normalize: 是否标准化音量
        
    Returns:
        处理后的音频文件路径
    """
    if not reduce_noise and not normalize:
        return audio_path
    
    try:
        logger.info("Preprocessing audio: noise_reduction=%s normalize=%s", reduce_noise, normalize)
        
        # 加载音频
        audio_data, sample_rate = librosa.load(audio_path, sr=16000, mono=True)
        
        # 降噪
        if reduce_noise:
            try:
                import noisereduce as nr
                audio_data = nr.reduce_noise(
                    y=audio_data,
                    sr=sample_rate,
                    stationary=True,
                    prop_decrease=0.8,
                )
                logger.debug("Noise reduction applied")
            except Exception as exc:
                logger.warning("Noise reduction failed, skipping: %s", exc)
        
        # 音量标准化
        if normalize:
            # 使用 RMS 标准化
            rms = np.sqrt(np.mean(audio_data ** 2))
            if rms > 0:
                target_rms = 0.1
                audio_data = audio_data * (target_rms / rms)
                # 防止削波
                max_val = np.abs(audio_data).max()
                if max_val > 1.0:
                    audio_data = audio_data / max_val
                logger.debug("Audio normalized")
        
        # 保存处理后的音频
        output_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        sf.write(output_path, audio_data, sample_rate)
        
        logger.info("Audio preprocessing completed: %s", output_path)
        return output_path
        
    except Exception as exc:
        logger.warning("Audio preprocessing failed: %s, using original file", exc)
        return audio_path


def perform_diarization(
    audio_path: str,
    min_speakers: int = 1,
    max_speakers: int = 10,
) -> Optional[List[Dict[str, Any]]]:
    """
    执行说话人识别
    
    Args:
        audio_path: 音频文件路径
        min_speakers: 最小说话人数量
        max_speakers: 最大说话人数量
        
    Returns:
        说话人片段列表，每个片段包含 {speaker, start, end}
    """
    pipeline = _get_diarization_pipeline()
    if pipeline is None:
        return None
    
    try:
        logger.info("Performing speaker diarization...")
        
        diarization = pipeline(
            audio_path,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": turn.start,
                "end": turn.end,
            })
        
        logger.info("Diarization completed: found %d segments", len(segments))
        return segments
        
    except Exception as exc:
        logger.error("Diarization failed: %s", exc)
        return None


def merge_transcription_with_diarization(
    transcription_segments: List[Dict[str, Any]],
    diarization_segments: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    将转录结果与说话人识别结果合并
    
    Args:
        transcription_segments: Whisper 转录的片段
        diarization_segments: 说话人识别的片段
        
    Returns:
        合并后的片段，每个片段包含文本、时间戳和说话人
    """
    if not diarization_segments:
        return transcription_segments
    
    merged = []
    
    for trans_seg in transcription_segments:
        trans_start = trans_seg["start"]
        trans_end = trans_seg["end"]
        trans_mid = (trans_start + trans_end) / 2
        
        # 找到中点时间对应的说话人
        speaker = "Unknown"
        for diar_seg in diarization_segments:
            if diar_seg["start"] <= trans_mid <= diar_seg["end"]:
                speaker = diar_seg["speaker"]
                break
        
        merged.append({
            **trans_seg,
            "speaker": speaker,
        })
    
    return merged


async def transcribe_audio(
    audio_data: bytes,
    filename: str,
    language: Optional[str] = None,
    enhance: bool = False,
    enhancement_type: str = "punctuation",
    model_id: Optional[str] = None
) -> Tuple[str, float]:
    """
    使用远程 API 转录音频文件
    
    Args:
        audio_data: 音频文件的二进制数据
        filename: 文件名（用于确定格式）
        language: 可选的语言代码（如 'zh', 'en'）
        enhance: 是否使用LLM增强标点符号和段落（默认False）
        enhancement_type: 增强类型 ("punctuation", "formal", "meeting")
        model_id: LLM模型ID（可选，不指定则使用默认模型）
        
    Returns:
        (转录后的文本, 音频时长)
        
    Raises:
        ValueError: 如果ASR服务未配置或音频格式不支持
        RuntimeError: 如果转录失败
    """
    settings = get_settings()
    
    if not settings.ASR_ENABLED:
        raise ValueError("ASR 服务未启用，请设置环境变量 ASR_ENABLED=true")
    
    if not is_audio_file(filename):
        ext = Path(filename).suffix.lower()
        raise ValueError(
            f"不支持的音频格式: {ext}。"
            f"支持的格式: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}"
        )
    
    # 获取ASR配置
    asr_config = _get_default_asr_config()
    if not asr_config:
        raise ValueError("未找到可用的ASR API配置，请在系统设置中添加")
    
    logger.info(
        "Starting audio transcription using remote API: %s",
        asr_config['name']
    )
    
    # 创建临时文件
    suffix = Path(filename).suffix.lower()
    temp_input = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temp_input.write(audio_data)
    temp_input.close()
    temp_input_path = temp_input.name
    
    temp_processed_path = None
    
    try:
        logger.info(
            "Starting audio transcription file=%s size=%d language=%s",
            filename,
            len(audio_data),
            language or "auto",
        )
        
        # 音频预处理（可选）
        if settings.ASR_ENABLE_PREPROCESSING:
            temp_processed_path = preprocess_audio(
                temp_input_path,
                reduce_noise=settings.ASR_NOISE_REDUCTION,
                normalize=settings.ASR_NORMALIZE_AUDIO,
            )
            audio_path_for_transcription = temp_processed_path
        else:
            audio_path_for_transcription = temp_input_path
        
        # 准备额外参数
        extra_params = dict(asr_config.get('extra_params', {}))
        if language:
            extra_params['language'] = language
        
        # 调用远程API
        text, duration = await call_remote_asr_api(
            audio_file_path=Path(audio_path_for_transcription),
            api_url=asr_config['api_url'],
            model_name=asr_config['model_name'],
            response_format=asr_config['response_format'],
            api_key=asr_config.get('api_key'),
            extra_params=extra_params
        )
        
        logger.info(
            "Audio transcription completed file=%s text_length=%d duration=%.2fs",
            filename,
            len(text),
            duration,
        )
        
        # LLM文本增强（如果启用）
        if enhance and text:
            from .text_enhancement_service import enhance_transcription
            try:
                logger.info(f"Starting text enhancement (type={enhancement_type}, model={model_id})")
                original_length = len(text)
                text = await enhance_transcription(
                    text=text,
                    enhancement_type=enhancement_type,
                    model_id=model_id
                )
                logger.info(f"Text enhancement completed: {original_length} → {len(text)} chars")
            except Exception as e:
                logger.warning(f"Text enhancement failed, using original: {e}")
        
        # 更新使用统计
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE asr_configs SET usage_count = usage_count + 1 WHERE id = %s",
                        (asr_config['id'],)
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update ASR config usage count: {e}")
        
        return text, duration
        
    except Exception as exc:
        logger.error("Audio transcription failed file=%s error=%s", filename, exc)
        raise RuntimeError(f"音频转录失败: {exc}") from exc
        
    finally:
        # 清理临时文件
        try:
            Path(temp_input_path).unlink()
            if temp_processed_path and temp_processed_path != temp_input_path:
                Path(temp_processed_path).unlink()
        except Exception as e:
            logger.warning("Failed to delete temp files: %s", e)


def get_model_info() -> Dict[str, Any]:
    """获取当前 ASR 配置信息"""
    settings = get_settings()
    
    return {
        "enabled": settings.ASR_ENABLED,
        "model": settings.ASR_MODEL,
        "device": settings.ASR_DEVICE,
        "preprocessing": settings.ASR_ENABLE_PREPROCESSING,
        "noise_reduction": settings.ASR_NOISE_REDUCTION,
        "normalize_audio": settings.ASR_NORMALIZE_AUDIO,
        "diarization": settings.ASR_ENABLE_DIARIZATION,
        "timestamps": settings.ASR_ENABLE_TIMESTAMPS,
        "word_timestamps": settings.ASR_WORD_TIMESTAMPS,
        "language": settings.ASR_LANGUAGE or "auto",
    }


async def transcribe_audio_streaming(
    audio_file_path: Path,
    language: Optional[str] = None
) -> Tuple[str, float]:
    """
    流式转写音频（用于WebSocket实时转写）
    
    简化版本：
    - 不进行复杂的预处理（实时性优先）
    - 只返回纯文本和时长
    
    Args:
        audio_file_path: 音频文件路径
        language: 语言代码（如 "zh", "en"）
    
    Returns:
        (转写文本, 音频时长)
    """
    settings = get_settings()
    
    if not settings.ASR_ENABLED:
        raise ValueError("ASR 功能未启用")
    
    # 获取ASR配置
    asr_config = _get_default_asr_config()
    if not asr_config:
        raise ValueError("未找到可用的ASR API配置")
    
    try:
        # 准备额外参数
        extra_params = dict(asr_config.get('extra_params', {}))
        if language:
            extra_params['language'] = language
        
        # 调用远程API
        text, duration = await call_remote_asr_api(
            audio_file_path=audio_file_path,
            api_url=asr_config['api_url'],
            model_name=asr_config['model_name'],
            response_format=asr_config['response_format'],
            api_key=asr_config.get('api_key'),
            extra_params=extra_params,
            timeout=180  # 流式转写使用较长超时（3分钟）
        )
        
        logger.info(f"Streaming transcription completed: {len(text)} chars")
        
        return text, duration
    
    except Exception as exc:
        logger.error("Streaming transcription failed: %s", exc)
        raise RuntimeError(f"流式转写失败: {exc}") from exc
