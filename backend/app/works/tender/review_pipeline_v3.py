"""
审核流水线 V3.1 - 固定分层裁决
Step 5: 实现 Mapping → Hard Gate → Quant Checks → Semantic Escalation → Consistency → Summary
Step A: 修复落库可追溯性（requirement_id + matched_response_id + review_run_id）
Step B: 修复 Mapping（topK 候选 + 轻量相似度）
Step C: 语义审核降级为 PENDING（禁止假 PASS）
Step D: NUMERIC 真实比较（从 schema/文本解析阈值）
Step E: Consistency 归一化+阈值
Step F: 统一 evidence_json 结构（role=tender/bid + 批量预取）
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


# ==================== Step D: 辅助函数 ====================

def _extract_number(text: str) -> Optional[float]:
    """从文本中提取数值"""
    if not text:
        return None
    
    # 移除常见单位和空格
    text = re.sub(r'[元天月年日个人台套%]', '', text)
    text = text.strip()
    
    # 匹配数字（支持小数）
    match = re.search(r'[-+]?\d*\.?\d+', text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _parse_threshold_from_text(text: str) -> Dict[str, Optional[float]]:
    """
    从文本中解析阈值（Step D）
    支持格式:
    - 不少于XX天/月/年
    - 不超过XX元
    - ≥XX, ≤XX, >XX, <XX
    - XX-YY之间
    """
    result = {"min": None, "max": None, "exact": None}
    
    if not text:
        return result
    
    # 1. "不少于XX"、"≥XX"、">XX"
    patterns_min = [
        r'不少于\s*(\d+\.?\d*)',
        r'大于等于\s*(\d+\.?\d*)',
        r'[≥>=]\s*(\d+\.?\d*)',
        r'最少\s*(\d+\.?\d*)',
        r'至少\s*(\d+\.?\d*)',
    ]
    
    for pattern in patterns_min:
        match = re.search(pattern, text)
        if match:
            result["min"] = float(match.group(1))
            break
    
    # 2. "不超过XX"、"≤XX"、"<XX"
    patterns_max = [
        r'不超过\s*(\d+\.?\d*)',
        r'小于等于\s*(\d+\.?\d*)',
        r'[≤<=]\s*(\d+\.?\d*)',
        r'最多\s*(\d+\.?\d*)',
    ]
    
    for pattern in patterns_max:
        match = re.search(pattern, text)
        if match:
            result["max"] = float(match.group(1))
            break
    
    # 3. "XX-YY之间"、"XX至YY"
    range_patterns = [
        r'(\d+\.?\d*)\s*[-~至]\s*(\d+\.?\d*)',
    ]
    
    for pattern in range_patterns:
        match = re.search(pattern, text)
        if match:
            result["min"] = float(match.group(1))
            result["max"] = float(match.group(2))
            break
    
    # 4. "XX天"、"XX元"（精确值）
    if not result["min"] and not result["max"]:
        exact_match = re.search(r'(\d+\.?\d*)\s*[天月年元]', text)
        if exact_match:
            result["exact"] = float(exact_match.group(1))
    
    return result


# Step E: 归一化函数
def normalize_money(value: Union[str, int, float]) -> Optional[int]:
    """
    归一化金额为"分"（Step E）
    支持: "1000元", "10万元", "1.5万", "￥1000", "1,000"
    """
    if value is None:
        return None
    
    if isinstance(value, (int, float)):
        return int(value * 100)  # 假设输入是元
    
    text = str(value)
    
    # 移除货币符号和空格
    text = re.sub(r'[￥¥$,，\s]', '', text)
    
    # 处理"万"
    if '万' in text:
        num_str = text.replace('万', '').replace('元', '')
        try:
            num = float(num_str)
            return int(num * 10000 * 100)  # 万元转分
        except ValueError:
            return None
    
    # 处理"元"
    if '元' in text:
        num_str = text.replace('元', '')
        try:
            num = float(num_str)
            return int(num * 100)  # 元转分
        except ValueError:
            return None
    
    # 纯数字（假设是元）
    try:
        num = float(text)
        return int(num * 100)
    except ValueError:
        return None


def normalize_duration(value: Union[str, int, float]) -> Optional[int]:
    """
    归一化工期为"天"（Step E）
    支持: "30天", "3个月", "1年", "90"
    """
    if value is None:
        return None
    
    if isinstance(value, (int, float)):
        return int(value)  # 假设输入是天
    
    text = str(value)
    
    # 处理"年"
    if '年' in text:
        num_str = re.search(r'(\d+\.?\d*)', text)
        if num_str:
            return int(float(num_str.group(1)) * 365)
    
    # 处理"月"
    if '月' in text:
        num_str = re.search(r'(\d+\.?\d*)', text)
        if num_str:
            return int(float(num_str.group(1)) * 30)
    
    # 处理"天"或纯数字
    num_str = re.search(r'(\d+\.?\d*)', text)
    if num_str:
        return int(float(num_str.group(1)))
    
    return None


def normalize_company_name(value: str) -> str:
    """
    归一化公司名称（Step E）
    - 去除空格
    - 全角转半角
    - 统一大小写
    """
    if not value:
        return ""
    
    # 全角转半角
    result = []
    for char in value:
        code = ord(char)
        if code == 0x3000:  # 全角空格
            code = 0x0020
        elif 0xFF01 <= code <= 0xFF5E:  # 全角字符
            code -= 0xFEE0
        result.append(chr(code))
    
    text = ''.join(result)
    
    # 去除空格并转小写
    text = text.replace(' ', '').replace('\t', '').replace('\n', '')
    text = text.lower()
    
    return text


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
    
    def _is_process_clause(self, text: str) -> bool:
        """
        目标A: 判断是否为过程性/现场性条款
        
        这类条款不应进入审核流程，而是直接标记为 PENDING + out_of_scope
        
        关键词包括：
        - 开标/评标相关：开标、评标、签到、报到、回避、询问
        - 现场相关：现场、启封、封条、封口、密封
        - 递交相关：送达、递交、收标地点、投标截止、开标时启封
        - 规则相关：不足3家、不得开标、电讯形式
        """
        if not text:
            return False
        
        # 过程性/现场性关键词
        process_keywords = [
            "开标", "评标", "现场", "签到", "报到", "回避", 
            "询问", "启封", "封条", "封口", "密封", "送达", 
            "递交", "收标地点", "不足3家", "不得开标", 
            "电讯形式", "投标截止", "开标时启封"
        ]
        
        # 统计命中的关键词数量
        hits = sum(1 for kw in process_keywords if kw in text)
        
        # 命中任意关键词即判定为过程性条款
        return hits > 0
    
    def _make_out_of_scope_item(self, req: Dict) -> Dict:
        """
        目标A: 为过程性条款生成 PENDING 结果
        
        标记 evaluator="out_of_scope" + rule_trace_json.scope="PROCESS"
        """
        return {
            "requirement_id": req.get("requirement_id"),
            "matched_response_id": None,
            "dimension": req.get("dimension", "other"),
            "clause_title": req.get("requirement_text", "")[:50],
            "tender_requirement": req.get("requirement_text", ""),
            "bid_response": "[过程性条款,不适用审核]",
            "status": "PENDING",
            "result": "risk",
            "is_hard": False,
            "remark": "过程性/现场性条款,不在本次审核范围内,需人工确认",
            "evaluator": "out_of_scope",
            "rule_trace_json": {
                "scope": "PROCESS",
                "reason": "process_or_onsite_clause",
                "method": "keyword_match"
            },
            "evidence_json": [],
            "tender_evidence_chunk_ids": req.get("evidence_chunk_ids", []),
            "bid_evidence_chunk_ids": [],
        }
    
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
        all_requirements = self._load_requirements(project_id)
        responses = self._load_responses(project_id, bidder_name)
        
        logger.info(f"ReviewPipeline: Loaded {len(all_requirements)} requirements, {len(responses)} responses")
        
        if not all_requirements:
            logger.warning("ReviewPipeline: No requirements found")
            return {"review_items": [], "stats": {}}
        
        # 目标A: 分流过程性条款 (不进入 HardGate/Quant/Semantic)
        process_reqs = [r for r in all_requirements if self._is_process_clause(r.get("requirement_text", ""))]
        requirements = [r for r in all_requirements if not self._is_process_clause(r.get("requirement_text", ""))]
        
        logger.info(f"ReviewPipeline: Filtered {len(process_reqs)} process clauses, {len(requirements)} for review")
        
        # 为过程性条款生成 out_of_scope 结果
        out_of_scope_results = [self._make_out_of_scope_item(r) for r in process_reqs]
        
        # Step F1: 批量预取 doc_segments
        all_segment_ids = self._collect_all_segment_ids(requirements, responses)
        seg_map = self._prefetch_doc_segments(list(all_segment_ids))
        
        # 2. Step 1: Mapping - 为每个 requirement 找候选 response
        candidates = self._build_candidates(requirements, responses)
        logger.info(f"ReviewPipeline: Built {len(candidates)} requirement-response candidate pairs")
        
        # 3. Step 2: Hard Gate - 确定性审核
        hard_gate_results = self._hard_gate(candidates, seg_map)
        logger.info(f"ReviewPipeline: Hard gate produced {len(hard_gate_results)} results")
        
        # 4. Step 3: Quant Checks - 计算验证
        quant_results = self._quant_checks(candidates, hard_gate_results, seg_map)
        logger.info(f"ReviewPipeline: Quant checks produced {len(quant_results)} results")
        
        # 5. Step 4: Semantic Escalation - 语义审核（仅 PENDING 或 SEMANTIC）
        semantic_results = []
        if use_llm_semantic:
            semantic_results = await self._semantic_escalate(
                candidates, hard_gate_results, quant_results, model_id, seg_map
            )
            logger.info(f"ReviewPipeline: Semantic escalation produced {len(semantic_results)} results")
        
        # 6. Step 5: Consistency Check - 一致性检查（Step 6）
        consistency_results = self._consistency_check(responses)
        logger.info(f"ReviewPipeline: Consistency check produced {len(consistency_results)} results")
        
        # 7. 合并所有结果（目标A: 加入 out_of_scope_results）
        all_results = out_of_scope_results + hard_gate_results + quant_results + semantic_results + consistency_results
        
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
    
    # ==================== Step F1: 批量预取 doc_segments ====================
    
    def _collect_all_segment_ids(
        self,
        requirements: List[Dict],
        responses: List[Dict]
    ) -> set:
        """
        Step F1: 收集所有需要查询的 segment_id
        
        从 requirements 和 responses 中收集所有 evidence_chunk_ids
        """
        segment_ids = set()
        
        # 从 requirements 收集
        for req in requirements:
            chunk_ids = req.get("evidence_chunk_ids") or []
            if chunk_ids:
                segment_ids.update(str(cid) for cid in chunk_ids if cid)
        
        # 从 responses 收集
        for resp in responses:
            # 1. evidence_chunk_ids
            chunk_ids = resp.get("evidence_chunk_ids") or []
            if chunk_ids:
                segment_ids.update(str(cid) for cid in chunk_ids if cid)
            
            # 2. evidence_json 中的 segment_id
            evidence_json = resp.get("evidence_json") or []
            if isinstance(evidence_json, list):
                for ev in evidence_json:
                    if isinstance(ev, dict) and ev.get("segment_id"):
                        segment_ids.add(str(ev["segment_id"]))
        
        # 过滤空字符串
        segment_ids.discard("")
        segment_ids.discard(None)
        
        return segment_ids
    
    def _prefetch_doc_segments(self, segment_ids: List[str]) -> Dict[str, Dict]:
        """
        Step F1: 批量预取 doc_segments
        
        Args:
            segment_ids: segment ID 列表
        
        Returns:
            Dict[segment_id, row_dict] 映射
        """
        if not segment_ids:
            return {}
        
        seg_map = {}
        
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # 使用 ANY 避免 IN 拼接
                cur.execute("""
                    SELECT 
                        id as segment_id,
                        doc_version_id,
                        content_text,
                        page_start,
                        page_end,
                        heading_path,
                        segment_type,
                        segment_no,
                        meta_json
                    FROM doc_segments
                    WHERE id = ANY(%s)
                """, (segment_ids,))
                
                rows = cur.fetchall()
                for row in rows:
                    seg_map[row["segment_id"]] = dict(row)
        
        logger.info(f"ReviewPipeline: Prefetched {len(seg_map)}/{len(segment_ids)} doc_segments")
        return seg_map
    
    # ==================== Step F2: Evidence 组装工具 ====================
    
    def _make_quote(self, text: str, limit: int = 220) -> str:
        """截取并清理空白"""
        if not text:
            return ""
        
        # 压缩连续空白为单空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 超长加省略号
        if len(text) > limit:
            return text[:limit] + "..."
        
        return text
    
    def _build_evidence_entries(
        self,
        role: str,
        segment_ids: List[str],
        seg_map: Dict[str, Dict],
        source: str = "doc_segments"
    ) -> List[Dict]:
        """
        Step F2: 从 segment_ids 构建统一 evidence 结构
        
        Args:
            role: "tender" or "bid"
            segment_ids: segment ID 列表
            seg_map: 预取的 segments 映射
            source: "doc_segments" or "fallback_chunk"
        
        Returns:
            List of evidence dicts with role, segment_id, page_start, quote, etc.
        """
        evidence_entries = []
        
        # 最多取前 5 个
        for seg_id in segment_ids[:5]:
            seg = seg_map.get(seg_id)
            
            if seg:
                # 从 seg_map 找到，组装完整信息
                evidence_entries.append({
                    "role": role,
                    "segment_id": seg_id,
                    "asset_id": seg.get("doc_version_id"),  # 用 doc_version_id 作为 asset_id
                    "page_start": seg.get("page_start"),
                    "page_end": seg.get("page_end"),
                    "heading_path": seg.get("heading_path"),
                    "quote": self._make_quote(seg.get("content_text", "")),
                    "source": source,
                })
            else:
                # 找不到，输出 fallback
                evidence_entries.append({
                    "role": role,
                    "segment_id": seg_id,
                    "asset_id": None,
                    "page_start": None,
                    "page_end": None,
                    "heading_path": None,
                    "quote": None,
                    "source": "fallback_chunk",
                })
        
        return evidence_entries
    
    def _normalize_existing_evidence(
        self,
        role: str,
        evidence_json: List[Dict],
        seg_map: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Step F2: 规范化已存在的 evidence_json
        
        对 response.evidence_json 中的条目：
        - 补上 role
        - 如果缺 quote/page_start 但有 segment_id，用 seg_map 补齐
        """
        normalized = []
        
        for ev in evidence_json[:5]:  # 最多取前 5
            if not isinstance(ev, dict):
                continue
            
            # 补上 role
            if "role" not in ev:
                ev["role"] = role
            
            # 如果有 segment_id 但缺信息，用 seg_map 补齐
            seg_id = ev.get("segment_id")
            if seg_id and seg_id in seg_map:
                seg = seg_map[seg_id]
                
                if not ev.get("quote"):
                    ev["quote"] = self._make_quote(seg.get("content_text", ""))
                
                if not ev.get("page_start"):
                    ev["page_start"] = seg.get("page_start")
                    ev["page_end"] = seg.get("page_end")
                
                if not ev.get("heading_path"):
                    ev["heading_path"] = seg.get("heading_path")
                
                if not ev.get("asset_id"):
                    ev["asset_id"] = seg.get("doc_version_id")
                
                if not ev.get("source"):
                    ev["source"] = "doc_segments"
            
            normalized.append(ev)
        
        return normalized
    
    def _merge_tender_bid_evidence(
        self,
        req: Dict,
        resp: Optional[Dict],
        seg_map: Dict[str, Dict]
    ) -> Tuple[List[Dict], List[str], List[str]]:
        """
        Step F2: 合并 tender 和 bid 的 evidence
        
        Returns:
            (evidence_json, tender_ids, bid_ids)
        """
        # 1. Tender evidence (from requirement)
        tender_ids = req.get("evidence_chunk_ids") or []
        tender_evs = self._build_evidence_entries("tender", tender_ids, seg_map)
        
        # 2. Bid evidence (from response)
        bid_evs = []
        bid_ids = []
        
        if resp:
            # 优先：如果 resp.evidence_json 非空，规范化它
            existing_evidence = resp.get("evidence_json") or []
            if isinstance(existing_evidence, list) and existing_evidence:
                bid_evs = self._normalize_existing_evidence("bid", existing_evidence, seg_map)
                # 从 evidence_json 提取 segment_ids
                bid_ids = [ev.get("segment_id") for ev in existing_evidence if ev.get("segment_id")]
            else:
                # 兜底：使用 evidence_chunk_ids
                bid_ids = resp.get("evidence_chunk_ids") or []
                bid_evs = self._build_evidence_entries("bid", bid_ids, seg_map)
        
        # 3. 合并
        evidence_json = tender_evs + bid_evs
        
        return evidence_json, tender_ids, bid_ids
    
    def _mapping_score(self, req: Dict, resp: Dict) -> int:
        """
        目标B+Step3: 轻量打分 - 关键词匹配 + normalized_fields 优先级
        
        改进（Step 3）：
        - 如果 requirement 期望特定 normalized_keys（如 total_price_cny, duration_days, warranty_months）
        - 且 response 的 normalized_fields_json 含这些 key → 得分直接 +100
        - 这样 NUMERIC/VALIDITY/PRESENCE 类条款能优先匹配到有结构化字段的 response
        
        关键词词表（极轻量版）：
        - 保证金相关：保证金、投标保证金
        - 价格相关：报价、投标总价、预算、最高限价
        - 资质相关：授权书、法定代表人、身份证、营业执照、统一社会信用代码、资质、业绩
        - 签字盖章：盖章、公章、签字、签章
        - 文档相关：目录、页码
        - 工期相关：工期、交付、验收、质保、售后、付款
        """
        req_text = req.get("requirement_text", "")
        if not req_text:
            return 0
        
        score = 0
        
        # ✅ Step 3: normalized_fields 命中优先级（超高权重）
        expected_evidence_json = req.get("expected_evidence_json", {})
        if isinstance(expected_evidence_json, dict):
            normalized_keys = expected_evidence_json.get("normalized_keys", [])
            if normalized_keys:
                resp_normalized = resp.get("normalized_fields_json", {})
                if isinstance(resp_normalized, dict):
                    # 检查期望的 key 是否在 response 的 normalized_fields 中
                    for key in normalized_keys:
                        if key in resp_normalized and resp_normalized[key] is not None:
                            # 命中一个关键字段 +100 分（远超关键词权重）
                            score += 100
                            logger.debug(
                                f"ReviewPipeline: Mapping boost for req={req.get('requirement_id')}, "
                                f"matched normalized_key={key}"
                            )
        
        # 关键词词表
        keywords = [
            # 保证金
            "保证金", "投标保证金",
            # 价格
            "报价", "投标总价", "预算", "最高限价", "报价单", "控制价",
            # 资质/证件
            "授权书", "法定代表人", "身份证", "营业执照", "统一社会信用代码", 
            "资质", "业绩", "证书", "许可证", "认证",
            # 签字盖章
            "盖章", "公章", "签字", "签章", "法人章",
            # 文档
            "目录", "页码",
            # 工期/服务
            "工期", "交付", "验收", "质保", "售后", "付款", "服务期"
        ]
        
        # 提取 response 文本
        resp_text = resp.get("response_text", "")
        
        # 也搜索 normalized_fields_json (转为字符串)
        normalized_fields = resp.get("normalized_fields_json", {})
        if isinstance(normalized_fields, dict):
            import json
            resp_text += " " + json.dumps(normalized_fields, ensure_ascii=False)
        
        # 统计关键词命中数
        for kw in keywords:
            if kw in req_text and kw in resp_text:
                score += 1
        
        return score
    
    def _build_candidates(
        self,
        requirements: List[Dict],
        responses: List[Dict],
        top_k: int = 5,
        keyword_threshold: int = 1  # 目标B: 关键词打分阈值
    ) -> List[Dict[str, Any]]:
        """
        Step 1: Mapping (Step 4: norm_key 优先 + 轻量打分 + 阈值拒配)
        为每个 requirement 找候选 response
        
        优先级（Step 4）：
        1. **norm_key 精确匹配优先**：
           - 若 requirement.value_schema_json.norm_key 存在
           - 在 responses 中找 normalized_fields_json._norm_key == norm_key 的候选
           - 若找不到，response=None（不要乱配）
        2. 否则：轻量打分（dimension + 关键词 + Jaccard相似度）
        3. 若最佳分数 < 阈值 → response=None
        """
        candidates = []
        
        for req in requirements:
            req_dimension = req.get("dimension", "")
            req_text = req.get("requirement_text", "")
            
            # ✅ Step 4: norm_key 精确匹配优先
            value_schema = req.get("value_schema_json")
            req_norm_key = None
            if isinstance(value_schema, dict):
                req_norm_key = value_schema.get("norm_key")
            
            # 如果requirement有norm_key，尝试精确匹配
            if req_norm_key:
                norm_key_candidates = [
                    resp for resp in responses
                    if resp.get("dimension") == req_dimension
                    and isinstance(resp.get("normalized_fields_json"), dict)
                    and resp["normalized_fields_json"].get("_norm_key") == req_norm_key
                ]
                
                if norm_key_candidates:
                    # 找到norm_key匹配的候选，直接使用（优先级最高）
                    logger.info(
                        f"ReviewPipeline: Requirement {req.get('requirement_id')} matched by norm_key={req_norm_key}, "
                        f"found {len(norm_key_candidates)} candidate(s)"
                    )
                    # 即使找到多个，也用简单的分数排序
                    scored_responses = []
                    for resp in norm_key_candidates:
                        # 给norm_key匹配的候选一个基础高分
                        base_score = 1000
                        # 加上文本相似度作为次要排序
                        resp_text = resp.get("response_text", "")
                        jaccard_score = _jaccard_similarity(req_text, resp_text)
                        combined_score = base_score + jaccard_score
                        
                        scored_responses.append({
                            "response": resp,
                            "score": combined_score,
                            "keyword_score": 0,
                            "jaccard_score": jaccard_score,
                            "method": "norm_key_exact"
                        })
                    
                    scored_responses.sort(key=lambda x: x["score"], reverse=True)
                    best_resp = scored_responses[0]["response"] if scored_responses else None
                    
                    candidates.append({
                        "requirement": req,
                        "candidates": scored_responses[:top_k],
                        "best_response": best_resp
                    })
                    continue
                else:
                    # 找不到norm_key匹配的候选，标记为None（不要乱配）
                    logger.warning(
                        f"ReviewPipeline: Requirement {req.get('requirement_id')} expects norm_key={req_norm_key}, "
                        f"but no matching response found. Setting response=None."
                    )
                    candidates.append({
                        "requirement": req,
                        "candidates": [],
                        "best_response": None
                    })
                    continue
            
            # 没有norm_key，使用传统匹配（轻量打分）
            # 找同维度的 responses
            matched_responses = [
                resp for resp in responses 
                if resp.get("dimension") == req_dimension
            ]
            
            # 计算相似度并排序（目标B: 同时用 Jaccard + 关键词打分）
            scored_responses = []
            for resp in matched_responses:
                resp_text = resp.get("response_text", "")
                
                # 1. Jaccard 相似度（Token overlap）
                jaccard_score = _jaccard_similarity(req_text, resp_text)
                
                # 2. Step3: 关键词匹配打分 + normalized_fields 优先级
                keyword_score = self._mapping_score(req, resp)
                
                # 3. 综合分数（关键词权重更高，normalized_fields 权重最高）
                combined_score = keyword_score * 10 + jaccard_score
                
                scored_responses.append({
                    "response": resp,
                    "score": combined_score,
                    "keyword_score": keyword_score,
                    "jaccard_score": jaccard_score,
                    "method": "keyword_jaccard"
                })
            
            # 按分数降序排序
            scored_responses.sort(key=lambda x: x["score"], reverse=True)
            
            # 取 topK
            top_candidates = scored_responses[:top_k]
            
            # 目标B: 若最佳分数的关键词打分 < 阈值 → best_response=None（不要硬配）
            best_response = None
            if top_candidates:
                best_candidate = top_candidates[0]
                if best_candidate["keyword_score"] >= keyword_threshold:
                    best_response = best_candidate["response"]
                else:
                    # 关键词打分不足，不匹配
                    logger.debug(
                        f"ReviewPipeline: Mapping rejected for req={req.get('requirement_id')}, "
                        f"best_keyword_score={best_candidate['keyword_score']} < {keyword_threshold}"
                    )
            
            # 构建候选信息（用于 trace）
            candidates_info = [
                {
                    "response_id": str(c["response"].get("id")),
                    "score": round(c["score"], 3),
                    "keyword_score": c["keyword_score"],
                    "jaccard_score": round(c["jaccard_score"], 3),
                    "method": c["method"]
                }
                for c in top_candidates[:3]  # 只保留前3个到 trace
            ]
            
            candidates.append({
                "requirement": req,
                "best_response": best_response,  # ✅ 统一使用best_response
                "candidates": top_candidates,  # 全部候选
                "candidates_info": candidates_info,  # 用于 trace
                "requirement_id": req.get("requirement_id"),
                "dimension": req_dimension,
            })
        
        return candidates
    
    def _hard_gate(self, candidates: List[Dict], seg_map: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """
        Step 2: Hard Gate (Step 5: 基于可验证键 + Step F: 统一 evidence)
        处理 must_reject=true 或硬性要求，使用确定性规则
        
        改进点（Step 5）：
        1. PRESENCE 仅用于 doc_*_present 这类 norm_key
        2. 找不到响应：
           - is_hard=true → PENDING（先别直接FAIL，避免抽取失败导致误杀）
           - is_hard=false → PENDING
        3. Step F: 使用统一 evidence_json 结构（role=tender/bid）
        """
        results = []
        
        for candidate in candidates:
            req = candidate["requirement"]
            resp = candidate.get("best_response")  # 注意：可能为None
            
            eval_method = req.get("eval_method")
            must_reject = req.get("must_reject", False)
            is_hard = req.get("is_hard", False)
            
            # Step 5: 只处理硬性条款
            if not (must_reject or is_hard):
                continue
            
            # Step 5: 如果找不到响应，标记为PENDING（不要直接FAIL）
            if not resp:
                status = "PENDING"
                remark = "未找到可比对响应（可能是抽取失败或norm_key不匹配），需人工复核"
                rule_trace = {
                    "eval_method": eval_method or "UNKNOWN",
                    "reason": "no_response_found",
                    "is_hard": is_hard,
                    "must_reject": must_reject
                }
                
                evidence_json, tender_ids, bid_ids = self._merge_tender_bid_evidence(req, None, seg_map)
                
                result = {
                    "requirement_id": req.get("requirement_id"),
                    "matched_response_id": None,
                    "dimension": req.get("dimension"),
                    "clause_title": req.get("requirement_text")[:50],
                    "tender_requirement": req.get("requirement_text"),
                    "bid_response": "[缺失]",
                    "status": status,
                    "result": self._status_to_result(status),
                    "is_hard": is_hard,
                    "remark": remark,
                    "evaluator": "hard_gate",
                    "rule_trace_json": rule_trace,
                    "evidence_json": evidence_json,
                    "tender_evidence_chunk_ids": tender_ids,
                    "bid_evidence_chunk_ids": bid_ids,
                }
                results.append(result)
                continue
            
            # Step 5: 如果没有 eval_method，默认使用 PRESENCE
            if not eval_method:
                eval_method = "PRESENCE"
            
            # Step 5: 只处理确定性评估方法（PRESENCE仅用于doc_*_present）
            if eval_method not in ("PRESENCE", "VALIDITY", "EXACT_MATCH"):
                continue
            
            # 执行确定性检查
            status, remark, rule_trace = self._evaluate_deterministic(
                req, resp, eval_method
            )
            
            # Step B: 添加候选信息到 trace
            rule_trace["candidates"] = candidate.get("candidates_info", [])
            
            # Step F: 统一 evidence_json 结构
            evidence_json, tender_ids, bid_ids = self._merge_tender_bid_evidence(req, resp, seg_map)
            
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
                "evidence_json": evidence_json,
                "tender_evidence_chunk_ids": tender_ids,
                "bid_evidence_chunk_ids": bid_ids,
            }
            
            results.append(result)
        
        return results
    
    def _evaluate_deterministic(
        self,
        req: Dict,
        resp: Optional[Dict],
        eval_method: str
    ) -> Tuple[str, str, Dict]:
        """
        执行确定性评估
        
        目标C: PRESENCE 不再"长度>10就PASS"
        改为：必须命中材料关键词（与目标B使用同一词表）
        """
        
        # 如果没有响应
        if not resp:
            return "FAIL", "未提供响应", {
                "method": eval_method,
                "reason": "no_response"
            }
        
        response_text = resp.get("response_text", "")
        
        if eval_method == "PRESENCE":
            # 目标C: 存在性检查 - 改为关键词命中验证
            
            # 1. 从 requirement_text 提取材料关键词（使用目标B的词表）
            req_text = req.get("requirement_text", "")
            material_keywords = [
                "保证金", "投标保证金",
                "报价", "投标总价", "预算", "最高限价", "报价单",
                "授权书", "法定代表人", "身份证", "营业执照", "统一社会信用代码", 
                "资质", "业绩", "证书", "许可证", "认证",
                "盖章", "公章", "签字", "签章", "法人章",
                "目录", "页码",
                "工期", "交付", "验收", "质保", "售后", "付款", "服务期"
            ]
            
            # 2. 找到 requirement 中出现的关键词
            req_keywords = [kw for kw in material_keywords if kw in req_text]
            
            # 3. 如果 requirement 没有任何可识别关键词 → PENDING（无法验证）
            if not req_keywords:
                return "PENDING", "无法识别材料类型,需人工验证", {
                    "method": "PRESENCE",
                    "reason": "no_identifiable_keywords",
                    "req_keywords": []
                }
            
            # 4. 检查 response 中是否命中关键词
            matched_keywords = [kw for kw in req_keywords if kw in response_text]
            
            # 5. 判断逻辑
            if matched_keywords:
                # 命中 ≥1 → PASS
                return "PASS", f"已提供（命中关键词: {', '.join(matched_keywords[:3])}）", {
                    "method": "PRESENCE",
                    "found": True,
                    "req_keywords": req_keywords,
                    "matched_keywords": matched_keywords
                }
            else:
                # 命中不了 → PENDING（目标C: 极小改动版先用 PENDING 更保守）
                if len(response_text.strip()) > 10:
                    # 有内容但关键词不匹配
                    return "PENDING", f"内容不明确,未命中预期关键词({', '.join(req_keywords[:3])}),需人工验证", {
                        "method": "PRESENCE",
                        "found": False,
                        "req_keywords": req_keywords,
                        "matched_keywords": [],
                        "has_content": True
                    }
                else:
                    # 内容不足
                    return "FAIL", "未提供或内容不足", {
                        "method": "PRESENCE",
                        "found": False,
                        "req_keywords": req_keywords,
                        "matched_keywords": [],
                        "has_content": False
                    }
        
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
        existing_results: List[Dict],
        seg_map: Dict[str, Dict]
    ) -> List[Dict[str, Any]]:
        """
        Step 3: Quant Checks (Step B: 改进版, Step F: 统一 evidence)
        处理 NUMERIC/TABLE_COMPARE 的数值/表格对照
        
        改进点：
        - 记录候选信息到 computed_trace_json
        - Step F: 使用统一 evidence_json 结构
        """
        results = []
        
        # 获取已处理的 requirement_id
        processed_ids = {r.get("requirement_id") for r in existing_results}
        
        for candidate in candidates:
            req = candidate["requirement"]
            resp = candidate.get("best_response")  # ✅ 统一使用best_response
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
            
            # Step F: 统一 evidence_json 结构
            evidence_json, tender_ids, bid_ids = self._merge_tender_bid_evidence(req, resp, seg_map)
            
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
                "evidence_json": evidence_json,
                "tender_evidence_chunk_ids": tender_ids,
                "bid_evidence_chunk_ids": bid_ids,
            }
            
            results.append(result)
        
        return results
    
    def _evaluate_quantitative(
        self,
        req: Dict,
        resp: Optional[Dict],
        eval_method: str
    ) -> Tuple[str, str, Dict]:
        """
        执行数值/表格评估（Step 5: 基于norm_key的精确比对）
        
        改进点（Step 5）：
        1. 若 requirement.value_schema_json.norm_key 存在 且 response.normalized_fields_json._norm_key 匹配
           → 直接从 normalized_fields_json[对应字段] 取值（最可靠）
        2. 否则从 extracted_value_json 取数值（兜底）
        3. 从 value_schema_json 读取阈值
        4. 从 requirement_text 解析阈值（兜底）
        5. 真实比较并记录完整过程
        6. 无法解析 → PENDING（不要假 PASS）
        """
        
        if not resp:
            return "PENDING", "未提供响应，需人工复核", {"method": eval_method, "reason": "no_response"}
        
        if eval_method == "NUMERIC":
            # Step 5: 真实数值比较（基于norm_key）
            value_schema = req.get("value_schema_json", {})
            extracted_value = resp.get("extracted_value_json", {})
            normalized_fields = resp.get("normalized_fields_json", {})
            requirement_text = req.get("requirement_text", "")
            
            # 1. 从 schema 获取阈值和norm_key
            required_min = value_schema.get("minimum") or value_schema.get("min") if isinstance(value_schema, dict) else None
            required_max = value_schema.get("maximum") or value_schema.get("max") if isinstance(value_schema, dict) else None
            required_const = value_schema.get("const") if isinstance(value_schema, dict) else None
            req_norm_key = value_schema.get("norm_key") if isinstance(value_schema, dict) else None
            
            # 2. 如果 schema 没有阈值，从 requirement_text 解析
            if required_min is None and required_max is None and required_const is None:
                thresholds = _parse_threshold_from_text(requirement_text)
                required_min = thresholds.get("min")
                required_max = thresholds.get("max")
                required_const = thresholds.get("exact")
            
            # 3. Step 5: 从 normalized_fields_json 优先获取实际值（通过norm_key）
            actual_value = None
            value_source = "unknown"
            
            if req_norm_key and isinstance(normalized_fields, dict):
                # 优先：通过norm_key直接获取（去掉_norm_key后缀，获取实际字段）
                # 例如：norm_key="price_upper_limit_cny"，实际字段可能是"total_price_cny"
                # 或者直接用norm_key作为字段名
                norm_key_map = {
                    "price_upper_limit_cny": "total_price_cny",
                    "duration_days": "duration_days",
                    "warranty_months": "warranty_months",
                    "bid_security_amount_cny": "bid_security_amount_cny",
                }
                
                # 尝试从映射表获取对应的response字段
                resp_field = norm_key_map.get(req_norm_key, req_norm_key)
                if resp_field in normalized_fields and normalized_fields[resp_field] is not None:
                    actual_value = normalized_fields[resp_field]
                    value_source = f"normalized_fields.{resp_field}"
                    logger.debug(
                        f"ReviewPipeline: Quantitative check using norm_key={req_norm_key}, "
                        f"got value={actual_value} from {value_source}"
                    )
            
            # 兜底：从 extracted_value 获取实际值
            if actual_value is None and isinstance(extracted_value, dict):
                # 尝试多个可能的键
                for key in ["value", "number", "amount", "days", "months", "duration"]:
                    if key in extracted_value:
                        actual_value = _extract_number(str(extracted_value[key]))
                        if actual_value is not None:
                            value_source = f"extracted_value.{key}"
                            break
            
            # 最后兜底：从 response_text 提取
            if actual_value is None:
                response_text = resp.get("response_text", "")
                actual_value = _extract_number(response_text)
                if actual_value is not None:
                    value_source = "response_text_parsed"
            
            # 4. 构建 trace (Step 5: 增加norm_key和value_source)
            computed_trace = {
                "method": "NUMERIC",
                "req_norm_key": req_norm_key,
                "required_min": required_min,
                "required_max": required_max,
                "required_const": required_const,
                "extracted_value": actual_value,
                "value_source": value_source,
                "threshold_source": "schema" if value_schema else "text_parse",
            }
            
            # 5. 判断逻辑
            # 如果无法提取数值 → PENDING
            if actual_value is None:
                computed_trace["reason"] = "cannot_extract_value"
                return "PENDING", "未能提取数值，需人工确认", computed_trace
            
            # 如果没有阈值 → PENDING
            if required_min is None and required_max is None and required_const is None:
                computed_trace["reason"] = "no_threshold"
                return "PENDING", "未找到阈值要求，需人工确认", computed_trace
            
            # 精确匹配
            if required_const is not None:
                if abs(actual_value - required_const) < 0.01:  # 浮点数容差
                    computed_trace["pass"] = True
                    return "PASS", f"数值符合要求（{actual_value} = {required_const}）", computed_trace
                else:
                    computed_trace["pass"] = False
                    return "FAIL", f"数值不符（实际:{actual_value}, 要求:{required_const}）", computed_trace
            
            # 范围检查
            pass_check = True
            reasons = []
            
            if required_min is not None and actual_value < required_min:
                pass_check = False
                reasons.append(f"低于最小值（{actual_value} < {required_min}）")
            
            if required_max is not None and actual_value > required_max:
                pass_check = False
                reasons.append(f"超过最大值（{actual_value} > {required_max}）")
            
            computed_trace["pass"] = pass_check
            
            if pass_check:
                return "PASS", f"数值符合要求（{actual_value}）", computed_trace
            else:
                return "FAIL", "; ".join(reasons), computed_trace
        
        elif eval_method == "TABLE_COMPARE":
            # Step D: 表格对照（暂时仍为 PENDING，实际需要更复杂逻辑）
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
        model_id: Optional[str],
        seg_map: Dict[str, Dict]
    ) -> List[Dict[str, Any]]:
        """
        Step 4: Semantic Escalation (Step C: 改进版, Step F: 统一 evidence)
        只处理 PENDING 或 eval_method=SEMANTIC 的条款
        
        改进点（Step C）：
        1. 当 LLM 未配置时，所有语义审核项输出 PENDING
        2. 禁止假 PASS
        
        Step F: 使用统一 evidence_json 结构
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
                resp = candidate.get("best_response")  # ✅ 统一使用best_response
                
                # Step F: 统一 evidence_json 结构
                evidence_json, tender_ids, bid_ids = self._merge_tender_bid_evidence(req, resp, seg_map)
                
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
                    "evidence_json": evidence_json,
                    "tender_evidence_chunk_ids": tender_ids,
                    "bid_evidence_chunk_ids": bid_ids,
                }
                
                results.append(result)
            
            return results
        
        # 如果有 LLM，批量调用
        if semantic_candidates:
            # 简化：每个候选都调用 LLM（实际应批量）
            for candidate in semantic_candidates[:10]:  # 限制数量避免超时
                req = candidate["requirement"]
                resp = candidate.get("best_response")  # ✅ 统一使用best_response
                
                # 调用 LLM 进行语义审核（简化版）
                status, remark, confidence = await self._llm_semantic_review(
                    req, resp, model_id
                )
                
                # 低置信度转 PENDING
                if confidence < 0.65:
                    status = "PENDING"
                    remark = f"{remark} (置信度:{confidence:.2f}, 需人工复核)"
                
                # Step F: 统一 evidence_json 结构
                evidence_json, tender_ids, bid_ids = self._merge_tender_bid_evidence(req, resp, seg_map)
                
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
                    "evidence_json": evidence_json,
                    "tender_evidence_chunk_ids": tender_ids,
                    "bid_evidence_chunk_ids": bid_ids,
                }
                
                results.append(result)
        
        return results
    
    def _requirement_to_question(self, req: Dict) -> str:
        """
        将招标要求转换为问题
        
        策略：
        - 资格类: "投标人是否具备/提供了 XXX？"
        - 技术类: "投标人的 XXX 是否满足 YYY？"
        - 商务类: "投标人的 XXX 条款是否满足要求？"
        - 数值类: "投标人的 XXX 是多少？"
        - 其他: 直接用原文
        """
        req_text = req.get("requirement_text", "")
        dimension = req.get("dimension", "")
        eval_method = req.get("eval_method", "")
        
        # 如果是数值类，问具体数值
        if eval_method == "NUMERIC":
            # 提取关键词
            if "价格" in req_text or "报价" in req_text:
                return f"投标人的投标报价是多少？要求：{req_text}"
            elif "工期" in req_text or "期限" in req_text:
                return f"投标人承诺的工期是多少天？要求：{req_text}"
            elif "质保" in req_text or "保修" in req_text:
                return f"投标人承诺的质保期是多少个月？要求：{req_text}"
            else:
                return f"投标人提供的数值是多少？要求：{req_text}"
        
        # 资格类：是否具备/提供
        if dimension in ["qualification", "资格"]:
            if "营业执照" in req_text:
                return f"投标人是否提供了有效的营业执照？要求：{req_text}"
            elif "资质" in req_text or "证书" in req_text:
                return f"投标人是否提供了所需的资质证书？要求：{req_text}"
            elif "授权" in req_text:
                return f"投标人是否提供了有效的授权文件？要求：{req_text}"
            else:
                return f"投标人是否满足以下资格要求：{req_text}"
        
        # 技术类：是否满足
        if dimension in ["technical", "技术"]:
            return f"投标人的技术方案是否满足以下要求：{req_text}"
        
        # 商务类：条款是否满足
        if dimension in ["business", "商务"]:
            return f"投标人的商务条款是否满足以下要求：{req_text}"
        
        # 其他：直接用原文
        return f"{req_text}"
    
    async def _qa_based_verification(
        self,
        req: Dict,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str] = None
    ) -> Tuple[str, str, float, List[Dict[str, Any]]]:
        """
        基于问答的验证（QA-based Verification）
        
        流程：
        1. 将requirement转换为question
        2. 使用RAG检索相关投标文档段落
        3. 调用LLM进行问答和符合性判断
        4. 返回结果和证据
        
        Returns:
            (status, remark, confidence, evidence_list)
            status: PASS/WARN/FAIL/PENDING
            remark: 判断理由
            confidence: 置信度 0.0-1.0
            evidence_list: 证据列表 [{"page_start", "quote", "heading_path"}]
        """
        from app.platform.retrieval.facade import RetrievalFacade
        
        # Step 1: 转换为问题
        question = self._requirement_to_question(req)
        
        logger.info(f"QA Verification: req_id={req.get('requirement_id')}, question={question[:100]}")
        
        # Step 2: 检索投标文档相关段落
        try:
            retrieval_facade = RetrievalFacade(self.pool)
            
            # 根据requirement的dimension决定检索范围
            dimension = req.get("dimension", "")
            doc_types = ["bid"]  # 只检索投标文档
            
            # 执行检索（top_k=10，获取更多候选）
            retrieved_chunks = await retrieval_facade.retrieve(
                query=question,
                project_id=project_id,
                doc_types=doc_types,
                top_k=10,
            )
            
            logger.info(f"QA Verification: Retrieved {len(retrieved_chunks)} chunks for req_id={req.get('requirement_id')}")
            
            # 转换为contexts（文本列表）
            contexts = []
            evidence_list = []
            
            for chunk in retrieved_chunks[:8]:  # 限制最多8个context（避免token过多）
                # 从meta中获取元数据
                meta = getattr(chunk, 'meta', {}) or {}
                page_start = meta.get('page_start') or meta.get('page_no')
                page_end = meta.get('page_end')
                heading_path = meta.get('heading_path', '')
                
                context_text = f"[页码: {page_start or '?'}]\n{chunk.text}"
                contexts.append(context_text)
                
                # 构造evidence结构
                evidence_list.append({
                    "role": "bid",
                    "page_start": page_start,
                    "page_end": page_end,
                    "heading_path": heading_path,
                    "quote": chunk.text[:300] if chunk.text else "",  # 限制长度
                    "segment_id": chunk.chunk_id,  # 使用chunk_id作为segment_id
                })
            
            if not contexts:
                logger.warning(f"QA Verification: No relevant context found for req_id={req.get('requirement_id')}")
                return "PENDING", "未检索到相关投标文档内容，需人工复核", 0.0, []
            
        except Exception as e:
            logger.error(f"QA Verification: Retrieval failed for req_id={req.get('requirement_id')}: {e}")
            return "PENDING", f"检索失败: {str(e)}", 0.0, []
        
        # Step 3: LLM判断
        if not self.llm:
            logger.warning(f"QA Verification: LLM not configured, returning PENDING")
            return "PENDING", f"QA验证-已检索到{len(contexts)}个相关段落，LLM未配置", 0.0, evidence_list
        
        try:
            # 构造prompt
            req_text = req.get("requirement_text", "")
            eval_method = req.get("eval_method", "")
            is_hard = req.get("is_hard", False)
            
            # 构造上下文
            context_str = "\n\n---\n\n".join(contexts)
            
            prompt = f"""你是一个专业的招投标审核专家。请基于提供的投标文档内容，判断投标人是否满足以下招标要求。

