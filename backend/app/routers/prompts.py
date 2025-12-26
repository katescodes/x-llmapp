"""
Prompt模板管理API路由
支持CRUD操作，实现Prompt在线编辑和版本管理
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

from app.services.db.postgres import _get_pool

router = APIRouter(prefix="/api/apps/tender/prompts", tags=["prompts"])


class PromptTemplateCreate(BaseModel):
    """创建Prompt模板"""
    module: str = Field(
        ..., 
        description="模块名称：project_info_v3(新), requirements_v1(新), bid_response_v1(新), review_v3(新), project_info(旧), risks, directory, review(旧)"
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
def list_modules():
    """获取所有模块列表"""
    return {
        "ok": True,
        "modules": [
            {
                "id": "project_info_v3",
                "name": "招标信息提取 (V3)",
                "description": "提取招标文件的九大类信息：项目概况、范围与标段、进度与提交、投标人资格、评审与评分、商务条款、技术要求、文件编制、投标保证金",
                "icon": "📋",
                "version": "v3",
                "category": "extraction"
            },
            {
                "id": "project_info",
                "name": "项目信息提取 (Legacy)",
                "description": "[旧版] 提取项目基本信息、技术参数、商务条款、评分标准",
                "icon": "📋",
                "deprecated": True,
                "category": "extraction"
            },
            {
                "id": "requirements_v1",
                "name": "招标要求抽取",
                "description": "从招标文件中抽取结构化的招标要求（基准条款库），包括资格要求、技术要求、商务要求等7个维度",
                "icon": "📝",
                "version": "v1",
                "category": "extraction"
            },
            {
                "id": "bid_response_v1",
                "name": "投标响应要素抽取",
                "description": "从投标文件中抽取结构化的响应要素，包括资格响应、技术响应、商务响应等7个维度",
                "icon": "📄",
                "version": "v1",
                "category": "extraction"
            },
            {
                "id": "risks",
                "name": "风险识别",
                "description": "识别招标文件中的法律、技术、商务、合规风险",
                "icon": "⚠️",
                "category": "analysis"
            },
            {
                "id": "directory",
                "name": "目录生成",
                "description": "自动生成投标文件语义大纲和章节结构",
                "icon": "📑",
                "category": "generation"
            },
            {
                "id": "review_v3",
                "name": "审核评估 (V3)",
                "description": "[新版] 基于 requirements × responses + 规则引擎的智能审核",
                "icon": "✅",
                "version": "v3",
                "category": "review"
            },
            {
                "id": "review",
                "name": "审核评估 (Legacy)",
                "description": "[旧版] 对投标文件进行合规性和完整性审核",
                "icon": "✓",
                "deprecated": True,
                "category": "review"
            }
        ]
    }


@router.get("/")
def list_prompts(
    module: Optional[str] = None,
    active_only: bool = True
):
    """获取Prompt列表"""
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
            columns = [desc[0] for desc in cur.description]
    
    prompts = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        prompts.append({
            "id": row_dict["id"],
            "module": row_dict["module"],
            "name": row_dict["name"],
            "description": row_dict["description"],
            "content": row_dict["content"],
            "version": row_dict["version"],
            "is_active": row_dict["is_active"],
            "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
            "updated_at": row_dict["updated_at"].isoformat() if row_dict.get("updated_at") else None,
        })
    
    return {"ok": True, "prompts": prompts}


@router.get("/{prompt_id}")
def get_prompt(prompt_id: str):
    """获取单个Prompt详情"""
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
            
            columns = [desc[0] for desc in cur.description]
            row_dict = dict(zip(columns, row))
    
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
            "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
            "updated_at": row_dict["updated_at"].isoformat() if row_dict.get("updated_at") else None,
        }
    }


@router.post("/")
def create_prompt(data: PromptTemplateCreate):
    """创建新Prompt模板"""
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
def update_prompt(prompt_id: str, data: PromptTemplateUpdate):
    """更新Prompt模板（自动创建历史版本）"""
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
            
            current_content, current_version = current
            
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
def get_prompt_history(prompt_id: str):
    """获取Prompt变更历史"""
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
            columns = [desc[0] for desc in cur.description]
    
    history = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        history.append({
            "id": row_dict["id"],
            "version": row_dict["version"],
            "change_note": row_dict["change_note"],
            "changed_at": row_dict["changed_at"].isoformat() if row_dict.get("changed_at") else None,
        })
    
    return {"ok": True, "history": history}


@router.get("/{prompt_id}/history/{version}")
def get_prompt_version(prompt_id: str, version: int):
    """获取指定版本的Prompt内容"""
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
            
            columns = [desc[0] for desc in cur.description]
            row_dict = dict(zip(columns, row))
    
    return {
        "ok": True,
        "version_data": {
            "content": row_dict["content"],
            "version": row_dict["version"],
            "change_note": row_dict["change_note"],
            "changed_at": row_dict["changed_at"].isoformat() if row_dict.get("changed_at") else None,
        }
    }


@router.delete("/{prompt_id}")
def delete_prompt(prompt_id: str):
    """删除Prompt模板（软删除，设置为inactive）"""
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
