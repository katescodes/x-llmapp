"""
录音管理API路由
"""
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import logging
import uuid
from datetime import datetime

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


class TranscribeRequest(BaseModel):
    """转写请求参数"""
    enhance: bool = False  # 是否启用LLM增强
    enhancement_type: str = "punctuation"  # 增强类型: punctuation, formal, meeting
    model_id: Optional[str] = None  # LLM模型ID（可选）


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
    recording = recording_service.get_recording_by_id(recording_id, current_user.user_id)
    
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
    try:
        logger.info(f"Import recording request: recording_id={recording_id}, user={current_user.user_id}, kb_id={request.kb_id}")
        
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
        
        logger.info(f"Import recording success: recording_id={recording_id}, doc_id={result.get('doc_id')}")
        return result
        
    except ValueError as e:
        logger.error(f"Import recording validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Import recording failed: recording_id={recording_id}, error={str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入失败: {str(e)}"
        )

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
    
    # 创建响应，避免中文文件名编码问题
    response = FileResponse(
        path=str(audio_file),
        media_type=f"audio/{recording['audio_format']}"
    )
    
    # 如果有文件名，添加Content-Disposition（用于下载时的文件名）
    if recording.get("filename"):
        from urllib.parse import quote
        import re
        
        original_filename = recording["filename"]
        # 生成ASCII安全的回退文件名
        ascii_filename = re.sub(r'[^\x00-\x7F]+', '_', original_filename)
        # URL编码原始文件名
        encoded_filename = quote(original_filename)
        
        response.headers["Content-Disposition"] = (
            f'inline; filename="{ascii_filename}"; '
            f"filename*=UTF-8''{encoded_filename}"
        )
    
    return response

@router.post("/upload")
async def upload_audio_file(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user)
):
    """
    上传外部音频文件并创建录音记录
    
    支持的音频格式: mp3, wav, m4a, ogg, webm, flac, aac
    需要认证
    """
    from app.config import get_settings
    from app.services.db.postgres import get_conn
    
    # 检查文件格式
    allowed_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.webm', '.flac', '.aac'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的音频格式: {file_ext}。支持的格式: {', '.join(allowed_extensions)}"
        )
    
    try:
        # 读取文件内容
        audio_data = await file.read()
        file_size = len(audio_data)
        
        # 检查文件大小（限制为 100MB）
        max_size = 100 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件过大，最大支持 {max_size // (1024*1024)}MB"
            )
        
        # 生成recording_id和文件名
        recording_id = f"rec_{uuid.uuid4().hex[:12]}"
        safe_filename = f"{recording_id}{file_ext}"
        
        # 保存音频文件
        settings = get_settings()
        audio_dir = Path(settings.APP_DATA_DIR) / "recordings"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        audio_path = audio_dir / safe_filename
        audio_path.write_bytes(audio_data)
        
        # 设置标题
        if not title:
            title = f"导入_{Path(file.filename).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建数据库记录（不包含转写内容，待后续转写）
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
                    current_user.user_id,
                    title,
                    safe_filename,
                    0,  # duration待转写后更新
                    file_size,
                    file_ext[1:],  # 去掉前面的点
                    "",  # 转写文本为空
                    0,   # 字数为0
                    str(audio_path),
                    "pending",
                    True  # 保留音频文件
                ))
            conn.commit()
        
        logger.info(f"Audio file uploaded: {recording_id}, user={current_user.user_id}, size={file_size}")
        
        return {
            "status": "success",
            "recording_id": recording_id,
            "title": title,
            "file_size": file_size,
            "message": "音频文件上传成功，请点击转写按钮进行语音识别"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload audio file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}"
        )


