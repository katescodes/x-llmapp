"""
统一文档生成框架
包含Tender和Declare共用的核心组件

Features:
- 文档检索
- Prompt构建
- 内容生成
- 质量评估
- 配置管理
- 策略扩展
- 监控日志
"""

from .document_retriever import (
    DocumentRetriever,
    RetrievalContext,
    RetrievalResult
)

from .prompt_builder import (
    PromptBuilder,
    PromptContext,
    PromptOutput
)

from .content_generator import (
    ContentGenerator,
    GenerationContext,
    GenerationResult
)

from .quality_assessor import (
    QualityAssessor,
    QualityMetrics
)

from .template_engine import (
    TemplateEngine,
    get_template_engine
)

from .config_loader import (
    GenerationConfig,
    get_config
)

from .strategies import (
    RetrievalStrategy,
    GenerationStrategy,
    SemanticRetrievalStrategy,
    KeywordRetrievalStrategy,
    HybridRetrievalStrategy,
    StandardGenerationStrategy,
    CreativeGenerationStrategy,
    ConservativeGenerationStrategy,
    StrategyRegistry,
    get_strategy_registry
)

from .monitoring import (
    PerformanceMetrics,
    PerformanceMonitor,
    AuditLog,
    AuditLogger,
    get_performance_monitor,
    get_audit_logger
)

__all__ = [
    # Retriever
    "DocumentRetriever",
    "RetrievalContext",
    "RetrievalResult",
    
    # Prompt Builder
    "PromptBuilder",
    "PromptContext",
    "PromptOutput",
    
    # Generator
    "ContentGenerator",
    "GenerationContext",
    "GenerationResult",
    
    # Quality Assessor
    "QualityAssessor",
    "QualityMetrics",
    
    # Template Engine
    "TemplateEngine",
    "get_template_engine",
    
    # Config
    "GenerationConfig",
    "get_config",
    
    # Strategies
    "RetrievalStrategy",
    "GenerationStrategy",
    "SemanticRetrievalStrategy",
    "KeywordRetrievalStrategy",
    "HybridRetrievalStrategy",
    "StandardGenerationStrategy",
    "CreativeGenerationStrategy",
    "ConservativeGenerationStrategy",
    "StrategyRegistry",
    "get_strategy_registry",
    
    # Monitoring
    "PerformanceMetrics",
    "PerformanceMonitor",
    "AuditLog",
    "AuditLogger",
    "get_performance_monitor",
    "get_audit_logger",
]

