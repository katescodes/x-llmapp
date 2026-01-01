"""
Prompt模板管理API路由
支持CRUD操作，实现Prompt在线编辑和版本管理
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

from app.services.db.postgres import _get_pool
from app.models.user import TokenData
from app.utils.permission import require_permission

router = APIRouter(prefix="/api/apps/tender/prompts", tags=["prompts"])


class PromptTemplateCreate(BaseModel):
    """创建Prompt模板"""
    module: str = Field(
        ..., 
        description="模块名称：project_info, requirements, bid_response, risks, directory, review"
    )
    name: str = Field(..., description="显示名称")
    description: Optional[str] = None
    content: str = Field(..., description="Prompt内容（Markdown格式）")


class PromptTemplateUpdate(BaseModel):
    """更新Prompt模板"""
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None
    change_note: Optional[str] = None  # 变更说明


class PromptTemplateResponse(BaseModel):
    """Prompt模板响应"""
    id: str
    module: str
    name: str
    description: Optional[str]
    content: str
    version: int
    is_active: bool
    created_at: str
    updated_at: str


@router.get("/modules")
def list_modules(current_user: TokenData = Depends(require_permission("system.prompt"))):
    """
    获取所有模块列表
    
    权限要求：system.prompt
    
    注意：project_info、requirements、bid_response、review 已废弃，
    系统已切换到 Checklist 框架，不再使用数据库 Prompt 管理。
    """
    return {
        "ok": True,
        "modules": [
            {
                "id": "directory",
                "name": "目录生成",
                "description": "自动生成投标文件语义大纲和章节结构（✅ 正在使用）",
                "icon": "📑",
                "category": "generation"
            }
        ]
    }


@router.get("/")
def list_prompts(
    module: Optional[str] = None,
    active_only: bool = True,
    current_user: TokenData = Depends(require_permission("system.prompt"))
):
    """
    获取Prompt列表
    
    权限要求：system.prompt
    """
    pool = _get_pool()
    
    sql = """
        SELECT id, module, name, description, content, version, is_active,
               created_at, updated_at
        FROM prompt_templates
        WHERE 1=1
    """
    params = []
    
    if module:
        params.append(module)
        sql += " AND module = %s"
    
    if active_only:
        sql += " AND is_active = TRUE"
    
    sql += " ORDER BY module, name"
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    
    prompts = []
    for row in rows:
        row_dict = dict(row)
        
        # DEBUG: 打印实际数据
        import sys
        print(f"DEBUG row type: {type(row)}", file=sys.stderr)
        print(f"DEBUG row_dict: {row_dict}", file=sys.stderr)
        print(f"DEBUG content: {row_dict.get('content', 'NO CONTENT')[:100]}", file=sys.stderr)
        
        # 处理时间字段：可能已经是字符串（psycopg3）或 datetime 对象
        created_at = row_dict.get("created_at")
        if created_at and hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        elif created_at:
            created_at = str(created_at)
        
        updated_at = row_dict.get("updated_at")
        if updated_at and hasattr(updated_at, "isoformat"):
            updated_at = updated_at.isoformat()
        elif updated_at:
            updated_at = str(updated_at)
        
        prompts.append({
            "id": row_dict["id"],
            "module": row_dict["module"],
            "name": row_dict["name"],
            "description": row_dict["description"],
            "content": row_dict["content"],
            "version": row_dict["version"],
            "is_active": row_dict["is_active"],
            "created_at": created_at,
            "updated_at": updated_at,
        })
    
    return {"ok": True, "prompts": prompts}


@router.get("/{prompt_id}")
def get_prompt(
    prompt_id: str,
    current_user: TokenData = Depends(require_permission("system.prompt"))
):
    """
    获取单个Prompt详情
    
    权限要求：system.prompt
    """
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, module, name, description, content, version, is_active,
                       created_at, updated_at
                FROM prompt_templates
                WHERE id = %s
                """,
                (prompt_id,)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Prompt not found")
            
            row_dict = dict(row)
    
    # 处理时间字段
    created_at = row_dict.get("created_at")
    if created_at and hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    elif created_at:
        created_at = str(created_at)
    
    updated_at = row_dict.get("updated_at")
    if updated_at and hasattr(updated_at, "isoformat"):
        updated_at = updated_at.isoformat()
    elif updated_at:
        updated_at = str(updated_at)
    
    return {
        "ok": True,
        "prompt": {
            "id": row_dict["id"],
            "module": row_dict["module"],
            "name": row_dict["name"],
            "description": row_dict["description"],
            "content": row_dict["content"],
            "version": row_dict["version"],
            "is_active": row_dict["is_active"],
            "created_at": created_at,
            "updated_at": updated_at,
        }
    }


