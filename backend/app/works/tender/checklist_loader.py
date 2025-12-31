"""
标准清单加载器
用于加载和解析YAML格式的招标要求标准清单模板
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ChecklistLoader:
    """标准清单加载器"""
    
    def __init__(self, checklists_dir: Optional[str] = None):
        """
        初始化加载器
        
        Args:
            checklists_dir: 清单模板目录路径（默认为当前目录下的checklists/）
        """
        if checklists_dir:
            self.checklists_dir = Path(checklists_dir)
        else:
            # 默认目录：backend/app/works/tender/checklists/
            self.checklists_dir = Path(__file__).parent / "checklists"
        
        logger.info(f"ChecklistLoader initialized with directory: {self.checklists_dir}")
    
    def load_template(self, template_name: str, version: str = "v1") -> Dict[str, Any]:
        """
        加载标准清单模板
        
        Args:
            template_name: 模板名称（如 "engineering", "goods", "service"）
            version: 版本号（默认 "v1"）
        
        Returns:
            解析后的清单数据
        
        Raises:
            FileNotFoundError: 模板文件不存在
            yaml.YAMLError: YAML解析失败
        """
        # 构建文件路径
        filename = f"{template_name}_{version}.yaml"
        filepath = self.checklists_dir / filename
        
        logger.info(f"Loading checklist template: {filepath}")
        
        if not filepath.exists():
            raise FileNotFoundError(f"Checklist template not found: {filepath}")
        
        # 加载YAML
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            logger.info(
                f"Successfully loaded template '{template_name}_{version}': "
                f"{data.get('metadata', {}).get('total_items', 0)} items"
            )
            
            return data
        
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML file {filepath}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load checklist template {filepath}: {e}")
            raise
    
    def get_all_items(self, template_data: Dict) -> List[Dict]:
        """
        获取模板中的所有检查项（扁平化）
        
        Args:
            template_data: 模板数据（load_template的返回值）
        
        Returns:
            检查项列表，每项包含：
            - id: 检查项ID
            - category: 类别名称
            - dimension: 维度
            - question: 问题
            - type: 数据类型
            - norm_key: 标准化键（可选）
            - is_hard: 是否硬性要求
            - req_type: 要求类型
            - eval_method: 评估方法
            - unit: 单位（可选）
            - must_reject: 是否必须拒绝（可选）
        """
        all_items = []
        
        # 遍历所有类别
        categories = [
            'price_and_security', 'duration_and_warranty',
            'qualification', 'technical', 'business',
            'document', 'evaluation', 'scoring', 'other'
        ]
        
        for category_key in categories:
            if category_key not in template_data:
                continue
            
            category_data = template_data[category_key]
            category_name = category_data.get('category', category_key)
            dimension = category_data.get('dimension', 'other')
            items = category_data.get('items', [])
            
            for item in items:
                # 添加类别和维度信息
                item_copy = item.copy()
                item_copy['category'] = category_name
                if 'dimension' not in item_copy:
                    item_copy['dimension'] = dimension
                
                all_items.append(item_copy)
        
        logger.info(f"Extracted {len(all_items)} items from template")
        
        return all_items
    
    def get_items_by_category(self, template_data: Dict, category_key: str) -> List[Dict]:
        """
        获取指定类别的检查项
        
        Args:
            template_data: 模板数据
            category_key: 类别键（如 "price_and_security"）
        
        Returns:
            该类别的检查项列表
        """
        if category_key not in template_data:
            logger.warning(f"Category '{category_key}' not found in template")
            return []
        
        category_data = template_data[category_key]
        items = category_data.get('items', [])
        
        # 添加类别和维度信息
        category_name = category_data.get('category', category_key)
        dimension = category_data.get('dimension', 'other')
        
        enriched_items = []
        for item in items:
            item_copy = item.copy()
            item_copy['category'] = category_name
            if 'dimension' not in item_copy:
                item_copy['dimension'] = dimension
            enriched_items.append(item_copy)
        
        return enriched_items
    
    def get_mandatory_items(self, template_data: Dict) -> List[Dict]:
        """
        获取所有硬性要求项
        
        Args:
            template_data: 模板数据
        
        Returns:
            硬性要求项列表
        """
        all_items = self.get_all_items(template_data)
        mandatory_items = [item for item in all_items if item.get('is_hard', False)]
        
        logger.info(f"Found {len(mandatory_items)} mandatory items")
        
        return mandatory_items
    
    def get_items_with_norm_key(self, template_data: Dict) -> List[Dict]:
        """
        获取所有有norm_key映射的检查项
        
        Args:
            template_data: 模板数据
        
        Returns:
            有norm_key的检查项列表
        """
        all_items = self.get_all_items(template_data)
        items_with_norm_key = [item for item in all_items if item.get('norm_key')]
        
        logger.info(f"Found {len(items_with_norm_key)} items with norm_key")
        
        return items_with_norm_key
    
    def get_template_metadata(self, template_data: Dict) -> Dict[str, Any]:
        """
        获取模板元数据
        
        Args:
            template_data: 模板数据
        
        Returns:
            元数据字典
        """
        return template_data.get('metadata', {})
    
    def list_available_templates(self) -> List[str]:
        """
        列出所有可用的模板
        
        Returns:
            模板名称列表（不含版本和扩展名）
        """
        if not self.checklists_dir.exists():
            logger.warning(f"Checklists directory not found: {self.checklists_dir}")
            return []
        
        templates = []
        for filepath in self.checklists_dir.glob("*.yaml"):
            # 提取模板名称（去除版本和扩展名）
            # 例如：engineering_v1.yaml → engineering
            name = filepath.stem  # engineering_v1
            if '_v' in name:
                name = name.rsplit('_v', 1)[0]  # engineering
            
            if name not in templates:
                templates.append(name)
        
        logger.info(f"Found {len(templates)} available templates: {templates}")
        
        return templates

