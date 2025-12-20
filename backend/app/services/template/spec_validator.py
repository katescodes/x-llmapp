"""
TemplateSpec JSON Schema 校验器
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

try:
    from jsonschema import validate, ValidationError, Draft7Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    ValidationError = Exception  # type: ignore


class SchemaValidationException(Exception):
    """Schema 校验异常"""
    pass


class TemplateSpecValidator:
    """模板规格校验器"""

    def __init__(self):
        self.schema: Dict[str, Any] = {}
        self._load_schema()

    def _load_schema(self):
        """加载 JSON Schema"""
        schema_path = Path(__file__).parent.parent.parent / "schemas" / "template" / "template-spec.v1.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    def validate(self, spec_json: str) -> Dict[str, Any]:
        """
        校验 JSON 字符串
        
        Args:
            spec_json: JSON 字符串
            
        Returns:
            解析后的 dict
            
        Raises:
            SchemaValidationException: 校验失败
        """
        if not JSONSCHEMA_AVAILABLE:
            # 如果 jsonschema 未安装，只做基本 JSON 解析
            try:
                data = json.loads(spec_json)
                # 基本字段检查
                self._basic_validation(data)
                return data
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                raise SchemaValidationException(f"Basic validation failed: {e}")
        
        try:
            data = json.loads(spec_json)
        except json.JSONDecodeError as e:
            raise SchemaValidationException(f"Invalid JSON: {e}")
        
        try:
            validate(instance=data, schema=self.schema)
        except ValidationError as e:
            raise SchemaValidationException(f"Schema validation failed: {e.message}")
        
        return data

    def _basic_validation(self, data: Dict[str, Any]):
        """基本校验（当 jsonschema 不可用时）"""
        required_fields = ["version", "language", "base_policy", "style_hints", "outline", "merge_policy", "diagnostics"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # 检查 base_policy.mode
        mode = data["base_policy"].get("mode")
        if mode not in ["KEEP_ALL", "KEEP_RANGE", "REBUILD"]:
            raise ValueError(f"Invalid base_policy.mode: {mode}")
        
        # 检查 diagnostics.confidence
        confidence = data["diagnostics"].get("confidence", 0)
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            raise ValueError(f"Invalid diagnostics.confidence: {confidence}")
        
        # 检查 outline 是否为数组
        if not isinstance(data["outline"], list):
            raise ValueError("outline must be an array")


# 全局单例
_validator_instance: TemplateSpecValidator | None = None


def get_validator() -> TemplateSpecValidator:
    """获取校验器单例"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = TemplateSpecValidator()
    return _validator_instance
