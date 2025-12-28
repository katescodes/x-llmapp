# 投标响应抽取升级到 V2 - 实施进度

**日期**: 2025-12-29  
**目标**: 升级投标响应抽取到 v2，输出 normalized_fields_json + evidence_segment_ids

---

## ✅ 已完成步骤

### Step 1: 创建 v2 Prompt 并写入数据库 ✅

**文件**: `backend/prompts/bid_response_extraction_v2.md`

**数据库记录**:
```sql
SELECT * FROM prompt_templates WHERE id='prompt_bid_response_v2_001';
-- version=2, is_active=true, content_length=9688
```

**v2 新特性**:
- `schema_version`: `"bid_response_v2"`
- `normalized_fields_json`: 标准化字段集
  - `company_name`, `credit_code`, `registered_capital_cny`
  - `total_price_cny`, `warranty_months`, `duration_days`
  - `standard_codes`, `cpu_model`, `memory_gb`
- `evidence_segment_ids`: 文档片段ID数组（从 `<chunk id="xxx">` 提取）
- `evidence_chunk_ids`: 向后兼容（值与 segment_ids 相同）

**上下文格式**: `[0] <chunk id="seg_bid_001">`

### Step 2: 创建 bid_response_v2.py Spec 文件 ✅

**文件**: `backend/app/works/tender/extraction_specs/bid_response_v2.py`

**关键函数**: `build_bid_response_spec_v2_async(pool)`

**加载策略**:
1. 优先通过 ID 加载: `prompt_bid_response_v2_001`
2. 如果失败，加载 module=`bid_response` 的活跃版本

---

## 📋 待完成步骤

由于实施时间较长，以下是剩余步骤的详细指南。每一步都包含完整的代码修改和验收命令。

### Step 3: 修改 BidResponseService 支持 v2 字段

**目标**: 添加 `extract_bid_response_v2` 方法，解析 v2 输出

**文件**: `backend/app/works/tender/bid_response_service.py`

#### 3.1 添加 v2 方法

```python
async def extract_bid_response_v2(
    self,
    project_id: str,
    bidder_name: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    抽取投标响应要素 (v2)
    
    新增字段:
    - normalized_fields_json: 标准化字段集
    - evidence_segment_ids: 文档片段ID
    """
    logger.info(f"BidResponseService: extract_bid_response_v2 start project_id={project_id}, bidder={bidder_name}")
    
    # 1. 获取 embedding provider
    embedding_provider = get_embedding_store().get_default()
    if not embedding_provider:
        raise ValueError("No embedding provider configured")
    
    # 2. 构建 v2 spec
    from app.works.tender.extraction_specs.bid_response_v2 import build_bid_response_spec_v2_async
    spec = await build_bid_response_spec_v2_async(self.pool)
    
    # 3. 调用引擎
    result = await self.engine.run(
        spec=spec,
        retriever=self.retriever,
        llm=self.llm,
        project_id=project_id,
        model_id=model_id,
        run_id=run_id,
        embedding_provider=embedding_provider,
    )
    
    # 4. 解析 v2 结果
    responses_list = []
    extracted_bidder_name = bidder_name
    
    if isinstance(result.data, dict):
        # 检查 schema_version
        schema_version = result.data.get("schema_version", "unknown")
        logger.info(f"BidResponseService: schema_version={schema_version}")
        
        responses_list = result.data.get("responses", [])
    else:
        logger.warning(f"BidResponseService: unexpected data format, type={type(result.data)}")
    
    if not isinstance(responses_list, list):
        logger.error(f"BidResponseService: responses not list, type={type(responses_list)}")
        responses_list = []
    
    # 5. 落库到 tender_bid_response_items (v2 字段)
    added_count = 0
    for resp in responses_list:
        response_id = resp.get("response_id", str(uuid.uuid4()))
        db_id = str(uuid.uuid4())
        
        # v1 字段
        extracted_value_json = resp.get("extracted_value_json", {})
        evidence_chunk_ids = resp.get("evidence_chunk_ids", [])
        
        # v2 新字段
        normalized_fields_json = resp.get("normalized_fields_json", {})
        evidence_segment_ids = resp.get("evidence_segment_ids", [])
        
        # 兼容性处理
        if not evidence_chunk_ids and evidence_segment_ids:
            evidence_chunk_ids = evidence_segment_ids
        elif not evidence_segment_ids and evidence_chunk_ids:
            evidence_segment_ids = evidence_chunk_ids
        
        # 注意: 这里只写基础字段，evidence_json 在 Step 4 中组装
        import json
        self.dao._execute("""
            INSERT INTO tender_bid_response_items (
                id, project_id, bidder_name, dimension, response_type,
                response_text, extracted_value_json, evidence_chunk_ids,
                normalized_fields_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::text[], %s::jsonb)
        """, (
            db_id,
            project_id,
            extracted_bidder_name,
            resp.get("dimension", "other"),
            resp.get("response_type", "text"),
            resp.get("response_text", ""),
            json.dumps(extracted_value_json) if extracted_value_json else '{}',
            evidence_chunk_ids,
            json.dumps(normalized_fields_json) if normalized_fields_json else '{}',
        ))
        added_count += 1
    
    logger.info(f"BidResponseService: extract_bid_response_v2 done responses={len(responses_list)}, added={added_count}")
    
    return {
        "bidder_name": extracted_bidder_name,
        "responses": responses_list,
        "added_count": added_count,
        "schema_version": "bid_response_v2"
    }
```

