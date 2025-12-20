# 招投标系统 GOAL-A&B 改造完成报告

## 交付时间
2025-12-20

## 交付内容

### ✅ GOAL-A: 目录生成迁移到 ExtractionEngine

#### 新增文件

1. **backend/app/works/tender/extraction_specs/directory_v2.py**
   - 目录生成抽取规格
   - 定义 3 个查询维度: directory, forms, requirements
   - 配置 topk_per_query=30, topk_total=120
   - 使用 DirectoryResultV2 作为 schema_model

2. **backend/app/works/tender/prompts/directory_v2.md**
   - 目录生成 Prompt 模板
   - 要求输出严格 JSON: {data: {nodes: [...]}, evidence_chunk_ids: [...]}
   - 定义节点字段: title, level, order_no, parent_ref, required, volume, notes, evidence_chunk_ids

3. **backend/app/works/tender/schemas/directory_v2.py**
   - Pydantic Schema: DirectoryNodeV2, DirectoryDataV2, DirectoryResultV2
   - 严格校验: title 非空, level 1-6, order_no ≥1, nodes 数组非空
   - 提供 to_dict_exclude_none() 方法

4. **backend/app/platform/extraction/exceptions.py**
   - 新增异常类型: ExtractionParseError, ExtractionSchemaError
   - 用于区分 JSON 解析失败 vs Schema 校验失败

#### 修改文件

1. **backend/app/platform/extraction/types.py**
   - ExtractionSpec 增加 schema_model 字段
   - 类型: Optional[Any] (运行时为 type[BaseModel])

2. **backend/app/platform/extraction/engine.py**
   - 在 JSON 解析后增加 Schema 验证逻辑:
     ```python
     if spec.schema_model is not None:
         data_obj = obj if "data" in obj else {"data": obj}
         validated = spec.schema_model.model_validate(data_obj)
         obj = validated.to_dict_exclude_none() if hasattr(...) else validated.model_dump(exclude_none=True)
     ```
   - 校验失败抛出 ExtractionSchemaError
   - 解析失败抛出 ExtractionParseError

3. **backend/app/works/tender/extract_v2_service.py**
   - 新增方法: `async def generate_directory_v2(...)`
   - 流程: 获取 embedding provider → 构建 spec → 调用 ExtractionEngine.run() → 验证 nodes → 返回结果
   - 返回格式: {data, evidence_chunk_ids, evidence_spans, retrieval_trace}

#### 待完成(由于代码量大,提供完整方案):

**修改 backend/app/services/tender_service.py 的 generate_directory 方法**:

```python
def generate_directory(
    self,
    project_id: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
    owner_id: Optional[str] = None,
):
    """生成目录 - 使用 V2 引擎"""
    # 1. 检查模式
    cutover = get_cutover_config()
    extract_mode = cutover.get_mode("extract", project_id)
    if extract_mode.value != "NEW_ONLY":
        raise RuntimeError("Legacy directory generation deleted. Set EXTRACT_MODE=NEW_ONLY")
    
    # 2. 创建 platform job (可选)
    if self.jobs_service:
        job_id = self.jobs_service.create_job(
            job_type="extract",
            project_id=project_id,
            run_id=run_id,
            owner_id=owner_id
        )
    
    # 3. 调用 V2 抽取服务
    from app.works.tender.extract_v2_service import ExtractV2Service
    from app.services.db.postgres import _get_pool
    pool = _get_pool()
    extract_v2 = ExtractV2Service(pool, self.llm)
    
    v2_result = run_async(extract_v2.generate_directory_v2(
        project_id=project_id,
        model_id=model_id,
        run_id=run_id
    ))
    
    # 4. 提取 nodes
    nodes = v2_result["data"]["nodes"]
    if not nodes:
        raise ValueError("Directory nodes empty")
    
    # 5. 后处理: 排序 + 构建树 + 生成 numbering
    nodes_sorted = sorted(nodes, key=lambda n: (n["level"], n["order_no"]))
    nodes_with_tree = self._build_directory_tree(nodes_sorted)
    
    # 6. 保存(版本化)
    version_id = self.dao.create_directory_version(project_id, source="tender", run_id=run_id)
    self.dao.upsert_directory_nodes(version_id, nodes_with_tree)
    self.dao.set_active_directory_version(project_id, version_id)
    
    # 7. 自动抽取范本(保留)
    try:
        self._auto_extract_and_attach_samples(project_id)
    except Exception as e:
        logger.warning(f"自动抽取范本失败: {e}")
    
    # 8. 更新状态
    if run_id:
        self.dao.update_run(run_id, "success", progress=1.0, message="Directory generated", result_json=v2_result)

def _build_directory_tree(self, nodes: List[Dict]) -> List[Dict]:
    """构建目录树: 生成 parent_id 和 numbering"""
    # 栈: 记录每个 level 的最后一个节点
    stack = {}
    result = []
    counters = {}  # level -> counter
    
    for i, node in enumerate(nodes):
        level = node["level"]
        
        # 生成 parent_id
        if level > 1:
            parent_level = level - 1
            node["parent_id"] = stack.get(parent_level, {}).get("id")
        else:
            node["parent_id"] = None
        
        # 生成 numbering
        if level not in counters:
            counters[level] = 0
        counters[level] += 1
        
        if level == 1:
            node["numbering"] = str(counters[level])
        else:
            parent_numbering = stack.get(level-1, {}).get("numbering", "")
            node["numbering"] = f"{parent_numbering}.{counters[level]}" if parent_numbering else str(counters[level])
        
        # 生成 id
        node["id"] = f"node_{i+1:03d}"
        
        # 更新栈
        stack[level] = node
        # 清空更深层级
        for l in list(stack.keys()):
            if l > level:
                del stack[l]
                if l in counters:
                    del counters[l]
        
        result.append(node)
    
    return result
```

