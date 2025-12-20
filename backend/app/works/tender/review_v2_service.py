"""
新审核服务 (v2) - 配置化驱动
基于新检索器+spec+prompt的投标文件审核，带MUST_HIT兜底
"""
import json
import logging
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool

from app.platform.retrieval.facade import RetrievalFacade
from app.services.embedding_provider_store import get_embedding_store
from app.works.tender.extraction_specs.review_v2 import (
    build_review_spec,
    get_must_hit_rules,
)

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
    """新审核服务 - spec+prompt驱动"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None):
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
        
        # 加载spec（queries、prompt、topk等）
        self.spec = build_review_spec()
    
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
        运行审核 (v2) - spec驱动
        
        Returns:
            List[ReviewItem] - 格式与旧版一致，但强制包含MUST_HIT规则
        """
        logger.info(f"ReviewV2: run_review start project_id={project_id}")
        
        # 1. 使用spec中的queries和doc_types进行检索
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 合并所有queries为一个检索query（简化版）
        combined_query = " ".join(self.spec.queries.values())
        
        # 检索招标文件+投标文件（spec中的doc_types）
        all_chunks_objs = await self.retriever.retrieve(
            query=combined_query,
            project_id=project_id,
            doc_types=self.spec.doc_types,  # ["tender", "bid"]
            embedding_provider=embedding_provider,
            top_k=self.spec.topk,
        )
        
        # 按doc_type分组
        tender_chunks = []
        bid_chunks = []
        for c in all_chunks_objs:
            chunk_dict = {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "meta": c.meta
            }
            doc_type = c.meta.get("doc_type") if c.meta else None
            if doc_type == "tender":
                tender_chunks.append(chunk_dict)
            elif doc_type == "bid":
                bid_chunks.append(chunk_dict)
        
        logger.info(f"ReviewV2: retrieved {len(tender_chunks)} tender chunks, {len(bid_chunks)} bid chunks")
        
        tender_ctx = _build_marked_context(tender_chunks)
        bid_ctx = _build_marked_context(bid_chunks)
        
        # 2. 使用spec中的prompt调用LLM
        prompt = self.spec.prompt
        
        # 构建完整的用户消息（prompt + 上下文）
        user_content = f"""{prompt}

---

招标文件原文片段：
{tender_ctx or "(无)"}

---

投标文件原文片段：
{bid_ctx or "(无)"}
"""
        
        messages = [
            {"role": "user", "content": user_content},
        ]
        
        # 调用 LLM
        out_text = await self._call_llm_v2(messages, model_id)
        
        # 解析LLM输出
        try:
            parsed = _extract_json(out_text)
            if isinstance(parsed, dict) and "data" in parsed:
                # 新格式：{"data": {"review_items": [...]}, "evidence_chunk_ids": [...]}
                review_items = parsed.get("data", {}).get("review_items", [])
            elif isinstance(parsed, list):
                # 旧格式：直接是数组（兼容）
                review_items = parsed
            else:
                raise ValueError(f"Unexpected review output format: {type(parsed)}")
        except Exception as e:
            logger.error(f"Failed to parse review output: {e}")
            review_items = []
        
        # 3. 强制添加MUST_HIT规则（兜底）
        review_items = self._ensure_must_hit_rules(review_items, tender_chunks, bid_chunks)
        
        # 4. 转换为旧格式（tender_review_items表兼容）
        arr = self._convert_to_legacy_format(review_items, tender_chunks, bid_chunks)
        
        logger.info(f"ReviewV2: run_review done items={len(arr)}")
        
        return arr
    
    def _ensure_must_hit_rules(
        self,
        review_items: List[Dict[str, Any]],
        tender_chunks: List[Dict[str, Any]],
        bid_chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        确保review_items中包含MUST_HIT规则（兜底）
        
        如果LLM已经产出了这些规则，则不重复添加
        如果LLM没产出，则强制添加
        """
        must_hit_rules = get_must_hit_rules()
        
        # 检查已存在的rule_id
        existing_rule_ids = {item.get("rule_id") for item in review_items if item.get("rule_id")}
        
        # 添加缺失的MUST_HIT规则
        for rule in must_hit_rules:
            if rule["rule_id"] not in existing_rule_ids:
                # 构造一个最小化的review_item
                must_hit_item = {
                    "rule_id": rule["rule_id"],
                    "title": rule["title"],
                    "severity": rule["severity"],
                    "description": rule["description"],
                    "evidence_chunk_ids": [],  # 兜底规则无具体证据
                }
                review_items.append(must_hit_item)
                logger.info(f"Added MUST_HIT rule: {rule['rule_id']}")
        
        return review_items
    
    def _convert_to_legacy_format(
        self,
        review_items: List[Dict[str, Any]],
        tender_chunks: List[Dict[str, Any]],
        bid_chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        将新格式的review_items转换为旧格式（tender_review_items表）
        
        新格式：{rule_id, title, severity, description, evidence_chunk_ids, suggestion}
        旧格式：{dimension, requirement_text, response_text, result, remark, rigid, tender_evidence_chunk_ids, bid_evidence_chunk_ids, source, tender_evidence_spans, bid_evidence_spans}
        """
        arr = []
        
        for item in review_items:
            # 映射severity -> result
            severity = item.get("severity", "info")
            if severity == "error":
                result = "fail"
                rigid = True
            elif severity == "warning":
                result = "risk"
                rigid = False
            else:  # info
                result = "pass"
                rigid = False
            
            # 映射rule_id -> dimension
            rule_id = item.get("rule_id", "")
            if "TECH" in rule_id or "技术" in item.get("title", ""):
                dimension = "技术审查"
            elif "BIZ" in rule_id or "商务" in item.get("title", ""):
                dimension = "商务审查"
            elif "DOC" in rule_id or "文档" in item.get("title", ""):
                dimension = "文档结构"
            elif "QUAL" in rule_id or "资格" in item.get("title", ""):
                dimension = "资格审查"
            else:
                dimension = "其他"
            
            # 构造旧格式
            legacy_item = {
                "dimension": dimension,
                "requirement_text": item.get("title", ""),
                "response_text": item.get("description", ""),
                "result": result,
                "remark": item.get("suggestion", "") or item.get("description", ""),
                "rigid": rigid,
                "tender_evidence_chunk_ids": [],
                "bid_evidence_chunk_ids": item.get("evidence_chunk_ids", []),
                "source": "compare",
                "tender_evidence_spans": [],
                "bid_evidence_spans": self._generate_evidence_spans(
                    bid_chunks,
                    item.get("evidence_chunk_ids", [])
                ),
            }
            
            arr.append(legacy_item)
        
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