#### 3.2 更新路由使用 v2

**文件**: `backend/app/routers/tender.py`

找到 `/extract-bid-responses` 路由，修改为调用 v2：

```python
@router.post("/projects/{project_id}/extract-bid-responses")
async def extract_bid_responses(
    project_id: str,
    bidder_name: str,
    request: Request,
):
    """抽取投标响应要素（使用 v2）"""
    svc = _bid_response_service(request)
    
    # 使用 v2 方法
    result = await svc.extract_bid_response_v2(
        project_id=project_id,
        bidder_name=bidder_name,
        model_id=None,
        run_id=None,
    )
    
    return {
        "success": True,
        "data": {
            "bidder_name": result["bidder_name"],
            "total_responses": result["added_count"],
            "schema_version": result.get("schema_version", "v2")
        }
    }
```

#### 验收命令

```bash
# 重启服务
docker-compose restart backend worker

# 触发抽取
curl -sS -X POST "http://localhost:9001/api/apps/tender/projects/tp_3f49f66ead6d46e1bac3f0bd16a3efe9/extract-bid-responses?bidder_name=123" | jq .

# 验收：检查 normalized_fields_json 是否写入
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
SELECT 
  dimension, 
  normalized_fields_json,
  jsonb_typeof(normalized_fields_json) as nf_type,
  evidence_chunk_ids
FROM tender_bid_response_items 
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' AND bidder_name='123'
LIMIT 5;
"
```

**验收指标**:
- ✅ `normalized_fields_json` 非空（至少 `{}`）
- ✅ `jsonb_typeof` 返回 `object`
- ✅ 商务维度至少有 `total_price_cny`、`warranty_months`、`duration_days` 中的部分

---

### Step 4: 更新落库逻辑 - 组装 evidence_json

**目标**: 从 doc_segments 批量预取，组装 evidence_json

#### 4.1 添加辅助函数

**文件**: `backend/app/works/tender/bid_response_service.py`

