"""
录音管理服务
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status

from app.services.db.postgres import get_conn
from app.services.kb_service import import_document

class RecordingResponse:
    """录音响应模型"""
    def __init__(self, row: tuple):
        self.id = row['id']
        self.user_id = row['user_id']
        self.title = row['title']
        self.filename = row['filename']
        self.duration = row['duration']
        self.file_size = row['file_size']
        self.audio_format = row['audio_format']
        self.transcript = row['transcript']
        self.word_count = row['word_count']
        self.language = row['language']
        self.kb_id = row['kb_id']
        self.doc_id = row['doc_id']
        self.import_status = row['import_status']
        self.tags = row.get('tags') or []
        self.category = row['category']
        self.notes = row['notes']
        self.created_at = row['created_at']
        self.imported_at = row.get('imported_at')
        self.audio_path = row.get('audio_path')
        self.keep_audio = row.get('keep_audio', False)
    
    def to_dict(self, include_kb_name: bool = False, kb_name: Optional[str] = None) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "filename": self.filename,
            "duration": self.duration,
            "file_size": self.file_size,
            "audio_format": self.audio_format,
            "transcript": self.transcript,
            "word_count": self.word_count,
            "language": self.language,
            "kb_id": self.kb_id,
            "doc_id": self.doc_id,
            "import_status": self.import_status,
            "tags": self.tags,
            "category": self.category,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "imported_at": self.imported_at.isoformat() if self.imported_at else None,
            "audio_path": self.audio_path,
            "keep_audio": self.keep_audio,
        }
        if include_kb_name and kb_name:
            result["kb_name"] = kb_name
        return result

def get_recordings(
    user_id: str,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None
) -> tuple[List[RecordingResponse], int]:
    """获取录音列表"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 构建查询条件
            conditions = ["user_id = %s", "deleted_at IS NULL"]
            params: List[Any] = [user_id]
            
            if status_filter and status_filter != "all":
                conditions.append("import_status = %s")
                params.append(status_filter)
            
            if search:
                conditions.append("(title ILIKE %s OR transcript ILIKE %s)")
                search_pattern = f"%{search}%"
                params.extend([search_pattern, search_pattern])
            
            where_clause = " AND ".join(conditions)
            
            # 查询总数
            cur.execute(f"SELECT COUNT(*) FROM voice_recordings WHERE {where_clause}", params)
            total = list(cur.fetchone().values())[0]
            
            # 查询数据
            offset = (page - 1) * page_size
            params.extend([page_size, offset])
            
            cur.execute(f"""
                SELECT 
                    id, user_id, title, filename, duration, file_size, audio_format,
                    transcript, word_count, language, kb_id, doc_id, import_status,
                    tags, category, notes, created_at, imported_at, audio_path, keep_audio
                FROM voice_recordings
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params)
            
            rows = cur.fetchall()
            recordings = [RecordingResponse(row) for row in rows]
            
            # 获取知识库名称
            recording_dicts = []
            for rec in recordings:
                rec_dict = rec.to_dict()
                if rec.kb_id:
                    cur.execute("SELECT name FROM knowledge_bases WHERE id = %s", (rec.kb_id,))
                    kb_row = cur.fetchone()
                    rec_dict["kb_name"] = list(kb_row.values())[0] if kb_row else None
                recording_dicts.append(rec_dict)
            
            return recording_dicts, total

def get_recording_by_id(recording_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """获取录音详情"""
    print(f"[DEBUG SERVICE] get_recording_by_id called: recording_id={recording_id}, user_id={user_id}")
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id, user_id, title, filename, duration, file_size, audio_format,
                    transcript, word_count, language, kb_id, doc_id, import_status,
                    tags, category, notes, created_at, imported_at, audio_path, keep_audio
                FROM voice_recordings
                WHERE id = %s AND user_id = %s AND deleted_at IS NULL
            """, (recording_id, user_id))
            
            row = cur.fetchone()
            print(f"[DEBUG SERVICE] Query result: row={row is not None}")
            if not row:
                # Try查询没有user_id限制的
                cur.execute("""
                    SELECT id, user_id FROM voice_recordings 
                    WHERE id = %s AND deleted_at IS NULL
                """, (recording_id,))
                check_row = cur.fetchone()
                if check_row:
                    print(f"[ERROR] Recording exists but user_id mismatch! DB user_id={list(check_row.values())[1]}, requested user_id={user_id}")
                else:
                    print(f"[ERROR] Recording not found in database: {recording_id}")
                return None
            
            rec = RecordingResponse(row)
            rec_dict = rec.to_dict()
            
            # 获取知识库名称
            if rec.kb_id:
                cur.execute("SELECT name FROM knowledge_bases WHERE id = %s", (rec.kb_id,))
                kb_row = cur.fetchone()
                rec_dict["kb_name"] = list(kb_row.values())[0] if kb_row else None
            
            return rec_dict