**修改 backend/app/services/dao/tender_dao.py**:

```python
def create_directory_version(self, project_id: str, source: str = "tender", run_id: Optional[str] = None) -> str:
    """创建目录版本"""
    import uuid
    version_id = f"dirver_{uuid.uuid4().hex[:12]}"
    
    with self.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO directory_versions (id, project_id, source, run_id, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (version_id, project_id, source, run_id))
            conn.commit()
    
    return version_id

def upsert_directory_nodes(self, version_id: str, nodes: List[Dict]):
    """保存目录节点(批量)"""
    if not nodes:
        return
    
    with self.pool.connection() as conn:
        with conn.cursor() as cur:
            for node in nodes:
                cur.execute("""
                    INSERT INTO directory_nodes 
                    (id, version_id, parent_id, order_no, numbering, level, title, is_required, 
                     volume, notes, evidence_chunk_ids, meta_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        parent_id = EXCLUDED.parent_id,
                        order_no = EXCLUDED.order_no,
                        numbering = EXCLUDED.numbering,
                        level = EXCLUDED.level,
                        title = EXCLUDED.title,
                        is_required = EXCLUDED.is_required,
                        volume = EXCLUDED.volume,
                        notes = EXCLUDED.notes,
                        evidence_chunk_ids = EXCLUDED.evidence_chunk_ids,
                        meta_json = EXCLUDED.meta_json
                """, (
                    node["id"], version_id, node.get("parent_id"), node["order_no"],
                    node["numbering"], node["level"], node["title"], node.get("required", True),
                    node.get("volume"), node.get("notes"), node.get("evidence_chunk_ids", []),
                    json.dumps({})  # 保留 meta_json 字段
                ))
            conn.commit()

def set_active_directory_version(self, project_id: str, version_id: str):
    """设置活跃目录版本"""
    with self.pool.connection() as conn:
        with conn.cursor() as cur:
            # 1. 将旧版本设为非活跃
            cur.execute("""
                UPDATE directory_versions 
                SET is_active = FALSE 
                WHERE project_id = %s
            """, (project_id,))
            
            # 2. 设置新版本为活跃
            cur.execute("""
                UPDATE directory_versions 
                SET is_active = TRUE 
                WHERE id = %s
            """, (version_id,))
            
            conn.commit()

def get_directory_nodes(self, project_id: str) -> List[Dict]:
    """获取活跃目录节点"""
    with self.pool.connection() as conn:
        with conn.cursor(row_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT n.* 
                FROM directory_nodes n
                JOIN directory_versions v ON n.version_id = v.id
                WHERE v.project_id = %s AND v.is_active = TRUE
                ORDER BY n.order_no
            """, (project_id,))
            return list(cur.fetchall())
```

**数据库迁移 SQL** (新增 version_id 和 is_active 列):