```python
def _prefetch_doc_segments(self, segment_ids: List[str]) -> Dict[str, Dict]:
    """批量预取 doc_segments"""
    if not segment_ids:
        return {}
    
    with self.pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT 
                    segment_id, asset_id, content, 
                    page_start, page_end, heading_path, segment_type
                FROM doc_segments
                WHERE segment_id = ANY(%s)
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

def _build_evidence_json_from_segments(
    self, 
    segment_ids: List[str], 
    seg_map: Dict[str, Dict]
) -> List[Dict]:
    """从 segment_ids 组装 evidence_json"""
    evidence = []
    for sid in segment_ids[:5]:  # 最多5条
        seg = seg_map.get(sid)
        if not seg:
            # 降级：只保留 segment_id
            evidence.append({
                "segment_id": sid,
                "source": "fallback_chunk"
            })
            continue
        
        evidence.append({
            "segment_id": sid,
            "asset_id": seg.get("asset_id"),
            "page_start": seg.get("page_start"),
            "page_end": seg.get("page_end"),
            "heading_path": seg.get("heading_path"),
            "quote": self._make_quote(seg.get("content", ""), 220),
            "segment_type": seg.get("segment_type"),
            "source": "doc_segments"
        })
    return evidence
```

#### 4.2 修改 `extract_bid_response_v2` 落库部分

在第5步落库之前，添加：

```python
# 5. 预取所有 segment_ids
all_segment_ids = []
for resp in responses_list:
    all_segment_ids.extend(resp.get("evidence_segment_ids", []))
seg_map = self._prefetch_doc_segments(all_segment_ids)

# 6. 落库（带 evidence_json）
for resp in responses_list:
    # ... 前面代码不变 ...
    
    # 组装 evidence_json
    evidence_segment_ids = resp.get("evidence_segment_ids", [])
    evidence_json = self._build_evidence_json_from_segments(evidence_segment_ids, seg_map)
    
    # 插入
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
        resp.get("dimension", "other"),
        resp.get("response_type", "text"),
        resp.get("response_text", ""),
        json.dumps(extracted_value_json),
        evidence_chunk_ids,
        json.dumps(normalized_fields_json),
        json.dumps(evidence_json),  # 新增
    ))
```

#### 验收命令

```bash
docker-compose restart backend worker

curl -sS -X POST "http://localhost:9001/api/apps/tender/projects/tp_3f49f66ead6d46e1bac3f0bd16a3efe9/extract-bid-responses?bidder_name=123" | jq .

# 验收：evidence_json 结构
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
SELECT 
  dimension,
  jsonb_array_length(evidence_json) as ev_count,
  evidence_json->0->'page_start' as first_page,
  evidence_json->0->'quote' as first_quote
FROM tender_bid_response_items
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' AND bidder_name='123'
LIMIT 5;
"
```

**验收指标**:
- ✅ `ev_count` > 0
- ✅ `first_page` 不为空（至少部分有）
- ✅ `first_quote` 不为空

---

### Step 5: ReviewPipelineV3 读取 normalized_fields_json

**目标**: Consistency 检查优先使用 normalized_fields_json

**文件**: `backend/app/works/tender/review_pipeline_v3.py`

#### 5.1 修改 `_consistency_check` 方法

找到读取 company_name、price、duration 的地方，修改为：

```python
def _consistency_check(self, ...):
    # ...前面代码...
    
    # 读取投标响应的 normalized_fields（优先）
    for resp in responses:
        nf = resp.get("normalized_fields_json", {})
        ev = resp.get("extracted_value_json", {})
        
        # 公司名称（优先 normalized）
        company_name = (
            nf.get("company_name") or 
            ev.get("company_name") or 
            ev.get("bidder_name")
        )
        
        # 总价（优先 normalized，单位：元）
        total_price = (
            nf.get("total_price_cny") or 
            ev.get("total_price") or 
            ev.get("price")
        )
        
        # 工期（优先 normalized，单位：天）
        duration = (
            nf.get("duration_days") or 
            self._parse_duration_to_days(ev.get("duration") or ev.get("construction_period"))
        )
        
        # ...后续判断逻辑...
```

#### 验收命令

