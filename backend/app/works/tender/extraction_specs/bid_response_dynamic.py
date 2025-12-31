"""
动态投标响应提取Spec构建器
基于招标要求（requirements）动态生成提取Spec，实现需求驱动的提取
"""
import logging
from typing import Dict, List, Optional, Any
from psycopg_pool import ConnectionPool

from app.platform.extraction.types import ExtractionSpec
from app.works.tender.requirement_postprocessor import generate_dynamic_prompt_supplement

logger = logging.getLogger(__name__)


async def build_bid_response_spec_from_requirements(
    pool: ConnectionPool,
    project_id: str
) -> ExtractionSpec:
    """
    基于招标要求动态构建投标响应提取spec
    
    核心思想：
    1. 从数据库加载招标要求（requirements）
    2. 从meta_json加载提取指南（extraction_guide）
    3. 生成动态prompt（基础prompt + 指南补充）
    4. 生成针对性检索查询（只针对要求的维度）
    5. 构建ExtractionSpec
    
    Args:
        pool: 数据库连接池
        project_id: 项目ID
    
    Returns:
        动态生成的ExtractionSpec
    """
    logger.info(f"Building dynamic bid response spec for project_id={project_id}")
    
    # 1. 加载招标要求
    requirements = await _load_requirements(pool, project_id)
    logger.info(f"Loaded {len(requirements)} requirements")
    
    # 2. 加载提取指南
    extraction_guide = await _load_extraction_guide(pool, project_id)
    
    if not extraction_guide:
        logger.warning(
            f"No extraction guide found for project_id={project_id}, "
            "generating on-the-fly"
        )
        # 如果没有提取指南，临时生成一个
        from app.works.tender.requirement_postprocessor import generate_bid_response_extraction_guide
        extraction_guide = generate_bid_response_extraction_guide(requirements)
    
    logger.info(
        f"Loaded extraction guide: "
        f"must_extract={len(extraction_guide.get('must_extract_norm_keys', []))}, "
        f"dimensions={len(extraction_guide.get('dimension_focus', {}))}"
    )
    
    # 3. 加载基础prompt（从数据库或文件）
    base_prompt = await _load_base_prompt(pool)
    
    # 4. 生成动态prompt补充（包含招标要求列表）
    prompt_supplement = generate_dynamic_prompt_supplement(extraction_guide, requirements)
    
    # 5. 组合完整prompt
    full_prompt = base_prompt + "\n\n" + prompt_supplement
    
    # 6. 生成针对性检索查询
    queries = _generate_targeted_queries(requirements, extraction_guide)
    
    # 7. 构建spec
    spec = ExtractionSpec(
        prompt=full_prompt,
        queries=queries,
        topk_per_query=25,  # 针对性检索，每个查询减少数量
        topk_total=100,     # 总量也减少（因为更精确）
        doc_types=["bid"],  # 只检索投标文档
        temperature=0.0,
    )
    
    logger.info(
        f"Built dynamic spec: queries={len(queries)}, "
        f"topk_per_query={spec.topk_per_query}, topk_total={spec.topk_total}"
    )
    
    return spec


async def _load_requirements(pool: ConnectionPool, project_id: str) -> List[Dict[str, Any]]:
    """从数据库加载招标要求"""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    requirement_id,
                    dimension,
                    req_type,
                    requirement_text,
                    is_hard,
                    value_schema_json,
                    evidence_chunk_ids
                FROM tender_requirements
                WHERE project_id = %s
                ORDER BY dimension, requirement_id
            """, (project_id,))
            
            rows = cur.fetchall()
            requirements = []
            for row in rows:
                # 兼容dict_row和tuple
                if isinstance(row, dict):
                    requirements.append({
                        "requirement_id": row.get("requirement_id"),
                        "dimension": row.get("dimension"),
                        "req_type": row.get("req_type"),
                        "requirement_text": row.get("requirement_text"),
                        "is_hard": row.get("is_hard"),
                        "value_schema_json": row.get("value_schema_json"),
                        "evidence_chunk_ids": row.get("evidence_chunk_ids") or [],
                    })
                else:
                    requirements.append({
                        "requirement_id": row[0],
                        "dimension": row[1],
                        "req_type": row[2],
                        "requirement_text": row[3],
                        "is_hard": row[4],
                        "value_schema_json": row[5],
                        "evidence_chunk_ids": row[6] or [],
                    })
            
            return requirements


async def _load_extraction_guide(pool: ConnectionPool, project_id: str) -> Optional[Dict[str, Any]]:
    """从meta_json加载提取指南（统一使用 extraction_guide 键，兼容旧键）"""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 优先读取新键 extraction_guide，兼容旧键 bid_response_extraction_guide
            cur.execute("""
                SELECT 
                    COALESCE(
                        meta_json->'extraction_guide',
                        meta_json->'bid_response_extraction_guide'
                    ) as guide
                FROM tender_projects
                WHERE id = %s
            """, (project_id,))
            
            result = cur.fetchone()
            if result:
                # 兼容dict_row和tuple
                guide = result.get("guide") if isinstance(result, dict) else result[0]
                return guide if guide else None
            return None


async def _load_base_prompt(pool: ConnectionPool) -> str:
    """
    加载基础投标响应提取prompt
    
    优先从数据库加载，如果不存在则使用默认prompt
    """
    # 1. 尝试从数据库加载
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT content 
                    FROM prompt_templates 
                    WHERE name = %s AND is_active = true 
                    ORDER BY version DESC 
                    LIMIT 1
                """, ("bid_response_extraction_v5",))
                
                result = cur.fetchone()
                if result:
                    # 兼容dict_row和tuple
                    content = result.get("content") if isinstance(result, dict) else result[0]
                    if content:
                        logger.info("Loaded base prompt from database: bid_response_extraction_v5")
                        return content
    except Exception as e:
        logger.warning(f"Failed to load prompt from database: {e}")
    
    # 2. 使用默认prompt
    logger.info("Using default base prompt")
    return _get_default_base_prompt()