async def import_recording_to_kb(
    recording_id: str,
    user_id: str,
    kb_id: Optional[str] = None,
    new_kb_name: Optional[str] = None,
    title: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """导入录音到知识库"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 获取录音
            cur.execute("""
                SELECT id, user_id, title, transcript, category, tags, notes
                FROM voice_recordings
                WHERE id = %s AND user_id = %s AND deleted_at IS NULL
            """, (recording_id, user_id))
            
            row = cur.fetchone()
            if not row:
                raise ValueError("Recording not found")
            
            # 使用字典访问
            rec_id = row['id']
            rec_user_id = row['user_id']
            rec_title = row['title']
            transcript = row['transcript']
            rec_category = row['category']
            rec_tags = row['tags']
            rec_notes = row['notes']
            
            # 验证转写内容
            if not transcript or len(transcript.strip()) == 0:
                raise ValueError("录音尚未转写或转写内容为空，无法导入知识库")
            
            # 确定目标知识库
            target_kb_id = kb_id
            
            # 如果需要创建新知识库
            if not target_kb_id and new_kb_name:
                from app.services.kb_service import create_kb
                new_kb = create_kb(new_kb_name, description=notes or "")
                target_kb_id = new_kb["id"]
            
            if not target_kb_id:
                raise ValueError("必须提供知识库ID或新知识库名称")
            
            # 如果之前已导入，先删除旧的文档
            old_doc_id = row.get('doc_id')
            if old_doc_id:
                try:
                    from app.services.kb_service import delete_document
                    # 获取旧的知识库ID（可能和新的不同）
                    old_kb_id = row.get('kb_id')
                    if old_kb_id:
                        delete_document(old_kb_id, old_doc_id, skip_asset_cleanup=True)
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"Deleted old document {old_doc_id} from kb {old_kb_id} before reimport")
                except Exception as e:
                    # 如果删除失败，记录日志但继续导入
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to delete old document during reimport: {e}")
            
            # 更新录音状态为"导入中"
            cur.execute("""
                UPDATE voice_recordings
                SET import_status = 'importing'
                WHERE id = %s
            """, (recording_id,))
            conn.commit()
            
            try:
                # 导入文档
                final_title = title or rec_title
                final_category = category or rec_category or "general_doc"
                final_tags = tags if tags is not None else rec_tags
                final_notes = notes or rec_notes
                
                # 构建文档内容
                doc_content = f"# {final_title}\n\n{transcript}"
                if final_notes:
                    doc_content += f"\n\n## 备注\n{final_notes}"
                
                # 导入到知识库
                result = await import_document(
                    kb_id=target_kb_id,
                    filename=f"{final_title}.txt",
                    data=doc_content.encode('utf-8'),
                    kb_category=final_category
                )
                
                # 检查导入是否成功
                if result.get("status") == "failed":
                    raise ValueError(f"导入失败: {result.get('error', '未知错误')}")
                
                doc_id = result.get("doc_id") or result.get("id")
                
                # 更新录音记录
                cur.execute("""
                    UPDATE voice_recordings
                    SET 
                        kb_id = %s,
                        doc_id = %s,
                        import_status = 'imported',
                        imported_at = CURRENT_TIMESTAMP,
                        title = %s,
                        category = %s,
                        tags = %s,
                        notes = %s
                    WHERE id = %s
                """, (
                    target_kb_id, doc_id, final_title, final_category,
                    final_tags, final_notes, recording_id
                ))
                conn.commit()
                
                return {
                    "status": "success",
                    "kb_id": target_kb_id,
                    "doc_id": doc_id,
                    "chunks": result.get("chunks", 0)
                }
                
            except Exception as e:
                # 导入失败，更新状态
                cur.execute("""
                    UPDATE voice_recordings
                    SET import_status = 'failed'
                    WHERE id = %s
                """, (recording_id,))
                conn.commit()
                
                # 记录错误日志
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to import recording {recording_id}: {str(e)}", exc_info=True)
                
                # 抛出错误供上层处理
                raise

def update_recording_metadata(
    recording_id: str,
    user_id: str,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """更新录音元数据"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 构建更新语句
            update_fields = []
            params = []
            
            if title is not None:
                update_fields.append("title = %s")
                params.append(title)
            if tags is not None:
                update_fields.append("tags = %s")
                params.append(tags)
            if notes is not None:
                update_fields.append("notes = %s")
                params.append(notes)
            
            if not update_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([recording_id, user_id])
            
            query = f"""
                UPDATE voice_recordings
                SET {', '.join(update_fields)}
                WHERE id = %s AND user_id = %s AND deleted_at IS NULL
                RETURNING id
            """
            
            cur.execute(query, params)
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Recording not found"
                )
            
            conn.commit()
            
            return {"status": "success", "id": result[0]}

def delete_recording(recording_id: str, user_id: str) -> bool:
    """删除录音（软删除）"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE voice_recordings
                SET deleted_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s AND deleted_at IS NULL
            """, (recording_id, user_id))
            
            deleted = cur.rowcount > 0
            conn.commit()
            
            return deleted

