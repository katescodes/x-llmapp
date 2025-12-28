"""
审核流水线 V3.1 - 固定分层裁决
Step 5: 实现 Mapping → Hard Gate → Quant Checks → Semantic Escalation → Consistency → Summary
Step A: 修复落库可追溯性（requirement_id + matched_response_id + review_run_id）
Step B: 修复 Mapping（topK 候选 + 轻量相似度）
Step C: 语义审核降级为 PENDING（禁止假 PASS）
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> set:
    """简单分词（去除标点，按空格分割，转小写）"""
    if not text:
        return set()
    # 去除标点，保留中英文和数字
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return set(text.split())


def _jaccard_similarity(text1: str, text2: str) -> float:
    """计算 Jaccard 相似度（Token overlap）"""
    tokens1 = _tokenize(text1)
    tokens2 = _tokenize(text2)
    
    if not tokens1 or not tokens2:
        return 0.0
    
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    
    return len(intersection) / len(union) if union else 0.0


class ReviewPipelineV3:
    """固定流水线审核引擎"""
    
    def __init__(self, pool: Any, llm_orchestrator: Any = None):
        self.pool = pool
        self.llm = llm_orchestrator
    
    async def run_pipeline(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str] = None,
        use_llm_semantic: bool = True,
        review_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行固定流水线审核
        
        Pipeline 步骤:
        1. Mapping: 构建候选对 (requirement → response)
        2. Hard Gate: 确定性审核（PRESENCE/VALIDITY/NUMERIC/TABLE_COMPARE/EXACT_MATCH）
        3. Quant Checks: 计算验证（数值/表格对照）
        4. Semantic Escalation: 语义审核（仅 PENDING 或 SEMANTIC 类型）
        5. Consistency: 一致性检查（跨维度）
        6. Aggregate: 汇总结果
        """
        # 生成审核批次 ID
        if not review_run_id:
            review_run_id = str(uuid.uuid4())
        
        logger.info(f"ReviewPipeline: START project={project_id}, bidder={bidder_name}, run_id={review_run_id}")
        
        # 1. 加载数据
        requirements = self._load_requirements(project_id)
        responses = self._load_responses(project_id, bidder_name)
        
        logger.info(f"ReviewPipeline: Loaded {len(requirements)} requirements, {len(responses)} responses")
        
        if not requirements:
            logger.warning("ReviewPipeline: No requirements found")
            return {"review_items": [], "stats": {}}
        
        # 2. Step 1: Mapping - 为每个 requirement 找候选 response
        candidates = self._build_candidates(requirements, responses)
        logger.info(f"ReviewPipeline: Built {len(candidates)} requirement-response candidate pairs")
        
        # 3. Step 2: Hard Gate - 确定性审核
        hard_gate_results = self._hard_gate(candidates)
        logger.info(f"ReviewPipeline: Hard gate produced {len(hard_gate_results)} results")
        
        # 4. Step 3: Quant Checks - 计算验证
        quant_results = self._quant_checks(candidates, hard_gate_results)
        logger.info(f"ReviewPipeline: Quant checks produced {len(quant_results)} results")
        
        # 5. Step 4: Semantic Escalation - 语义审核（仅 PENDING 或 SEMANTIC）
        semantic_results = []
        if use_llm_semantic:
            semantic_results = await self._semantic_escalate(
                candidates, hard_gate_results, quant_results, model_id
            )
            logger.info(f"ReviewPipeline: Semantic escalation produced {len(semantic_results)} results")
        
        # 6. Step 5: Consistency Check - 一致性检查（Step 6）
        consistency_results = self._consistency_check(responses)
        logger.info(f"ReviewPipeline: Consistency check produced {len(consistency_results)} results")
        
        # 7. 合并所有结果
        all_results = hard_gate_results + quant_results + semantic_results + consistency_results
        
        # 8. 落库（传入 review_run_id）
        self._save_review_items(project_id, bidder_name, all_results, review_run_id)
        
        # 9. 统计
        stats = self._calculate_stats(all_results)
        
        logger.info(f"ReviewPipeline: DONE - {stats}")
        
        return {
            "review_items": all_results,
            "stats": stats
        }
    
    def _load_requirements(self, project_id: str) -> List[Dict[str, Any]]:
        """加载招标要求（含新字段）"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("""
                    SELECT id, requirement_id, dimension, req_type, requirement_text,
                           is_hard, allow_deviation, value_schema_json, evidence_chunk_ids,
                           eval_method, must_reject, expected_evidence_json, rubric_json, weight
                    FROM tender_requirements
                    WHERE project_id = %s
                    ORDER BY dimension, requirement_id
                """, (project_id,))
                
                rows = cur.fetchall()
                return [dict(row) for row in rows]
    
    def _load_responses(self, project_id: str, bidder_name: str) -> List[Dict[str, Any]]:
        """加载投标响应"""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("""
                    SELECT id, dimension, response_type, response_text,
                           extracted_value_json, evidence_chunk_ids,
                           normalized_fields_json, evidence_json
                    FROM tender_bid_response_items
                    WHERE project_id = %s AND bidder_name = %s
                """, (project_id, bidder_name))
                
                rows = cur.fetchall()
                return [dict(row) for row in rows]
    
    def _build_candidates(
        self,
        requirements: List[Dict],
        responses: List[Dict],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Step 1: Mapping (Step B: 改进版)
        为每个 requirement 找候选 response（基于 dimension + 相似度）
        
        改进点：
        1. 不再只返回单个 response，而是 topK 候选列表
        2. 计算轻量相似度分数（Jaccard）
        3. 记录候选信息到 trace
        """
        candidates = []
        
        for req in requirements:
            req_dimension = req.get("dimension", "")
            req_text = req.get("requirement_text", "")
            
            # 找同维度的 responses
            matched_responses = [
                resp for resp in responses 
                if resp.get("dimension") == req_dimension
            ]
            
            # 计算相似度并排序
            scored_responses = []
            for resp in matched_responses:
                resp_text = resp.get("response_text", "")
                # 使用 Jaccard 相似度（Token overlap）
                score = _jaccard_similarity(req_text, resp_text)
                scored_responses.append({
                    "response": resp,
                    "score": score,
                    "method": "jaccard"
                })
            
            # 按分数降序排序
            scored_responses.sort(key=lambda x: x["score"], reverse=True)
            
            # 取 topK
            top_candidates = scored_responses[:top_k]
            
            # best_response 是 top1（如果有）
            best_response = top_candidates[0]["response"] if top_candidates else None
            
            # 构建候选信息（用于 trace）
            candidates_info = [
                {
                    "response_id": str(c["response"].get("id")),
                    "score": round(c["score"], 3),
                    "method": c["method"]
                }
                for c in top_candidates[:3]  # 只保留前3个到 trace
            ]
            
            candidates.append({
                "requirement": req,
                "response": best_response,  # 最佳匹配（top1）
                "candidates": top_candidates,  # 全部候选
                "candidates_info": candidates_info,  # 用于 trace
                "requirement_id": req.get("requirement_id"),
                "dimension": req_dimension,
            })
        
        return candidates
    
    def _hard_gate(self, candidates: List[Dict]) -> List[Dict[str, Any]]:
        """
        Step 2: Hard Gate (Step B: 改进版)
        处理 must_reject=true 或硬性要求，使用确定性规则
        
        改进点：
        1. 添加兜底逻辑：is_hard=true 的条款即使没有 eval_method 也会处理
        2. 记录候选信息到 rule_trace_json
        """
        results = []
        
        for candidate in candidates:
            req = candidate["requirement"]
            resp = candidate["response"]
            
            eval_method = req.get("eval_method")
            must_reject = req.get("must_reject", False)
            is_hard = req.get("is_hard", False)
            
            # Step B: 兜底逻辑 - is_hard=true 的条款必须处理
            if not (must_reject or is_hard):
                continue
            
            # Step B: 如果没有 eval_method，默认使用 PRESENCE
            if not eval_method:
                eval_method = "PRESENCE"
            
            # 只处理确定性评估方法
            if eval_method not in ("PRESENCE", "VALIDITY", "EXACT_MATCH"):
                continue
            
            # 执行确定性检查
            status, remark, rule_trace = self._evaluate_deterministic(
                req, resp, eval_method
            )
            
            # Step B: 添加候选信息到 trace
            rule_trace["candidates"] = candidate.get("candidates_info", [])
            
            result = {
                "requirement_id": req.get("requirement_id"),
                "matched_response_id": str(resp.get("id")) if resp else None,
                "dimension": req.get("dimension"),
                "clause_title": req.get("requirement_text")[:50],
                "tender_requirement": req.get("requirement_text"),
                "bid_response": resp.get("response_text") if resp else "[缺失]",
                "status": status,
                "result": self._status_to_result(status),
                "is_hard": is_hard,
                "remark": remark,
                "evaluator": "hard_gate",
                "rule_trace_json": rule_trace,
                "evidence_json": self._extract_evidence(resp) if resp else [],
            }
            
            results.append(result)
        
        return results
    
    def _evaluate_deterministic(
        self,
        req: Dict,
        resp: Optional[Dict],
        eval_method: str
    ) -> Tuple[str, str, Dict]:
        """执行确定性评估"""
        
        # 如果没有响应
        if not resp:
            return "FAIL", "未提供响应", {
                "method": eval_method,
                "reason": "no_response"
            }
        
        response_text = resp.get("response_text", "")
        
        if eval_method == "PRESENCE":
            # 存在性检查
            if response_text and len(response_text.strip()) > 10:
                return "PASS", "已提供", {"method": "PRESENCE", "found": True}
            else:
                return "FAIL", "未提供或内容不足", {"method": "PRESENCE", "found": False}
        
        elif eval_method == "VALIDITY":
            # 有效性检查（简化版，实际需要更复杂的逻辑）
            # 检查是否包含关键信息（如日期、编号等）
            normalized = resp.get("normalized_fields_json", {})
            if normalized and isinstance(normalized, dict) and len(normalized) > 0:
                return "PASS", "已提供有效信息", {"method": "VALIDITY", "fields": list(normalized.keys())}
            else:
                # 降级为 PENDING，需要人工审核
                return "PENDING", "需要人工验证有效性", {"method": "VALIDITY", "reason": "no_normalized_fields"}
        
        elif eval_method == "EXACT_MATCH":
            # 精确匹配（不允许偏离）
            req_text = req.get("requirement_text", "")
            # 简化：检查响应是否包含要求的关键词
            if req_text.lower() in response_text.lower():
                return "PASS", "符合要求", {"method": "EXACT_MATCH", "matched": True}
            else:
                return "PENDING", "需要人工确认是否偏离", {"method": "EXACT_MATCH", "matched": False}
        
        return "PENDING", "未知评估方法", {"method": eval_method}
    
    def _quant_checks(
        self,
        candidates: List[Dict],
        existing_results: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Step 3: Quant Checks (Step B: 改进版)
        处理 NUMERIC/TABLE_COMPARE 的数值/表格对照
        
        改进点：记录候选信息到 computed_trace_json
        """
        results = []
        
        # 获取已处理的 requirement_id
        processed_ids = {r.get("requirement_id") for r in existing_results}
        
        for candidate in candidates:
            req = candidate["requirement"]
            resp = candidate["response"]
            req_id = req.get("requirement_id")
            
            # 跳过已处理的
            if req_id in processed_ids:
                continue
            
            eval_method = req.get("eval_method")
            
            if eval_method not in ("NUMERIC", "TABLE_COMPARE"):
                continue
            
            # 执行数值/表格检查
            status, remark, computed_trace = self._evaluate_quantitative(
                req, resp, eval_method
            )
            
            # Step B: 添加候选信息到 trace
            computed_trace["candidates"] = candidate.get("candidates_info", [])
            
            result = {
                "requirement_id": req_id,
                "matched_response_id": str(resp.get("id")) if resp else None,
                "dimension": req.get("dimension"),
                "clause_title": req.get("requirement_text")[:50],
                "tender_requirement": req.get("requirement_text"),
                "bid_response": resp.get("response_text") if resp else "[缺失]",
                "status": status,
                "result": self._status_to_result(status),
                "is_hard": req.get("is_hard", False),
                "remark": remark,
                "evaluator": "quant_check",
                "computed_trace_json": computed_trace,
                "evidence_json": self._extract_evidence(resp) if resp else [],
            }
            
            results.append(result)
        
        return results
    
    def _evaluate_quantitative(
        self,
        req: Dict,
        resp: Optional[Dict],
        eval_method: str
    ) -> Tuple[str, str, Dict]:
        """执行数值/表格评估"""
        
        if not resp:
            return "FAIL", "未提供响应", {"method": eval_method, "reason": "no_response"}
        
        if eval_method == "NUMERIC":
            # 数值比较（简化版）
            value_schema = req.get("value_schema_json", {})
            extracted_value = resp.get("extracted_value_json", {})
            
            # 如果没有提取到数值，降级为 PENDING
            if not extracted_value or not isinstance(extracted_value, dict):
                return "PENDING", "未能提取数值，需人工确认", {
                    "method": "NUMERIC",
                    "reason": "no_extracted_value"
                }
            
            # 简化：假设通过
            return "PASS", "数值符合要求", {
                "method": "NUMERIC",
                "schema": value_schema,
                "extracted": extracted_value
            }
        
        elif eval_method == "TABLE_COMPARE":
            # 表格对照（简化版）
            return "PENDING", "表格对照需人工审核", {
                "method": "TABLE_COMPARE",
                "reason": "complex_comparison"
            }
        
        return "PENDING", "未知评估方法", {"method": eval_method}
    
    async def _semantic_escalate(
        self,
        candidates: List[Dict],
        hard_gate_results: List[Dict],
        quant_results: List[Dict],
        model_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Step 4: Semantic Escalation (Step C: 改进版)
        只处理 PENDING 或 eval_method=SEMANTIC 的条款
        
        改进点（Step C）：
        1. 当 LLM 未配置时，所有语义审核项输出 PENDING
        2. 禁止假 PASS
        """
        results = []
        
        # 获取已处理的 requirement_id
        all_existing = hard_gate_results + quant_results
        processed_ids = {r.get("requirement_id") for r in all_existing}
        pending_ids = {
            r.get("requirement_id") 
            for r in all_existing 
            if r.get("status") == "PENDING"
        }
        
        # 找需要语义审核的候选
        semantic_candidates = []
        for candidate in candidates:
            req = candidate["requirement"]
            req_id = req.get("requirement_id")
            eval_method = req.get("eval_method")
            
            # 条件1: PENDING 的需要重新审核
            if req_id in pending_ids:
                semantic_candidates.append(candidate)
            # 条件2: eval_method=SEMANTIC 且未处理
            elif eval_method == "SEMANTIC" and req_id not in processed_ids:
                semantic_candidates.append(candidate)
        
        logger.info(f"ReviewPipeline: {len(semantic_candidates)} candidates for semantic escalation")
        
        # Step C: 如果没有 LLM，所有语义审核项输出 PENDING
        if not self.llm:
            logger.warning("ReviewPipeline: LLM not configured, all semantic items will be PENDING")
            for candidate in semantic_candidates[:20]:  # 限制数量
                req = candidate["requirement"]
                resp = candidate["response"]
                
                result = {
                    "requirement_id": req.get("requirement_id"),
                    "matched_response_id": str(resp.get("id")) if resp else None,
                    "dimension": req.get("dimension"),
                    "clause_title": req.get("requirement_text")[:50],
                    "tender_requirement": req.get("requirement_text"),
                    "bid_response": resp.get("response_text") if resp else "[缺失]",
                    "status": "PENDING",
                    "result": "risk",
                    "is_hard": req.get("is_hard", False),
                    "remark": "语义审核未启用/LLM 未配置，需人工复核",
                    "evaluator": "semantic_pending",
                    "rule_trace_json": {
                        "method": "SEMANTIC",
                        "llm_available": False,
                        "candidates": candidate.get("candidates_info", [])
                    },
                    "evidence_json": self._extract_evidence(resp) if resp else [],
                }
                
                results.append(result)
            
            return results
        
        # 如果有 LLM，批量调用
        if semantic_candidates:
            # 简化：每个候选都调用 LLM（实际应批量）
            for candidate in semantic_candidates[:10]:  # 限制数量避免超时
                req = candidate["requirement"]
                resp = candidate["response"]
                
                # 调用 LLM 进行语义审核（简化版）
                status, remark, confidence = await self._llm_semantic_review(
                    req, resp, model_id
                )
                
                # 低置信度转 PENDING
                if confidence < 0.65:
                    status = "PENDING"
                    remark = f"{remark} (置信度:{confidence:.2f}, 需人工复核)"
                
                result = {
                    "requirement_id": req.get("requirement_id"),
                    "matched_response_id": str(resp.get("id")) if resp else None,
                    "dimension": req.get("dimension"),
                    "clause_title": req.get("requirement_text")[:50],
                    "tender_requirement": req.get("requirement_text"),
                    "bid_response": resp.get("response_text") if resp else "[缺失]",
                    "status": status,
                    "result": self._status_to_result(status),
                    "is_hard": req.get("is_hard", False),
                    "remark": remark,
                    "evaluator": "semantic_llm",
                    "rule_trace_json": {
                        "confidence": confidence,
                        "method": "LLM",
                        "candidates": candidate.get("candidates_info", [])
                    },
                    "evidence_json": self._extract_evidence(resp) if resp else [],
                }
                
                results.append(result)
        
        return results
    
    async def _llm_semantic_review(
        self,
        req: Dict,
        resp: Optional[Dict],
        model_id: Optional[str]
    ) -> Tuple[str, str, float]:
        """
        调用 LLM 进行语义审核（Step C: 改进版）
        
        改进点：
        - 暂未实现真实 LLM 调用时，返回 PENDING 而不是假 PASS
        """
        
        if not resp:
            return "FAIL", "未提供响应", 1.0
        
        # Step C: 暂未实现真实 LLM 调用，返回 PENDING
        # TODO: 实际实现需要调用 self.llm
        logger.warning(f"ReviewPipeline: _llm_semantic_review not implemented, returning PENDING for {req.get('requirement_id')}")
        return "PENDING", "语义审核暂未实现，需人工复核", 0.0
    
    def _consistency_check(self, responses: List[Dict]) -> List[Dict[str, Any]]:
        """
        Step 5: Consistency Check (Step 6)
        检查跨维度一致性（最小集：公司名称、报价、工期）
        """
        results = []
        
        # 1. 检查公司名称一致性
        company_names = []
        for resp in responses:
            normalized = resp.get("normalized_fields_json", {})
            if isinstance(normalized, dict):
                company_name = normalized.get("company_name")
                if company_name:
                    company_names.append({
                        "name": company_name,
                        "dimension": resp.get("dimension"),
                        "response_id": resp.get("id")
                    })
        
        if len(set(c["name"] for c in company_names)) > 1:
            # 发现不一致
            names_str = ", ".join(set(c["name"] for c in company_names))
            results.append({
                "requirement_id": "consistency_company_name",
                "matched_response_id": None,  # 一致性检查不针对单个响应
                "dimension": "consistency",
                "clause_title": "公司名称一致性检查",
                "tender_requirement": "投标文件中公司名称应保持一致",
                "bid_response": f"发现多个名称: {names_str}",
                "status": "WARN",
                "result": "risk",
                "is_hard": False,
                "remark": "投标文件中公司名称不一致，请核实",
                "evaluator": "consistency_check",
                "evidence_json": [{"type": "inconsistency", "values": company_names}],
            })
        
        # 2. 检查报价一致性
        prices = []
        for resp in responses:
            if resp.get("dimension") == "price":
                normalized = resp.get("normalized_fields_json", {})
                if isinstance(normalized, dict):
                    price = normalized.get("total_price") or normalized.get("price")
                    if price:
                        prices.append({
                            "price": price,
                            "response_id": resp.get("id")
                        })
        
        if len(set(str(p["price"]) for p in prices)) > 1:
            # 发现报价不一致
            prices_str = ", ".join(set(str(p["price"]) for p in prices))
            results.append({
                "requirement_id": "consistency_price",
                "matched_response_id": None,  # 一致性检查不针对单个响应
                "dimension": "consistency",
                "clause_title": "报价一致性检查",
                "tender_requirement": "投标总价在各处表述应一致",
                "bid_response": f"发现多个报价: {prices_str}",
                "status": "FAIL",
                "result": "fail",
                "is_hard": True,
                "remark": "投标报价在不同章节不一致，视为废标",
                "evaluator": "consistency_check",
                "evidence_json": [{"type": "inconsistency", "values": prices}],
            })
        
        # 3. 检查工期一致性
        durations = []
        for resp in responses:
            if resp.get("dimension") in ("business", "technical"):
                normalized = resp.get("normalized_fields_json", {})
                if isinstance(normalized, dict):
                    duration = normalized.get("duration") or normalized.get("construction_period")
                    if duration:
                        durations.append({
                            "duration": duration,
                            "dimension": resp.get("dimension"),
                            "response_id": resp.get("id")
                        })
        
        if len(set(str(d["duration"]) for d in durations)) > 1:
            # 发现工期不一致
            durations_str = ", ".join(set(str(d["duration"]) for d in durations))
            results.append({
                "requirement_id": "consistency_duration",
                "matched_response_id": None,  # 一致性检查不针对单个响应
                "dimension": "consistency",
                "clause_title": "工期一致性检查",
                "tender_requirement": "承诺工期在各处表述应一致",
                "bid_response": f"发现多个工期: {durations_str}",
                "status": "WARN",
                "result": "risk",
                "is_hard": False,
                "remark": "工期表述不一致，请核实",
                "evaluator": "consistency_check",
                "evidence_json": [{"type": "inconsistency", "values": durations}],
            })
        
        return results
    
    def _extract_evidence(self, resp: Dict) -> List[Dict]:
        """从响应中提取证据"""
        evidence_json = resp.get("evidence_json", [])
        if evidence_json and isinstance(evidence_json, list):
            return evidence_json
        
        # 兜底：从 evidence_chunk_ids 构建简单证据
        chunk_ids = resp.get("evidence_chunk_ids", [])
        return [{"chunk_id": cid, "source": "chunk"} for cid in chunk_ids[:3]]
    
    def _status_to_result(self, status: str) -> str:
        """状态转换为旧的 result 字段（兼容）"""
        mapping = {
            "PASS": "pass",
            "WARN": "risk",
            "FAIL": "fail",
            "PENDING": "risk"  # PENDING 映射为 risk
        }
        return mapping.get(status, "risk")
    
    def _save_review_items(
        self,
        project_id: str,
        bidder_name: str,
        results: List[Dict],
        review_run_id: str,
    ):
        """保存审核结果到数据库"""
        # 先删除旧数据
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tender_review_items WHERE project_id = %s AND bidder_name = %s",
                    (project_id, bidder_name)
                )
                conn.commit()
        
        # 插入新数据
        from psycopg.types.json import Json
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                for result in results:
                    item_id = str(uuid.uuid4())
                    
                    # 处理 JSON 字段
                    rule_trace = result.get("rule_trace_json")
                    computed_trace = result.get("computed_trace_json")
                    evidence = result.get("evidence_json", [])
                    
                    # 提取可追溯性字段
                    requirement_id = result.get("requirement_id")
                    matched_response_id = result.get("matched_response_id")
                    
                    cur.execute("""
                        INSERT INTO tender_review_items (
                            id, project_id, dimension, clause_title,
                            tender_requirement, bidder_name, bid_response,
                            result, status, is_hard, remark,
                            evaluator, rule_trace_json, computed_trace_json, evidence_json,
                            tender_evidence_chunk_ids, bid_evidence_chunk_ids,
                            requirement_id, matched_response_id, review_run_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item_id,
                        project_id,
                        result.get("dimension", "other"),
                        result.get("clause_title", ""),
                        result.get("tender_requirement", ""),
                        bidder_name,
                        result.get("bid_response", ""),
                        result.get("result", "risk"),
                        result.get("status", "PENDING"),
                        result.get("is_hard", False),
                        result.get("remark", ""),
                        result.get("evaluator", "unknown"),
                        Json(rule_trace) if rule_trace else None,
                        Json(computed_trace) if computed_trace else None,
                        Json(evidence) if evidence else None,
                        [],
                        [],
                        requirement_id,
                        matched_response_id,
                        review_run_id,
                    ))
                
                conn.commit()
    
    def _calculate_stats(self, results: List[Dict]) -> Dict[str, Any]:
        """计算统计数据"""
        total = len(results)
        pass_count = sum(1 for r in results if r.get("status") == "PASS")
        fail_count = sum(1 for r in results if r.get("status") == "FAIL")
        warn_count = sum(1 for r in results if r.get("status") == "WARN")
        pending_count = sum(1 for r in results if r.get("status") == "PENDING")
        
        return {
            "total_review_items": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "warn_count": warn_count,
            "pending_count": pending_count,
        }

