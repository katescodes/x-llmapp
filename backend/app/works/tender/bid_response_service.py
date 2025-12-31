"""
投标响应要素抽取服务 (v2)

v2 特性:
- 输出 normalized_fields_json (标准化字段集)
- 输出 evidence_segment_ids (文档片段ID)
- 组装 evidence_json (页码+引用片段)
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.platform.extraction.engine import ExtractionEngine
from app.platform.retrieval.facade import RetrievalFacade
from app.services.embedding_provider_store import get_embedding_store
from app.services.dao.tender_dao import TenderDAO

logger = logging.getLogger(__name__)


def normalize_and_fix_response(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    抽取后矫正器（增强版）：修正错误、过滤无关响应、验证norm_key
    
    规则：
    1. 统一维度枚举（中文→英文）
    2. 过滤明显无关的响应（只包含注册资本、地址等无用信息）
    3. dimension=="price" 且包含业绩关键词 OR 不满足price锚点 → 强制改为 qualification
    4. dimension=="doc_structure" 且包含证书关键词 → 强制改为 qualification
    5. dimension=="other" 且包含业绩案例 → 强制改为 qualification
    6. business 文本同时含质保和工期 → 拆成两条
    7. 验证_norm_key存在且有效
    8. 验证文本长度（过长需要警告）
    
    Returns:
        修正后的 responses 列表（可能是0条、1条或2条）
        空列表表示该响应应该被过滤掉
    """
    import re
    import copy
    from app.works.tender.review.audit_keys import (
        normalize_dimension, 
        is_price_anchor, 
        is_valid_norm_key,
        validate_normalized_fields
    )
    
    response_text = resp.get("response_text", "")
    dimension = resp.get("dimension", "other")
    response_type = resp.get("response_type", "direct_answer")
    
    # ✅ Step -1: 兼容处理 - 如果LLM输出了列表格式，转换为字符串
    if isinstance(dimension, list):
        dimension = dimension[0] if len(dimension) > 0 else "other"
        resp["dimension"] = dimension  # 修正原始数据
        logger.warning(f"[Corrector] Fixed dimension from list to string: {dimension}")
    
    if isinstance(response_type, list):
        response_type = response_type[0] if len(response_type) > 0 else "direct_answer"
        resp["response_type"] = response_type  # 修正原始数据
        logger.warning(f"[Corrector] Fixed response_type from list to string: {response_type}")
    
    # Step 0: 过滤明显无关的响应（如果只包含注册资本、地址等）
    # 检查是否只包含无用信息
    useless_patterns = [
        r'^(公司)?注册资本[:：]\s*[\d.]+',  # "注册资本：8293万元"
        r'^(公司)?实收资本[:：]\s*[\d.]+',
        r'^(公司)?总部地址[:：]',          # "总部地址：杭州市XX区"
        r'^(公司)?注册地址[:：]',
        r'^(公司)?成立日期[:：]',          # "成立日期：2005年"
        r'^(公司)?成立时间[:：]',
    ]
    
    # 如果响应文本很短（<30字）且匹配无用模式，过滤掉
    if len(response_text) < 30:
        for pattern in useless_patterns:
            if re.search(pattern, response_text):
                logger.warning(f"[Corrector] Filtering useless response: {response_text}")
                return []  # 返回空列表，表示过滤掉
    
    # 检查是否是混合了多个字段的无用响应（如"公司名称XX；地址YY；注册资本ZZ"）
    # 如果包含多个分隔符（；或、）且包含注册资本/地址等关键词，警告
    if response_text.count('；') >= 2 or response_text.count('、') >= 2:
        useless_keywords = ['注册资本', '实收资本', '总部地址', '注册地址', '成立日期', '成立时间']
        if any(kw in response_text for kw in useless_keywords):
            # 如果还包含有用信息（如营业执照、公司名称），尝试提取
            if '营业执照' in response_text or '统一社会信用代码' in response_text:
                # 只保留有用部分
                useful_parts = []
                if '营业执照' in response_text:
                    useful_parts.append('营业执照')
                if '统一社会信用代码' in response_text:
                    match = re.search(r'统一社会信用代码[:：]\s*([A-Z0-9]+)', response_text)
                    if match:
                        useful_parts.append(f'统一社会信用代码：{match.group(1)}')
                
                if useful_parts:
                    response_text = '；'.join(useful_parts)
                    resp["response_text"] = response_text
                    logger.warning(f"[Corrector] Cleaned mixed response: {response_text}")
                else:
                    logger.warning(f"[Corrector] Filtering mixed useless response: {response_text[:50]}...")
                    return []
    
    # Step 0.1: 验证文本长度
    if len(response_text) > 250:
        logger.warning(f"[Corrector] Long response text ({len(response_text)} chars): {response_text[:80]}...")
        # 如果是业绩案例（很长的案例列表），可以简化
        if '合同金额' in response_text or '项目' in response_text:
            # 尝试统计案例数量
            project_count = response_text.count('项目') + response_text.count('工程')
            if project_count > 2:
                resp["response_text"] = f"提供{project_count}个类似项目案例"
                logger.info(f"[Corrector] Simplified long project list to: {resp['response_text']}")
    
    # Step 1: 统一维度枚举（中文→英文）
    dimension = normalize_dimension(dimension)
    resp["dimension"] = dimension
    
    # Step 2.1: 统一维度枚举（中文→英文）
    dimension = normalize_dimension(dimension)
    resp["dimension"] = dimension
    
    # Step 2: price 维度严格验证
    if dimension == "price":
        # 检查是否包含业绩关键词（强制排除）
        performance_keywords = r'(合同金额|项目业绩|中标金额|类似项目|历史业绩|业绩合同|已完成项目|完工项目金额|近\S*年\S*完成|业绩证明)'
        has_performance = re.search(performance_keywords, response_text)
        
        # 检查是否满足price锚点
        is_valid_price = is_price_anchor(response_text)
        
        if has_performance or not is_valid_price:
            logger.warning(f"[Corrector] price→qualification (performance={has_performance}, valid_price={is_valid_price}): {response_text[:50]}...")
            resp["dimension"] = "qualification"
            resp["response_type"] = "document_ref"
            
            # 标记为业绩证明（如果是业绩关键词）
            extracted_value = resp.get("extracted_value_json", {})
            if not isinstance(extracted_value, dict):
                extracted_value = {}
            if has_performance:
                extracted_value["type"] = "past_performance"
            resp["extracted_value_json"] = extracted_value
            return [resp]
    
    # Step 3: doc_structure 中的证书 → qualification
    if dimension == "doc_structure":
        cert_keywords = r'(营业执照|授权书|授权委托书|资质证书|安全生产许可证|保证金回执|基本存款账户|银行开户许可证|财务审计报告|业绩证明|资格证书|建造师|项目经理)'
        if re.search(cert_keywords, response_text):
            logger.warning(f"[Corrector] doc_structure→qualification: {response_text[:50]}...")
            resp["dimension"] = "qualification"
            return [resp]
    
    # Step 4: other 维度中的业绩案例 → qualification
    if dimension == "other":
        performance_keywords = r'(合同金额|项目业绩|中标金额|类似项目|历史业绩|业绩合同|已完成项目|完工项目金额|近\S*年\S*完成|业绩证明|类似工程)'
        has_performance = re.search(performance_keywords, response_text)
        
        # 检查是否是培训方案（应该是business）
        training_keywords = r'(培训|训练|教学|授课|学习|人员配备|项目负责人|技术负责人)'
        has_training = re.search(training_keywords, response_text)
        
        if has_performance:
            logger.warning(f"[Corrector] other→qualification (performance): {response_text[:50]}...")
            resp["dimension"] = "qualification"
            resp["response_type"] = "document_ref"
            extracted_value = resp.get("extracted_value_json", {})
            if not isinstance(extracted_value, dict):
                extracted_value = {}
            extracted_value["type"] = "past_performance"
            resp["extracted_value_json"] = extracted_value
            return [resp]
        elif has_training:
            logger.warning(f"[Corrector] other→business (training): {response_text[:50]}...")
            resp["dimension"] = "business"
            return [resp]
    
    # Step 5: business 同时含质保和工期 → 拆成两条
    if dimension == "business":
        has_warranty = bool(re.search(r'(质保|保修|售后|服务期|保修期|\d+\s*年|\d+\s*个月)', response_text))
        has_duration = bool(re.search(r'(工期|交付|完成|验收|\d+\s*天|\d+\s*日|自然日)', response_text))
        
        if has_warranty and has_duration:
            logger.warning(f"[Corrector] Splitting business with both warranty and duration: {response_text[:50]}...")
            
            # 创建两条记录
            warranty_resp = copy.deepcopy(resp)
            duration_resp = copy.deepcopy(resp)
            
            # 质保保留在 business
            warranty_resp["dimension"] = "business"
            warranty_resp["response_id"] = warranty_resp.get("response_id", "").replace("_resp_", "_warranty_")
            # 尝试截取质保相关文本
            warranty_match = re.search(r'(质保[^，。；]*|保修[^，。；]*|\d+\s*年[^，。；]*|\d+\s*个月[^，。；]*)', response_text)
            if warranty_match:
                warranty_resp["response_text"] = warranty_match.group(0)
            
            # 工期放到 schedule_quality
            duration_resp["dimension"] = "schedule_quality"
            duration_resp["response_id"] = duration_resp.get("response_id", "").replace("_resp_", "_duration_")
            # 尝试截取工期相关文本
            duration_match = re.search(r'(工期[^，。；]*|交付[^，。；]*|\d+\s*天[^，。；]*|\d+\s*日[^，。；]*)', response_text)
            if duration_match:
                duration_resp["response_text"] = duration_match.group(0)
            
            return [warranty_resp, duration_resp]
    
    # Step 6: 验证并清理 normalized_fields_json
    normalized_fields = resp.get("normalized_fields_json", {})
    if isinstance(normalized_fields, dict):
        # 确保 _norm_key 字段存在（即使为null）
        if "_norm_key" not in normalized_fields:
            normalized_fields["_norm_key"] = None
            logger.debug(f"[Corrector] Added missing _norm_key field for {dimension}: {response_text[:50]}...")
        
        # 清理不在允许列表中的字段
        cleaned = validate_normalized_fields(normalized_fields)
        resp["normalized_fields_json"] = cleaned
        
        # 检查 _norm_key 是否有效
        norm_key = cleaned.get("_norm_key")
        if norm_key and not is_valid_norm_key(norm_key):
            logger.warning(f"[Corrector] Invalid _norm_key '{norm_key}' for {dimension}, setting to null: {response_text[:50]}...")
            cleaned["_norm_key"] = None
            resp["normalized_fields_json"] = cleaned
    else:
        # 如果 normalized_fields_json 不是字典，创建一个空字典
        logger.warning(f"[Corrector] normalized_fields_json is not dict, creating empty: {response_text[:50]}...")
        resp["normalized_fields_json"] = {"_norm_key": None}
    
    # Step 7: 最终检查 - 确保response_text不为空
    if not response_text or len(response_text.strip()) == 0:
        logger.warning(f"[Corrector] Empty response_text, filtering out")
        return []
    
    # 无需修正，返回原样
    logger.debug(f"[Corrector] Response OK: dimension={resp.get('dimension')}: {response_text[:50]}...")
    
    return [resp]


