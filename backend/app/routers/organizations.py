"""
企业管理路由
提供企业信息查询、更新和成员管理功能
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg_pool import ConnectionPool
import psycopg.rows
import logging

from app.utils.auth import get_current_user, TokenData
from app.utils.permission import require_permission
from app.services.db.postgres import _get_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


# ===== Schemas =====

class OrganizationInfo(BaseModel):
    """企业信息"""
    id: str
    name: str
    created_at: str
    updated_at: str


class OrganizationUpdate(BaseModel):
    """更新企业信息请求"""
    name: str = Field(..., min_length=1, max_length=255, description="企业名称")


class OrganizationCreate(BaseModel):
    """创建企业请求"""
    name: str = Field(..., min_length=1, max_length=255, description="企业名称")


class OrganizationStats(BaseModel):
    """企业统计信息"""
    total_members: int
    members_by_role: Dict[str, int]
    shared_resources: Dict[str, int]


class OrganizationDetail(BaseModel):
    """企业详情（包含统计信息）"""
    info: OrganizationInfo
    stats: OrganizationStats


class UserBrief(BaseModel):
    """用户简要信息"""
    id: str
    username: str
    role: str
    organization_id: Optional[str]
    created_at: str


class BatchBindRequest(BaseModel):
    """批量绑定用户到企业"""
    user_ids: List[str] = Field(..., min_items=1, description="用户ID列表")


class UserOrgBinding(BaseModel):
    """用户企业绑定信息"""
    user_id: str
    organization_id: str
    created_at: str


class UserWithOrganizations(BaseModel):
    """带企业列表的用户信息"""
    id: str
    username: str
    email: Optional[str]
    role: str
    display_name: Optional[str]
    organizations: List[str]  # 企业ID列表
    organization_names: List[str]  # 企业名称列表


# ===== Routes =====

@router.get("/", response_model=List[OrganizationInfo])
async def list_organizations(
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.view"))
):
    """
    获取所有企业列表（管理员功能）
    权限：organization.view
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("""
                    SELECT id, name, created_at, updated_at
                    FROM organizations
                    ORDER BY created_at DESC
                """)
                
                organizations = []
                for row in cur.fetchall():
                    organizations.append(OrganizationInfo(
                        id=row["id"],
                        name=row["name"],
                        created_at=str(row["created_at"]),
                        updated_at=str(row["updated_at"])
                    ))
                
                return organizations
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.post("/", response_model=OrganizationInfo)
async def create_organization(
    req: OrganizationCreate,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.edit"))
):
    """
    创建新企业
    权限：organization.edit
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 生成企业ID
                import uuid
                org_id = f"org_{uuid.uuid4().hex[:12]}"
                
                # 插入企业
                cur.execute("""
                    INSERT INTO organizations (id, name, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    RETURNING id, name, created_at, updated_at
                """, [org_id, req.name])
                
                org_row = cur.fetchone()
                conn.commit()
                
                return OrganizationInfo(
                    id=org_row["id"],
                    name=org_row["name"],
                    created_at=str(org_row["created_at"]),
                    updated_at=str(org_row["updated_at"])
                )
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.get("/current", response_model=OrganizationDetail)
async def get_current_organization(
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.view"))
):
    """
    获取当前用户所属企业的详细信息
    权限：organization.view
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 获取企业信息
                cur.execute("""
                    SELECT id, name, created_at, updated_at
                    FROM organizations
                    WHERE id = (SELECT organization_id FROM users WHERE id = %s)
                """, [current_user.user_id])
                
                org_row = cur.fetchone()
                if not org_row:
                    raise HTTPException(status_code=404, detail="企业信息不存在")
                
                return await _get_organization_detail(cur, org_row["id"])
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.get("/{org_id}/detail", response_model=OrganizationDetail)
async def get_organization_detail(
    org_id: str,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.view"))
):
    """
    获取指定企业的详细信息
    权限：organization.view
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 验证企业存在
                cur.execute("""
                    SELECT id, name, created_at, updated_at
                    FROM organizations
                    WHERE id = %s
                """, [org_id])
                
                org_row = cur.fetchone()
                if not org_row:
                    raise HTTPException(status_code=404, detail="企业信息不存在")
                
                return await _get_organization_detail(cur, org_id)
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


async def _get_organization_detail(cur, org_id: str) -> OrganizationDetail:
    """获取企业详细信息的内部方法"""
    # 获取企业基本信息
    cur.execute("""
        SELECT id, name, created_at, updated_at
        FROM organizations
        WHERE id = %s
    """, [org_id])
    
    org_row = cur.fetchone()
    if not org_row:
        raise HTTPException(status_code=404, detail="企业信息不存在")
    
    org_info = OrganizationInfo(
        id=org_row["id"],
        name=org_row["name"],
        created_at=str(org_row["created_at"]),
        updated_at=str(org_row["updated_at"])
    )
    
    # 获取成员统计（从 user_organization_mappings 表）
    cur.execute("""
        SELECT 
            COUNT(DISTINCT uom.user_id) as total,
            r.code as role,
            COUNT(DISTINCT uom.user_id) as count
        FROM user_organization_mappings uom
        JOIN users u ON uom.user_id = u.id
        LEFT JOIN user_roles ur ON u.id = ur.user_id
        LEFT JOIN roles r ON ur.role_id = r.id
        WHERE uom.organization_id = %s
        GROUP BY r.code
    """, [org_id])
    
    role_stats = {}
    total_members = 0
    for row in cur.fetchall():
        role = row["role"] or "unknown"
        count = row["count"]
        role_stats[role] = count
        total_members += count
    
    # 获取共享资源统计
    cur.execute("""
        SELECT COUNT(*) as count FROM format_templates 
        WHERE scope = 'organization' AND organization_id = %s
    """, [org_id])
    templates_count = cur.fetchone()["count"]
    
    cur.execute("""
        SELECT COUNT(*) as count FROM tender_rule_packs 
        WHERE scope = 'organization' AND organization_id = %s
    """, [org_id])
    rule_packs_count = cur.fetchone()["count"]
    
    cur.execute("""
        SELECT COUNT(*) as count FROM knowledge_bases 
        WHERE scope = 'organization' AND organization_id = %s
    """, [org_id])
    knowledge_bases_count = cur.fetchone()["count"]
    
    cur.execute("""
        SELECT COUNT(*) as count FROM tender_user_documents 
        WHERE scope = 'organization' AND organization_id = %s
    """, [org_id])
    documents_count = cur.fetchone()["count"]
    
    stats = OrganizationStats(
        total_members=total_members,
        members_by_role=role_stats,
        shared_resources={
            "templates": templates_count,
            "rule_packs": rule_packs_count,
            "knowledge_bases": knowledge_bases_count,
            "documents": documents_count
        }
    )
    
    return OrganizationDetail(info=org_info, stats=stats)


@router.put("/{org_id}", response_model=OrganizationInfo)
async def update_organization(
    org_id: str,
    req: OrganizationUpdate,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.edit"))
):
    """
    更新企业信息
    权限：organization.edit
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 验证用户是否属于该企业
                cur.execute("""
                    SELECT organization_id FROM users WHERE id = %s
                """, [current_user.user_id])
                
                user_org = cur.fetchone()
                if not user_org or user_org["organization_id"] != org_id:
                    raise HTTPException(status_code=403, detail="无权操作该企业")
                
                # 更新企业名称
                cur.execute("""
                    UPDATE organizations 
                    SET name = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, name, created_at, updated_at
                """, [req.name, org_id])
                
                updated = cur.fetchone()
                if not updated:
                    raise HTTPException(status_code=404, detail="企业不存在")
                
                conn.commit()
                
                return OrganizationInfo(
                    id=updated["id"],
                    name=updated["name"],
                    created_at=str(updated["created_at"]),
                    updated_at=str(updated["updated_at"])
                )
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.get("/{org_id}/members", response_model=List[UserBrief])
async def get_organization_members(
    org_id: str,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.view"))
):
    """
    获取企业成员列表（使用多对多关系）
    权限：organization.view
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 获取成员列表（通过user_organization_mappings表）
                cur.execute("""
                    SELECT 
                        u.id, 
                        u.username, 
                        COALESCE(r.code, 'unknown') as role,
                        u.organization_id,
                        u.created_at,
                        u.display_name,
                        u.email
                    FROM user_organization_mappings uom
                    JOIN users u ON uom.user_id = u.id
                    LEFT JOIN user_roles ur ON u.id = ur.user_id
                    LEFT JOIN roles r ON ur.role_id = r.id
                    WHERE uom.organization_id = %s
                    ORDER BY u.created_at DESC
                """, [org_id])
                
                members = []
                for row in cur.fetchall():
                    members.append(UserBrief(
                        id=row["id"],
                        username=row["username"],
                        role=row["role"],
                        organization_id=row["organization_id"],
                        created_at=str(row["created_at"])
                    ))
                
                return members
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.post("/{org_id}/members/batch-bind")
async def batch_bind_users_to_organization(
    org_id: str,
    req: BatchBindRequest,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.member"))
):
    """
    批量绑定用户到企业（使用多对多关系）
    权限：organization.member
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 验证企业存在
                cur.execute("SELECT id FROM organizations WHERE id = %s", [org_id])
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="企业不存在")
                
                # 批量插入用户-企业关联
                success_count = 0
                for user_id in req.user_ids:
                    try:
                        cur.execute("""
                            INSERT INTO user_organization_mappings (user_id, organization_id)
                            VALUES (%s, %s)
                            ON CONFLICT (user_id, organization_id) DO NOTHING
                        """, [user_id, org_id])
                        if cur.rowcount > 0:
                            success_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to bind user {user_id}: {e}")
                        continue
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": f"成功绑定{success_count}个用户到企业",
                    "updated_count": success_count
                }
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.delete("/{org_id}/members/{user_id}")
async def remove_user_from_organization(
    org_id: str,
    user_id: str,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.member"))
):
    """
    将用户从企业移除（删除关联关系）
    权限：organization.member
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 删除用户-企业关联
                cur.execute("""
                    DELETE FROM user_organization_mappings
                    WHERE user_id = %s AND organization_id = %s
                """, [user_id, org_id])
                
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="用户不属于该企业或关联不存在")
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "成功将用户从企业移除"
                }
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.post("/{org_id}/members/{user_id}")
async def add_user_to_organization(
    org_id: str,
    user_id: str,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.member"))
):
    """
    添加单个用户到企业
    权限：organization.member
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 验证企业存在
                cur.execute("SELECT id FROM organizations WHERE id = %s", [org_id])
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="企业不存在")
                
                # 验证用户存在
                cur.execute("SELECT id FROM users WHERE id = %s", [user_id])
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="用户不存在")
                
                # 插入用户-企业关联
                cur.execute("""
                    INSERT INTO user_organization_mappings (user_id, organization_id)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, organization_id) DO NOTHING
                """, [user_id, org_id])
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "用户添加成功"
                }
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.get("/{org_id}/available-users")
async def get_available_users(
    org_id: str,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.member"))
):
    """
    获取可添加到企业的用户列表（未绑定该企业的用户）
    权限：organization.member
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 获取未绑定该企业的所有用户
                cur.execute("""
                    SELECT u.id, u.username, u.display_name, u.email, COALESCE(r.code, 'unknown') as role
                    FROM users u
                    LEFT JOIN user_roles ur ON u.id = ur.user_id
                    LEFT JOIN roles r ON ur.role_id = r.id
                    WHERE u.id NOT IN (
                        SELECT user_id FROM user_organization_mappings WHERE organization_id = %s
                    )
                    ORDER BY u.username
                """, [org_id])
                
                users = []
                for row in cur.fetchall():
                    users.append({
                        "id": row["id"],
                        "username": row["username"],
                        "display_name": row.get("display_name"),
                        "email": row.get("email"),
                        "role": row["role"]
                    })
                
                return users
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    request: Request,
    current_user: TokenData = Depends(require_permission("organization.edit"))
):
    """
    删除企业
    权限：organization.edit
    注意：删除前会删除所有用户-企业关联关系
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 检查企业是否存在
                cur.execute("SELECT id FROM organizations WHERE id = %s", [org_id])
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="企业不存在")
                
                # 删除用户-企业关联（由于设置了 ON DELETE CASCADE，会自动删除）
                # 但为了明确，我们手动删除
                cur.execute("""
                    DELETE FROM user_organization_mappings
                    WHERE organization_id = %s
                """, [org_id])
                
                # 删除企业
                cur.execute("DELETE FROM organizations WHERE id = %s", [org_id])
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "企业删除成功"
                }
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="数据库错误")