def _get_default_base_prompt() -> str:
    """获取默认的基础prompt"""
    return """# 角色与任务

你是一位资深的投标文件审核专家。你的任务是：

**📋 核心目标**：针对下方提供的招标要求列表，逐条从投标文档中提取对应的响应内容。

**⚠️ 关键原则**：
1. **需求驱动**：只提取招标要求中明确需要的内容，避免过度提取
2. **一一对应**：每条响应应对应一个招标要求，确保完整覆盖
3. **精准匹配**：响应的维度(dimension)和norm_key必须与招标要求一致

## 提取流程

### Step 1: 阅读招标要求
- 仔细阅读下方的"招标要求清单"
- 理解每条要求的维度(dimension)和norm_key
- 识别硬性要求（带▲标识）

### Step 2: 检索投标文档
- 针对每条招标要求，在投标文档中搜索对应的响应内容
- 注意：响应可能在不同章节、不同位置
- 特别关注带▲★●※符号的投标文档内容

### Step 3: 提取响应
- **一一对应**：每条招标要求对应一条响应
- **维度匹配**：响应的dimension必须与招标要求一致
- **norm_key匹配**：如果招标要求有norm_key，响应的_norm_key必须相同
- **保留符号**：投标文档中的▲★●※符号必须保留在response_text中

### Step 4: 质量检查
- 响应数量是否覆盖大部分招标要求（80%-120%）
- 每条响应是否有evidence_segment_ids
- 每条响应是否有_norm_key字段（即使为null）
- dimension分类是否正确

## 核心原则

### 1. 需求驱动（最重要）
- ✅ **只提取招标要求中明确需要的内容**
- ✅ **招标要求没提到的，不要主动提取**（如：注册资本、公司地址）
- ✅ **按招标要求的维度和norm_key组织响应**

### 2. 完整性与精准性平衡
- **保留关键信息**：证书号、有效期、页码、金额、时间等
- **避免冗余**：同一内容不要重复提取
- **文本长度适中**：简单证件10-30字，数值20-50字，方案80-150字

### 3. 特别关注符号标识 ⚠️
- **▲ 三角形**：实质性承诺、关键指标、重要证明
- **★ 星号**：重点响应、核心优势
- **● 圆点**：具体承诺条款
- **※ 特殊符号**：特别说明内容
- 带符号内容必须完整提取并保留符号

### 4. 维度匹配
- **qualification（资格）**：证照、资质、业绩、人员
- **technical（技术）**：参数、规格、方案
- **business（商务）**：质保、售后、培训、付款
- **price（价格）**：总价、单价、报价明细
- **doc_structure（文档）**：装订、签章、份数
- **schedule_quality（工期）**：工期、进度、质量
- **other（其他）**：仅当无法分类时使用

## 输出格式

返回JSON对象：
```json
{
  "responses": [
    {
      "response_id": "resp_001",
      "requirement_id": "对应的招标要求ID（从上方清单中复制）",
      "dimension": "与招标要求的dimension一致",
      "response_type": "direct_answer|table_extract|document_ref|promise|missing",
      "response_text": "响应内容（保留完整信息，包括符号标识、证书号、有效期、金额、时间、页码等）",
      "extracted_value_json": {
        "value": "具体值",
        "unit": "单位",
        "status": "符合|不符合|未提供|偏离"
      },
      "normalized_fields_json": {
        "_norm_key": "与招标要求的norm_key一致（如：total_price_cny、duration_days等）",
        "total_price_cny": 1560000,
        "duration_days": 90
      },
      "evidence_segment_ids": ["seg_xxx", "seg_yyy"]
    }
  ]
}
```

**⚠️ 关键字段说明**：
- `requirement_id`：**必填**，标识该响应对应哪条招标要求
- `dimension`：**必须与招标要求的dimension一致**
- `_norm_key`：**必须与招标要求的norm_key一致**（如果招标要求有norm_key）
- `evidence_segment_ids`：**必填**，标识响应内容的来源段落

## 示例（参考理解方式）

**示例1：资格响应（对应招标要求）**
假设招标要求为："投标人须具备建筑工程施工总承包二级及以上资质"
```json
{
  "response_id": "resp_001",
  "requirement_id": "checklist_qualification_003",
  "dimension": "qualification",
  "response_type": "document_ref",
  "response_text": "▲建筑工程施工总承包二级资质，证书编号：D233012345678，有效期至2026年12月31日，见附件2资质证书复印件（加盖公章）",
  "normalized_fields_json": {
    "_norm_key": "doc_qualification_present",
    "doc_qualification_present": true
  },
  "evidence_segment_ids": ["seg_012", "seg_013"]
}
```

**示例2：工期响应（匹配norm_key）**
假设招标要求为："工期不超过90天"，norm_key为`duration_days`
```json
{
  "response_id": "resp_002",
  "requirement_id": "checklist_schedule_001",
  "dimension": "schedule_quality",
  "response_type": "direct_answer",
  "response_text": "承诺工期90个日历天，自合同签订之日起计算，见报价文件第3页",
  "normalized_fields_json": {
    "_norm_key": "duration_days",
    "duration_days": 90
  },
  "evidence_segment_ids": ["seg_045"]
}
```

**示例3：价格响应（匹配norm_key）**
假设招标要求为："投标报价"，norm_key为`total_price_cny`
```json
{
  "response_id": "resp_003",
  "requirement_id": "checklist_price_001",
  "dimension": "price",
  "response_type": "direct_answer",
  "response_text": "投标总价：人民币36,799,949.77元（大写：叁仟陆佰柒拾玖万玖仟玖佰肆拾玖元柒角柒分），见开标一览表",
  "normalized_fields_json": {
    "_norm_key": "total_price_cny",
    "total_price_cny": 36799949.77
  },
  "evidence_segment_ids": ["seg_089"]
}
```

## 最终检查

提取完成后，请自检：
1. ✅ **每条响应是否都有requirement_id**？（标识对应的招标要求）
2. ✅ **响应数量是否与招标要求数量接近**？（80%-120%覆盖率）
3. ✅ **dimension和norm_key是否与招标要求一致**？
4. ✅ 所有带特殊符号（▲★●※等）的招标要求都有响应吗？
5. ✅ response_text是否包含足够信息（证书号、有效期、页码、金额、时间等）？
6. ✅ 每条响应是否都有evidence_segment_ids？
7. ✅ 是否避免了提取招标文件未要求的信息（如注册资本、地址等）？

---

**下方将提供招标要求清单和提取指南，请严格按照招标要求逐条提取响应。**
"""


