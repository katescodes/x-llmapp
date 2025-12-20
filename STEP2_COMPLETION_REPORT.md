# Step 2: DocStore 文档底座双写 - 完成报告

**日期**: 2025-12-19  
**状态**: ✅ 完成

---

## 完成内容

### A. 数据库表 ✅

**迁移文件**: `backend/migrations/021_create_docstore_tables.sql`

已存在完整的 DocStore 表结构：

1. **`documents`** - 文档表（逻辑文档）
   - `id` (TEXT PRIMARY KEY)
- `namespace` (TEXT) - 业务命名空间，如 "tender"
   - `doc_type` (TEXT) - 文档类型：tender, bid, template, custom_rule
   - `owner_id` (VARCHAR) - 文档所有者
   - `created_at` (TIMESTAMPTZ)

2. **`document_versions`** - 文档版本表
   - `id` (TEXT PRIMARY KEY)
   - `document_id` (TEXT FK) - 关联文档
   - `sha256` (TEXT) - 文件内容哈希
   - `filename` (TEXT) - 原始文件名
   - `storage_path` (TEXT) - 存储路径
   - `created_at` (TIMESTAMPTZ)

3. **`doc_segments`** - 文档片段表
   - `id` (TEXT PRIMARY KEY)
   - `doc_version_id` (TEXT FK) - 关联文档版本
   - `segment_no` (INT) - 片段序号
   - `content_text` (TEXT) - 文本内容
   - `meta_json` (JSONB) - 元数据（chunk_id映射、页码等）
   - `created_at` (TIMESTAMPTZ)

### B. 后端服务层 ✅

**文件**: `backend/app/services/platform/docstore_service.py`

已存在完整的 `DocStoreService` 类：

```python
class DocStoreService:
    def create_document(namespace, doc_type, owner_id) -> document_id
    def create_document_version(document_id, filename, file_content, storage_path) -> version_id
    def create_segments(doc_version_id, segments) -> segment_ids
    def get_document_version(version_id) -> dict
    def get_segments_by_version(doc_version_id) -> list
    def count_segments_by_version(doc_version_id) -> int
```

**特性**:
- 自动计算 SHA256 哈希
- 支持批量创建片段
- 幂等友好设计

### C. 资产上传旁路双写 ✅

**文件**: `backend/app/services/tender_service.py`

在 `import_assets()` 方法中已实现双写逻辑：

```python
# 旁路双写：DocStore（如果启用）
if self.feature_flags.DOCSTORE_DUALWRITE:
    try:
        docstore = DocStoreService(pool)
        
        # 1. 创建文档
        document_id = docstore.create_document(
        namespace="tender",
            doc_type=kind,
            owner_id=proj.get("owner_id")
        )
        
        # 2. 创建文档版本
        doc_version_id = docstore.create_document_version(
            document_id=document_id,
            filename=filename,
            file_content=b,
            storage_path=storage_path
        )
        
        # 3. 将 doc_version_id 写入 meta_json
        # (在后续代码中会写入 tender_assets.meta_json)
        
    except Exception as e:
        # 降级处理：双写失败只记录日志，不阻断主流程
        logger.warning(f"DocStore dualwrite failed: {e}")
```

**降级策略**: 双写失败只记录日志，不影响主流程 ✅

### D. 调试接口 ✅

**文件**: `backend/app/routers/debug.py`

新增接口：`GET /api/_debug/docstore/assets/{asset_id}`

**功能**:
- 获取资产信息
- 从 `meta_json` 中读取 `doc_version_id`
- 查询 DocStore 版本信息
- 统计 segments 数量

**响应示例**:
```json
{
  "asset_id": "ta_xxx",
  "found": true,
  "kind": "bid",
  "filename": "bid_sample.docx",
  "doc_version_id": "dv_xxx",
  "docstore": {
    "version_found": true,
    "version_info": {
      "id": "dv_xxx",
      "document_id": "doc_xxx",
      "sha256": "38e12e...",
      "filename": "bid_sample.docx",
      "storage_path": "data/tender_assets/...",
      "created_at": "2025-12-19T06:33:37..."
    },
    "segments_count": 0
  }
}
```

### E. 环境变量 ✅

**配置文件**: 
- `backend/env.example` - 已有 `DOCSTORE_DUALWRITE=false`
- `backend/app/config.py` - 已有 `FeatureFlags.DOCSTORE_DUALWRITE`
- `docker-compose.yml` - 已添加环境变量

---

## 验收结果

### ✅ 验收 1：默认关闭双写，运行 Smoke 测试

**配置**: `DOCSTORE_DUALWRITE=false`

```bash
$ python scripts/smoke/tender_e2e.py

✓ 登录成功
✓ 项目创建成功
✓ 招标文件上传成功
✓ Step 1 完成
✓ Step 2 完成
✓ Step 3 完成
✓ 投标文件上传成功
✓ Step 5 完成
✓ 导出成功
✓ 所有测试通过！
```

**结果**: ✅ 全部通过，默认关闭不影响现有功能

### ✅ 验收 2：开启双写，运行 Smoke 测试

**配置**: `DOCSTORE_DUALWRITE=true`

```bash
$ python scripts/smoke/tender_e2e.py

✓ 登录成功
✓ 项目创建成功
✓ 招标文件上传成功
✓ Step 1 完成
✓ Step 2 完成
✓ Step 3 完成
✓ 投标文件上传成功
✓ Step 5 完成
✓ 导出成功
✓ 所有测试通过！
```

