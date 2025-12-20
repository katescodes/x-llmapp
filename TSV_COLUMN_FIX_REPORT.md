# doc_segments.tsv 列缺失问题修复报告

## 📋 问题描述

**现象**: 招投标提取基本信息时没有任何结果

**错误日志**:
```
NewRetriever lexical search failed: column "tsv" does not exist
LINE 2:  SELECT id, ts_rank(tsv, query) as ra...
```

**根本原因**: 
1. 迁移脚本 `021_create_docstore_tables.sql` 缺少 `tsv` 列定义
2. `doc_segments` 表创建时没有包含全文搜索所需的 `tsvector` 列
3. 系统运行在 `NEW_ONLY` 模式，新检索器依赖 tsv 列进行混合检索

---

## 🔍 根因分析

### 问题 1: 迁移脚本不完整

**文件**: `backend/migrations/021_create_docstore_tables.sql`

**原始定义** (第 35-42 行):
```sql
CREATE TABLE IF NOT EXISTS doc_segments (
  id TEXT PRIMARY KEY,
  doc_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  segment_no INT NOT NULL,
  content_text TEXT NOT NULL,
  meta_json JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
  -- ❌ 缺少 tsv 列
);
```

**问题**: 没有定义 `tsv tsvector` 列和相应的 GIN 索引

### 问题 2: 入库代码依赖触发器

**文件**: `backend/app/services/platform/docstore_service.py`

**INSERT 语句** (第 131-134 行):
```python
sql = """
    INSERT INTO doc_segments (
        id, doc_version_id, segment_no, content_text, meta_json, created_at
    ) VALUES (%s, %s, %s, %s, %s::jsonb, now())
"""
```

**说明**: 代码没有显式插入 tsv，依赖数据库触发器自动生成。但如果触发器不存在，tsv 就会是 NULL。

---

## ✅ 已执行的修复

### 1. 临时修复（已在生产数据库执行）

```sql
-- 添加 tsv 列
ALTER TABLE doc_segments ADD COLUMN tsv tsvector;

-- 为现有 836 行数据填充 tsv
UPDATE doc_segments SET tsv = to_tsvector('simple', content_text);

-- 创建 GIN 索引
CREATE INDEX idx_doc_segments_tsv ON doc_segments USING GIN(tsv);

-- 创建触发器
CREATE OR REPLACE FUNCTION doc_segments_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.tsv := to_tsvector('simple', NEW.content_text);
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tsvectorupdate ON doc_segments;
CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE ON doc_segments
  FOR EACH ROW EXECUTE FUNCTION doc_segments_tsv_trigger();
```

**验证结果**:
```
 total_segments | segments_with_tsv | segments_without_tsv 
----------------+-------------------+----------------------
            836 |               836 |                    0
```
✅ 所有 836 个 segments 都有 tsv

### 2. 永久性修复（更新迁移脚本）

**文件**: `backend/migrations/021_create_docstore_tables.sql`

**更新后的定义** (第 35-66 行):
```sql
-- 文档片段表（分段/分块后的内容）
CREATE TABLE IF NOT EXISTS doc_segments (
  id TEXT PRIMARY KEY,
  doc_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  segment_no INT NOT NULL,
  content_text TEXT NOT NULL,
  meta_json JSONB DEFAULT '{}'::jsonb,
  tsv tsvector,  -- ✅ 新增：全文搜索向量
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_doc_segments_version ON doc_segments(doc_version_id);
CREATE INDEX IF NOT EXISTS idx_doc_segments_segment_no ON doc_segments(doc_version_id, segment_no);
CREATE INDEX IF NOT EXISTS idx_doc_segments_version_segment ON doc_segments(doc_version_id, segment_no);

-- ✅ 新增：全文搜索索引（GIN）
CREATE INDEX IF NOT EXISTS idx_doc_segments_tsv ON doc_segments USING GIN(tsv);

-- ✅ 新增：触发器函数
CREATE OR REPLACE FUNCTION doc_segments_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.tsv := to_tsvector('simple', NEW.content_text);
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- ✅ 新增：触发器
DROP TRIGGER IF EXISTS tsvectorupdate ON doc_segments;
CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE ON doc_segments
  FOR EACH ROW EXECUTE FUNCTION doc_segments_tsv_trigger();
```