def _generate_targeted_queries(
    requirements: List[Dict[str, Any]], 
    extraction_guide: Dict[str, Any]
) -> Dict[str, str]:
    """
    生成针对性检索查询
    
    只为requirements中出现的维度生成查询，避免无用检索
    
    Args:
        requirements: 招标要求列表
        extraction_guide: 提取指南
    
    Returns:
        查询字典 {query_key: query_string}
    """
    queries = {}
    
    # 1. 统计requirements中的维度
    dimensions_in_requirements = set()
    for req in requirements:
        dim = req.get("dimension", "")
        if dim and dim != "out_of_scope":
            dimensions_in_requirements.add(dim)
    
    logger.info(f"Dimensions in requirements: {dimensions_in_requirements}")
    
    # 2. 为每个维度生成增强的查询
    dimension_focus = extraction_guide.get("dimension_focus", {})
    
    for dimension in dimensions_in_requirements:
        focus = dimension_focus.get(dimension, {})
        keywords = focus.get("focus_keywords", [])
        
        # 基础查询词
        base_queries = {
            "qualification": "投标人资格 公司资质 营业执照 资质证书 业绩证明 项目经验 人员配置 财务状况",
            "technical": "技术参数 技术规格 设备配置 性能指标 技术方案 技术响应",
            "business": "商务响应 质保期 售后服务 付款条件 验收标准 培训计划",
            "price": "投标报价 报价表 投标总价 价格明细 报价汇总 开标一览表",
            "doc_structure": "投标文件 文件格式 装订要求 签字盖章 正本副本",
            "schedule_quality": "工期承诺 施工进度 质量保证 验收标准 里程碑计划",
            "evaluation": "评分响应 评分说明",
        }
        
        base_query = base_queries.get(dimension, dimension)
        
        # 如果有focus关键词，追加到查询中
        if keywords:
            enhanced_query = base_query + " " + " ".join(keywords)
        else:
            enhanced_query = base_query
        
        queries[dimension] = enhanced_query
    
    # 3. 为必须提取的norm_keys添加专门查询
    must_extract_keys = extraction_guide.get("must_extract_norm_keys", [])
    
    norm_key_queries = {
        "total_price_cny": "投标报价 投标总价 报价表 开标一览表 报价汇总",
        "duration_days": "工期 工期承诺 施工周期 完成期限",
        "warranty_months": "质保期 保修期 质量保证期",
        "bid_security_amount_cny": "投标保证金 保证金金额 保证金缴纳",
        "company_name": "投标人 公司名称 投标单位",
    }
    
    for norm_key in must_extract_keys:
        if norm_key in norm_key_queries:
            query_key = f"norm_key_{norm_key}"
            queries[query_key] = norm_key_queries[norm_key]
    
    logger.info(f"Generated {len(queries)} targeted queries")
    
    return queries

