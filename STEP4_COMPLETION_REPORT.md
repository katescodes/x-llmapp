# Step 4 完成报告：新入库/分片/向量化链路

## ✅ 验收状态

**所有验收项通过！**

---

## 📋 实现内容

### A. 新索引存储

#### 1. PostgreSQL 全文搜索 (FTS)
- **迁移文件**: `backend/migrations/024_add_doc_segments_fts.sql`
- **功能**:
  - 为 `doc_segments` 表添加 `tsv` (tsvector) 列
  - 创建自动更新触发器 `doc_segments_tsv_trigger()`
  - 创建 GIN 索引 `idx_doc_segments_tsv`
  - 创建复合索引 `idx_doc_segments_version_tsv`

#### 2. Milvus 新集合
- **文件**: `backend/app/services/vectorstore/milvus_docseg_store.py`
- **集合名称**: `doc_segments_v1`
- **Schema**:
  ```python
  - pk (INT64, auto_id, primary)
  - segment_id (VARCHAR, 512) # doc_segments.id
  - doc_version_id (VARCHAR, 512)
  - project_id (VARCHAR, 128)
  - doc_type (VARCHAR, 64) # tender/bid/etc
  - dense (FLOAT_VECTOR, dim=dynamic)
  ```
- **索引**: HNSW (M=8, efConstruction=64, metric=COSINE)

### B. 新 Ingest 服务

**文件**: `backend/app/platform/ingest/v2_service.py`

**核心流程** (`ingest_asset_v2`):
1. 确保 DocStore document/version 存在
2. 解析文件 (复用 `app/services/documents/parser.py`)
3. 分片 (复用 `app/services/segmenter/chunker.py`)
4. 写入 `doc_segments` (自动触发 PG FTS)
5. Embedding (调用 embedding service)
6. 写入 Milvus `doc_segments_v1`

**返回**: `IngestV2Result` (doc_version_id, segment_count, milvus_count)

### C. 新检索服务

**文件**: `backend/app/platform/retrieval/new_retriever.py`

**核心流程** (`retrieve`):
1. 从 `tender_project_assets` 获取项目下的 `doc_version_ids`
2. Milvus 向量检索 (dense)
3. PG tsvector 全文检索 (lexical)
4. RRF 融合 (Reciprocal Rank Fusion)
5. 加载完整 chunk 文本

**支持过滤**:
- `project_id`: 项目范围
- `doc_types`: 文档类型 (tender/bid/etc)

### D. 接入资产上传 (Cutover 控制)

**文件**: `backend/app/services/tender_service.py` (`import_assets` 方法)

**Cutover 模式**:
- **OLD**: 仅旧入库 (KB + 旧 Milvus)
- **SHADOW**: 旧入库成功后，同步跑新入库 (失败仅记录，不影响主流程)
- **PREFER_NEW**: 先跑新入库，失败回退旧入库
- **NEW_ONLY**: 仅新入库，失败抛错

**Meta 记录** (`tender_project_assets.meta_json`):
```json
{
  "doc_version_id": "dv_xxx",
  "ingest_v2_status": "success|failed|failed_fallback",
  "ingest_v2_segments": 41,
  "ingest_v2_error": null
}
```

### E. Debug 接口

**文件**: `backend/app/routers/debug.py`

#### 1. `/api/_debug/ingest/v2?asset_id=xxx`
查看新入库状态:
```json
{
  "asset_id": "ta_xxx",
  "ingest_v2": {
    "status": "success",
    "doc_version_id": "dv_xxx",
    "segments_count": 41,
    "actual_segments_in_db": 41,
    "milvus_collection": "doc_segments_v1"
  }
}
```

#### 2. `/api/_debug/retrieval/test?query=xxx&project_id=xxx&doc_types=tender&top_k=5`
测试新检索器:
```json
{
  "query": "tender",
  "project_id": "tp_xxx",
  "doc_types": ["tender"],
  "results_count": 2,
  "results": [
    {
      "chunk_id": "seg_xxx",
      "text": "...",
      "score": 0.85,
      "meta": {
        "doc_version_id": "dv_xxx",
        "chunk_position": 33
      }
    }
  ]
}
```

### F. 环境变量

**文件**: `backend/env.example`, `docker-compose.yml`

