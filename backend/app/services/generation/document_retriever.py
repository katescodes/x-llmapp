"""
统一的文档检索器
支持Tender和Declare两种场景的资料检索
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


@dataclass
class RetrievalContext:
    """检索上下文"""
    kb_id: str
    section_title: str
    section_level: int
    document_type: str  # 'tender' or 'declare'
    project_info: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None


@dataclass
class RetrievalResult:
    """检索结果"""
    chunks: List[Dict[str, Any]]
    quality_score: float
    has_relevant: bool
    retrieval_strategy: str  # 使用的检索策略
    
    def get_chunk_ids(self) -> List[str]:
        """获取所有chunk ID列表"""
        ids = []
        for chunk in self.chunks:
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            if chunk_id:
                ids.append(chunk_id)
        return ids
    
    def format_for_prompt(self) -> str:
        """格式化为Prompt文本"""
        if not self.chunks:
            return ""
        
        lines = ["【参考资料】"]
        for idx, chunk in enumerate(self.chunks, 1):
            text = chunk.get("text", "")
            doc_name = chunk.get("metadata", {}).get("filename", "未知文档")
            lines.append(f"{idx}. 【{doc_name}】")
            lines.append(text)
            lines.append("")
        
        return "\n".join(lines)


class DocumentRetriever:
    """
    统一的文档检索器
    
    功能：
    1. 根据章节标题智能构建检索query
    2. 从Milvus检索相关文档片段
    3. 评估检索质量
    4. 支持多种检索策略
    """
    
    def __init__(self, pool: ConnectionPool):
        """
        初始化检索器
        
        Args:
            pool: ConnectionPool实例
        """
        from app.platform.retrieval.facade import RetrievalFacade
        self.pool = pool
        self.retrieval_facade = RetrievalFacade(pool)
    
    async def retrieve(
        self, 
        context: RetrievalContext,
        top_k: int = 5,
        strategy: str = "auto"
    ) -> RetrievalResult:
        """
        检索相关文档
        
        Args:
            context: 检索上下文
            top_k: 返回的最相关片段数量
            strategy: 检索策略 ('auto', 'semantic', 'keyword', 'hybrid')
            
        Returns:
            检索结果
        """
        try:
            # Step 1: 构建检索query
            query = self._build_query(context, strategy)
            
            # Step 2: 确定文档类型过滤
            doc_type_filters = self._get_doc_type_filters(context)
            
            # Step 3: 从Milvus检索（使用RetrievalFacade）
            from app.services.embedding_provider_store import get_embedding_provider
            embedding_provider = get_embedding_provider(self.pool)
            
            retrieved_chunks = await self.retrieval_facade.retrieve_from_kb(
                query=query,
                kb_ids=[context.kb_id],
                kb_categories=doc_type_filters,
                embedding_provider=embedding_provider,
                top_k=top_k
            )
            
            # 转换为统一格式
            search_results = [
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "score": chunk.score,
                    "metadata": chunk.metadata
                }
                for chunk in retrieved_chunks
            ]
            
            # Step 4: 评估检索质量
            quality_score = self._assess_quality(search_results)
            has_relevant = quality_score > 0.4
            
            result = RetrievalResult(
                chunks=search_results or [],
                quality_score=quality_score,
                has_relevant=has_relevant,
                retrieval_strategy=strategy
            )
            
            logger.info(
                f"[DocumentRetriever] 检索完成: "
                f"type={context.document_type}, "
                f"section={context.section_title}, "
                f"chunks={len(result.chunks)}, "
                f"quality={quality_score:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[DocumentRetriever] 检索失败: {e}", exc_info=True)
            return RetrievalResult(
                chunks=[],
                quality_score=0.0,
                has_relevant=False,
                retrieval_strategy=strategy
            )
    
    def _build_query(self, context: RetrievalContext, strategy: str) -> str:
        """
        构建检索query
        
        Args:
            context: 检索上下文
            strategy: 检索策略
            
        Returns:
            检索query字符串
        """
        if strategy == "keyword":
            # 关键词策略：仅使用章节标题
            return context.section_title
        
        # 语义和混合策略：扩展关键词
        title_lower = context.section_title.lower()
        
        # Tender特定的关键词映射
        if context.document_type == "tender":
            return self._build_tender_query(title_lower, context.section_title)
        
        # Declare特定的关键词映射
        elif context.document_type == "declare":
            return self._build_declare_query(title_lower, context.section_title, context.requirements)
        
        # 默认：返回标题
        return context.section_title
    
    def _build_tender_query(self, title_lower: str, original_title: str) -> str:
        """构建招投标检索query"""
        if any(kw in title_lower for kw in ["公司", "企业", "简介", "概况", "资质"]):
            return f"{original_title} 企业简介 资质证书 荣誉奖项"
        elif any(kw in title_lower for kw in ["技术", "方案", "实施", "设计"]):
            return f"{original_title} 技术方案 实施方法 技术路线"
        elif any(kw in title_lower for kw in ["案例", "业绩", "项目经验", "成功案例"]):
            return f"{original_title} 项目案例 成功业绩 类似项目"
        elif any(kw in title_lower for kw in ["财务", "报表", "审计"]):
            return f"{original_title} 财务报表 审计报告"
        else:
            return original_title
    
    def _build_declare_query(
        self, 
        title_lower: str, 
        original_title: str,
        requirements: Optional[Dict[str, Any]]
    ) -> str:
        """构建申报书检索query"""
        # 如果有申报要求，可以结合要求构建更精准的query
        query_parts = [original_title]
        
        # 根据章节类型添加扩展关键词
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
    
    def _get_doc_type_filters(self, context: RetrievalContext) -> List[str]:
        """
        获取文档类型过滤条件
        
        Args:
            context: 检索上下文
            
        Returns:
            文档类型列表
        """
        if context.document_type == "tender":
            # 招投标：检索企业资料
            return [
                "qualification_doc",  # 公司资料、证书
                "technical_material",  # 技术文档
                "history_case",       # 案例证明
                "financial_doc"       # 财务文档
            ]
        elif context.document_type == "declare":
            # 申报书：检索用户文档和申报指南
            return [
                "declare_user_doc",   # 用户文档
                "technical_material",  # 技术材料
                "qualification_doc",   # 资质文档
            ]
        else:
            return []
    
    def _assess_quality(self, search_results: List[Dict]) -> float:
        """
        评估检索质量
        
        Args:
            search_results: 检索结果列表
            
        Returns:
            质量评分 (0-1)
        """
        if not search_results:
            return 0.0
        
        # 提取相似度分数
        scores = []
        for chunk in search_results:
            score = chunk.get("score", 0.0)
            # 有些检索系统返回的是distance，需要转换
            if score < 0:
                score = 1.0 / (1.0 + abs(score))
            scores.append(score)
        
        if not scores:
            return 0.0
        
        # 综合评分策略：最高分(0.6权重) + 平均分(0.4权重)
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        
        quality = max_score * 0.6 + avg_score * 0.4
        
        return min(quality, 1.0)

