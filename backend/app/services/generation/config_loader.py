"""
配置加载器
从YAML文件加载配置
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class GenerationConfig:
    """
    生成框架配置类
    
    单例模式，全局共享配置
    """
    
    _instance: Optional['GenerationConfig'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """加载配置文件"""
        try:
            import yaml
            
            # 查找配置文件
            config_path = self._find_config_file()
            if not config_path:
                logger.warning("未找到配置文件，使用默认配置")
                self._config = self._default_config()
                return
            
            # 加载YAML
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            
            logger.info(f"已加载配置文件: {config_path}")
            
        except ImportError:
            logger.warning("PyYAML未安装，使用默认配置")
            self._config = self._default_config()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，使用默认配置")
            self._config = self._default_config()
    
    def _find_config_file(self) -> Optional[Path]:
        """查找配置文件"""
        # 1. 环境变量指定的路径
        env_path = os.getenv("GENERATION_CONFIG_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path
        
        # 2. 当前目录下的config.yaml
        current_dir = Path(__file__).parent
        config_path = current_dir / "config.yaml"
        if config_path.exists():
            return config_path
        
        # 3. 项目根目录下的generation_config.yaml
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "generation_config.yaml"
        if config_path.exists():
            return config_path
        
        return None
    
    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            "global": {
                "default_temperature": 0.7,
                "default_max_tokens": 2000,
                "default_concurrency": 5
            },
            "retrieval": {
                "default_top_k": 5,
                "quality_threshold": 0.4
            },
            "tender": {
                "templates": {
                    "system": "tender_system.md",
                    "user": "tender_user.md"
                },
                "llm": {
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                "min_words": {
                    "level_1": 800,
                    "level_2": 500,
                    "level_3": 300,
                    "level_4": 200
                },
                "doc_type_filters": [
                    "qualification_doc",
                    "technical_material",
                    "history_case",
                    "financial_doc"
                ]
            },
            "declare": {
                "templates": {
                    "system": "declare_system.md",
                    "user": "declare_user.md"
                },
                "llm": {
                    "temperature": 0.6,
                    "max_tokens": 2500
                },
                "doc_type_filters": [
                    "declare_user_doc",
                    "technical_material",
                    "qualification_doc"
                ]
            },
            "quality_assessment": {
                "weights": {
                    "completeness": 0.4,
                    "evidence": 0.3,
                    "format": 0.3
                }
            },
            "monitoring": {
                "enabled": True,
                "log_level": "INFO"
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的多级键，如 "tender.llm.temperature"
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_tender_config(self) -> Dict[str, Any]:
        """获取Tender配置"""
        return self.get("tender", {})
    
    def get_declare_config(self) -> Dict[str, Any]:
        """获取Declare配置"""
        return self.get("declare", {})
    
    def get_retrieval_config(self) -> Dict[str, Any]:
        """获取检索配置"""
        return self.get("retrieval", {})
    
    def get_quality_config(self) -> Dict[str, Any]:
        """获取质量评估配置"""
        return self.get("quality_assessment", {})
    
    def reload(self):
        """重新加载配置"""
        self._load_config()
        logger.info("配置已重新加载")


# 全局配置实例
_config_instance = None


def get_config() -> GenerationConfig:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = GenerationConfig()
    return _config_instance