```bash
# Ingest 模式
INGEST_MODE=OLD  # OLD|SHADOW|PREFER_NEW|NEW_ONLY

# Milvus 新集合
MILVUS_COLLECTION_DOCSEG=doc_segments_v1
```

---

## 🧪 验收测试结果

### 1. INGEST_MODE=OLD
```bash
✅ Step 0 smoke 测试全绿
✅ 旧入库正常工作
✅ 不影响现有功能
```

### 2. INGEST_MODE=SHADOW
```bash
✅ Step 0 smoke 测试全绿
✅ 旧入库正常工作
✅ 新入库成功写入:
   - doc_version_id: dv_979bd796b6244d4986fc2fbed19f9b1d
   - segments_count: 41
   - actual_segments_in_db: 41
   - milvus_collection: doc_segments_v1
```

### 3. 新检索器测试
```bash
✅ 查询: "tender"
✅ 返回: 2 个相关分片
✅ 包含完整文本和元数据
✅ 混合检索 (PG FTS + Milvus) 正常工作
```

---

## 📊 关键指标

| 指标 | 数值 |
|------|------|
| 测试文件 | tender_sample.pdf (767KB, 66页) |
| 解析字符数 | 43,151 |
| 分片数量 | 41 |
| PG FTS 索引 | ✅ 已创建 |
| Milvus 向量 | ✅ 已写入 |
| 检索延迟 | < 1s |

---

## 🔧 技术亮点

### 1. 幂等性设计
- DocStore `create_document`/`create_document_version` 基于 SHA256 幂等
- Milvus `upsert_segments` 先删除再插入

### 2. 失败隔离
- SHADOW 模式：新入库失败仅记录，不影响主流程
- 错误信息记录在 `meta_json.ingest_v2_error`

### 3. 混合检索
- PG tsvector (全文搜索)
- Milvus HNSW (向量搜索)
- RRF 融合 (k=60)

### 4. 灵活过滤
- 按项目 ID 过滤
- 按文档类型过滤 (tender/bid/etc)

---

## 📝 代码变更摘要

### 新增文件
```
backend/migrations/024_add_doc_segments_fts.sql
backend/app/services/vectorstore/milvus_docseg_store.py
backend/app/platform/__init__.py
backend/app/platform/ingest/__init__.py
backend/app/platform/ingest/v2_service.py
backend/app/platform/retrieval/__init__.py
backend/app/platform/retrieval/new_retriever.py
```

### 修改文件
```
backend/app/services/tender_service.py (import_assets 方法)
backend/app/services/platform/docstore_service.py (create_segments 修复)
backend/app/routers/debug.py (新增 debug 接口)
backend/env.example (新增环境变量)
docker-compose.yml (新增环境变量)
```

---

## 🎯 下一步建议

### Step 5: 新检索接入业务 (RETRIEVAL_MODE=SHADOW)
1. 修改 `retrieve(...)` facade 接入 cutover 控制
2. SHADOW 模式：同时跑新旧检索，对比结果
3. 记录 shadow diff 到日志
4. 验证新检索质量

### Step 6: 异步 Worker 化
1. 将 SHADOW 模式的新入库改为异步任务
2. 使用 Celery/RQ 队列
3. 避免阻塞主流程

### Step 7: 监控与告警
1. 新入库成功率监控
2. 新检索召回率/准确率监控
3. 性能指标监控 (延迟/吞吐)

---

## ✅ 验收清单

- [x] PG FTS 索引创建成功
- [x] Milvus 新集合创建成功
- [x] 新 Ingest 服务实现
- [x] 新检索服务实现
- [x] Cutover 控制接入
- [x] Debug 接口实现
- [x] 环境变量配置
- [x] INGEST_MODE=OLD 测试通过
- [x] INGEST_MODE=SHADOW 测试通过
- [x] 新入库数据验证通过
- [x] 新检索器测试通过

---

## 🎉 总结

**Step 4 完成！**

成功实现了新的入库/分片/向量化链路，支持：
- ✅ 双索引 (PG FTS + Milvus)
- ✅ 混合检索 (Lexical + Dense)
- ✅ Cutover 控制 (4种模式)
- ✅ 失败隔离 (SHADOW 模式)
- ✅ 完整的 Debug 工具

**默认配置 (INGEST_MODE=OLD) 不影响现有功能，可安全部署！**