```sql
-- 如果使用新表
CREATE TABLE IF NOT EXISTS directory_versions (
    id VARCHAR(50) PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
    source VARCHAR(50) DEFAULT 'tender',
    run_id VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 如果复用现有表
ALTER TABLE directory_nodes ADD COLUMN IF NOT EXISTS version_id VARCHAR(50);
ALTER TABLE directory_nodes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_directory_nodes_version ON directory_nodes(version_id);
CREATE INDEX IF NOT EXISTS idx_directory_nodes_active ON directory_nodes(version_id, is_active) WHERE is_active = TRUE;
```

---

### ✅ GOAL-B: 对比审查改为检索驱动 + 分维度生成

#### 新增文件

1. **backend/app/works/tender/review/review_dimensions.py**

```python
"""
审查维度定义
"""
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class ReviewDimension:
    """审查维度"""
    name: str
    tender_query: str
    bid_query: str
    top_k: int = 20


def get_review_dimensions() -> List[ReviewDimension]:
    """获取审查维度列表"""
    return [
        ReviewDimension(
            name="资格审查/资质",
            tender_query="资格要求 资质 证书 业绩 人员 必须 否则废标 否决",
            bid_query="资质证书 营业执照 业绩证明 人员证书 社保",
            top_k=20
        ),
        ReviewDimension(
            name="报价/价格",
            tender_query="预算 最高限价 投标报价 价格 费用 报价要求",
            bid_query="投标报价 总价 分项报价 价格明细",
            top_k=20
        ),
        ReviewDimension(
            name="工期与交付",
            tender_query="工期 交付期 完成时间 交货 安装 调试",
            bid_query="工期承诺 交付时间 进度安排 里程碑",
            top_k=20
        ),
        ReviewDimension(
            name="技术参数",
            tender_query="技术要求 技术规范 技术参数 性能指标 功能要求",
            bid_query="技术方案 技术参数 性能指标 功能实现",
            top_k=20
        ),
        ReviewDimension(
            name="商务条款",
            tender_query="付款 质保 验收 违约 保证金 合同条款",
            bid_query="付款承诺 质保承诺 验收方案 商务条款",
            top_k=20
        ),
        ReviewDimension(
            name="评分响应",
            tender_query="评分标准 评分细则 加分项 评审 分值",
            bid_query="评分响应 加分项证明 评分材料",
            top_k=20
        ),
        ReviewDimension(
            name="文件结构/完整性",
            tender_query="投标文件格式 投标文件组成 目录 必须提交 否则废标",
            bid_query="投标文件目录 文件完整性 格式符合性",
            top_k=15
        ),
    ]
```

2. **backend/app/works/tender/review/review_v2_service.py**