@router.post("/")
def create_prompt(
    data: PromptTemplateCreate,
    current_user: TokenData = Depends(require_permission("system.prompt"))
):
    """
    创建新Prompt模板
    
    权限要求：system.prompt
    """
    pool = _get_pool()
    prompt_id = f"prompt_{uuid.uuid4().hex[:16]}"
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO prompt_templates (id, module, name, description, content, version, is_active)
                VALUES (%s, %s, %s, %s, %s, 1, TRUE)
                """,
                (prompt_id, data.module, data.name, data.description, data.content)
            )
            conn.commit()
    
    return {"ok": True, "prompt_id": prompt_id}


@router.put("/{prompt_id}")
def update_prompt(
    prompt_id: str, 
    data: PromptTemplateUpdate,
    current_user: TokenData = Depends(require_permission("system.prompt"))
):
    """
    更新Prompt模板（自动创建历史版本）
    
    权限要求：system.prompt
    """
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 获取当前版本
            cur.execute(
                "SELECT content, version FROM prompt_templates WHERE id = %s",
                (prompt_id,)
            )
            current = cur.fetchone()
            
            if not current:
                raise HTTPException(status_code=404, detail="Prompt not found")
            
            # 正确处理 DictRow
            current_dict = dict(current)
            current_content = current_dict["content"]
            current_version = current_dict["version"]
            
            # 如果content有变化，保存历史版本
            if data.content and data.content != current_content:
                history_id = f"hist_{uuid.uuid4().hex[:16]}"
                cur.execute(
                    """
                    INSERT INTO prompt_history (id, prompt_id, content, version, change_note)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (history_id, prompt_id, current_content, current_version, data.change_note or "手动更新")
                )
                new_version = current_version + 1
            else:
                new_version = current_version
            
            # 更新模板
            update_fields = []
            params = []
            
            if data.name is not None:
                update_fields.append("name = %s")
                params.append(data.name)
            
            if data.description is not None:
                update_fields.append("description = %s")
                params.append(data.description)
            
            if data.content is not None:
                update_fields.append("content = %s")
                params.append(data.content)
                update_fields.append("version = %s")
                params.append(new_version)
            
            if data.is_active is not None:
                update_fields.append("is_active = %s")
                params.append(data.is_active)
            
            update_fields.append("updated_at = %s")
            params.append(datetime.utcnow())
            
            params.append(prompt_id)
            
            sql = f"""
                UPDATE prompt_templates
                SET {', '.join(update_fields)}
                WHERE id = %s
            """
            
            cur.execute(sql, params)
            conn.commit()
    
    return {"ok": True, "message": "Prompt updated", "version": new_version}


@router.get("/{prompt_id}/history")
def get_prompt_history(
    prompt_id: str,
    current_user: TokenData = Depends(require_permission("system.prompt"))
):
    """
    获取Prompt变更历史
    
    权限要求：system.prompt
    """
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, version, change_note, changed_at
                FROM prompt_history
                WHERE prompt_id = %s
                ORDER BY version DESC
                """,
                (prompt_id,)
            )
            rows = cur.fetchall()
    
    history = []
    for row in rows:
        row_dict = dict(row)
        
        # 处理时间字段
        changed_at = row_dict.get("changed_at")
        if changed_at and hasattr(changed_at, "isoformat"):
            changed_at = changed_at.isoformat()
        elif changed_at:
            changed_at = str(changed_at)
        
        history.append({
            "id": row_dict["id"],
            "version": row_dict["version"],
            "change_note": row_dict["change_note"],
            "changed_at": changed_at,
        })
    
    return {"ok": True, "history": history}


@router.get("/{prompt_id}/history/{version}")
def get_prompt_version(
    prompt_id: str, 
    version: int,
    current_user: TokenData = Depends(require_permission("system.prompt"))
):
    """
    获取指定版本的Prompt内容
    
    权限要求：system.prompt
    """
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content, version, change_note, changed_at
                FROM prompt_history
                WHERE prompt_id = %s AND version = %s
                """,
                (prompt_id, version)
            )
            row = cur.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Version not found")
            
            row_dict = dict(row)
    
    # 处理时间字段
    changed_at = row_dict.get("changed_at")
    if changed_at and hasattr(changed_at, "isoformat"):
        changed_at = changed_at.isoformat()
    elif changed_at:
        changed_at = str(changed_at)
    
    return {
        "ok": True,
        "version_data": {
            "content": row_dict["content"],
            "version": row_dict["version"],
            "change_note": row_dict["change_note"],
            "changed_at": changed_at,
        }
    }


@router.delete("/{prompt_id}")
def delete_prompt(
    prompt_id: str,
    current_user: TokenData = Depends(require_permission("system.prompt"))
):
    """
    删除Prompt模板（软删除，设置为inactive）
    
    权限要求：system.prompt
    """
    pool = _get_pool()
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE prompt_templates SET is_active = FALSE WHERE id = %s",
                (prompt_id,)
            )
            count = cur.rowcount
            conn.commit()
    
    if count == 0:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    return {"ok": True, "message": "Prompt deactivated"}
