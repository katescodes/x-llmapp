"""
远程ASR API服务
用于调用远程语音转文本API
"""
import logging
import httpx
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

async def call_remote_asr_api(
    audio_file_path: Path,
    api_url: str,
    model_name: str = "whisper",
    response_format: str = "verbose_json",
    api_key: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
    timeout: int = 300
) -> Tuple[str, float]:
    """
    调用远程ASR API进行语音转文本
    
    Args:
        audio_file_path: 音频文件路径
        api_url: API地址
        model_name: 模型名称
        response_format: 响应格式
        api_key: API密钥（可选）
        extra_params: 额外参数
        timeout: 超时时间（秒）
    
    Returns:
        (转写文本, 音频时长)
    """
    try:
        # 读取音频文件
        with open(audio_file_path, 'rb') as f:
            audio_data = f.read()
        
        # 构建表单数据
        files = {
            'file': (audio_file_path.name, audio_data, 'audio/mpeg')
        }
        
        data = {
            'model': model_name,
            'response_format': response_format,
        }
        
        # 添加额外参数
        if extra_params:
            data.update(extra_params)
        
        # 如果extra_params中没有timestamp_granularities，添加word级别以支持标点
        if 'timestamp_granularities' not in data:
            data['timestamp_granularities[]'] = 'word'
        
        # 构建请求头
        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        # 发送请求
        # 设置更长的超时时间，包括连接超时和读取超时
        timeout_config = httpx.Timeout(
            timeout=timeout,
            connect=10.0,  # 连接超时10秒
            read=timeout,  # 读取超时使用传入的timeout值
            write=30.0     # 写入超时30秒
        )
        async with httpx.AsyncClient(timeout=timeout_config, verify=False) as client:
            logger.info(f"Calling ASR API: url={api_url}, file={audio_file_path.name}, size={len(audio_data)} bytes, model={model_name}, format={response_format}")
            
            response = await client.post(
                api_url,
                files=files,
                data=data,
                headers=headers
            )
            
            logger.info(f"ASR API response: status={response.status_code}")
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"ASR API success: text_length={len(result.get('text', ''))} chars")
            
            # 解析响应
            if response_format == "verbose_json":
                # verbose_json 格式包含详细信息
                text = result.get('text', '')
                duration = result.get('duration', 0.0)
                
                # 如果有segments，优先使用segments组装文本
                if 'segments' in result:
                    segments = result['segments']
                    text_parts = [seg.get('text', '').strip() for seg in segments]
                    text = ' '.join(text_parts)
                
                return text, duration
            else:
                # 其他格式（json, text等）
                if isinstance(result, dict):
                    text = result.get('text', str(result))
                else:
                    text = str(result)
                
                # 尝试估算时长（如果没有提供）
                duration = result.get('duration', 0.0) if isinstance(result, dict) else 0.0
                
                return text, duration
    
    except httpx.HTTPStatusError as e:
        error_text = e.response.text
        status_code = e.response.status_code
        
        # 记录完整的错误信息
        logger.error(f"ASR API HTTP error: status={status_code}, response={error_text[:500]}")
        
        # 尝试解析JSON错误
        error_detail = error_text
        try:
            error_json = e.response.json()
            error_detail = error_json.get('error', {}).get('message', error_text) if isinstance(error_json.get('error'), dict) else str(error_json)
        except:
            pass
        
        # 构建友好的错误信息
        error_message = f"ASR API调用失败 (HTTP {status_code}): {error_detail[:200]}"
        
        # 检查具体错误类型（不要轻易判断为OOM）
        error_lower = error_text.lower()
        if "out of memory" in error_lower or "oom" in error_lower:
            # 只有明确的OOM错误才提示显存不足
            if "cuda" in error_lower or "gpu" in error_lower or "memory" in error_lower:
                error_message = f"ASR服务显存不足: {error_detail[:200]}"
            else:
                # 可能不是真正的显存问题
                error_message = f"ASR处理失败: {error_detail[:200]}"
        elif "model" in error_lower and "load" in error_lower:
            error_message = "ASR模型加载失败，请检查服务状态"
        elif status_code == 503:
            error_message = "ASR服务暂时不可用，请稍后重试"
        elif status_code == 413:
            error_message = "音频文件过大，请尝试较短的音频"
        elif status_code == 400:
            error_message = f"请求参数错误: {error_detail[:200]}"
        
        raise RuntimeError(error_message)
    
    except httpx.RequestError as e:
        logger.error(f"ASR API request error: {e}")
        raise RuntimeError(f"ASR API网络错误: {str(e)}")
    
    except Exception as e:
        logger.error(f"ASR API error: {e}")
        raise RuntimeError(f"ASR API调用失败: {str(e)}")


async def test_asr_api(
    api_url: str,
    model_name: str = "whisper",
    response_format: str = "verbose_json",
    api_key: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    测试ASR API配置是否可用
    使用最小的WAV音频进行测试（不依赖ffmpeg）
    
    Returns:
        {
            "success": bool,
            "message": str,
            "response_time": float (秒)
        }
    """
    import time
    import tempfile
    import struct
    import wave
    
    try:
        # 创建一个最小的WAV测试文件（1秒，16kHz采样率，单声道）
        # 这个方法不需要ffmpeg或pydub
        sample_rate = 16000
        duration_sec = 1
        num_samples = sample_rate * duration_sec
        
        # 生成静音音频数据（全0）
        audio_data = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
        
        # 写入临时WAV文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            
            with wave.open(str(temp_path), 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 调用API
            text, duration = await call_remote_asr_api(
                audio_file_path=temp_path,
                api_url=api_url,
                model_name=model_name,
                response_format=response_format,
                api_key=api_key,
                extra_params=extra_params,
                timeout=30
            )
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            return {
                "success": True,
                "message": f"测试成功，响应时间: {response_time:.2f}秒",
                "response_time": response_time,
                "test_result": {
                    "text": text[:100] if text else "(空或静音)",
                    "duration": duration
                }
            }
        
        finally:
            # 删除临时文件
            temp_path.unlink(missing_ok=True)
    
    except Exception as e:
        logger.error(f"ASR API测试失败: {e}")
        return {
            "success": False,
            "message": f"测试失败: {str(e)}",
            "response_time": 0
        }