**招标要求**：
{req_text}

**投标文档相关内容**：
{context_str}

**判断标准**：
- 如果投标文档明确满足要求：回答"满足"
- 如果投标文档明确不满足要求：回答"不满足"
- 如果投标文档信息不足或模糊：回答"不确定"

**回答要求**：
1. 判断结果：[满足/不满足/不确定]
2. 理由：简要说明判断依据（1-2句话）
3. 置信度：[高/中/低]

请严格按照以下JSON格式输出：
{{
  "result": "满足|不满足|不确定",
  "reason": "判断理由",
  "confidence": "高|中|低"
}}
"""
            
            messages = [{"role": "user", "content": prompt}]
            
            # 调用LLM
            llm_response = self.llm.chat(
                messages=messages,
                model_id=model_id,
                temperature=0.3,  # 低温度，提高一致性
                max_tokens=500,    # 限制输出长度
            )
            
            # 解析LLM响应
            content = llm_response["choices"][0]["message"]["content"].strip()
            
            # 尝试解析JSON
            import json
            try:
                # 提取JSON部分（可能包含markdown代码块）
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                parsed = json.loads(content)
                result = parsed.get("result", "不确定")
                reason = parsed.get("reason", "LLM未返回原因")
                confidence_str = parsed.get("confidence", "中")
                
            except Exception as e:
                logger.warning(f"QA Verification: Failed to parse LLM JSON response: {e}, content: {content[:200]}")
                # 回退：简单文本解析
                if "满足" in content and "不满足" not in content:
                    result = "满足"
                elif "不满足" in content:
                    result = "不满足"
                else:
                    result = "不确定"
                reason = content[:200]  # 限制长度
                confidence_str = "中"
            
            # 映射到status
            if result == "满足":
                status = "PASS"
                confidence = 0.9 if confidence_str == "高" else (0.7 if confidence_str == "中" else 0.5)
            elif result == "不满足":
                status = "FAIL" if is_hard else "WARN"
                confidence = 0.9 if confidence_str == "高" else (0.7 if confidence_str == "中" else 0.5)
            else:  # 不确定
                status = "PENDING"
                confidence = 0.0
            
            remark = f"QA验证：{result}。{reason}"
            
            logger.info(f"QA Verification: req_id={req.get('requirement_id')}, status={status}, confidence={confidence}")
            
            return status, remark, confidence, evidence_list
            
        except Exception as e:
            logger.error(f"QA Verification: LLM judgment failed for req_id={req.get('requirement_id')}: {e}")
            import traceback
            traceback.print_exc()
            return "PENDING", f"LLM判断失败: {str(e)}", 0.0, evidence_list
    
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
        Step 5: Consistency Check (Step E: 改进版)
        检查跨维度一致性（最小集：公司名称、报价、工期）
        
        改进点（Step E）:
        1. 使用归一化函数处理数值
        2. 添加阈值判断（报价: 0.5%）
        3. 可降级（PENDING/WARN）而不是直接 FAIL
        """
        results = []
        
        # 1. 检查公司名称一致性
        company_names = []
        for resp in responses:
            normalized_fields = resp.get("normalized_fields_json", {})
            if isinstance(normalized_fields, dict):
                company_name = normalized_fields.get("company_name")
                if company_name:
                    # Step E: 归一化公司名称
                    normalized = normalize_company_name(company_name)
                    company_names.append({
                        "original": company_name,
                        "normalized": normalized,
                        "dimension": resp.get("dimension"),
                        "response_id": resp.get("id")
                    })
        
        # 检查归一化后的名称是否一致
        if company_names:
            unique_normalized = set(c["normalized"] for c in company_names)
            if len(unique_normalized) > 1:
                # 发现不一致
                names_str = ", ".join(set(c["original"] for c in company_names))
                
                # Step F3: 统一 evidence 结构（derived_consistency）
                evidence_json = [{
                    "role": "bid",
                    "source": "derived_consistency",
                    "quote": f"发现多个公司名称: {names_str}",
                    "page_start": None,
                    "segment_id": None,
                    "meta": {"type": "inconsistency", "values": company_names}
                }]
                
                results.append({
                    "requirement_id": "consistency_company_name",
                    "matched_response_id": None,
                    "dimension": "consistency",
                    "clause_title": "公司名称一致性检查",
                    "tender_requirement": "投标文件中公司名称应保持一致",
                    "bid_response": f"发现多个名称: {names_str}",
                    "status": "WARN",  # Step E: 降级为 WARN 而不是 FAIL
                    "result": "risk",
                    "is_hard": False,
                    "remark": "投标文件中公司名称不一致，请核实",
                    "evaluator": "consistency_check",
                    "evidence_json": evidence_json,
                    "tender_evidence_chunk_ids": [],
                    "bid_evidence_chunk_ids": [],
                })
        
        # 2. 检查报价一致性（Step E: 改进版）
        prices = []
        for resp in responses:
            if resp.get("dimension") == "price":
                normalized_fields = resp.get("normalized_fields_json", {})
                if isinstance(normalized_fields, dict):
                    # v2标准: 优先使用 total_price_cny，降级到 total_price/price
                    price_field = (
                        normalized_fields.get("total_price_cny") or 
                        normalized_fields.get("total_price") or 
                        normalized_fields.get("price")
                    )
                    if price_field:
                        # Step E: 归一化为"分"
                        normalized_price = normalize_money(price_field)
                        if normalized_price is not None:
                            prices.append({
                                "original": price_field,
                                "normalized": normalized_price,  # 单位：分
                                "response_id": resp.get("id")
                            })
        
        if len(prices) > 1:
            # Step E: 使用阈值判断
            unique_prices = set(p["normalized"] for p in prices)
            
            if len(unique_prices) > 1:
                # 计算差异
                price_values = [p["normalized"] for p in prices]
                max_price = max(price_values)
                min_price = min(price_values)
                diff_ratio = (max_price - min_price) / max_price if max_price > 0 else 0
                
                # Step E: 阈值判断
                if diff_ratio > 0.005:  # 0.5%
                    status = "WARN"  # 不直接 FAIL，降级为 WARN
                    remark = f"投标报价在不同章节不一致（差异: {diff_ratio*100:.2f}%），请核实"
                else:
                    # 差异很小，可能是四舍五入
                    status = "WARN"
                    remark = f"投标报价略有差异（差异: {diff_ratio*100:.2f}%），可能是四舍五入"
                
                prices_str = ", ".join(f"{p['original']}" for p in prices)
                
                # Step F3: 统一 evidence 结构
                evidence_json = [{
                    "role": "bid",
                    "source": "derived_consistency",
                    "quote": f"发现多个报价: {prices_str}，差异 {diff_ratio*100:.2f}%",
                    "page_start": None,
                    "segment_id": None,
                    "meta": {
                        "type": "inconsistency",
                        "values": prices,
                        "diff_ratio": diff_ratio
                    }
                }]
                
                results.append({
                    "requirement_id": "consistency_price",
                    "matched_response_id": None,
                    "dimension": "consistency",
                    "clause_title": "报价一致性检查",
                    "tender_requirement": "投标总价在各处表述应一致",
                    "bid_response": f"发现多个报价: {prices_str} (差异:{diff_ratio*100:.2f}%)",
                    "status": status,
                    "result": "risk",
                    "is_hard": False,  # Step E: 不设为硬性要求
                    "remark": remark,
                    "evaluator": "consistency_check",
                    "evidence_json": evidence_json,
                    "tender_evidence_chunk_ids": [],
                    "bid_evidence_chunk_ids": [],
                })
        elif len(prices) == 0:
            # Step E: 无法解析报价 → PENDING
            results.append({
                "requirement_id": "consistency_price",
                "matched_response_id": None,
                "dimension": "consistency",
                "clause_title": "报价一致性检查",
                "tender_requirement": "投标总价在各处表述应一致",
                "bid_response": "未能解析报价信息",
                "status": "PENDING",
                "result": "risk",
                "is_hard": False,
                "remark": "未能解析报价信息，需人工核实",
                "evaluator": "consistency_check",
                "evidence_json": [],
            })
        
        # 3. 检查工期一致性（Step E: 改进版）
        durations = []
        for resp in responses:
            if resp.get("dimension") in ("business", "technical"):
                normalized_fields = resp.get("normalized_fields_json", {})
                if isinstance(normalized_fields, dict):
                    # v2标准: 优先使用 duration_days，降级到 duration/construction_period
                    duration_field = (
                        normalized_fields.get("duration_days") or 
                        normalized_fields.get("duration") or 
                        normalized_fields.get("construction_period")
                    )
                    if duration_field:
                        # Step E: 归一化为"天"
                        normalized_duration = normalize_duration(duration_field)
                        if normalized_duration is not None:
                            durations.append({
                                "original": duration_field,
                                "normalized": normalized_duration,  # 单位：天
                                "dimension": resp.get("dimension"),
                                "response_id": resp.get("id")
                            })
        
        if len(durations) > 1:
            unique_durations = set(d["normalized"] for d in durations)
            if len(unique_durations) > 1:
                durations_str = ", ".join(f"{d['original']}" for d in durations)
                
                # Step F3: 统一 evidence 结构
                evidence_json = [{
                    "role": "bid",
                    "source": "derived_consistency",
                    "quote": f"发现多个工期表述: {durations_str}",
                    "page_start": None,
                    "segment_id": None,
                    "meta": {"type": "inconsistency", "values": durations}
                }]
                
                results.append({
                    "requirement_id": "consistency_duration",
                    "matched_response_id": None,
                    "dimension": "consistency",
                    "clause_title": "工期一致性检查",
                    "tender_requirement": "承诺工期在各处表述应一致",
                    "bid_response": f"发现多个工期: {durations_str}",
                    "status": "WARN",  # Step E: 降级为 WARN
                    "result": "risk",
                    "is_hard": False,
                    "remark": "工期表述不一致，请核实",
                    "evaluator": "consistency_check",
                    "evidence_json": evidence_json,
                    "tender_evidence_chunk_ids": [],
                    "bid_evidence_chunk_ids": [],
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
                        result.get("tender_evidence_chunk_ids", []),
                        result.get("bid_evidence_chunk_ids", []),
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