@router.get("/{recording_id}/download")
async def download_recording_audio(
    recording_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    下载录音音频文件（带原始文件名）
    
    需要认证
    """
    try:
        logger.info(f"Download request: recording_id={recording_id}, user={current_user.user_id}")
        
        recording = recording_service.get_recording_by_id(recording_id, current_user.user_id)
        
        if not recording:
            logger.warning(f"Recording not found: {recording_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )
        
        logger.debug(f"Recording found: {recording}")
        
        if not recording.get("audio_path"):
            logger.error(f"No audio_path in recording: {recording_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audio path not configured"
            )
        
        if not recording.get("keep_audio"):
            logger.warning(f"Audio not kept for recording: {recording_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audio file not available (not preserved)"
            )
        
        audio_file = Path(recording["audio_path"])
        if not audio_file.exists():
            logger.error(f"Audio file not found on disk: {audio_file}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found on disk: {audio_file.name}"
            )
        
        # 检查文件是否可读
        if not audio_file.is_file():
            logger.error(f"Audio path is not a file: {audio_file}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid audio file"
            )
        
        # 生成友好的下载文件名
        title = recording.get("title", "recording")
        # 移除标题中的特殊字符，保留中文、字母、数字、空格、短横线、下划线
        import re
        safe_title = re.sub(r'[^\w\s\-_\u4e00-\u9fff]', '', title).strip()
        if not safe_title:
            safe_title = "recording"
        
        file_ext = recording.get("audio_format", "webm")
        download_filename = f"{safe_title}.{file_ext}"
        
        # URL编码文件名（用于Content-Disposition）
        from urllib.parse import quote
        encoded_filename = quote(download_filename)
        
        # 生成ASCII安全的回退文件名（用于不支持RFC 5987的旧浏览器）
        ascii_filename = re.sub(r'[^\x00-\x7F]+', '_', download_filename)
        
        logger.info(f"Serving download: file={download_filename}, path={audio_file}, size={audio_file.stat().st_size}")
        
        # 创建FileResponse，不使用filename参数（避免latin-1编码错误）
        response = FileResponse(
            path=str(audio_file),
            media_type=f"audio/{file_ext}"
        )
        
        # 手动设置Content-Disposition头（RFC 5987标准）
        # filename: ASCII回退名称
        # filename*: UTF-8编码的实际名称
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{ascii_filename}"; '
            f"filename*=UTF-8''{encoded_filename}"
        )
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: recording_id={recording_id}, error={str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
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
        
        system_prompt = "你是一个专业的文本摘要助手。请用自然的中文段落形式输出摘要，不要使用代码、列表或特殊格式。"
        user_prompt = f"""请为以下录音转写内容生成一个简洁的摘要（200-300字）：

转写内容：
{transcript}

要求：
1. 提取核心要点和关键信息
2. 用流畅的段落形式表述，不要使用列表或代码格式
3. 简洁明了，200-300字
4. 只输出摘要正文，不要有标题或其他说明"""
        
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


@router.post("/{recording_id}/mindmap")
async def generate_recording_mindmap(
    recording_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    通过LLM生成录音思维导图（Mermaid格式）
    
    需要认证
    """
    recording = recording_service.get_recording_by_id(recording_id, current_user.user_id)
    
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    
    # 调用LLM生成思维导图
    from app.services.llm_client import generate_answer_with_llm, select_llm_profile
    
    try:
        transcript = recording.get("transcript", "")
        if not transcript:
            raise ValueError("录音转写内容为空")
        
        system_prompt = """你是一个专业的思维导图生成助手。你需要将内容转换为Mermaid格式的思维导图。

重要规则：
1. 使用graph LR语法（从左到右的横向布局）
2. 节点ID必须是简单的英文字母或数字，如：A, B, C1, C2等，绝对不能包含中文
3. 节点文本必须用双引号包裹，可以是中文
4. 连接使用 --> 符号
5. 只输出mermaid代码，不要有任何其他文字说明
6. 每行一个语句

正确示例：
graph LR
    A["中心主题"]
    B["分支1"]
    C["分支2"]
    A --> B
    A --> C
"""

        user_prompt = f"""请将以下内容转换为Mermaid思维导图：

内容：
{transcript[:2000]}

要求：
1. 提取主要话题作为中心节点（节点ID用A）
2. 提取2-4个一级分支（节点ID用B, C, D, E）
3. 每个分支下可以有2-3个二级节点（节点ID用B1, B2, C1, C2等）
4. 节点ID只能用英文字母和数字
5. 节点文本用中文，必须用双引号包裹
6. 使用graph LR格式
7. 只输出代码，从graph LR开始，不要有其他说明文字"""
        
        # 获取默认LLM配置
        profile = select_llm_profile(None)
        
        mindmap_code = await generate_answer_with_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            history=[],
            profile=profile,
            overrides={"temperature": 0.5, "max_tokens": 1024}
        )
        
        # 清理输出，确保只保留mermaid代码
        mindmap_code = mindmap_code.strip()
        
        # 移除markdown代码块标记
        if mindmap_code.startswith("```mermaid"):
            mindmap_code = mindmap_code[10:]
        elif mindmap_code.startswith("```"):
            mindmap_code = mindmap_code[3:]
        
        if mindmap_code.endswith("```"):
            mindmap_code = mindmap_code[:-3]
        
        mindmap_code = mindmap_code.strip()
        
        # 确保以graph开头
        if not mindmap_code.startswith("graph"):
            mindmap_code = "graph LR\n" + mindmap_code
        
        # 验证和清理代码
        import re
        lines = mindmap_code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 保留graph声明
            if line.startswith('graph'):
                cleaned_lines.append(line)
                continue
            
            # 清理节点定义和连接
            if '-->' in line:
                # 连接语句，确保格式正确
                parts = line.split('-->')
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    cleaned_lines.append(f"    {left} --> {right}")
            elif '[' in line and ']' in line:
                # 节点定义，确保文本用双引号包裹
                match = re.match(r'^([A-Za-z0-9_]+)\s*\[(.+?)\]', line)
                if match:
                    node_id = match.group(1)
                    node_text = match.group(2).strip('"').strip("'").strip()
                    # 确保文本不包含特殊字符，转义双引号
                    node_text = node_text.replace('"', '\\"')
                    cleaned_lines.append(f'    {node_id}["{node_text}"]')
            else:
                # 跳过其他行
                pass
        
        mindmap_code = '\n'.join(cleaned_lines)
        
        # 如果清理后代码为空或太短，返回一个默认的思维导图
        if len(mindmap_code) < 20:
            mindmap_code = """graph LR
    A["录音内容"]
    B["主要内容"]
    C["关键信息"]
    A --> B
    A --> C"""
        
        return {"mindmap": mindmap_code}
        
    except Exception as e:
        logger.error(f"生成思维导图失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成思维导图失败: {str(e)}"
        )


