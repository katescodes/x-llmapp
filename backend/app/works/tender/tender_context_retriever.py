"""
招标文档上下文检索组件（公共）

统一封装招标侧信息抽取和要求抽取的检索逻辑，
避免重复检索、保证数据一致性、减少成本。
"""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TenderContextData:
    """招标文档上下文数据"""
    chunks: List[Any]  # 原始检索到的chunks
    context_text: str  # 拼接后的上下文文本（带SEG标记）
    segment_id_map: Dict[str, Any]  # segment_id → chunk对象的映射
    total_chunks: int  # 总检索chunks数量
    used_chunks: int  # 实际使用的chunks数量（token限制）
    

class TenderContextRetriever:
    """招标文档上下文检索器（公共组件）"""
    
    # 合同条款相关的关键词（用于过滤）
    # 强匹配：几乎100%是合同条款
    STRONG_CONTRACT_KEYWORDS = [
        "甲方：", "乙方：",
        "法定代表人签字", "授权代表签字",
        "（甲方）", "（乙方）", "（盖章）",
        "签订地点：", "签订日期：",
        "本合同一式", "份正本",
    ]
    
    # 中等匹配：很可能是合同条款
    MEDIUM_CONTRACT_KEYWORDS = [
        "合同条款", "合同格式", "合同协议书",
        "合同专用条款", "合同通用条款",
        "合同主要条款", "合同范本",
        "争议解决：", "仲裁委员会",
    ]
    
    def __init__(self, retriever):
        """
        初始化
        
        Args:
            retriever: RetrievalFacade实例
        """
        self.retriever = retriever
    
    def _is_contract_clause_chunk(self, chunk: Any) -> bool:
        """
        判断 chunk 是否属于合同条款部分
        
        Args:
            chunk: 检索到的 chunk
        
        Returns:
            True 如果是合同条款，应该被过滤
        """
        text = chunk.text or ""
        
        # 1. 强匹配：直接过滤
        for keyword in self.STRONG_CONTRACT_KEYWORDS:
            if keyword in text:
                logger.debug(f"过滤合同条款chunk（强匹配）: {keyword[:20]}...")
                return True
        
        # 2. 中等匹配：计数
        medium_matches = sum(1 for kw in self.MEDIUM_CONTRACT_KEYWORDS if kw in text)
        if medium_matches >= 2:  # 至少2个中等关键词
            logger.debug(f"过滤合同条款chunk（中等匹配）: {medium_matches}个关键词")
            return True
        
        # 3. 检查 heading_path（如果有）
        if hasattr(chunk, 'meta') and chunk.meta:
            heading_path = chunk.meta.get('heading_path', '')
            if heading_path and (
                '合同条款' in heading_path or 
                '合同格式' in heading_path or
                '合同协议' in heading_path
            ):
                logger.debug(f"过滤合同条款chunk（标题匹配）: {heading_path}")
                return True
        
        return False
    
    async def retrieve_tender_context(
        self,
        project_id: str,
        query: Optional[str] = None,
        top_k: int = 150,
        max_context_chunks: int = 100,
        sort_by_position: bool = True,
        filter_contract_clauses: bool = False,  # ✨ 新增参数
    ) -> TenderContextData:
        """
        检索招标文档上下文（统一入口）
        
        Args:
            project_id: 项目ID
            query: 查询词（默认使用通用招标查询词）
            top_k: 检索chunks数量
            max_context_chunks: 最多使用多少chunks拼接上下文（token限制）
            sort_by_position: 是否按文档位置排序（保持原文顺序）
            filter_contract_clauses: 是否过滤合同条款相关内容（默认False）
            
        Returns:
            TenderContextData: 统一的上下文数据对象
        """
        # 使用默认通用查询词（覆盖各类招标/采购）
        if query is None:
            query = (
                "招标文件 投标人须知 评分标准 技术要求 资格条件 商务条款 "
                "工期 质保 价格 磋商 资信 报价 方案 合同 授权 资质 "
                "保证金 承诺 证明 材料 评审 评分 废标 一票否决 "
                "实质性要求 偏离 附件 文件格式"
            )
        
        logger.info(
            f"TenderContextRetriever: 检索招标上下文 project_id={project_id}, "
            f"top_k={top_k}, max_context_chunks={max_context_chunks}"
        )
        
        # 1. 检索
        context_chunks = await self.retriever.retrieve(
            query=query,
            project_id=project_id,
            doc_types=["tender"],
            top_k=top_k,
        )
        
        logger.info(f"TenderContextRetriever: 检索到 {len(context_chunks)} 个chunks")
        
        if not context_chunks:
            logger.warning(f"TenderContextRetriever: 未检索到任何chunks！project_id={project_id}")
            return TenderContextData(
                chunks=[],
                context_text="",
                segment_id_map={},
                total_chunks=0,
                used_chunks=0,
            )
        
        # 2. 可选：按文档位置排序（保持原文顺序，有助于理解上下文）
        if sort_by_position:
            context_chunks = self._sort_by_position(context_chunks)
            logger.info("TenderContextRetriever: 已按文档位置排序")
        
        # ✨ 2.5. 可选：过滤合同条款
        if filter_contract_clauses:
            original_count = len(context_chunks)
            context_chunks = [
                chunk for chunk in context_chunks 
                if not self._is_contract_clause_chunk(chunk)
            ]
            filtered_count = original_count - len(context_chunks)
            if filtered_count > 0:
                logger.info(
                    f"TenderContextRetriever: 过滤了 {filtered_count} 个合同条款相关chunks "
                    f"({original_count} → {len(context_chunks)})"
                )
        
        # 3. 截取（token限制）
        used_chunks = context_chunks[:max_context_chunks]
        
        # 4. 拼接上下文文本（带SEG标记）
        context_text = "\n\n".join([
            f"[SEG:{chunk.chunk_id}] {chunk.text}"
            for chunk in used_chunks
        ])
        
        # 5. 构建segment_id映射表（用于后续evidence验证）
        segment_id_map = {chunk.chunk_id: chunk for chunk in used_chunks}
        
        # 6. 返回统一的上下文对象
        result = TenderContextData(
            chunks=used_chunks,
            context_text=context_text,
            segment_id_map=segment_id_map,
            total_chunks=len(context_chunks),
            used_chunks=len(used_chunks),
        )
        
        logger.info(
            f"TenderContextRetriever: 上下文准备完成 "
            f"total={result.total_chunks}, used={result.used_chunks}, "
            f"text_length={len(result.context_text)}"
        )
        
        return result
    
    def _sort_by_position(self, chunks: List[Any]) -> List[Any]:
        """按文档位置排序chunks"""
        # 假设chunk对象有position属性
        try:
            return sorted(chunks, key=lambda c: getattr(c, 'position', 0))
        except Exception as e:
            logger.warning(f"TenderContextRetriever: 排序失败，保持原顺序: {e}")
            return chunks