class BidResponseService:
    """投标响应要素抽取服务"""
    
    def __init__(
        self,
        pool: Any,
        engine: ExtractionEngine,
        retriever: RetrievalFacade,
        llm: Any,  # LLM orchestrator (使用Any避免循环导入)
    ):
        self.pool = pool
        self.engine = engine
        self.retriever = retriever
        self.llm = llm
        self.dao = TenderDAO(pool)
        # 框架式提取器（懒加载）
        self._framework_extractor = None
    
    def _get_framework_extractor(self):
        """获取框架式提取器（懒加载）"""
        if self._framework_extractor is None:
            from app.works.tender.framework_bid_response_extractor import FrameworkBidResponseExtractor
            self._framework_extractor = FrameworkBidResponseExtractor(
                llm_orchestrator=self.llm,
                retriever=self.retriever
            )
        return self._framework_extractor
    
    def _prefetch_doc_segments(self, segment_ids: List[str]) -> Dict[str, Dict]:
        """批量预取 doc_segments"""
        if not segment_ids:
            return {}
        
        import psycopg.rows
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("""
                    SELECT 
                        id as segment_id, 
                        doc_version_id as asset_id, 
                        content_text as content, 
                        page_start, 
                        page_end, 
                        heading_path, 
                        segment_type
                    FROM doc_segments
                    WHERE id = ANY(%s)
                """, (list(set(segment_ids)),))
                rows = cur.fetchall()
        
        return {row["segment_id"]: row for row in rows}
    
    def _make_quote(self, text: str, limit: int = 220) -> str:
        """截取 quote"""
        if not text:
            return ""
        text = " ".join(text.split())  # 压缩空白
        if len(text) <= limit:
            return text
        return text[:limit] + "..."
    
    def _deduplicate_responses(self, responses: List[Dict]) -> List[Dict]:
        """
        去除重复的响应
        基于response_text的相似度判断
        """
        if not responses:
            return []
        
        unique_responses = []
        seen_texts = set()
        
        for resp in responses:
            resp_text = resp.get("response_text", "").strip()
            # 简化文本用于比较（去除空白和标点）
            normalized_text = "".join(resp_text.split())
            
            # 检查是否与已有响应重复（使用前100个字符作为指纹）
            fingerprint = normalized_text[:100]
            
            if fingerprint and fingerprint not in seen_texts:
                unique_responses.append(resp)
                seen_texts.add(fingerprint)
        
        logger.info(f"BidResponseService: dedup {len(responses)} -> {len(unique_responses)}")
        return unique_responses
    
    def _build_evidence_json_from_segments(
        self, 
        segment_ids: List[str], 
        seg_map: Dict[str, Dict]
    ) -> List[Dict]:
        """从 segment_ids 组装 evidence_json（增强版 - 更多证据，更长上下文）"""
        evidence = []
        # ✅ 增加证据数量上限：5 → 10条，提供更完整的证据链
        for sid in segment_ids[:10]:
            seg = seg_map.get(sid)
            if not seg:
                # 降级：只保留 segment_id
                evidence.append({
                    "segment_id": sid,
                    "source": "fallback_chunk"
                })
                continue
            
            # ✅ 增加quote长度：220 → 400字符，保留更多上下文
            evidence.append({
                "segment_id": sid,
                "asset_id": seg.get("asset_id"),
                "page_start": seg.get("page_start"),
                "page_end": seg.get("page_end"),
                "heading_path": seg.get("heading_path"),
                "quote": self._make_quote(seg.get("content", ""), 400),
                "segment_type": seg.get("segment_type"),
                "source": "doc_segments"
            })
        return evidence
    
    async def _check_extraction_coverage(
        self,
        project_id: str,
        extracted_count: int
    ) -> Dict[str, Any]:
        """
        检查提取覆盖率
        
        Args:
            project_id: 项目ID
            extracted_count: 实际提取的响应数量
        
        Returns:
            {
                "requirements_count": 20,
                "extracted_count": 15,
                "coverage_rate": 0.75,
                "target_min": 16,
                "target_max": 24,
                "status": "low|ok|high",
                "warnings": [...]
            }
        """
        # 1. 查询招标要求数量
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count FROM tender_requirements
                    WHERE project_id = %s
                """, (project_id,))
                result = cur.fetchone()
                
                # 兼容处理：result可能是tuple或dict
                if result is None:
                    requirements_count = 0
                elif isinstance(result, dict):
                    requirements_count = result.get('count', 0)
                else:
                    requirements_count = result[0] if len(result) > 0 else 0
        
        # 2. 计算目标范围（80%-120%）
        target_min = int(requirements_count * 0.8)
        target_max = int(requirements_count * 1.2)
        
        # 3. 计算覆盖率
        coverage_rate = extracted_count / requirements_count if requirements_count > 0 else 0
        
        # 4. 判断状态
        status = "ok"
        warnings = []
        
        if extracted_count < target_min:
            status = "low"
            warnings.append(f"提取数量偏低: 实际{extracted_count}条, 目标{target_min}-{target_max}条 (覆盖率{coverage_rate:.1%})")
            warnings.append(f"建议: 检查投标文档是否完整，或调整提取策略")
        elif extracted_count > target_max:
            status = "high"
            warnings.append(f"提取数量偏多: 实际{extracted_count}条, 目标{target_min}-{target_max}条 (覆盖率{coverage_rate:.1%})")
            warnings.append(f"可能原因: 过度提取无关信息，或粒度过细")
        else:
            logger.info(f"[Coverage Check] OK: extracted={extracted_count}, target={target_min}-{target_max}")
        
        return {
            "requirements_count": requirements_count,
            "extracted_count": extracted_count,
            "coverage_rate": coverage_rate,
            "target_min": target_min,
            "target_max": target_max,
            "status": status,
            "warnings": warnings
        }
    
    async def extract_bid_response(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        抽取投标响应要素
        
        特性:
        - 输出 normalized_fields_json (标准化字段集)
        - 输出 evidence_segment_ids (文档片段ID)
        - 组装 evidence_json (页码+引用片段)
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: LLM模型ID
            run_id: 运行ID（可选）
        
        Returns:
            {
                "bidder_name": "投标人名称",
                "responses": [...],
                "added_count": 15,
                "schema_version": "bid_response_v2"
            }
        """
        logger.info(f"BidResponseService: extract_bid_response start project_id={project_id}, bidder={bidder_name}")
        
        # 0. ✅ 前置检查：确保招标要求已提取
        logger.info(f"BidResponseService: Checking if requirements exist for project_id={project_id}")
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count FROM tender_requirements 
                    WHERE project_id = %s
                """, (project_id,))
                result = cur.fetchone()
                
                # 兼容处理：result可能是tuple或dict
                if result is None:
                    requirements_count = 0
                elif isinstance(result, dict):
                    requirements_count = result.get('count', 0)
                else:
                    requirements_count = result[0] if len(result) > 0 else 0
        
        if requirements_count == 0:
            error_msg = f"❌ 未找到招标要求，请先提取招标要求。项目ID: {project_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"BidResponseService: Found {requirements_count} requirements, proceeding with extraction")
        
        # 1. 删除旧数据（避免重复抽取累积）
        try:
            self.dao._execute("""
                DELETE FROM tender_bid_response_items 
                WHERE project_id = %s AND bidder_name = %s
            """, (project_id, bidder_name))
            logger.info(f"BidResponseService: Deleted old bid responses for project={project_id}, bidder={bidder_name}")
        except Exception as e:
            logger.warning(f"BidResponseService: Failed to delete old data: {e}")
        
        # 2. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 3. 构建 spec（✅ 需求驱动：基于招标要求动态生成）
        try:
            from app.works.tender.extraction_specs.bid_response_dynamic import build_bid_response_spec_from_requirements
            spec = await build_bid_response_spec_from_requirements(self.pool, project_id)
            logger.info(f"BidResponseService: Using dynamic spec (requirement-driven)")
        except Exception as e:
            # 降级：如果动态生成失败，使用固定spec
            logger.warning(f"BidResponseService: Failed to build dynamic spec: {e}, falling back to fixed spec")
            from app.works.tender.extraction_specs.bid_response_v2 import build_bid_response_spec_v2_async
            spec = await build_bid_response_spec_v2_async(self.pool)
        
        # 4. 单次调用（暂时接受LLM的输出限制）
        # TODO: 后续可以实现分批提取策略
        print(f"[DEBUG BidResponse] Single extraction call...")
        
        result = await self.engine.run(
            spec=spec,
            retriever=self.retriever,
            llm=self.llm,
            project_id=project_id,
            model_id=model_id,
            run_id=run_id,
            embedding_provider=embedding_provider,
            module_name="bid_response",
        )
        
        # 解析结果
        responses_list = []
        extracted_bidder_name = bidder_name
        
        if isinstance(result.data, dict):
            responses_list = result.data.get("responses", [])
            print(f"[DEBUG BidResponse] Extracted {len(responses_list)} responses")
        
        # 4. 解析结果（保留原有逻辑）
        
        # 诊断：打印原始LLM返回数据
        print(f"[DEBUG BidResponse] result.data type: {type(result.data)}")
        if isinstance(result.data, dict):
            print(f"[DEBUG BidResponse] result.data keys: {list(result.data.keys())}")
            print(f"[DEBUG BidResponse] responses length: {len(result.data.get('responses', []))}")
        
        if isinstance(result.data, dict):
            # 检查 schema_version (支持v2-v5)
            schema_version = result.data.get("schema_version", "unknown")
            logger.info(f"BidResponseService: schema_version={schema_version}")
            
            # ✅ 兼容v2-v5版本
            expected_versions = ["bid_response_v2", "bid_response_v3", "bid_response_v5"]
            if schema_version not in expected_versions:
                logger.warning(f"BidResponseService: Unexpected schema version: {schema_version}, expected one of {expected_versions}")
            
            responses_list = result.data.get("responses", [])
            logger.info(f"BidResponseService: parsed responses_list length={len(responses_list)}")
            
            # 诊断：打印所有response的维度分布
            dimension_count = {}
            for resp in responses_list:
                dim = resp.get('dimension', 'unknown')
                # ✅ 兼容处理：如果dimension是列表，取第一个元素
                if isinstance(dim, list):
                    dim = dim[0] if len(dim) > 0 else 'unknown'
                dimension_count[dim] = dimension_count.get(dim, 0) + 1
            print(f"[DEBUG BidResponse] Dimension distribution: {dimension_count}")
            
            # 诊断：打印前3个response的简要信息
            for idx, resp in enumerate(responses_list[:3]):
                logger.info(f"BidResponseService: response[{idx}]: dimension={resp.get('dimension')}, " +
                           f"type={resp.get('response_type')}, " +
                           f"has_normalized={bool(resp.get('normalized_fields_json'))}, " +
                           f"has_segment_ids={bool(resp.get('evidence_segment_ids'))}")
        else:
            logger.warning(f"BidResponseService: unexpected data format, type={type(result.data)}")
        
        if not isinstance(responses_list, list):
            logger.error(f"BidResponseService: responses not list, type={type(responses_list)}")
            responses_list = []
        
        # 5. 预取所有 segment_ids
        all_segment_ids = []
        for resp in responses_list:
            all_segment_ids.extend(resp.get("evidence_segment_ids", []))
        
        logger.info(f"BidResponseService: prefetching {len(set(all_segment_ids))} unique segments")
        seg_map = self._prefetch_doc_segments(all_segment_ids)
        logger.info(f"BidResponseService: fetched {len(seg_map)} segments from database")
        
        # 6. 落库到 tender_bid_response_items
        added_count = 0
        for resp in responses_list:
            # ✅ Step 2: 应用矫正器（可能返回1条或2条）
            corrected_resps = normalize_and_fix_response(resp)
            
            for corrected_resp in corrected_resps:
                response_id = corrected_resp.get("response_id", str(uuid.uuid4()))
                db_id = str(uuid.uuid4())
                
                # 旧字段（向后兼容）
                extracted_value_json = corrected_resp.get("extracted_value_json", {})
                evidence_chunk_ids = corrected_resp.get("evidence_chunk_ids", [])
                
                # 新字段
                normalized_fields_json = corrected_resp.get("normalized_fields_json", {})
                evidence_segment_ids = corrected_resp.get("evidence_segment_ids", [])
                
                # 兼容性处理
                if not evidence_chunk_ids and evidence_segment_ids:
                    evidence_chunk_ids = evidence_segment_ids
                elif not evidence_segment_ids and evidence_chunk_ids:
                    evidence_segment_ids = evidence_chunk_ids
                
                # 组装 evidence_json
                evidence_json = self._build_evidence_json_from_segments(evidence_segment_ids, seg_map)
                
                # 插入数据库
                import json
                self.dao._execute("""
                    INSERT INTO tender_bid_response_items (
                        id, project_id, bidder_name, dimension, response_type,
                        response_text, extracted_value_json, evidence_chunk_ids,
                        normalized_fields_json, evidence_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::text[], %s::jsonb, %s::jsonb)
                """, (
                    db_id,
                    project_id,
                    extracted_bidder_name,
                    corrected_resp.get("dimension", "other"),
                    corrected_resp.get("response_type", "text"),
                    corrected_resp.get("response_text", ""),
                    json.dumps(extracted_value_json) if extracted_value_json else '{}',
                    evidence_chunk_ids,
                    json.dumps(normalized_fields_json) if normalized_fields_json else '{}',
                    json.dumps(evidence_json) if evidence_json else None,
                ))
                added_count += 1
        
        logger.info(f"BidResponseService: extract_bid_response done responses={len(responses_list)}, added={added_count}")
        
        # ✅ Step 3.5: P1优化 - 结构化补充扫描
        logger.info("[P1优化] 开始投标响应结构化补充扫描...")
        supplement_responses = await self._supplement_bid_response_structural(
            project_id=project_id,
            bidder_name=extracted_bidder_name,
            model_id=model_id,
            existing_responses=responses_list,
            seg_map=seg_map,
        )
        
        if supplement_responses:
            logger.info(f"[P1优化] 补充扫描发现 {len(supplement_responses)} 条额外响应")
            added_count += len(supplement_responses)
        else:
            logger.info("[P1优化] 补充扫描未发现额外响应")
        
        # ✅ Step 3.6: P2优化 - 审核兜底抽取（确保关键审核字段一定被抽到）
        logger.info("[P2优化] 开始审核兜底抽取...")
        from .bid_baseline_extractor import BidBaselineExtractor
        
        baseline_extractor = BidBaselineExtractor(
            llm_orchestrator=self.llm,
            retriever=self.retriever,
            dao=self.dao,
        )
        
        # 读取当前所有响应（包括补充的）
        all_responses = await self._load_all_responses(project_id, extracted_bidder_name)
        
        baseline_responses = await baseline_extractor.extract_baseline_fields(
            project_id=project_id,
            bidder_name=extracted_bidder_name,
            model_id=model_id,
            existing_responses=all_responses,
        )
        
        if baseline_responses:
            logger.info(f"[P2优化] 兜底抽取补充了 {len(baseline_responses)} 条关键字段")
            added_count += len(baseline_responses)
        else:
            logger.info("[P2优化] 兜底抽取：所有关键字段已覆盖")
        
        # ✅ Step 4: 检查提取覆盖率
        coverage_info = await self._check_extraction_coverage(project_id, added_count)
        if coverage_info.get("warnings"):
            for warning in coverage_info["warnings"]:
                logger.warning(f"[Coverage Check] {warning}")
        
        return {
            "bidder_name": extracted_bidder_name,
            "responses": responses_list,
            "added_count": added_count,
            "schema_version": "bid_response_v2",
            "coverage_info": coverage_info  # ✅ 新增覆盖率信息
        }
    
    async def extract_bid_response_framework(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        使用框架式方法抽取投标响应
        
        特性：
        - 按维度分组批量提取（6次LLM调用 vs 原来52次）
        - 支持复杂对应关系（一对多、多对一）
        - 更强的语义理解能力
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: LLM模型ID
            run_id: 运行ID（可选）
        
        Returns:
            {
                "bidder_name": "投标人名称",
                "responses": [...],
                "added_count": 52,
                "extraction_method": "framework",
                "schema_version": "bid_response_framework"
            }
        """
        logger.info(f"BidResponseService: extract_bid_response_framework start project_id={project_id}, bidder={bidder_name}")
        
        # 1. 检查招标要求是否已提取
        logger.info(f"Loading tender requirements for project_id={project_id}")
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id, project_id, requirement_id, dimension, req_type,
                        requirement_text, is_hard, value_schema_json,
                        evidence_chunk_ids, eval_method, must_reject,
                        expected_evidence_json, rubric_json, weight
                    FROM tender_requirements 
                    WHERE project_id = %s
                    ORDER BY dimension, requirement_id
                """, (project_id,))
                
                rows = cur.fetchall()
                
                if not rows:
                    error_msg = f"❌ 未找到招标要求，请先提取招标要求。项目ID: {project_id}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # 转换为字典列表
                columns = [desc[0] for desc in cur.description]
                requirements = [dict(zip(columns, row)) for row in rows]
        
        logger.info(f"Loaded {len(requirements)} tender requirements")
        
        # 2. 删除旧数据（避免重复）
        try:
            self.dao._execute("""
                DELETE FROM tender_bid_response_items 
                WHERE project_id = %s AND bidder_name = %s
            """, (project_id, bidder_name))
            logger.info(f"Deleted old bid responses for project={project_id}, bidder={bidder_name}")
        except Exception as e:
            logger.warning(f"Failed to delete old data: {e}")
        
        # 3. 使用框架式提取器提取所有响应
        extractor = self._get_framework_extractor()
        responses = await extractor.extract_all_responses(
            project_id=project_id,
            requirements=requirements,
            model_id=model_id
        )
        
        logger.info(f"Framework extractor returned {len(responses)} responses")
        
        # 4. 后处理：转换为数据库格式并保存
        saved_count = 0
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                from psycopg.types.json import Json
                
                for resp in responses:
                    req_id = resp.get("requirement_id")
                    response_text = resp.get("response_text")
                    
                    # 跳过null响应
                    if response_text is None or response_text == "":
                        logger.debug(f"Skipping null response for requirement {req_id}")
                        continue
                    
                    # 准备JSONB字段
                    normalized_fields = resp.get("normalized_fields", {})
                    if normalized_fields and not isinstance(normalized_fields, Json):
                        normalized_fields = Json(normalized_fields)
                    
                    evidence_segment_ids = resp.get("evidence_segment_ids", [])
                    is_compliant = resp.get("is_compliant", None)
                    confidence = resp.get("confidence", 0.0)
                    notes = resp.get("notes", "")
                    
                    # 插入数据库
                    cur.execute("""
                        INSERT INTO tender_bid_response_items (
                            id, project_id, bidder_name, requirement_id,
                            response_text, normalized_fields_json,
                            evidence_segment_ids, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        str(uuid.uuid4()),
                        project_id,
                        bidder_name,
                        req_id,
                        response_text,
                        normalized_fields,
                        evidence_segment_ids
                    ))
                    
                    saved_count += 1
                
                conn.commit()
        
        logger.info(f"Saved {saved_count} bid responses to database")
        
        return {
            "bidder_name": bidder_name,
            "responses": responses,
            "added_count": saved_count,
            "extraction_method": "framework",
            "schema_version": "bid_response_framework"
        }
    
    async def extract_all_bidders_responses(
        self,
        project_id: str,
        bidder_names: List[str],
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        批量抽取所有投标人的响应要素
        
        Args:
            project_id: 项目ID
            bidder_names: 投标人名称列表
            model_id: LLM模型ID
            run_id: 运行ID（可选）
        
        Returns:
            {
                "total_bidders": 3,
                "total_responses": 50,
                "bidders": {
                    "投标人A": {"responses": [...], "added_count": 15},
                    "投标人B": {"responses": [...], "added_count": 18},
                    ...
                }
            }
        """
        logger.info(f"BidResponseService: extract_all_bidders_responses start project_id={project_id}, bidders={len(bidder_names)}")
        
        results = {}
        total_responses = 0
        
        for bidder_name in bidder_names:
            try:
                result = await self.extract_bid_response(
                    project_id=project_id,
                    bidder_name=bidder_name,
                    model_id=model_id,
                    run_id=run_id,
                )
                results[bidder_name] = result
                total_responses += len(result.get("responses", []))
            except Exception as e:
                logger.error(f"BidResponseService: Failed to extract for bidder={bidder_name}: {e}", exc_info=True)
                results[bidder_name] = {"error": str(e), "responses": [], "added_count": 0}
        
        logger.info(f"BidResponseService: extract_all_bidders_responses done total_responses={total_responses}")
        
        return {
            "total_bidders": len(bidder_names),
            "total_responses": total_responses,
            "bidders": results
        }
    
    async def _supplement_bid_response_structural(
        self,
        project_id: str,
        bidder_name: str,
        model_id: Optional[str],
        existing_responses: List[Dict[str, Any]],
        seg_map: Dict[str, Dict],
    ) -> List[Dict[str, Any]]:
        """
        P1优化：结构化补充扫描投标响应
        
        策略：
        1. 按投标书章节结构扫描
        2. 识别需求驱动提取可能遗漏的内容
        3. 特别关注：资质证书、业绩案例、技术方案完整性、附件材料
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            model_id: 模型ID
            existing_responses: 已提取的响应列表
            seg_map: segment映射
        
        Returns:
            补充的响应列表
        """
        logger.info(f"[补充扫描] 开始，已有 {len(existing_responses)} 条响应")
        
        try:
            # 1. 加载招标要求（了解应该提取什么）
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT requirement_id, dimension, requirement_text, is_hard
                        FROM tender_requirements
                        WHERE project_id = %s
                        ORDER BY dimension, requirement_id
                    """, (project_id,))
                    requirements = [dict(row) for row in cur.fetchall()]
            
            # 2. 构建已响应的需求集合
            covered_dimensions = set()
            covered_keywords = set()
            for resp in existing_responses:
                covered_dimensions.add(resp.get("dimension", ""))
                # 提取关键词
                text = resp.get("response_text", "")[:100].lower()
                for keyword in ["营业执照", "资质", "业绩", "技术方案", "报价", "质保", "授权"]:
                    if keyword in text:
                        covered_keywords.add(keyword)
            
            logger.info(f"[补充扫描] 已覆盖维度: {covered_dimensions}")
            logger.info(f"[补充扫描] 已覆盖关键词: {covered_keywords}")
            
            # 3. 识别可能遗漏的维度和关键要求
            missing_areas = []
            for req in requirements:
                dim = req.get("dimension")
                text = req.get("requirement_text", "")
                is_hard = req.get("is_hard", False)
                
                # 硬性要求且该维度覆盖不足
                if is_hard and dim not in covered_dimensions:
                    missing_areas.append({
                        "dimension": dim,
                        "requirement": text[:80],
                        "priority": "high"
                    })
            
            if not missing_areas:
                logger.info("[补充扫描] 未发现明显遗漏领域")
                return []
            
            logger.info(f"[补充扫描] 发现 {len(missing_areas)} 个可能遗漏的领域")
            
            # 4. 检索投标文件相关章节
            # 构建针对性查询
            search_queries = []
            for area in missing_areas[:5]:  # 限制查询数量
                dim = area["dimension"]
                if dim == "qualification":
                    search_queries.append("资格条件 营业执照 资质证书 业绩证明 人员配置")
                elif dim == "technical":
                    search_queries.append("技术方案 技术参数 设备规格 实施方案")
                elif dim == "business":
                    search_queries.append("商务条款 质保期 售后服务 付款方式")
                elif dim == "price":
                    search_queries.append("投标报价 价格 总价 单价 报价表")
                elif dim == "schedule_quality":
                    search_queries.append("工期 进度计划 质量标准 交付时间")
            
            # 合并查询
            combined_query = " ".join(set(search_queries))
            
            # 检索投标文件
            bid_chunks = await self.retriever.retrieve(
                query=combined_query,
                project_id=project_id,
                doc_types=["bid"],
                top_k=100,
            )
            
            logger.info(f"[补充扫描] 检索到 {len(bid_chunks)} 个投标文件片段")
            
            if not bid_chunks:
                logger.warning("[补充扫描] 未检索到投标文件内容")
                return []
            
            # 5. 构建补充扫描prompt
            bid_context = "\n\n".join([
                f"[SEG:{chunk.chunk_id}] {chunk.text}"
                for chunk in bid_chunks[:80]
            ])
            
            existing_summary = []
            for resp in existing_responses[:30]:
                dim = resp.get("dimension", "")
                text = resp.get("response_text", "")[:50]
                existing_summary.append(f"[{dim}] {text}")
            
            supplement_prompt = f"""# 投标响应补充扫描任务

## 背景
已通过需求驱动方式提取了 {len(existing_responses)} 条投标响应，现需要结构化扫描投标文件，识别可能遗漏的响应。

## 已提取响应摘要（前30条）
{chr(10).join(existing_summary)}

## 可能遗漏的领域
{chr(10).join([f"- {area['dimension']}: {area['requirement']}" for area in missing_areas[:5]])}

## 投标文件内容
{bid_context}

## 任务要求
请扫描投标文件，识别以下**未被已提取响应覆盖的内容**：

### 重点关注（高频遗漏）
1. **资质证书、营业执照**：完整的证书信息和有效期
2. **业绩案例**：类似项目业绩、合同金额、验收情况
3. **技术方案完整性**：方案章节、技术参数、实施计划
4. **附件材料**：各类证明文件、承诺函、授权书
5. **人员配置**：项目团队、人员资质
6. **质保和售后**：质保期、售后服务承诺

### 输出格式
返回JSON数组，**只包含新发现的、未被已提取响应覆盖的条目**：

```json
{{
  "supplement_responses": [
    {{
      "dimension": "qualification|technical|business|price|doc_structure|schedule_quality|other",
      "response_type": "direct_answer|table_extract|document_ref|promise",
      "response_text": "响应内容（包含关键信息：证书号、金额、日期等）",
      "evidence_segment_ids": ["seg_xxx", "seg_yyy"],
      "reasoning": "为什么这是一个新响应（未被已提取响应覆盖）"
    }}
  ]
}}
```

### 去重原则
- **仔细对比已提取响应**：如果某内容已被覆盖，**不要重复提取**
- **宁缺毋滥**：不确定是否重复时，选择不提取
- **聚焦关键信息**：优先提取包含具体数值、日期、证书号等关键信息的内容

请开始分析并输出JSON。"""

            # 6. 调用LLM
            messages = [{"role": "user", "content": supplement_prompt}]
            llm_response = await self.llm.achat(
                messages=messages,
                model_id=model_id,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4096,
            )
            
            # 7. 解析响应
            import json
            import uuid
            llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content")
            if not llm_output:
                logger.warning("[补充扫描] LLM返回空内容")
                return []
            
            try:
                result_data = json.loads(llm_output)
                supplement_items = result_data.get("supplement_responses", [])
            except json.JSONDecodeError as e:
                logger.error(f"[补充扫描] JSON解析失败: {e}")
                return []
            
            if not supplement_items:
                logger.info("[补充扫描] 未发现额外响应")
                return []
            
            logger.info(f"[补充扫描] LLM返回 {len(supplement_items)} 条补充响应")
            
            # 8. 保存到数据库
            saved_count = 0
            for item in supplement_items:
                response_id = f"supplement_{uuid.uuid4().hex[:8]}"
                db_id = str(uuid.uuid4())
                
                evidence_segment_ids = item.get("evidence_segment_ids", [])
                evidence_json = self._build_evidence_json_from_segments(evidence_segment_ids, seg_map)
                
                try:
                    self.dao._execute("""
                        INSERT INTO tender_bid_response_items (
                            id, project_id, bidder_name, dimension, response_type,
                            response_text, extracted_value_json, evidence_chunk_ids,
                            normalized_fields_json, evidence_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::text[], %s::jsonb, %s::jsonb)
                    """, (
                        db_id,
                        project_id,
                        bidder_name,
                        item.get("dimension", "other"),
                        item.get("response_type", "direct_answer"),
                        item.get("response_text", ""),
                        json.dumps({}),
                        evidence_segment_ids,
                        json.dumps({"_norm_key": None, "source": "structural_supplement"}),
                        json.dumps(evidence_json) if evidence_json else None,
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"[补充扫描] 保存失败: {e}")
            
            logger.info(f"[补充扫描] 成功保存 {saved_count} 条补充响应")
            return supplement_items
            
        except Exception as e:
            logger.error(f"[补充扫描] 失败: {e}", exc_info=True)
            return []
    
    async def _load_all_responses(
        self,
        project_id: str,
        bidder_name: str
    ) -> List[Dict[str, Any]]:
        """
        加载当前项目和投标人的所有响应（用于兜底抽取检查）
        
        Args:
            project_id: 项目ID
            bidder_name: 投标人名称
            
        Returns:
            响应列表
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT dimension, response_type, response_text,
                           normalized_fields_json, evidence_chunk_ids
                    FROM tender_bid_response_items
                    WHERE project_id = %s AND bidder_name = %s
                """, (project_id, bidder_name))
                
                rows = cur.fetchall()
                responses = []
                for row in rows:
                    if isinstance(row, dict):
                        responses.append(row)
                    else:
                        # tuple格式
                        responses.append({
                            "dimension": row[0],
                            "response_type": row[1],
                            "response_text": row[2],
                            "normalized_fields_json": row[3],
                            "evidence_chunk_ids": row[4],
                        })
                
                return responses

