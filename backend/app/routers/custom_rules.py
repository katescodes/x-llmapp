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