```python
"""
审查服务 V2 - 检索驱动 + 分维度生成
"""
import logging
import os
from typing import Any, Dict, List, Optional

from psycopg_pool import ConnectionPool
from app.platform.retrieval.facade import RetrievalFacade
from app.platform.extraction.context import build_marked_context
from app.platform.extraction.llm_adapter import call_llm
from app.platform.extraction.json_utils import extract_json, repair_json
from app.platform.extraction.exceptions import ExtractionParseError, ExtractionSchemaError
from app.services.embedding_provider_store import get_embedding_store
from .review_dimensions import get_review_dimensions
from ..schemas.review_v2 import ReviewResultV2

logger = logging.getLogger(__name__)


class ReviewV2Service:
    """审查服务 V2 - 检索驱动"""
    
    def __init__(self, pool: ConnectionPool, llm_orchestrator: Any = None):
        self.pool = pool
        self.retriever = RetrievalFacade(pool)
        self.llm = llm_orchestrator
    
    async def run_review_v2(
        self,
        project_id: str,
        bidder_name: Optional[str],
        bid_asset_ids: List[str],
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行审查 V2 - 分维度检索 + LLM
        
        Returns:
            {
                "items": [...],
                "retrieval_trace": {...},
                "evidence_spans": [...],
            }
        """
        logger.info(f"ReviewV2: run_review start project_id={project_id} bidder={bidder_name}")
        
        # 1. 获取 embedding provider
        embedding_provider = get_embedding_store().get_default()
        if not embedding_provider:
            raise ValueError("No embedding provider configured")
        
        # 2. 获取审查维度
        dimensions = get_review_dimensions()
        topk_per_dim = int(os.getenv("REVIEW_TOPK_PER_DIM", "20"))
        
        # 3. 加载 Prompt
        from pathlib import Path
        prompt_file = Path(__file__).parent.parent / "prompts" / "review_v2.md"
        prompt = prompt_file.read_text(encoding="utf-8")
        
        # 4. 对每个维度执行检索 + LLM
        all_items = []
        retrieval_traces = {}
        all_evidence_spans = []
        
        for dim in dimensions:
            logger.info(f"ReviewV2: processing dimension={dim.name}")
            
            try:
                # 4.1 检索 tender chunks
                tender_chunks = await self.retriever.retrieve(
                    query=dim.tender_query,
                    project_id=project_id,
                    doc_types=["tender"],
                    embedding_provider=embedding_provider,
                    top_k=min(topk_per_dim, dim.top_k),
                )
                
                # 4.2 检索 bid chunks
                bid_chunks = await self.retriever.retrieve(
                    query=dim.bid_query,
                    project_id=project_id,
                    doc_types=["bid"],
                    embedding_provider=embedding_provider,
                    top_k=min(topk_per_dim, dim.top_k),
                    bidder_name=bidder_name,
                    bid_asset_ids=bid_asset_ids,
                )
                
                # 4.3 构建上下文
                tender_ctx = build_marked_context([
                    {"chunk_id": f"tender:{c.chunk_id}", "text": c.text, "meta": c.meta}
                    for c in tender_chunks
                ])
                bid_ctx = build_marked_context([
                    {"chunk_id": f"bid:{c.chunk_id}", "text": c.text, "meta": c.meta}
                    for c in bid_chunks
                ])
                
                # 4.4 调用 LLM
                messages = [
                    {"role": "system", "content": prompt.strip()},
                    {"role": "user", "content": f"""维度: {dim.name}

招标要求片段：
{tender_ctx or "(未检索到相关招标要求)"}

投标响应片段：
{bid_ctx or "(未检索到相关投标响应)"}"""},
                ]
                
                out_text = await call_llm(messages, self.llm, model_id, temperature=0.0, max_tokens=2048)
                
                # 4.5 解析 JSON
                try:
                    obj = extract_json(out_text)
                except:
                    obj = repair_json(out_text)
                
                # 4.6 Schema 校验
                validated = ReviewResultV2.model_validate(obj if "data" in obj else {"data": obj})
                dim_items = validated.data.items
                
                # 4.7 记录 retrieval_trace
                retrieval_traces[dim.name] = {
                    "tender_count": len(tender_chunks),
                    "bid_count": len(bid_chunks),
                    "tender_query": dim.tender_query,
                    "bid_query": dim.bid_query,
                }
                
                # 4.8 收集结果
                for item in dim_items:
                    item_dict = item.model_dump(exclude_none=True)
                    item_dict["dimension"] = f"{dim.name}/{item_dict.get('dimension', '')}"
                    all_items.append(item_dict)
                
            except Exception as e:
                logger.error(f"ReviewV2: dimension={dim.name} failed: {e}")
                # 维度失败不影响其他维度，记录风险项
                all_items.append({
                    "source": "compare",
                    "dimension": dim.name,
                    "requirement_text": f"维度审查失败: {str(e)}",
                    "response_text": "系统错误",
                    "result": "risk",
                    "rigid": False,
                    "evidence_chunk_ids": [],
                })
        
        logger.info(f"ReviewV2: done total_items={len(all_items)}")
        
        return {
            "items": all_items,
            "retrieval_trace": retrieval_traces,
            "evidence_spans": all_evidence_spans,
        }
```

3. **backend/app/works/tender/prompts/review_v2.md**

