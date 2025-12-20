"""
录音管理API路由
"""
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
import logging

from app.services import recording_service
from app.utils.auth import get_current_user, TokenData

router = APIRouter(prefix="/api/recordings", tags=["Recordings"])
logger = logging.getLogger(__name__)

class ImportRecordingRequest(BaseModel):
    """导入录音请求"""
    kb_id: Optional[str] = None
    new_kb_name: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None

class UpdateRecordingRequest(BaseModel):
    """更新录音元数据请求"""
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None

@router.get("")
async def list_recordings(
    status: Optional[str] = Query(None, description="Filter by status: pending, imported, failed, all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search in title and transcript"),
    current_user: TokenData = Depends(get_current_user)
):
    """
    获取录音列表
    
    需要认证
    """
    recordings, total = recording_service.get_recordings(
        user_id=current_user.user_id,
        status_filter=status,
        page=page,
        page_size=page_size,
        search=search
    )
    
    return {
        "items": recordings,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.get("/{recording_id}")
async def get_recording(
    recording_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    获取录音详情
    
    需要认证
    """
    recording = recording_service.get_recording_by_id(recording_id, user_id)
    
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    
    return recording

@router.post("/{recording_id}/import")
async def import_recording(
    recording_id: str,
    request: ImportRecordingRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """
    导入录音到知识库
    
    需要认证
    """
    result = await recording_service.import_recording_to_kb(
        recording_id=recording_id,
        user_id=current_user.user_id,
        kb_id=request.kb_id,
        new_kb_name=request.new_kb_name,
        title=request.title,
        category=request.category,
        tags=request.tags,
        notes=request.notes
    )
    
    return result

@router.patch("/{recording_id}")
async def update_recording(
    recording_id: str,
    request: UpdateRecordingRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """
    更新录音元数据
    
    需要认证
    """
    result = recording_service.update_recording_metadata(
        recording_id=recording_id,
        user_id=current_user.user_id,
        title=request.title,
        tags=request.tags,
        notes=request.notes
    )
    
    return result

@router.delete("/{recording_id}")
async def delete_recording(
    recording_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    删除录音（软删除）
    
    需要认证
    """
    deleted = recording_service.delete_recording(recording_id, current_user.user_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    
    return {"message": "Recording deleted successfully"}

@router.get("/{recording_id}/audio")
async def get_recording_audio(
    recording_id: str,
    token: str = Query(None)
):
    """
    获取录音音频文件
    
    支持Query参数token认证（用于audio标签）
    """
    # 从Query参数获取token并验证
    from app.utils.auth import decode_access_token
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token"
        )
    
    try:
        token_data = decode_access_token(token)
        user_id = token_data.user_id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token"
        )
    recording = recording_service.get_recording_by_id(recording_id, user_id)
    
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    
    if not recording.get("audio_path") or not recording.get("keep_audio"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not available"
        )
    
    audio_file = Path(recording["audio_path"])
    if not audio_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found on disk"
        )
    
    return FileResponse(
        path=str(audio_file),
        media_type=f"audio/{recording['audio_format']}",
        filename=recording["filename"]
    )

@router.post("/{recording_id}/summary")
async def generate_recording_summary(
    recording_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    通过LLM生成录音摘要
    
    需要认证
    """
    recording = recording_service.get_recording_by_id(recording_id, current_user.user_id)
    
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    
    # 调用LLM生成摘要
    from app.services.llm_client import generate_answer_with_llm, select_llm_profile
    
    try:
        transcript = recording.get("transcript", "")
        if not transcript:
            raise ValueError("录音转写内容为空")
        
        system_prompt = "你是一个专业的文本摘要助手。"
        user_prompt = f"""请为以下录音转写内容生成一个简洁的摘要（100-200字）：

转写内容：
{transcript}

要求：
1. 提取核心要点
2. 简洁明了
3. 100-200字"""
        
        # 获取默认LLM配置
        profile = select_llm_profile(None)
        
        summary = await generate_answer_with_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            history=[],
            profile=profile,
            overrides={"temperature": 0.3, "max_tokens": 512}
        )
        
        return {"summary": summary.strip()}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成摘要失败: {str(e)}"
        )

@router.post("/{recording_id}/transcribe")
async def transcribe_recording(
    recording_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    手动转写录音文件
    
    用于重新转写或转写之前未转写的录音
    需要认证
    """
    print(f"[DEBUG] Transcribe request: recording_id={recording_id}, user_id={current_user.user_id}, username={current_user.username}")
    recording = recording_service.get_recording_by_id(recording_id, current_user.user_id)
    print(f"[DEBUG] Recording查询结果: found={recording is not None}")
    
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    
    # 检查是否有音频文件
    audio_path = recording.get("audio_path")
    if not audio_path or not Path(audio_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found"
        )
    
    try:
        # 调用转写服务
        from app.services.asr_service import transcribe_audio
        
        # 读取音频文件
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        filename = recording.get("filename", "audio.webm")
        
        # 执行转写
        transcript, duration = await transcribe_audio(
            audio_data=audio_data,
            filename=filename,
            language="zh"
        )
        
        # 更新数据库
        word_count = len(transcript)
        from app.services.db.postgres import get_conn
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE voice_recordings
                    SET transcript = %s, 
                        word_count = %s,
                        duration = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (transcript, word_count, int(duration), recording_id))
            conn.commit()
        
        return {
            "status": "success",
            "transcript": transcript,
            "word_count": word_count,
            "duration": int(duration)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"转写失败: {str(e)}"
        )