@router.post("/{recording_id}/transcribe")
async def transcribe_recording(
    recording_id: str,
    request: TranscribeRequest = TranscribeRequest(),
    current_user: TokenData = Depends(get_current_user)
):
    """
    手动转写录音文件
    
    用于重新转写或转写之前未转写的录音
    支持LLM文本增强（标点符号和段落划分）
    需要认证
    """
    print(f"[DEBUG] Transcribe request: recording_id={recording_id}, user_id={current_user.user_id}, enhance={request.enhance}, type={request.enhancement_type}")
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
        # 调用转写服务（内部已有并发控制）
        from app.services.asr_service import transcribe_audio
        
        # 读取音频文件
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        filename = recording.get("filename", "audio.webm")
        
        # 执行转写（支持增强）
        transcript, duration = await transcribe_audio(
            audio_data=audio_data,
            filename=filename,
            language="zh",
            enhance=request.enhance,
            enhancement_type=request.enhancement_type,
            model_id=request.model_id
        )
        
        # 更新数据库
        word_count = len(transcript)
        # 处理duration可能为None的情况
        duration_int = int(duration) if duration is not None else 0
        
        from app.services.db.postgres import get_conn
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 转写成功：更新转写内容，并将状态恢复为 pending（如果之前失败了）
                cur.execute("""
                    UPDATE voice_recordings
                    SET transcript = %s, 
                        word_count = %s,
                        duration = %s,
                        import_status = CASE 
                            WHEN import_status = 'failed' THEN 'pending'
                            ELSE import_status
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (transcript, word_count, duration_int, recording_id))
            conn.commit()
        
        return {
            "status": "success",
            "transcript": transcript,
            "word_count": word_count,
            "duration": duration_int
        }
        
    except HTTPException:
        # HTTPException 直接传播
        # 转写失败时更新数据库状态
        try:
            from app.services.db.postgres import get_conn
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE voice_recordings
                        SET import_status = 'failed',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (recording_id,))
                conn.commit()
        except Exception as db_err:
            logger.error(f"Failed to update status to failed: {db_err}")
        raise
    except Exception as e:
        # 其他异常才包装
        logger.error(f"Transcription failed: {e}", exc_info=True)
        
        # 更新数据库状态为失败
        try:
            from app.services.db.postgres import get_conn
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE voice_recordings
                        SET import_status = 'failed',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (recording_id,))
                conn.commit()
        except Exception as db_err:
            logger.error(f"Failed to update status to failed: {db_err}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)  # 直接使用异常消息，不再添加"转写失败"前缀
        )


@router.get("/stats/asr-concurrency")
async def get_asr_concurrency_stats(
    current_user: TokenData = Depends(get_current_user)
):
    """
    获取ASR并发控制统计信息
    
    需要认证
    """
    try:
        from app.services.asr_concurrency import ASRConcurrencyManager
        
        manager = await ASRConcurrencyManager.get_instance()
        stats = manager.get_stats()
        
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get ASR concurrency stats: {e}")
        return {
            "status": "error",
            "message": str(e),
            "stats": {}
        }

