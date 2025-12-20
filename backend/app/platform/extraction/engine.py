"""
Extraction Engine
通用抽取引擎
"""
import logging
import os
from typing import Any, Dict, List, Optional, Union

from .context import build_marked_context
from .json_utils import extract_json, repair_json
from .llm_adapter import call_llm
from .types import ExtractionSpec, ExtractionResult, RetrievalTrace, RetrievedChunk

logger = logging.getLogger(__name__)


class ExtractionEngine:
    """
    通用抽取引擎
    
    负责：
    - 根据 spec 执行检索
    - 构建上下文
    - 调用 LLM
    - 解析和修复 JSON
    - 生成追踪信息
    """
    
    async def run(
        self,
        spec: ExtractionSpec,
        retriever: Any,
        llm: Any,
        project_id: str,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        embedding_provider: Optional[str] = None,
    ) -> ExtractionResult:
        """
        执行抽取任务
        
        Args:
            spec: 抽取规格
            retriever: 检索器（RetrievalFacade）
            llm: LLM 编排器
            project_id: 项目 ID
            model_id: 模型 ID
            run_id: 运行 ID（用于追踪）
            embedding_provider: 嵌入提供者
            
        Returns:
            ExtractionResult: 抽取结果
        """
        import time
        trace_enabled = os.getenv("EXTRACT_TRACE_ENABLED", "true").lower() in ("true", "1", "yes")
        mode = os.getenv("EXTRACT_MODE", "unknown")
        
        # 使用 print 确保能看到输出
        print(f"[DEBUG ExtractionEngine] START project_id={project_id} llm_type={type(llm).__name__ if llm else 'None'} llm_is_none={llm is None}")
        logger.info(f"[ExtractionEngine] START project_id={project_id} run_id={run_id} mode={mode} llm={type(llm).__name__ if llm else 'None'}")
        overall_start = time.time()
        
        # 1. 执行检索
        retrieval_start = time.time()
        all_chunks, query_trace = await self._retrieve_chunks(
            spec=spec,
            retriever=retriever,
            project_id=project_id,
            embedding_provider=embedding_provider,
            trace_enabled=trace_enabled,
            run_id=run_id,
            mode=mode,
        )
        retrieval_ms = int((time.time() - retrieval_start) * 1000)
        logger.info(f"[ExtractionEngine] AFTER_RETRIEVAL project_id={project_id} run_id={run_id} count={len(all_chunks)} ms={retrieval_ms}")
        
        if not all_chunks:
            logger.warning(f"[ExtractionEngine] NO_CHUNKS project_id={project_id} run_id={run_id}")
            trace = self._build_trace(query_trace, spec, 0, trace_enabled)
            return ExtractionResult(
                data={},
                evidence_chunk_ids=[],
                evidence_spans=[],
                raw_model_output="",
                retrieval_trace=trace
            )
        
        # 2. 构建上下文
        ctx_start = time.time()
        chunk_dicts = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "meta": c.meta
            }
            for c in all_chunks
        ]
        ctx = build_marked_context(chunk_dicts)
        ctx_ms = int((time.time() - ctx_start) * 1000)
        
        # 3. 调用 LLM
        messages = [
            {"role": "system", "content": spec.prompt.strip()},
            {"role": "user", "content": f"招标文件原文片段：\n{ctx}"},
        ]
        
        prompt_len = len(spec.prompt)
        ctx_len = len(ctx)
        logger.info(f"[ExtractionEngine] BEFORE_LLM project_id={project_id} run_id={run_id} prompt_len={prompt_len} ctx_len={ctx_len}")
        
        llm_start = time.time()
        
        try:
            print(f"[DEBUG] About to call LLM: llm={llm} llm_type={type(llm).__name__ if llm else 'None'}")
            
            # 确保 max_tokens 足够大（至少 4096）
            out_text = await call_llm(
                messages,
                llm,
                model_id,
                temperature=spec.temperature,
                max_tokens=4096
            )
            
            llm_ms = int((time.time() - llm_start) * 1000)
            out_len = len(out_text) if out_text else 0
            
            print(f"[DEBUG] LLM returned: out_len={out_len}")
            if out_text:
                print(f"[DEBUG] LLM output preview: {out_text[:200]}")
            
            logger.info(
                f"[ExtractionEngine] AFTER_LLM project_id={project_id} run_id={run_id} "
                f"ms={llm_ms} out_len={out_len} mode={mode}"
            )
            
        except Exception as llm_error:
            llm_ms = int((time.time() - llm_start) * 1000)
            error_type = type(llm_error).__name__
            error_msg = str(llm_error)
            
            # 立刻落日志证据（包含所有关键信息）
            logger.error(
                f"[ExtractionEngine] LLM_CALL_FAILED project_id={project_id} run_id={run_id}\n"
                f"  mode={mode}\n"
                f"  task_type={spec.__class__.__name__ if hasattr(spec, '__class__') else 'unknown'}\n"
                f"  model_id={model_id or 'default'}\n"
                f"  llm_type={type(llm).__name__ if llm else 'None'}\n"
                f"  timeout_ms={llm_ms}\n"
                f"  temperature={spec.temperature}\n"
                f"  prompt_len={prompt_len}\n"
                f"  ctx_len={ctx_len}\n"
                f"  error_type={error_type}\n"
                f"  error_msg={error_msg}\n"
                f"  payload_preview={{messages_count={len(messages)}, first_msg_len={len(messages[0]['content']) if messages else 0}}}"
            )
            
            # 打印 payload（去敏）
            payload_safe = {
                "messages_count": len(messages),
                "system_prompt_len": len(messages[0]["content"]) if len(messages) > 0 else 0,
                "user_content_len": len(messages[1]["content"]) if len(messages) > 1 else 0,
                "temperature": spec.temperature,
                "max_tokens": 4096,
            }
            logger.error(f"[ExtractionEngine] LLM_PAYLOAD_SAFE: {payload_safe}")
            
            # 重新抛出异常，让上层处理
            raise RuntimeError(
                f"LLM call failed for project_id={project_id} run_id={run_id}: {error_type}: {error_msg}"
            ) from llm_error
        
        # 4. 解析 JSON
        parse_start = time.time()
        try:
            obj = extract_json(out_text)
            logger.info(f"[ExtractionEngine] JSON_PARSED project_id={project_id} obj_type={type(obj).__name__} obj_keys={list(obj.keys()) if isinstance(obj, dict) else 'NOT_DICT'}")
        except Exception as e:
            logger.warning(f"ExtractionEngine: extract_json failed, trying repair: {e}")
            logger.warning(f"  out_text preview: {out_text[:500] if out_text else 'EMPTY'}")
            try:
                obj = repair_json(out_text)
                logger.info(f"[ExtractionEngine] JSON_REPAIRED project_id={project_id} obj_type={type(obj).__name__}")
            except Exception as e2:
                logger.error(f"ExtractionEngine: repair_json also failed: {e2}")
                logger.error(f"  out_text preview: {out_text[:500] if out_text else 'EMPTY'}")
                obj = {}
        
        parse_ms = int((time.time() - parse_start) * 1000)
        
        # 5. 提取数据和证据
        # 处理两种格式：dict（project-info）或 list（risks）
        if isinstance(obj, dict):
            data = obj.get("data") or obj
            evidence_chunk_ids = obj.get("evidence_chunk_ids") or []
            logger.info(
                f"[ExtractionEngine] EXTRACT_DATA project_id={project_id} "
                f"obj_has_data_key={'data' in obj} "
                f"data_type={type(data).__name__} "
                f"data_keys={list(data.keys()) if isinstance(data, dict) else 'NOT_DICT'} "
                f"data_len={len(data) if data else 0}"
            )
        elif isinstance(obj, list):
            # risks等返回list，每个元素可能有自己的evidence_chunk_ids
            data = obj
            # 收集所有evidence_chunk_ids
            evidence_chunk_ids = []
            for item in obj:
                if isinstance(item, dict):
                    item_evidence = item.get("evidence_chunk_ids") or []
                    evidence_chunk_ids.extend(item_evidence)
        else:
            logger.warning(f"ExtractionEngine: unexpected obj type {type(obj)}")
            data = obj
            evidence_chunk_ids = []
        
        # 6. 生成 evidence_spans
        evidence_spans = self._generate_evidence_spans(all_chunks, evidence_chunk_ids)
        
        # 7. 构建追踪信息
        trace = self._build_trace(query_trace, spec, len(all_chunks), trace_enabled)
        
        logger.info(f"[ExtractionEngine] AFTER_PARSE project_id={project_id} run_id={run_id} ms={parse_ms} evidence_count={len(evidence_chunk_ids)}")
        
        overall_ms = int((time.time() - overall_start) * 1000)
        logger.info(
            f"[ExtractionEngine] DONE project_id={project_id} run_id={run_id} mode={mode} "
            f"total_ms={overall_ms} chunks={len(all_chunks)} evidence={len(evidence_chunk_ids)}"
        )
        
        return ExtractionResult(
            data=data,
            evidence_chunk_ids=evidence_chunk_ids,
            evidence_spans=evidence_spans,
            raw_model_output=out_text,
            retrieval_trace=trace
        )
    
    async def _retrieve_chunks(
        self,
        spec: ExtractionSpec,
        retriever: Any,
        project_id: str,
        embedding_provider: Optional[str],
        trace_enabled: bool,
        run_id: Optional[str] = None,
        mode: str = "unknown",
    ) -> tuple[List[RetrievedChunk], Dict[str, Any]]:
        """
        执行检索（支持单查询、多查询列表、多查询字典）
        
        Returns:
            (chunks, query_trace)
        """
        import time
        queries = spec.queries
        
        # 归一化查询为字典格式
        if isinstance(queries, str):
            queries_dict = {"default": queries}
        elif isinstance(queries, list):
            queries_dict = {f"query_{i}": q for i, q in enumerate(queries)}
        else:
            queries_dict = queries
        
        all_chunks = []
        chunk_id_set = set()
        query_trace = {}
        
        for query_name, query_text in queries_dict.items():
            try:
                logger.info(f"[ExtractionEngine] BEFORE_RETRIEVAL project_id={project_id} run_id={run_id} query_name={query_name} query_text={query_text[:100]} top_k={spec.topk_per_query}")
                
                query_start = time.time()
                query_chunks = await retriever.retrieve(
                    query=query_text,
                    project_id=project_id,
                    doc_types=spec.doc_types,
                    embedding_provider=embedding_provider,
                    top_k=spec.topk_per_query,
                )
                query_ms = int((time.time() - query_start) * 1000)
                
                logger.info(f"[ExtractionEngine] AFTER_RETRIEVAL_QUERY project_id={project_id} run_id={run_id} query_name={query_name} count={len(query_chunks)} ms={query_ms}")
                
                query_trace[query_name] = {
                    "query": query_text if trace_enabled else None,
                    "retrieved_count": len(query_chunks),
                    "top_ids": [c.chunk_id for c in query_chunks[:5]] if trace_enabled else []
                }
                
                # 去重合并
                for chunk_obj in query_chunks:
                    # 转换为 RetrievedChunk（如果不是）
                    if not isinstance(chunk_obj, RetrievedChunk):
                        chunk = RetrievedChunk(
                            chunk_id=chunk_obj.chunk_id,
                            text=chunk_obj.text,
                            meta=chunk_obj.meta if hasattr(chunk_obj, 'meta') else {},
                            score=chunk_obj.score if hasattr(chunk_obj, 'score') else None
                        )
                    else:
                        chunk = chunk_obj
                    
                    if chunk.chunk_id not in chunk_id_set:
                        chunk_id_set.add(chunk.chunk_id)
                        all_chunks.append(chunk)
                
                logger.info(f"  Query '{query_name}': retrieved {len(query_chunks)} chunks")
                
            except Exception as e:
                logger.warning(f"  Query '{query_name}' failed: {e}")
                query_trace[query_name] = {"error": str(e), "retrieved_count": 0}
        
        # 截断到总量限制
        if len(all_chunks) > spec.topk_total:
            all_chunks = all_chunks[:spec.topk_total]
        
        return all_chunks, query_trace
    
    def _generate_evidence_spans(
        self,
        chunks: List[RetrievedChunk],
        evidence_chunk_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        生成 evidence_spans（基于 meta.page_no）
        
        Returns:
            [
                {
                    "source": "doc_version_id",
                    "page_no": 5,
                    "snippet": "证据片段..."
                }
            ]
        """
        spans = []
        chunk_map = {c.chunk_id: c for c in chunks}
        
        for chunk_id in evidence_chunk_ids:
            chunk = chunk_map.get(chunk_id)
            if not chunk:
                continue
            
            meta = chunk.meta or {}
            page_no = meta.get("page_no") or meta.get("chunk_position", 0)
            doc_version_id = meta.get("doc_version_id", "")
            
            spans.append({
                "source": doc_version_id,
                "page_no": page_no,
                "snippet": chunk.text[:200]  # 只取前 200 字符作为片段
            })
        
        return spans
    
    def _build_trace(
        self,
        query_trace: Dict[str, Any],
        spec: ExtractionSpec,
        retrieved_count_total: int,
        trace_enabled: bool
    ) -> Optional[RetrievalTrace]:
        """构建追踪信息"""
        if not trace_enabled:
            return None
        
        # 判断检索策略
        if isinstance(spec.queries, str):
            strategy = "single_query"
        elif isinstance(spec.queries, (list, dict)):
            strategy = "multi_query"
        else:
            strategy = "unknown"
        
        return RetrievalTrace(
            retrieval_provider="new",
            retrieval_strategy=strategy,
            queries=query_trace,
            top_k_per_query=spec.topk_per_query,
            top_k_total=spec.topk_total,
            retrieved_count_total=retrieved_count_total,
            doc_types=spec.doc_types,
        )


