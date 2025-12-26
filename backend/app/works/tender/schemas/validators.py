"""
Tender Info V3 Validators - 招标信息校验器

用于校验 LLM 返回的 tender_info_v3 JSON 结构
"""
from typing import Any, Dict
from pydantic import ValidationError

from .tender_info_v3 import TenderInfoV3, TENDER_INFO_V3_KEYS, SCHEMA_VERSION_V3


class TenderInfoV3ValidationError(Exception):
    """Tender Info V3 校验错误"""
    pass


def validate_tender_info_v3(data_json: Dict[str, Any]) -> None:
    """
    校验 tender_info_v3 JSON 数据
    
    Args:
        data_json: 待校验的 JSON 数据
        
    Raises:
        TenderInfoV3ValidationError: 校验失败时抛出异常
    """
    # 检查 schema_version
    if "schema_version" not in data_json:
        raise TenderInfoV3ValidationError("Missing required field: schema_version")
    
    if data_json["schema_version"] != SCHEMA_VERSION_V3:
        raise TenderInfoV3ValidationError(
            f"Invalid schema_version: expected '{SCHEMA_VERSION_V3}', got '{data_json['schema_version']}'"
        )
    
    # 检查九大类 key 是否存在
    for key in TENDER_INFO_V3_KEYS:
        if key not in data_json:
            raise TenderInfoV3ValidationError(f"Missing required category: {key}")
    
    # 使用 Pydantic 进行完整的类型校验
    try:
        TenderInfoV3(**data_json)
    except ValidationError as e:
        raise TenderInfoV3ValidationError(f"Pydantic validation failed: {str(e)}") from e


def validate_tender_info_v3_partial(data_json: Dict[str, Any]) -> None:
    """
    部分校验（允许缺少某些 key，只校验存在的部分）
    
    用于增量更新或部分数据的场景
    
    Args:
        data_json: 待校验的 JSON 数据
        
    Raises:
        TenderInfoV3ValidationError: 校验失败时抛出异常
    """
    # 检查 schema_version（如果存在）
    if "schema_version" in data_json and data_json["schema_version"] != SCHEMA_VERSION_V3:
        raise TenderInfoV3ValidationError(
            f"Invalid schema_version: expected '{SCHEMA_VERSION_V3}', got '{data_json['schema_version']}'"
        )
    
    # 只校验存在的 key
    for key in data_json:
        if key == "schema_version":
            continue
        if key not in TENDER_INFO_V3_KEYS:
            raise TenderInfoV3ValidationError(f"Unknown category key: {key}")
    
    # 使用 Pydantic 校验类型（填充默认值后）
    full_data = {
        "schema_version": SCHEMA_VERSION_V3,
        **{k: {} for k in TENDER_INFO_V3_KEYS},  # 默认值
        **data_json,  # 覆盖已提供的值
    }
    
    try:
        TenderInfoV3(**full_data)
    except ValidationError as e:
        raise TenderInfoV3ValidationError(f"Pydantic validation failed: {str(e)}") from e


def is_valid_tender_info_v3(data_json: Dict[str, Any]) -> bool:
    """
    检查数据是否为有效的 tender_info_v3 格式
    
    Args:
        data_json: 待检查的 JSON 数据
        
    Returns:
        bool: 是否有效
    """
    try:
        validate_tender_info_v3(data_json)
        return True
    except TenderInfoV3ValidationError:
        return False

