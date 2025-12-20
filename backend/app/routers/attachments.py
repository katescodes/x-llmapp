"""
附件上传和管理接口
"""
import logging
import os
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.config import get_settings
from ..schemas.attachment import AttachmentUploadResponse, AttachmentDeleteResponse
from ..models.attachment import Attachment
from ..services.attachment_store import get_attachment_store
from ..utils.text_extractor import (
    extract_text_from_file,
    get_safe_filename,
    is_allowed_extension,
    TextExtractionError,
)

router = APIRouter(prefix="/api/attachments", tags=["attachments"])
settings = get_settings()
logger = logging.getLogger(__name__)

# 配置
ALLOWED_EXTENSIONS = {'.txt', '.md', '.pdf', '.docx', '.pptx', '.json', '.csv'}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
STORAGE_DIR = Path("./storage/attachments")

# 确保存储目录存在
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=AttachmentUploadResponse)
async def upload_attachment(
    file: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
):
    """
    上传附件
    
    - 接收文件并校验
    - 保存到本地存储
    - 抽取文本内容
    - 返回附件信息
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    # 1. 校验扩展名
    if not is_allowed_extension(file.filename, ALLOWED_EXTENSIONS):
        allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型。允许的类型: {allowed_list}"
        )
    
    # 2. 读取文件内容并校验大小
    try:
        file_content = await file.read()
        file_size = len(file_content)
    except Exception as e:
        logger.error(f"读取上传文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="文件读取失败")
    
    if file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大 {MAX_UPLOAD_MB}MB）"
        )
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")
    
    # 3. 生成安全的存储文件名
    attachment_id = uuid4().hex
    safe_name = get_safe_filename(file.filename)
    ext = Path(file.filename).suffix.lower()
    stored_filename = f"{attachment_id}_{safe_name}"
    stored_path = STORAGE_DIR / stored_filename
    
    # 4. 保存文件到磁盘
    try:
        with open(stored_path, "wb") as f:
            f.write(file_content)
        logger.info(f"File saved: {stored_path} size={file_size}")
    except Exception as e:
        logger.error(f"保存文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="文件保存失败")
    
    # 5. 抽取文本
    try:
        extracted_text = extract_text_from_file(str(stored_path), file.content_type)
        logger.info(
            f"Text extracted: file={file.filename} text_length={len(extracted_text)}"
        )
    except TextExtractionError as e:
        # 抽取失败，删除已保存的文件
        if stored_path.exists():
            stored_path.unlink()
        logger.warning(f"文本抽取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 其他异常
        if stored_path.exists():
            stored_path.unlink()
        logger.error(f"文本抽取异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文本抽取失败: {str(e)}")
    
    # 6. 创建附件记录
    attachment = Attachment(
        id=attachment_id,
        original_name=file.filename,
        stored_path=str(stored_path),
        mime_type=file.content_type or "application/octet-stream",
        size=file_size,
        extracted_text=extracted_text,
    )
    
    # 7. 保存到存储
    store = get_attachment_store()
    store.save(attachment)
    
    logger.info(
        f"Attachment uploaded: id={attachment_id} name={file.filename} "
        f"size={file_size} text_len={len(extracted_text)} "
        f"conversation_id={conversation_id or 'none'}"
    )
    
    # 8. 返回响应
    return AttachmentUploadResponse(
        id=attachment.id,
        name=attachment.original_name,
        size=attachment.size,
        mime=attachment.mime_type,
        text_length=len(extracted_text),
        created_at=attachment.created_at.isoformat() if attachment.created_at else None,
    )


@router.delete("/{attachment_id}", response_model=AttachmentDeleteResponse)
async def delete_attachment(attachment_id: str):
    """
    删除附件
    
    - 从存储中删除记录
    - 从磁盘删除文件
    """
    store = get_attachment_store()
    attachment = store.get(attachment_id)
    
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    # 删除磁盘文件
    try:
        stored_path = Path(attachment.stored_path)
        if stored_path.exists():
            stored_path.unlink()
            logger.info(f"File deleted: {stored_path}")
    except Exception as e:
        logger.warning(f"删除文件失败: {e}")
        # 继续执行，即使文件删除失败
    
    # 删除记录
    store.delete(attachment_id)
    
    logger.info(f"Attachment deleted: id={attachment_id}")
    
    return AttachmentDeleteResponse(
        success=True,
        message="附件已删除"
    )


@router.get("/{attachment_id}")
async def get_attachment_info(attachment_id: str):
    """获取附件信息（不含完整文本）"""
    store = get_attachment_store()
    attachment = store.get(attachment_id)
    
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    return attachment.to_dict()