**结果**: ✅ 全部通过，开启双写不影响现有功能

### ✅ 验收 3：检查 DocStore 双写结果

**测试**: 查询上传资产的 DocStore 信息

```bash
$ curl /api/_debug/docstore/assets/ta_bc66481c1cbb4694a1a8ba486f234675

{
  "asset_id": "ta_bc66481c1cbb4694a1a8ba486f234675",
  "found": true,
  "kind": "bid",
  "filename": "bid_sample.docx",
  "doc_version_id": "dv_838b8d7dba93447dac968083e640bd24",
  "docstore": {
    "version_found": true,
    "version_info": {
      "id": "dv_838b8d7dba93447dac968083e640bd24",
      "document_id": "doc_807c63cddd644f829b8edf3ceaa17a3b",
      "sha256": "38e12e7928f57ac1b3157402768107e28b532364b9d7124edfecfb40afd9c58b",
      "filename": "bid_sample.docx",
      "storage_path": "data/tender_assets/.../bid_sample.docx",
      "created_at": "2025-12-19T06:33:37..."
    },
    "segments_count": 0
  }
}
```

**验证**:
- ✅ `doc_version_id` 已写入 `meta_json`
- ✅ DocStore 中能查到对应的 `document_version`
- ✅ SHA256 哈希正确计算
- ✅ `segments_count` 为 0（当前未写入 segments，符合预期）

---

## 设计特性

### 1. 旁路双写，不切读

- ✅ 仅在资产上传时写入 DocStore
- ✅ 不修改任何读取路径
- ✅ 不替换现有 KB/分片/向量化逻辑
- ✅ 旧逻辑完全不动

### 2. 默认关闭

- ✅ `DOCSTORE_DUALWRITE=false` 默认值
- ✅ 不影响现有功能
- ✅ 需要显式开启才生效

### 3. 降级处理

- ✅ 双写失败只记录日志
- ✅ 不阻断主流程
- ✅ 保证系统稳定性

### 4. 元数据存储

- ✅ `doc_version_id` 写入 `tender_assets.meta_json`
- ✅ 不修改旧表结构
- ✅ 向后兼容

### 5. Segments 预留

- ✅ `doc_segments` 表已创建
- ✅ 当前不写入内容（后续优化）
- ✅ 为未来 chunking 同步预留接口

---

## 数据流

### 资产上传流程（开启双写）

```
1. 用户上传文件
   ↓
2. 读取文件内容 (bytes)
   ↓
3. 旧逻辑：
   - 入库到 KB
   - Chunking
   - Embedding
   - 写入 Milvus
   - 创建 tender_assets 记录
   ↓
4. 新逻辑（旁路双写）：
   if DOCSTORE_DUALWRITE:
     - 创建 document
     - 创建 document_version (计算 SHA256)
     - 将 doc_version_id 写入 meta_json
     - (暂不写入 segments)
   ↓
5. 返回资产信息
```

### DocStore 表关系

```
documents (1)
  ↓
document_versions (N)
  ↓
doc_segments (N)
```

---

## 后续优化方向

### 1. Segments 同步（可选）

在 chunking 时同步写入 `doc_segments`：

```python
if DOCSTORE_DUALWRITE and doc_version_id:
    segments = [
        {
            "segment_no": i,
            "content_text": chunk.text,
            "meta_json": {
                "chunk_id": chunk.id,
                "page_no": chunk.page,
                "bbox": chunk.bbox
            }
        }
        for i, chunk in enumerate(chunks)
    ]
    docstore.create_segments(doc_version_id, segments)
```

### 2. 去重优化

利用 SHA256 哈希避免重复上传：

```python
# 检查是否已存在相同内容的版本
existing = docstore.find_version_by_sha256(sha256)
if existing:
    doc_version_id = existing["id"]
else:
    doc_version_id = docstore.create_document_version(...)
```

### 3. 切换读取路径

后续可以逐步切换读取路径：
- 从 DocStore 读取文档元数据
- 从 DocStore 读取 segments
- 替换 KB 查询

---

## 文件清单

### 已存在文件（复用）

- `backend/migrations/021_create_docstore_tables.sql` - 表结构
- `backend/app/services/platform/docstore_service.py` - 服务层
- `backend/app/services/tender_service.py` - 双写逻辑
- `backend/app/config.py` - FeatureFlags
- `backend/env.example` - 环境变量示例

### 新增文件

- `backend/app/routers/debug.py` - 新增 `/docstore/assets/{asset_id}` 接口

### 修改文件

- `docker-compose.yml` - 已有 `DOCSTORE_DUALWRITE=false`

---

## 注意事项

1. **默认关闭** - `DOCSTORE_DUALWRITE=false`
2. **不切读** - 所有读取路径保持不变
3. **降级处理** - 双写失败不阻断主流程
4. **Segments 预留** - 表已建好，暂不写入
5. **元数据存储** - 使用 `meta_json`，不改旧表

---

## 总结

✅ **Step 2 完成**

- DocStore 表结构完整
- 服务层实现完整
- 旁路双写正常工作
- 降级处理保证稳定性
- 默认关闭不影响现有功能
- 验收全部通过

**查看 DocStore 信息**:
```bash
curl /api/_debug/docstore/assets/{asset_id}
```

**开启双写**:
```bash
DOCSTORE_DUALWRITE=true
```

---

**完成日期**: 2025-12-19  
**验收状态**: ✅ 通过  
