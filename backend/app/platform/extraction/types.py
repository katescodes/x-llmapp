"""
Platform Extraction Types
抽取引擎的基础类型定义
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class RetrievedChunk:
    """检索到的文档块"""
    chunk_id: str
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)
    score: Optional[float] = None


@dataclass
class ExtractionSpec:
    """
    抽取任务规格说明
    
    包含了一次抽取所需的所有配置：
    - prompt: 系统提示词
    - queries: 检索查询（可以是单个字符串、列表或字典）
    - schema: 期望的输出 schema（用于验证，可选）
    - topk_per_query: 每个查询的 top-k
    - topk_total: 最终合并后的总量限制
    - doc_types: 文档类型过滤
    """
    prompt: str
    queries: Union[str, List[str], Dict[str, str]]
    topk_per_query: int = 30
    topk_total: int = 120
    doc_types: List[str] = field(default_factory=lambda: ["tender"])
    schema: Optional[Dict[str, Any]] = None
    temperature: float = 0.0


@dataclass
class RetrievalTrace:
    """
    检索追踪信息
    
    记录检索过程的详细信息，用于调试和审计
    """
    retrieval_provider: str = "new"
    retrieval_strategy: str = "single_query"
    queries: Dict[str, Any] = field(default_factory=dict)
    top_k_per_query: int = 30
    top_k_total: int = 120
    retrieved_count_total: int = 0
    doc_types: List[str] = field(default_factory=list)
    embedding_provider: Optional[str] = None
    resolved_mode: Optional[str] = None


@dataclass
class ExtractionResult:
    """
    抽取结果
    
    包含：
    - data: 结构化数据
    - evidence_chunk_ids: 证据块 ID 列表
    - evidence_spans: 证据片段（包含页码等信息）
    - raw_model_output: LLM 原始输出
    - retrieval_trace: 检索追踪信息
    """
    data: Dict[str, Any]
    evidence_chunk_ids: List[str] = field(default_factory=list)
    evidence_spans: List[Dict[str, Any]] = field(default_factory=list)
    raw_model_output: str = ""
    retrieval_trace: Optional[RetrievalTrace] = None