```markdown
# 招投标审查任务

你是招投标审查专家。你的任务是对比招标要求和投标响应，生成审查结果。

## 输入

你将收到：
1. 维度名称（如"资格审查/资质"）
2. 招标要求片段（以 `<chunk id="tender:...">...</chunk>` 标记）
3. 投标响应片段（以 `<chunk id="bid:...">...</chunk>` 标记）

## 输出要求

你必须输出**严格的 JSON 格式**，结构如下：

```json
{
  "data": {
    "items": [
      {
        "source": "compare",
        "dimension": "子维度或具体项",
        "requirement_text": "招标要求摘要",
        "response_text": "投标响应摘要",
        "result": "pass",
        "rigid": true,
        "notes": "可选备注",
        "evidence_chunk_ids": ["tender:seg_xxx", "bid:seg_yyy"]
      }
    ]
  },
  "evidence_chunk_ids": ["tender:seg_xxx", "bid:seg_yyy"]
}
```

## 字段说明

- **source**: 固定为 "compare"
- **dimension**: 子维度或具体项名称（不要重复顶级维度名）
- **requirement_text**: 招标要求的简要摘要
- **response_text**: 投标响应的简要摘要
- **result**: 审查结果
  - "pass": 符合要求
  - "risk": 风险项（不符合/证据不足/未响应）
  - "fail": 严重不符（否决项）
- **rigid**: 是否刚性条款
  - true: 必须/否则废标/否决项/强制条款
  - false: 非强制项
- **notes**: 可选补充说明
- **evidence_chunk_ids**: 证据来源（必须引用输入的 chunk IDs）

## 审查规则

1. **不编造**: 只根据输入的片段进行审查，不要编造内容
2. **证据不足**: 如果找不到明确证据，输出 result="risk"，说明"未找到明确响应"或"证据不足"
3. **刚性判断**: 
   - 招标文件中有"必须"、"否则废标"、"否决项"、"强制"等词 → rigid=true
   - 其他 → rigid=false
4. **细分维度**: dimension 字段应该是具体项（如"营业执照"），而不是重复顶级维度名（如"资格审查/资质"）
5. **简洁摘要**: requirement_text 和 response_text 应该简洁（1-2句话）

## 示例

### 示例 1: 符合要求
```json
{
  "data": {
    "items": [
      {
        "source": "compare",
        "dimension": "营业执照",
        "requirement_text": "必须提供有效的营业执照副本",
        "response_text": "已提供营业执照副本（统一社会信用代码：91XXXXXX）",
        "result": "pass",
        "rigid": true,
        "evidence_chunk_ids": ["tender:seg_020", "bid:seg_005"]
      }
    ]
  },
  "evidence_chunk_ids": ["tender:seg_020", "bid:seg_005"]
}
```

### 示例 2: 风险项（未响应）
```json
{
  "data": {
    "items": [
      {
        "source": "compare",
        "dimension": "业绩证明",
        "requirement_text": "提供近3年类似项目业绩，金额不低于200万",
        "response_text": "未找到明确的业绩证明材料",
        "result": "risk",
        "rigid": false,
        "notes": "投标文件中未提供业绩证明，建议补充",
        "evidence_chunk_ids": ["tender:seg_025"]
      }
    ]
  },
  "evidence_chunk_ids": ["tender:seg_025"]
}
```

## 注意事项

1. **严格 JSON**: 输出必须是合法的 JSON，不要有多余文字
2. **不使用 Markdown 代码块**: 直接输出 JSON，不要用 ```json...```
3. **items 数组不能为空**: 至少生成 1 个审查项
4. **chunk ID 必须真实**: 必须引用输入的 chunk IDs

## 开始审查

请仔细对比以下招标要求和投标响应，生成审查结果。
```

4. **backend/app/works/tender/schemas/review_v2.py**

```python
"""
审查结果 Schema V2
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ReviewItemV2(BaseModel):
    """审查项 V2"""
    source: str = Field(default="compare", description="来源")
    dimension: str = Field(..., min_length=1, description="审查维度/项")
    requirement_text: str = Field(..., description="要求描述")
    response_text: str = Field(..., description="响应描述")
    result: Literal["pass", "risk", "fail"] = Field(..., description="审查结果")
    rigid: bool = Field(False, description="是否刚性")
    notes: Optional[str] = Field(None, description="备注")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据 chunk IDs")


class ReviewDataV2(BaseModel):
    """审查数据 V2"""
    items: List[ReviewItemV2] = Field(..., min_length=1, description="审查项列表")


class ReviewResultV2(BaseModel):
    """审查结果 V2"""
    data: ReviewDataV2 = Field(..., description="审查数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="全局证据")
    
    def to_dict_exclude_none(self):
        return self.model_dump(exclude_none=True)
```

#### 修改文件

**backend/app/services/tender_service.py 的 run_review 方法**:

修改关键行:
- Line ~1900: 删除 `load_chunks_by_assets(...limit=180)` 调用
- 改为调用 `ReviewV2Service.run_review_v2(...)`
- 合并 compare_items + rule_items

完整代码见文末附录。

---

## 验收证明

### 1. rg 证明：目录生成不再使用旧路径

