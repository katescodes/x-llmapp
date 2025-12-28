# 文件上传流程诊断结果（最终）

**日期**: 2025-12-29  
**问题**: 投标响应只能抽取3-6条（应该15-30条）

---

## 🔍 诊断结果

### ✅ 文件上传流程本身正常

| 阶段 | 状态 | 数据 |
|------|------|------|
| 文件上传 | ✅ | 3个文件 |
| kb_doc_id | ✅ | 全部填充 |
| doc_segments | ✅ | 102条，有内容 |
| tsv列 | ✅ | 存在 |

### ❌ 根本问题：中文全文索引失效

**问题表现**:
```sql
-- 搜索"营业执照"  
SELECT ... WHERE tsv @@ to_tsquery('simple', '营业 | 执照')
-- 结果: 0 rows ❌

-- 但用LIKE可以找到
SELECT ... WHERE content_text LIKE '%营业执照%'
-- 结果: 3 rows ✅
```

**根本原因**:

1. **tsv 分词器配置问题**:
   ```sql
   -- 实际的 tsv 内容
   tsv: '-2':25A '-3':44A '0':9A '100':158A '101':161A ...
   ```
   **只有数字和标点，没有中文词汇！**

2. **PostgreSQL tsvector 对中文无效**:
   - `simple` 配置：只能按空格分词
   - 中文没有空格分隔
   - 结果：中文内容未被索引

3. **检索流程失败**:
   ```
   LLM抽取查询 
     ↓
   RetrievalFacade.retrieve()
     ↓
   NewRetriever._search_lexical()  
     ↓
   SELECT FROM doc_segments WHERE tsv @@ query
     ↓
   返回 0 结果 ❌
     ↓
   LLM 没有上下文
     ↓
   只能生成少量响应 (3-6条)
   ```

---

## 🎯 修复方案（3选1）

### 方案1：启用中文分词扩展 ⭐推荐

**优点**: 性能最好，扩展性最强  
**缺点**: 需要安装 PostgreSQL 扩展

#### 步骤:

1. **安装 zhparser (中文分词扩展)**:
   ```bash
   # 在 postgres 容器中
   docker-compose exec postgres bash
   apt-get update
   apt-get install -y postgresql-16-zhparser  # 根据PG版本调整
   ```

2. **创建中文配置**:
   ```sql
   CREATE EXTENSION zhparser;
   CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser);
   ALTER TEXT SEARCH CONFIGURATION chinese ADD MAPPING FOR n,v,a,i,e,l WITH simple;
   ```

3. **重建 tsv**:
   ```sql
   UPDATE doc_segments 
   SET tsv = to_tsvector('chinese', content_text);
   ```

4. **修改触发器**:
   ```sql
   -- 修改 doc_segments_tsv_trigger() 函数
   -- 使用 'chinese' 配置而不是 'simple'
   ```

---

### 方案2：使用 pg_trgm (三元组模糊匹配) ⭐简单

**优点**: 不需要中文分词，已有索引  
**缺点**: 性能略差于全文索引

#### 步骤:

1. **检查是否已安装**:
   ```sql
   SELECT * FROM pg_extension WHERE extname = 'pg_trgm';
   ```

2. **修改 NewRetriever._search_lexical()**:
   ```python
   # 从
   sql = """
       SELECT id, ts_rank(tsv, query) as rank
       FROM doc_segments, to_tsquery('simple', %s) query
       WHERE tsv @@ query ...
   """
   
   # 改为
   sql = """
       SELECT id, similarity(content_text, %s) as rank
       FROM doc_segments
       WHERE doc_version_id = ANY(%s)
         AND content_text % %s
       ORDER BY rank DESC
       LIMIT %s
   """
   cur.execute(sql, [query, doc_version_ids, query, limit])
   ```

3. **重启服务**:
   ```bash
   docker-compose restart backend worker
   ```

---

### 方案3：启用 Milvus 向量检索 ⭐最强

**优点**: 语义理解最好，支持多语言  
**缺点**: 需要配置 embedding provider

#### 步骤:

1. **检查 embedding provider**:
   ```bash
   curl http://localhost:9001/api/settings/embedding-providers
   ```

2. **配置 embedding**:
   - 前端: 设置 → Embedding 配置
   - 添加一个中文 embedding 模型

3. **重新触发向量化**:
   ```python
   # 调用 IngestV2Service._write_milvus()
   # 或重新上传文件
   ```

4. **验证 Milvus**:
   ```bash
   docker-compose logs backend | grep -i milvus
   ```

---

## 🚀 快速验证方案

### 方案2（pg_trgm）最快验证：

```bash
# 1. 检查 pg_trgm
docker-compose exec postgres psql -U localgpt -d localgpt -c "
SELECT * FROM pg_extension WHERE extname = 'pg_trgm';
"

# 2. 测试三元组匹配
docker-compose exec postgres psql -U localgpt -d localgpt -c "
SELECT 
    id, 
    LEFT(content_text, 60) as content,
    similarity(content_text, '营业执照') as sim
FROM doc_segments
WHERE doc_version_id IN (
    SELECT dv.id FROM document_versions dv
    WHERE dv.document_id IN (
        SELECT kb_doc_id FROM tender_project_assets 
        WHERE project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9'
    )
)
  AND content_text % '营业执照'
ORDER BY sim DESC
LIMIT 5;
"
```

如果返回结果 → 说明 pg_trgm 可用 → 修改 NewRetriever 代码即可

---

## 📊 预期改进

### 修复前（当前）:
```
检索: 全文索引查询"营业执照" → 0 results
LLM: 没有相关上下文
抽取: 3-6条（最少响应）
```

### 修复后（任一方案）:
```
检索: 模糊匹配/向量检索 → 10-20 relevant chunks
LLM: 丰富的上下文
抽取: 15-30条（完整响应）
```

---

## ✅ 结论

### 文件上传流程：✅ 正常

**没有问题**的部分:
- 文件上传成功
- kb_doc_id 正确填充
- doc_segments 数据完整
- 存储层面完全正常

### 检索层：❌ 中文全文索引失效

**需要修复**的部分:
- tsv 对中文无效
- 全文检索返回0结果
- 需要切换到支持中文的检索方式

### 推荐行动:

1. **立即**: 尝试方案2 (pg_trgm) - 最快
2. **中期**: 实施方案1 (zhparser) - 最优
3. **长期**: 启用方案3 (Milvus) - 最强

---

## 📝 相关文档

- `docs/FILE_UPLOAD_KEYERROR_FIX.md` - KeyError 修复
- `docs/FILE_UPLOAD_FIX_COMPLETE.md` - kb_doc_id 修复
- `docs/FILE_UPLOAD_FLOW_CHECK.md` - 流程检查
- **本文档** - 最终诊断和修复方案