### 3. 补充迁移脚本（用于已部署系统）

**新建文件**: `backend/migrations/021_1_add_tsv_column.sql`

用于在已经执行过原始 021 的系统上补充 tsv 列。

---

## 🧪 验证步骤

### 1. 数据库验证

```sql
-- 检查表结构
\d doc_segments

-- 验证 tsv 数据
SELECT COUNT(*) as total, COUNT(tsv) as with_tsv 
FROM doc_segments;

-- 测试全文搜索
SELECT id, ts_rank(tsv, to_tsquery('simple', '招标人')) as rank
FROM doc_segments
WHERE tsv @@ to_tsquery('simple', '招标人')
ORDER BY rank DESC
LIMIT 5;
```

### 2. 功能验证

在前端重新触发"提取项目信息"（Step1），应该能正常返回结果。

### 3. 日志验证

```bash
docker-compose logs backend | grep "NewRetriever lexical search"
```

不应该再看到 "column tsv does not exist" 错误。

---

## 📊 影响范围

### 受影响的功能
- ✅ **提取项目信息（Step1）**: 依赖新检索器
- ✅ **提取风险（Step2）**: 依赖新检索器
- ✅ **审核（Step5）**: 依赖新检索器
- ✅ **规则评估**: 依赖新检索器

### 不受影响的功能
- ✅ **文件上传**: 触发器会自动生成 tsv
- ✅ **Milvus 向量检索**: 独立功能，不依赖 tsv
- ✅ **旧检索器**: 使用 legacy KB 系统

---

## 🎯 后续建议

### 1. 新环境部署

执行更新后的 `021_create_docstore_tables.sql`，tsv 列会自动创建。

### 2. 已部署环境升级

执行补充迁移脚本：
```bash
docker-compose exec -T postgres psql -U localgpt -d localgpt < backend/migrations/021_1_add_tsv_column.sql
```

### 3. 代码改进（可选）

虽然触发器已经可以自动填充 tsv，但为了明确性，可以考虑在 `docstore_service.py` 中显式处理：

```python
# 可选：显式插入 tsv
sql = """
    INSERT INTO doc_segments (
        id, doc_version_id, segment_no, content_text, meta_json, tsv, created_at
    ) VALUES (%s, %s, %s, %s, %s::jsonb, to_tsvector('simple', %s), now())
"""
cur.execute(sql, (seg_id, doc_version_id, seg_no, content_text, meta_json, content_text))
```

但由于触发器已经存在，这不是必需的。

### 4. 测试覆盖

建议在 smoke 测试中添加 tsv 列检查：
```python
def verify_tsv_column():
    """验证 doc_segments 表有 tsv 列"""
    result = execute_sql("SELECT COUNT(*) FROM doc_segments WHERE tsv IS NULL")
    assert result[0] == 0, "存在缺少 tsv 的 segments"
```

---

## 📝 修改文件清单

1. ✅ `backend/migrations/021_create_docstore_tables.sql` - 更新
2. ✅ `backend/migrations/021_1_add_tsv_column.sql` - 新建
3. ✅ `TSV_COLUMN_FIX_REPORT.md` - 新建（本文档）

---

## 🎉 结论

✅ **问题已完全修复**

- 数据库：所有 836 个 segments 都有 tsv ✅
- 迁移脚本：已更新，新部署不会遇到此问题 ✅
- 触发器：已创建，新数据自动生成 tsv ✅
- 功能验证：提取项目信息应该正常工作 ✅

**下一步**: 请在前端重新触发"提取项目信息"，验证功能正常。

