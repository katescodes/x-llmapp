"""
策略插件系统
支持自定义检索和生成策略
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ==================== 检索策略 ====================

class RetrievalStrategy(ABC):
    """检索策略基类"""
    
    @abstractmethod
    def build_query(self, section_title: str, context: Dict[str, Any]) -> str:
        """
        构建检索query
        
        Args:
            section_title: 章节标题
            context: 上下文信息（project_info, requirements等）
            
        Returns:
            检索query字符串
        """
        pass
    
    @abstractmethod
    def get_doc_type_filters(self, document_type: str) -> List[str]:
        """
        获取文档类型过滤条件
        
        Args:
            document_type: 文档类型 ('tender' or 'declare')
            
        Returns:
            文档类型列表
        """
        pass


class SemanticRetrievalStrategy(RetrievalStrategy):
    """语义检索策略（扩展关键词）"""
    
    def build_query(self, section_title: str, context: Dict[str, Any]) -> str:
        """构建语义检索query"""
        document_type = context.get("document_type", "")
        
        if document_type == "tender":
            return self._build_tender_query(section_title)
        elif document_type == "declare":
            return self._build_declare_query(section_title, context.get("requirements"))
        else:
            return section_title
    
    def _build_tender_query(self, title: str) -> str:
        """构建招投标检索query"""
        title_lower = title.lower()
        
        if any(kw in title_lower for kw in ["公司", "企业", "简介", "概况", "资质"]):
            return f"{title} 企业简介 资质证书 荣誉奖项"
        elif any(kw in title_lower for kw in ["技术", "方案", "实施", "设计"]):
            return f"{title} 技术方案 实施方法 技术路线"
        elif any(kw in title_lower for kw in ["案例", "业绩", "项目经验", "成功案例"]):
            return f"{title} 项目案例 成功业绩 类似项目"
        elif any(kw in title_lower for kw in ["财务", "报表", "审计"]):
            return f"{title} 财务报表 审计报告"
        else:
            return title
    
    def _build_declare_query(self, title: str, requirements: Optional[Dict]) -> str:
        """构建申报书检索query"""
        title_lower = title.lower()
        query_parts = [title]
        
        if any(kw in title_lower for kw in ["项目背景", "研究背景", "立项依据"]):
            query_parts.append("项目背景 研究现状 技术难点")
        elif any(kw in title_lower for kw in ["技术方案", "研究方案", "实施方案"]):
            query_parts.append("技术路线 实施方法 创新点")
        elif any(kw in title_lower for kw in ["创新点", "技术创新", "特色"]):
            query_parts.append("创新特色 技术优势 突破点")
        elif any(kw in title_lower for kw in ["团队", "人员", "组织"]):
            query_parts.append("团队介绍 人员配置 项目组")
        elif any(kw in title_lower for kw in ["预算", "经费", "资金"]):
            query_parts.append("经费预算 资金计划 成本明细")
        
        return " ".join(query_parts)
    
    def get_doc_type_filters(self, document_type: str) -> List[str]:
        """获取文档类型过滤条件"""
        if document_type == "tender":
            return [
                "qualification_doc",
                "technical_material",
                "history_case",
                "financial_doc"
            ]
        elif document_type == "declare":
            return [
                "declare_user_doc",
                "technical_material",
                "qualification_doc"
            ]
        else:
            return []


class KeywordRetrievalStrategy(RetrievalStrategy):
    """关键词检索策略（仅使用标题）"""
    
    def build_query(self, section_title: str, context: Dict[str, Any]) -> str:
        """构建关键词检索query"""
        return section_title
    
    def get_doc_type_filters(self, document_type: str) -> List[str]:
        """获取文档类型过滤条件"""
        # 使用语义策略的过滤条件
        semantic_strategy = SemanticRetrievalStrategy()
        return semantic_strategy.get_doc_type_filters(document_type)


class HybridRetrievalStrategy(RetrievalStrategy):
    """混合检索策略（结合语义和关键词）"""
    
    def build_query(self, section_title: str, context: Dict[str, Any]) -> str:
        """构建混合检索query"""
        # 当前实现与语义策略相同，未来可以扩展
        semantic_strategy = SemanticRetrievalStrategy()
        return semantic_strategy.build_query(section_title, context)
    
    def get_doc_type_filters(self, document_type: str) -> List[str]:
        """获取文档类型过滤条件"""
        semantic_strategy = SemanticRetrievalStrategy()
        return semantic_strategy.get_doc_type_filters(document_type)


# ==================== 生成策略 ====================

class GenerationStrategy(ABC):
    """生成策略基类"""
    
    @abstractmethod
    def get_temperature(self, document_type: str, section_level: int) -> float:
        """
        获取温度参数
        
        Args:
            document_type: 文档类型
            section_level: 章节层级
            
        Returns:
            温度值
        """
        pass
    
    @abstractmethod
    def get_max_tokens(self, document_type: str, section_level: int) -> int:
        """
        获取最大token数
        
        Args:
            document_type: 文档类型
            section_level: 章节层级
            
        Returns:
            最大token数
        """
        pass


class StandardGenerationStrategy(GenerationStrategy):
    """标准生成策略"""
    
    def get_temperature(self, document_type: str, section_level: int) -> float:
        """获取温度参数"""
        if document_type == "tender":
            return 0.7
        elif document_type == "declare":
            return 0.6  # 申报书更严谨
        else:
            return 0.7
    
    def get_max_tokens(self, document_type: str, section_level: int) -> int:
        """获取最大token数"""
        if section_level == 1:
            return 3000
        elif section_level >= 4:
            return 1500
        else:
            return 2000


class CreativeGenerationStrategy(GenerationStrategy):
    """创意生成策略（更高温度）"""
    
    def get_temperature(self, document_type: str, section_level: int) -> float:
        """获取温度参数"""
        return 0.9  # 更高的随机性
    
    def get_max_tokens(self, document_type: str, section_level: int) -> int:
        """获取最大token数"""
        return 2500


class ConservativeGenerationStrategy(GenerationStrategy):
    """保守生成策略（更低温度）"""
    
    def get_temperature(self, document_type: str, section_level: int) -> float:
        """获取温度参数"""
        return 0.4  # 更低的随机性，更确定
    
    def get_max_tokens(self, document_type: str, section_level: int) -> int:
        """获取最大token数"""
        return 2000


# ==================== 策略注册表 ====================

class StrategyRegistry:
    """策略注册表"""
    
    def __init__(self):
        self._retrieval_strategies: Dict[str, RetrievalStrategy] = {}
        self._generation_strategies: Dict[str, GenerationStrategy] = {}
        
        # 注册默认策略
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """注册默认策略"""
        # 检索策略
        self.register_retrieval_strategy("semantic", SemanticRetrievalStrategy())
        self.register_retrieval_strategy("keyword", KeywordRetrievalStrategy())
        self.register_retrieval_strategy("hybrid", HybridRetrievalStrategy())
        
        # 生成策略
        self.register_generation_strategy("standard", StandardGenerationStrategy())
        self.register_generation_strategy("creative", CreativeGenerationStrategy())
        self.register_generation_strategy("conservative", ConservativeGenerationStrategy())
    
    def register_retrieval_strategy(self, name: str, strategy: RetrievalStrategy):
        """注册检索策略"""
        self._retrieval_strategies[name] = strategy
        logger.info(f"注册检索策略: {name}")
    
    def register_generation_strategy(self, name: str, strategy: GenerationStrategy):
        """注册生成策略"""
        self._generation_strategies[name] = strategy
        logger.info(f"注册生成策略: {name}")
    
    def get_retrieval_strategy(self, name: str = "semantic") -> RetrievalStrategy:
        """获取检索策略"""
        strategy = self._retrieval_strategies.get(name)
        if strategy is None:
            logger.warning(f"检索策略 '{name}' 不存在，使用默认策略 'semantic'")
            return self._retrieval_strategies["semantic"]
        return strategy
    
    def get_generation_strategy(self, name: str = "standard") -> GenerationStrategy:
        """获取生成策略"""
        strategy = self._generation_strategies.get(name)
        if strategy is None:
            logger.warning(f"生成策略 '{name}' 不存在，使用默认策略 'standard'")
            return self._generation_strategies["standard"]
        return strategy
    
    def list_retrieval_strategies(self) -> List[str]:
        """列出所有检索策略"""
        return list(self._retrieval_strategies.keys())
    
    def list_generation_strategies(self) -> List[str]:
        """列出所有生成策略"""
        return list(self._generation_strategies.keys())


# 全局策略注册表
_strategy_registry = None


def get_strategy_registry() -> StrategyRegistry:
    """获取全局策略注册表"""
    global _strategy_registry
    if _strategy_registry is None:
        _strategy_registry = StrategyRegistry()
    return _strategy_registry

