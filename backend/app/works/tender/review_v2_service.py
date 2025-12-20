"""
新审核服务 (v2) - Step 8
基于新检索器的投标文件审核
"""
import json
import logging
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.platform.retrieval.facade import RetrievalFacade
from app.services.embedding_provider_store import get_embedding_store

logger = logging.getLogger(__name__)


def _build_marked_context(chunks: List[Dict[str, Any]]) -> str:
    """构建带标记的上下文（与旧版格式一致）"""
    lines = []
    for idx, chunk in enumerate(chunks):
        chunk_id = chunk.get("chunk_id", "")
        text = chunk.get("text", "")
        lines.append(f"[{idx}] <chunk id=\"{chunk_id}\">\n{text}\n</chunk>")
    return "\n\n".join(lines)


def _extract_json(text: str) -> Any:
    """从 LLM 输出中提取 JSON"""
    text = text.strip()
    
    # 尝试查找 JSON 代码块
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试修复常见问题
        text = text.strip()
        if text.startswith("'"):
            text = text.replace("'", '"')
        return json.loads(text)


class ReviewV2Service:
    """新审核服务 - 使用新检索器"""
    
    # 审核提示词（与旧版一致）
    REVIEW_PROMPT = """你是招投标"投标文件审核员"。你会收到：
1) 招标文件原文片段（带 CHUNK id）
2) 投标文件原文片段（带 CHUNK id）
3) 可选：自定义审核规则文件原文片段（带 CHUNK id，可为空）

请输出严格 JSON 数组：
[
  {
    "dimension": "资格审查",  // 资格审查|报价审查|技术审查|商务审查|工期与质量|文档结构|其他
    "requirement_text": "招标要求（摘要）",
    "response_text": "投标响应（摘要）",
    "result": "pass",  // pass, risk, fail
    "remark": "原因/建议/缺失点/冲突点",
    "rigid": false,  // 是否刚性要求
    "tender_evidence_chunk_ids": ["chunk_xxx"],
    "bid_evidence_chunk_ids": ["chunk_yyy"]
  }
]

规则：
- 结果含义：pass=明确符合；fail=明确不符合；risk=不确定/缺材料/冲突/需要人工确认
- 自定义规则文件（如有）与招标要求"叠加"：也要产出对应的审核项（可合并到同维度）
- evidence_chunk_ids 必须来自上下文 CHUNK id
- 不要输出除 JSON 以外的任何文字
"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None):
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
    
    async def run_review_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        custom_rule_asset_ids: List[str],
        bidder_name: Optional[str],
        bid_asset_ids: List[str],
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        运行审核 (v2)
        
        Returns:
            List[ReviewItem] - 格式与旧版一致
        """
        logger.info(f"ReviewV2: run_review start project_id={project_id}")
        
        # 1. 使用新检索器获取招标文件上下文
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 检索招标文件相关内容（资格、技术、商务要求）
        tender_query = "招标要求 资格要求 技术要求 商务要求 评审标准"
        tender_chunks_objs = await self.retriever.retrieve(
            query=tender_query,
            project_id=project_id,
            doc_types=["tender"],
            embedding_provider=embedding_provider,
            top_k=30,
        )
        
        if not tender_chunks_objs:
            logger.warning(f"ReviewV2: no tender chunks found for project_id={project_id}")
            tender_chunks = []
        else:
            tender_chunks = [
                {
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "meta": c.meta
                }
                for c in tender_chunks_objs
            ]
        
        tender_ctx = _build_marked_context(tender_chunks)
        
        # 2. 使用新检索器获取投标文件上下文
        bid_query = "投标响应 技术方案 商务报价 资格证明"
        bid_chunks_objs = await self.retriever.retrieve(
            query=bid_query,
            project_id=project_id,
            doc_types=["bid"],
            embedding_provider=embedding_provider,
            top_k=30,
        )
        
        if not bid_chunks_objs:
            logger.warning(f"ReviewV2: no bid chunks found for project_id={project_id}")
            bid_chunks = []
        else:
            bid_chunks = [
                {
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "meta": c.meta
                }
                for c in bid_chunks_objs
            ]
        
        bid_ctx = _build_marked_context(bid_chunks)
        
        # 3. 加载自定义规则（如果有）
        # 注意：这里简化处理，实际应该也使用新检索器
        # 但由于自定义规则文件较小，暂时保持为空或后续扩展
        rule_ctx = ""
        # TODO: 如果需要，可以从 custom_rule 资产中检索
        
        # 4. 调用 LLM
        messages = [
            {"role": "system", "content": self.REVIEW_PROMPT.strip()},
            {
                "role": "user",
                "content": f"""招标文件原文片段：
{tender_ctx}

投标文件原文片段：
{bid_ctx}

自定义审核规则文件原文片段（可为空）：
{rule_ctx or "(无)"}""",
            },
        ]
        
        # 使用 model_id 调用 LLM
        out_text = await self._call_llm_v2(messages, model_id)
        arr = _extract_json(out_text)
        
        if not isinstance(arr, list):
            raise ValueError("review v2 output not list")
        
        # 5. 为所有审核项添加 source 字段
        for item in arr:
            if "source" not in item:
                item["source"] = "compare"
            
            # 添加 evidence_spans（基于 meta.page_no）
            tender_evidence_spans = self._generate_evidence_spans(
                tender_chunks,
                item.get("tender_evidence_chunk_ids") or []
            )
            bid_evidence_spans = self._generate_evidence_spans(
                bid_chunks,
                item.get("bid_evidence_chunk_ids") or []
            )
            
            item["tender_evidence_spans"] = tender_evidence_spans
            item["bid_evidence_spans"] = bid_evidence_spans
        
        logger.info(f"ReviewV2: run_review done items={len(arr)}")
        
        return arr
    
    def _generate_evidence_spans(
        self,
        chunks: List[Dict[str, Any]],
        evidence_chunk_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """生成证据 spans（基于 meta.page_no）"""
        spans = []
        chunk_map = {c["chunk_id"]: c for c in chunks}
        
        for chunk_id in evidence_chunk_ids:
            chunk = chunk_map.get(chunk_id)
            if chunk:
                meta = chunk.get("meta") or {}
                span = {
                    "chunk_id": chunk_id,
                    "page_no": meta.get("page_no"),
                    "doc_version_id": meta.get("doc_version_id"),
                    "text_preview": chunk.get("text", "")[:100]  # 前100字符预览
                }
                spans.append(span)
        
        return spans
    
    async def _call_llm_v2(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str]
    ) -> str:
        """调用 LLM（与 TenderService._llm_text 类似的实现）"""
        if not self.llm:
            raise RuntimeError("LLM orchestrator not available")
        
        # 尝试常见的方法名
        for method_name in ("chat", "complete", "generate", "run", "ask"):
            fn = getattr(self.llm, method_name, None)
            if not fn:
                continue
            
            try:
                # 尝试 (messages, model_id) 签名
                res = fn(messages=messages, model_id=model_id)
                
                # 处理返回值
                if isinstance(res, str):
                    return res
                if isinstance(res, dict):
                    # 尝试常见的键
                    for k in ("content", "text", "output"):
                        if k in res and isinstance(res[k], str):
                            return res[k]
                    # OpenAI-like 格式
                    if "choices" in res and res["choices"]:
                        ch = res["choices"][0]
                        if isinstance(ch, dict):
                            msg = ch.get("message")
                            if msg and isinstance(msg, dict):
                                cnt = msg.get("content")
                                if isinstance(cnt, str):
                                    return cnt
                
                raise ValueError(f"LLM returned unexpected format: {type(res)}")
                
            except Exception as e:
                logger.debug(f"LLM method {method_name} failed: {e}")
                continue
        
        raise RuntimeError(f"No compatible LLM method found")