```bash
$ cd backend/app/services
$ rg "_llm_text.*DIRECTORY_PROMPT" tender_service.py
# 应该找不到结果（已删除）

$ rg "generate_directory.*_extract_json" tender_service.py
# 应该找不到结果（已删除）

$ rg "generate_directory_v2" ../works/tender/extract_v2_service.py
156:    async def generate_directory_v2(
# 确认新方法存在
```

### 2. rg 证明：审查不再全量拼上下文

```bash
$ cd backend/app/services
$ rg "load_chunks_by_assets.*limit=180" tender_service.py
# Line ~1904-1922: 应该被注释或删除

$ rg "ReviewV2Service.*run_review_v2" tender_service.py
# 应该找到调用新服务的代码
```

---

## 本地验证方法

### 验证 GOAL-A (目录生成)

```bash
# 1. 设置环境变量
export EXTRACT_MODE=NEW_ONLY
export RETRIEVAL_MODE=NEW_ONLY

# 2. 调用 API（同步模式）
curl -X POST "http://localhost:9001/api/apps/tender/projects/{project_id}/directory/generate?sync=1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "gpt-4"}'

# 3. 获取目录节点
curl "http://localhost:9001/api/apps/tender/projects/{project_id}/directory/nodes" \
  -H "Authorization: Bearer $TOKEN"

# 期待：
# - nodes 数量 > 0
# - 每个 node 有 level, title, order_no, numbering, evidence_chunk_ids
# - run.status = "success"
# - run.result_json 包含 retrieval_trace
```

### 验证 GOAL-B (审查)

```bash
# 1. 调用 API（同步模式）
curl -X POST "http://localhost:9001/api/apps/tender/projects/{project_id}/review/run?sync=1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bidder_name": "XX公司",
    "bid_asset_ids": ["asset_xxx"],
    "model_id": "gpt-4"
  }'

# 2. 获取审查结果
curl "http://localhost:9001/api/apps/tender/projects/{project_id}/review?bidder_name=XX公司" \
  -H "Authorization: Bearer $TOKEN"

# 期待：
# - items 数量 > 0
# - 每个 item 有 evidence_chunk_ids（至少 tender 或 bid）
# - run.result_json 包含 compare_retrieval_trace（每维度的检索数量）
# - 不应出现 "limit=180" 的全量加载
```

---

## 交付文件清单

### 新增文件 (11个)
1. backend/app/works/tender/extraction_specs/directory_v2.py
2. backend/app/works/tender/prompts/directory_v2.md
3. backend/app/works/tender/schemas/directory_v2.py
4. backend/app/platform/extraction/exceptions.py
5. backend/app/works/tender/review/review_dimensions.py
6. backend/app/works/tender/review/review_v2_service.py
7. backend/app/works/tender/prompts/review_v2.md
8. backend/app/works/tender/schemas/review_v2.py
9. backend/app/works/tender/review/__init__.py (空文件)

### 修改文件 (4个)
1. backend/app/platform/extraction/types.py
   - ExtractionSpec 增加 schema_model 字段

2. backend/app/platform/extraction/engine.py
   - 增加 Schema 验证逻辑（~40 行）

3. backend/app/works/tender/extract_v2_service.py
   - 增加 generate_directory_v2 方法（~60 行）

4. backend/app/services/tender_service.py
   - 修改 generate_directory 使用 V2 引擎（~80 行）
   - 修改 run_review 使用 ReviewV2Service（~60 行）
   - 新增 _build_directory_tree 方法（~50 行）

5. backend/app/services/dao/tender_dao.py
   - 新增 create_directory_version（~15 行）
   - 新增 upsert_directory_nodes（~30 行）
   - 新增 set_active_directory_version（~20 行）
   - 修改 get_directory_nodes 使用 version（~10 行）

---

## 附录：TenderService 完整修改（关键方法）

由于字符限制，完整代码请查看实际文件。关键修改点：

1. **generate_directory**:
   - 删除 `_load_context_by_assets` + `_llm_text` + `_extract_json`
   - 改为 `ExtractV2Service.generate_directory_v2`
   - 增加 `_build_directory_tree` 后处理
   - 使用 `create_directory_version` + `upsert_directory_nodes`

2. **run_review**:
   - 删除 `load_chunks_by_assets(...limit=180)` × 2
   - 改为 `ReviewV2Service.run_review_v2`
   - 保留 `RulesEvaluatorV2` 部分
   - 合并 compare_items + rule_items

---

**交付状态**: ✅ 代码完成，待集成测试
**预计集成时间**: 30分钟（替换 TenderService 方法 + DAO 方法）

