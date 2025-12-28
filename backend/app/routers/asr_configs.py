"""
ASR配置管理API路由
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.services import asr_config_service
from app.models.user import TokenData
from app.utils.permission import require_permission

router = APIRouter(prefix="/api/asr-configs", tags=["ASR Configurations"])

class ASRConfigCreate(BaseModel):
    """创建ASR配置请求"""
    name: str
    api_url: str
    model_name: str = "whisper"
    response_format: str = "verbose_json"
    api_key: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    extra_params: Optional[Dict[str, Any]] = None

class ASRConfigUpdate(BaseModel):
    """更新ASR配置请求"""
    name: Optional[str] = None
    api_url: Optional[str] = None
    model_name: Optional[str] = None
    response_format: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    extra_params: Optional[Dict[str, Any]] = None

class ImportCurlRequest(BaseModel):
    """导入curl命令请求"""
    curl_command: str

@router.get("")
async def list_configs(
    current_user: TokenData = Depends(require_permission("system.asr"))
):
    """
    获取所有ASR配置列表
    
    权限要求：system.asr
    """
    configs = asr_config_service.get_all_configs()
    return {"items": configs, "total": len(configs)}

@router.get("/{config_id}")
async def get_config(
    config_id: str,
    current_user: TokenData = Depends(require_permission("system.asr"))
):
    """
    获取指定ASR配置详情
    
    权限要求：system.asr
    """
    config = asr_config_service.get_config_by_id(config_id)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    return config

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_config(
    config_data: ASRConfigCreate,
    current_user: TokenData = Depends(require_permission("system.asr"))
):
    """
    创建新的ASR配置
    
    权限要求：system.asr
    """
    config = asr_config_service.create_config(
        name=config_data.name,
        api_url=config_data.api_url,
        model_name=config_data.model_name,
        response_format=config_data.response_format,
        api_key=config_data.api_key,
        is_active=config_data.is_active,
        is_default=config_data.is_default,
        extra_params=config_data.extra_params
    )
    
    return config

@router.patch("/{config_id}")
async def update_config(
    config_id: str,
    update_data: ASRConfigUpdate,
    current_user: TokenData = Depends(require_permission("system.asr"))
):
    """
    更新ASR配置
    
    权限要求：system.asr
    """
    config = asr_config_service.update_config(
        config_id=config_id,
        name=update_data.name,
        api_url=update_data.api_url,
        model_name=update_data.model_name,
        response_format=update_data.response_format,
        api_key=update_data.api_key,
        is_active=update_data.is_active,
        is_default=update_data.is_default,
        extra_params=update_data.extra_params
    )
    
    return config

@router.delete("/{config_id}")
async def delete_config(
    config_id: str,
    current_user: TokenData = Depends(require_permission("system.asr"))
):
    """
    删除ASR配置
    
    权限要求：system.asr
    """
    deleted = asr_config_service.delete_config(config_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    return {"message": "Configuration deleted successfully"}

@router.post("/{config_id}/test")
async def test_config(
    config_id: str,
    current_user: TokenData = Depends(require_permission("system.asr"))
):
    """
    测试ASR配置是否可用
    
    权限要求：system.asr
    """
    result = await asr_config_service.test_config(config_id)
    return result

@router.post("/import/curl", status_code=status.HTTP_201_CREATED)
async def import_from_curl(
    request: ImportCurlRequest,
    current_user: TokenData = Depends(require_permission("system.asr"))
):
    """
    从curl命令导入ASR配置
    
    权限要求：system.asr
    
    示例curl命令:
    ```
    curl --location --request POST 'https://ai.yglinker.com:6399/v1/audio/transcriptions' \
    --form 'model="whisper"' \
    --form 'response_format="verbose_json"' \
    --form 'file=@"path/to/audio.mp3"'
    ```
    """
    config = asr_config_service.import_from_curl(request.curl_command)
    return config

