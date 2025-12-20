"""
附件存储服务
使用内存存储，支持替换为数据库
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from ..models.attachment import Attachment

logger = logging.getLogger(__name__)


class AttachmentStore:
    """附件存储（内存实现）"""
    
    def __init__(self):
        self._attachments: Dict[str, Attachment] = {}
    
    def save(self, attachment: Attachment) -> None:
        """保存附件记录"""
        self._attachments[attachment.id] = attachment
        logger.info(f"Attachment saved: id={attachment.id} name={attachment.original_name}")
    
    def get(self, attachment_id: str) -> Optional[Attachment]:
        """获取附件"""
        return self._attachments.get(attachment_id)
    
    def get_many(self, attachment_ids: list[str]) -> list[Attachment]:
        """批量获取附件"""
        result = []
        for aid in attachment_ids:
            attachment = self.get(aid)
            if attachment:
                result.append(attachment)
        return result
    
    def delete(self, attachment_id: str) -> bool:
        """删除附件记录"""
        if attachment_id in self._attachments:
            del self._attachments[attachment_id]
            logger.info(f"Attachment deleted: id={attachment_id}")
            return True
        return False
    
    def count(self) -> int:
        """获取附件总数"""
        return len(self._attachments)


# 全局实例
_attachment_store = AttachmentStore()


def get_attachment_store() -> AttachmentStore:
    """获取附件存储实例"""
    return _attachment_store