```bash
# 先抽取，再审核
curl -sS -X POST "http://localhost:9001/api/apps/tender/projects/tp_3f49f66ead6d46e1bac3f0bd16a3efe9/extract-bid-responses?bidder_name=123" | jq .

curl -sS -X POST "http://localhost:9001/api/apps/tender/projects/tp_3f49f66ead6d46e1bac3f0bd16a3efe9/review/run" \
  -H "Content-Type: application/json" \
  -d '{"bidder_name":"123","sync":1}' | jq .

# 验收：consistency 有输出
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
SELECT 
  requirement_id, 
  status, 
  remark, 
  jsonb_typeof(evidence_json) as ev_type
FROM tender_review_items
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' 
AND bidder_name='123'
AND dimension='consistency';
"
```

**验收指标**:
- ✅ consistency 条目存在
- ✅ `evidence_json` 不为空
- ✅ company_name/price/duration 的一致性判断不再全是 PENDING

---

### Step 6: 完整测试验收

#### 测试脚本

```bash
#!/bin/bash
PROJECT_ID="tp_3f49f66ead6d46e1bac3f0bd16a3efe9"
BIDDER="123"

echo "===== Step 1: 清理旧数据 ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
DELETE FROM tender_bid_response_items WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}';
DELETE FROM tender_review_items WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}';
"

echo "===== Step 2: 抽取投标响应 (v2) ====="
curl -sS -X POST "http://localhost:9001/api/apps/tender/projects/${PROJECT_ID}/extract-bid-responses?bidder_name=${BIDDER}" | jq .

echo "===== Step 3: 验收 normalized_fields_json ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN normalized_fields_json != '{}' THEN 1 ELSE 0 END) as has_nf,
  SUM(CASE WHEN evidence_json IS NOT NULL THEN 1 ELSE 0 END) as has_ev
FROM tender_bid_response_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}';
"

echo "===== Step 4: 查看商务维度 normalized_fields ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
SELECT 
  dimension,
  normalized_fields_json->'total_price_cny' as price,
  normalized_fields_json->'warranty_months' as warranty,
  normalized_fields_json->'duration_days' as duration
FROM tender_bid_response_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}'
AND dimension='business';
"

echo "===== Step 5: 运行审核 ====="
curl -sS -X POST "http://localhost:9001/api/apps/tender/projects/${PROJECT_ID}/review/run" \
  -H "Content-Type: application/json" \
  -d "{\"bidder_name\":\"${BIDDER}\",\"sync\":1}" | jq .

echo "===== Step 6: 验收审核结果 ====="
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
SELECT 
  dimension,
  status,
  COUNT(*) as count
FROM tender_review_items
WHERE project_id='${PROJECT_ID}' AND bidder_name='${BIDDER}'
GROUP BY dimension, status
ORDER BY dimension, status;
"

echo "===== Done! ====="
```

#### 最终验收指标

- ✅ `has_nf` >= 70% (至少70%的响应有 normalized_fields)
- ✅ `has_ev` >= 70% (至少70%的响应有 evidence_json)
- ✅ 商务维度至少有 `total_price_cny`、`warranty_months`、`duration_days` 中的部分
- ✅ 审核结果中 consistency 维度不再全是 PENDING
- ✅ quant_check 的 `computed_trace_json` 包含真实对比值

---

## 📝 Git 提交建议

