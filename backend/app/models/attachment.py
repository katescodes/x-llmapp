"""
附件数据模型
"""
from datetime import datetime
from typing import Optional


class Attachment:
    """附件模型"""
    
    def __init__(
        self,
        id: str,
        original_name: str,
        stored_path: str,
        mime_type: str,
        size: int,
        extracted_text: str,
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.original_name = original_name
        self.stored_path = stored_path
        self.mime_type = mime_type
        self.size = size
        self.extracted_text = extracted_text
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "original_name": self.original_name,
            "stored_path": self.stored_path,
            "mime_type": self.mime_type,
            "size": self.size,
            "text_length": len(self.extracted_text),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
