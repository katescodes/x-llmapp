"""
自定义规则管理 API 路由
支持创建、查询、删除自定义规则
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.utils.auth import get_current_user_sync
from app.utils.permission import require_permission
from app.models.user import TokenData
from app.schemas.custom_rules import (
    CustomRulePackCreateReq,
    CustomRulePackOut,
    CustomRuleOut,
)
from app.services.custom_rule_service import CustomRuleService
from app.services.db.postgres import _get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/custom-rules", tags=["custom-rules"])


def _get_service(request: Request) -> CustomRuleService:
    """获取自定义规则服务实例"""
    pool = _get_pool()
    return CustomRuleService(pool)


@router.post("/rule-packs", response_model=CustomRulePackOut)
def create_rule_pack(
    req: CustomRulePackCreateReq,
    request: Request,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    创建自定义规则包
    
    用户输入规则要求文本，系统自动分析并生成结构化规则
    权限要求：已登录用户
    """
    try:
        service = _get_service(request)
        
        # 创建规则包
        rule_pack = service.create_rule_pack(
            project_id=req.project_id,
            pack_name=req.pack_name,
            rule_requirements=req.rule_requirements,
            model_id=req.model_id,
            owner_id=user.user_id if user else None,
        )
        
        return rule_pack
        
    except ValueError as e:
        # ValueError 包含详细的错误信息
        logger.error(f"创建规则包失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 其他未预料的异常
        logger.error(f"创建规则包失败（未知错误）: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建规则包失败：{str(e)}")


@router.get("/rule-packs", response_model=List[CustomRulePackOut])
def list_rule_packs(
    project_id: Optional[str] = None,
    request: Request = None,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    列出自定义规则包
    
    Args:
        project_id: 项目ID（可选，为空则列出所有项目的规则包）
    权限要求：已登录用户
    """
    service = _get_service(request)
    
    # 获取用户的规则包列表
    owner_id = user.user_id if user else None
    rule_packs = service.list_rule_packs(
        project_id=project_id,
        owner_id=owner_id,
    )
    
    return rule_packs


@router.get("/rule-packs/{pack_id}", response_model=CustomRulePackOut)
def get_rule_pack(
    pack_id: str,
    request: Request,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    获取单个规则包详情
    权限要求：已登录用户
    """
    service = _get_service(request)
    
    rule_pack = service.get_rule_pack(pack_id)
    
    if not rule_pack:
        raise HTTPException(status_code=404, detail="Rule pack not found")
    
    # 权限检查：验证所有权
    if user and user.role != 'admin':
        project_id = rule_pack.get("project_id")
        if project_id:
            # TODO: 验证用户是否有权访问该项目
            pass
    
    return rule_pack


@router.delete("/rule-packs/{pack_id}")
def delete_rule_pack(
    pack_id: str,
    request: Request,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    删除规则包（级联删除所有关联规则）
    权限要求：已登录用户
    """
    service = _get_service(request)
    
    # 先获取规则包，验证权限
    rule_pack = service.get_rule_pack(pack_id)
    
    if not rule_pack:
        raise HTTPException(status_code=404, detail="Rule pack not found")
    
    # 权限检查：验证所有权
    if user and user.role != 'admin':
        project_id = rule_pack.get("project_id")
        if project_id:
            # TODO: 验证用户是否有权访问该项目
            pass
    
    # 删除规则包
    service.delete_rule_pack(pack_id)
    
    return {"message": "Rule pack deleted successfully"}


@router.get("/rule-packs/{pack_id}/rules", response_model=List[CustomRuleOut])
def list_rules(
    pack_id: str,
    request: Request,
    user: TokenData = Depends(get_current_user_sync),
):
    """
    列出规则包中的所有规则
    权限要求：已登录用户
    """
    service = _get_service(request)
    
    rules = service.list_rules(pack_id)
    
    return rules


# ==================== 资源共享接口 ====================

@router.post("/rule-packs/{pack_id}/share")
def share_rule_pack_to_organization(
    pack_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    共享规则包到企业
    只有规则包的创建者可以共享
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            import psycopg.rows
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 检查规则包是否存在且用户是否为owner
                # 规则包通过project_id关联到项目，项目有owner_id
                cur.execute("""
                    SELECT rp.id, rp.pack_name, rp.scope, p.owner_id
                    FROM tender_rule_packs rp
                    LEFT JOIN tender_projects p ON rp.project_id = p.project_id
                    WHERE rp.id = %s
                """, [pack_id])
                
                pack = cur.fetchone()
                if not pack:
                    raise HTTPException(status_code=404, detail="规则包不存在")
                
                # 如果是共享规则包（没有project_id），检查是否有权限
                # 假设共享规则包只有admin可以共享
                if pack["owner_id"] is None:
                    if user.role != "admin":
                        raise HTTPException(status_code=403, detail="只有管理员可以共享公共规则包")
                elif pack["owner_id"] != user.user_id:
                    raise HTTPException(status_code=403, detail="只有规则包创建者可以共享")
                
                if pack["scope"] == 'organization':
                    return {"success": True, "message": "规则包已经是共享状态"}
                
                # 获取用户的企业ID
                cur.execute("SELECT organization_id FROM users WHERE id = %s", [user.user_id])
                user_row = cur.fetchone()
                user_org_id = user_row['organization_id'] if user_row else None
                
                if not user_org_id:
                    raise HTTPException(status_code=400, detail="用户没有关联企业，无法共享")
                
                # 更新为共享状态，并设置企业ID
                cur.execute("""
                    UPDATE tender_rule_packs 
                    SET scope = 'organization', 
                        organization_id = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, [user_org_id, pack_id])
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "规则包已共享到企业",
                    "pack_id": pack_id,
                    "scope": "organization"
                }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"共享规则包失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"共享失败: {str(e)}")


@router.post("/rule-packs/{pack_id}/unshare")
def unshare_rule_pack_from_organization(
    pack_id: str,
    request: Request,
    user: TokenData = Depends(require_permission("tender.edit"))
):
    """
    取消共享规则包（改回私有）
    只有规则包的创建者可以取消共享
    """
    pool = _get_pool()
    
    try:
        with pool.connection() as conn:
            import psycopg.rows
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # 检查规则包是否存在且用户是否为owner
                cur.execute("""
                    SELECT rp.id, rp.pack_name, rp.scope, p.owner_id
                    FROM tender_rule_packs rp
                    LEFT JOIN tender_projects p ON rp.project_id = p.project_id
                    WHERE rp.id = %s
                """, [pack_id])
                
                pack = cur.fetchone()
                if not pack:
                    raise HTTPException(status_code=404, detail="规则包不存在")
                
                # 检查权限
                if pack["owner_id"] is None:
                    if user.role != "admin":
                        raise HTTPException(status_code=403, detail="只有管理员可以取消共享公共规则包")
                elif pack["owner_id"] != user.user_id:
                    raise HTTPException(status_code=403, detail="只有规则包创建者可以取消共享")
                
                if pack["scope"] == 'private':
                    return {"success": True, "message": "规则包已经是私有状态"}
                
                # 更新为私有状态，并清除企业ID
                cur.execute("""
                    UPDATE tender_rule_packs 
                    SET scope = 'private', 
                        organization_id = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                """, [pack_id])
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "规则包已取消共享",
                    "pack_id": pack_id,
                    "scope": "private"
                }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消共享规则包失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"取消共享失败: {str(e)}")