```bash
# Step 1 & 2
git add backend/prompts/bid_response_extraction_v2.md \
        backend/app/works/tender/extraction_specs/bid_response_v2.py
git commit -m "✨ 新增: 投标响应抽取 v2 (normalized_fields + evidence_segments)

- 创建 bid_response_extraction_v2.md prompt (9688字符)
- 写入数据库 prompt_templates (id=prompt_bid_response_v2_001)
- 创建 bid_response_v2.py spec
- 新增字段: normalized_fields_json (标准化字段集)
- 新增字段: evidence_segment_ids (文档片段ID)
- 保留向后兼容: evidence_chunk_ids

标准字段包括:
- company_name, credit_code, registered_capital_cny
- total_price_cny, warranty_months, duration_days
- standard_codes, cpu_model, memory_gb

上下文格式: [0] <chunk id=\"seg_bid_001\">"

# Step 3 & 4
git add backend/app/works/tender/bid_response_service.py \
        backend/app/routers/tender.py
git commit -m "🔧 实现: BidResponseService v2 抽取与落库

- 新增 extract_bid_response_v2() 方法
- 解析 v2 schema (normalized_fields_json + evidence_segment_ids)
- 兼容性处理: chunk_ids ↔ segment_ids
- 批量预取 doc_segments
- 组装 evidence_json (page/quote/heading_path)
- 更新路由调用 v2

落库字段:
- normalized_fields_json: JSONB
- evidence_json: JSONB array
- evidence_chunk_ids: TEXT[]"

# Step 5
git add backend/app/works/tender/review_pipeline_v3.py
git commit -m "♻️ 重构: ReviewPipelineV3 读取 normalized_fields_json

- Consistency检查优先使用 normalized_fields_json
- 标准字段: company_name, total_price_cny, duration_days
- 降级兼容: 仍读取 extracted_value_json
- 单位统一: 价格(元), 工期(天), 质保(月)"
```

---

## 🎯 当前实施状态

✅ **Step 1**: v2 Prompt 创建并写入数据库  
✅ **Step 2**: bid_response_v2.py Spec 文件创建  
⏳ **Step 3**: BidResponseService 支持 v2 字段（待实施）  
⏳ **Step 4**: 更新落库逻辑（待实施）  
⏳ **Step 5**: ReviewPipelineV3 读取 normalized_fields（待实施）  
⏳ **Step 6**: 完整测试验收（待实施）

---

## 💡 注意事项

### 1. 证据ID约束（重要）
- LLM 只能引用上下文中存在的 `<chunk id="xxx">`
- 如果上下文格式不是 `<chunk id="seg_bid_001">`，需要修改 prompt 中的标记说明
- 禁止编造不存在的 ID

### 2. normalized_fields 单位规范
- **价格**: 统一为"元" (`total_price_cny`)
- **工期**: 统一为"天" (`duration_days`)
- **质保**: 统一为"月" (`warranty_months`)
- **注册资本**: 统一为"元" (`registered_capital_cny`)

### 3. 兼容性保证
- 保留 `evidence_chunk_ids` 字段（与 `evidence_segment_ids` 值相同）
- 保留 `extracted_value_json` 字段（原始抽取值）
- ReviewPipelineV3 应先读 normalized，再降级到 extracted

### 4. 性能优化
- 使用 `_prefetch_doc_segments()` 批量预取，避免 N+1 查询
- evidence_json 最多保留 5 条
- quote 截取最多 220 字符

---

##  联系人

如有问题，请参考：
- Prompt 模板: `backend/prompts/bid_response_extraction_v2.md`
- Spec 文件: `backend/app/works/tender/extraction_specs/bid_response_v2.py`
- 数据库: `prompt_templates.id='prompt_bid_response_v2_001'`

## 附录: 数据库表结构

### tender_bid_response_items (需要确认已有字段)

```sql
-- 已有字段 (v1)
id UUID PRIMARY KEY,
project_id TEXT,
bidder_name TEXT,
dimension TEXT,
response_type TEXT,
response_text TEXT,
extracted_value_json JSONB,
evidence_chunk_ids TEXT[],

-- v2 新增字段（需要确认是否已添加）
normalized_fields_json JSONB,
evidence_json JSONB
```

如果没有，需要运行 migration:

```sql
ALTER TABLE tender_bid_response_items
  ADD COLUMN IF NOT EXISTS normalized_fields_json JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS evidence_json JSONB NULL;

CREATE INDEX IF NOT EXISTS idx_bid_response_normalized 
  ON tender_bid_response_items USING GIN (normalized_fields_json);
```

