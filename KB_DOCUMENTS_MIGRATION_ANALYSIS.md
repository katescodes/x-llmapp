# kb_documents 数据迁移分析

生成时间：2025-12-31
分析人：AI Assistant

---

## 📊 数据分析

### 基本情况
- **总数**：15条记录
- **所属知识库**：3个（测试、测试2、测试4）
- **文档类型**：
  - tender_doc: 6条（招标文件）
  - bid_doc: 9条（投标文件）

### 关键发现 ✅

1. **所有15条记录都有 doc_version_id**
   - 这些 doc_version_id **已经存在于新系统**（document_versions表）
   - 新系统有完整的文档数据（155条 documents + document_versions）

2. **kb_documents 是桥接表**
   - 作用：通过 kb_id 关联知识库和文档
   - meta_json 中存储：project_id, asset_id, doc_version_id

3. **资产关联情况**
   - 有asset关联：6条
   - 无asset关联：9条（可能是重复上传或测试数据）

---

## 🔍 数据详情

### 项目分布

| 项目ID | 项目名称 | 知识库ID | 文档数 |
|--------|----------|----------|--------|
| tp_259c05d1979e402db656a58a930467e2 | 测试2 | 8a24331e323a4f6b86e2fb74ee92127e | 6 |
| tp_3f49f66ead6d46e1bac3f0bd16a3efe9 | 测试4 | 84ff45f7f3944293beefacb1323eb58f | 7 |
| tp_39699fd683e8408d88eb2f1a5ef3c91d | 测试 | 2a149e2c215c4b3096aec5d731af7c41 | 2 |

### 文档版本映射验证

所有 kb_documents 的 doc_version_id 都在新系统中：

```sql
SELECT 
    kd.id as kb_doc_id,
    kd.meta_json->>'doc_version_id' as doc_version_id,
    dv.id as actual_version_id,
    dv.document_id
FROM kb_documents kd
LEFT JOIN document_versions dv ON (kd.meta_json->>'doc_version_id')::text = dv.id
```

**结果**：✅ 100% 匹配（15/15）

---

## 🎯 使用场景分析

### 1. 检索系统

**当前逻辑**（`app/platform/retrieval/facade.py`）：
```python
# 策略1: 从 kb_documents 获取 doc_version_ids
doc_version_ids = self._get_doc_version_ids_from_kb(kb_ids)

# 查询逻辑
SELECT DISTINCT meta_json->>'doc_version_id' as doc_version_id
FROM kb_documents
WHERE kb_id IN (...)
```

**新逻辑**（应该改为）：
```python
# 直接从 documents 表查询
SELECT DISTINCT dv.id as doc_version_id
FROM documents d
JOIN document_versions dv ON d.id = dv.document_id
WHERE d.namespace = 'tender' 
  AND d.meta_json->>'kb_id' IN (...)
```

### 2. 知识库服务

**当前逻辑**（`app/services/kb_service.py`）：
- `import_document()` - 插入 kb_documents
- `delete_document()` - 删除 kb_documents
- `list_documents()` - 列出 kb_documents

**新逻辑**（应该改为）：
- 直接操作 documents 表
- 在 documents.meta_json 中存储 kb_id

### 3. 轻量入库

**当前逻辑**（`app/services/dao/tender_dao.py`）：
```python
def create_kb_document(...) -> str:
    INSERT INTO kb_documents (...)
```

**新逻辑**（已废弃）：
- 所有入库通过 `platform/ingest/v2_service.py`
- 直接写入 documents 表

---

## 🚀 迁移策略

### 方案：数据已经在新系统，只需要补充 kb_id 映射

由于所有文档数据已经在新系统中（通过 doc_version_id），我们只需要：

1. ✅ 在 `documents` 表的 `meta_json` 中添加 `kb_id` 字段
2. ✅ 更新检索逻辑，从 documents 表查询
3. ✅ 删除 kb_documents 表
4. ✅ 清理相关代码

**优点**：
- 无需迁移实际文档数据
- 只是补充元数据
- 风险极低

---

## 📝 迁移脚本设计

### Step 1: 数据补充

```sql
-- 为每个 document 添加 kb_id 映射
UPDATE documents d
SET meta_json = meta_json || jsonb_build_object('kb_id', kd.kb_id)
FROM kb_documents kd
JOIN document_versions dv ON (kd.meta_json->>'doc_version_id')::text = dv.id
WHERE d.id = dv.document_id;
```

### Step 2: 验证

```sql
-- 验证所有文档都有 kb_id
SELECT 
    COUNT(*) as total,
    COUNT(meta_json->>'kb_id') as with_kb_id
FROM documents
WHERE namespace = 'tender';
```

### Step 3: 更新代码

修改以下文件：
1. `app/platform/retrieval/facade.py` - 检索逻辑
2. `app/services/kb_service.py` - 知识库服务
3. `app/services/dao/tender_dao.py` - 数据访问层

### Step 4: 删除旧表

```sql
DROP TABLE kb_documents CASCADE;
DROP TABLE kb_chunks CASCADE;
```

---

## ⚠️ 风险评估

### 低风险 ✅
- 数据已在新系统，只是补充映射
- 15条数据量小，易于回滚
- 可以先在测试环境验证

### 需要注意
1. 检索逻辑变更后需要全面测试
2. 确保所有 kb_id 都正确映射
3. 清理代码时避免遗漏

---

## 📋 执行计划

### Phase 1: 准备（已完成）
- ✅ 分析数据结构
- ✅ 识别使用场景
- ✅ 设计迁移方案

### Phase 2: 数据迁移（待执行）
1. 备份当前数据
2. 补充 kb_id 到 documents.meta_json
3. 验证数据完整性

### Phase 3: 代码迁移（待执行）
1. 更新检索逻辑
2. 更新知识库服务
3. 清理废弃代码

### Phase 4: 验证（待执行）
1. 单元测试
2. 集成测试
3. 功能测试

### Phase 5: 清理（待执行）
1. 删除 kb_documents 表
2. 删除 kb_chunks 表
3. 更新文档

---

## 🎯 预期结果

### 系统简化
- ✅ 删除2个废弃表
- ✅ 统一文档存储
- ✅ 简化检索逻辑

### 代码质量
- ✅ 消除冗余代码
- ✅ 提升可维护性
- ✅ 明确系统边界

### 性能优化
- ✅ 减少表join
- ✅ 简化查询逻辑
- ✅ 提升检索速度

---

**分析完成！准备开始迁移。**

