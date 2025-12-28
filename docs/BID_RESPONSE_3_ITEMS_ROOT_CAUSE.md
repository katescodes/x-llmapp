# 投标响应抽取只有3条的问题分析

## 🔍 根本原因

**投标文件没有正确导入到知识库系统！**

### 证据

1. **tender_project_assets 表**：
```sql
SELECT kind, bidder_name, kb_doc_id 
FROM tender_project_assets 
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' AND kind='bid';

-- 结果：
 kind | bidder_name | kb_doc_id 
------+-------------+-----------
 bid  | 123         | (NULL)      ← 问题！
 bid  | 123         | (NULL)      ← 问题！
```

2. **tender_project_documents 表**：
```sql
SELECT * FROM tender_project_documents 
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9';

-- 结果：0 rows  ← 没有文档关联记录！
```

3. **doc_segments 表**：
- 由于没有 kb_doc_id，无法检索到投标文件的 segments
- LLM 收到的上下文非常少或为空

### 为什么只抽取了3条？

LLM 可能基于：
- **项目元数据** (项目名称、描述等)
- **极少量的通用文本**
- **prompt 中的示例**

强行生成了最少量的响应：
- 1条 qualification (资格)
- 1条 technical (技术)
- 1条 business (商务)

---

## 🎯 解决方案

### 方案1: 重新上传投标文件（推荐）

#### 步骤：
1. **删除现有的无效文件**：
```sql
DELETE FROM tender_project_assets 
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' 
  AND kind='bid' 
  AND kb_doc_id IS NULL;
```

2. **在前端重新上传投标文件**：
   - 进入项目
   - 选择投标人 "123"
   - 上传投标文件（会自动导入到KB）
   - 确认上传成功后，检查：
```sql
SELECT id, kind, bidder_name, title, kb_doc_id 
FROM tender_project_assets 
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' AND kind='bid';
-- kb_doc_id 应该不为 NULL
```

3. **再次执行抽取**：
   - 点击"开始抽取"
   - 期待结果：15-30条响应（根据文档复杂度）

---

### 方案2: 修复现有文件的导入（如果文件仍在存储中）

#### 步骤：
1. **检查文件是否存在**：
```sql
SELECT id, storage_path, filename, size_bytes 
FROM tender_project_assets 
WHERE project_id='tp_3f49f66ead6d46e1bac3f0bd16a3efe9' AND kind='bid';
```

2. **如果 storage_path 不为空**，需要：
   - 手动触发文档导入流程
   - 或使用脚本批量导入

3. **具体脚本**（需要后端开发支持）：
```python
# 伪代码
for asset in assets:
    if asset.storage_path and not asset.kb_doc_id:
        # 读取文件
        # 调用 KB 导入 API
        # 更新 asset.kb_doc_id
        # 触发文档解析和切分
```

---

## 🧪 验收标准

### 修复后应满足：

1. **assets 表**：
```sql
SELECT COUNT(*) FROM tender_project_assets 
WHERE project_id='...' AND kind='bid' AND kb_doc_id IS NOT NULL;
-- 应该 >= 1
```

2. **documents 表**：
```sql
SELECT COUNT(*) FROM documents d
JOIN tender_project_assets tpa ON d.id = tpa.kb_doc_id
WHERE tpa.project_id='...' AND tpa.kind='bid';
-- 应该 >= 1
```

3. **doc_segments 表**：
```sql
SELECT COUNT(*) FROM doc_segments ds
JOIN document_versions dv ON ds.doc_version_id = dv.id
JOIN documents d ON dv.document_id = d.id
JOIN tender_project_assets tpa ON d.id = tpa.kb_doc_id
WHERE tpa.project_id='...' AND tpa.kind='bid';
-- 应该 >= 50 (取决于文档大小)
```

4. **抽取结果**：
```sql
SELECT dimension, COUNT(*) FROM tender_bid_response_items 
WHERE project_id='...' AND bidder_name='123'
GROUP BY dimension;
-- 应该有 5-7 个维度，每个维度 2-10 条
```

---

## 📊 预期改进

### 修复前：
- ❌ kb_doc_id: NULL
- ❌ doc_segments: 0 条
- ❌ 抽取结果: 3 条（qualification, technical, business 各1条）

### 修复后：
- ✅ kb_doc_id: 有效ID
- ✅ doc_segments: 100-500 条（取决于文档）
- ✅ 抽取结果: 15-30 条
  - qualification: 3-5条
  - technical: 5-10条
  - business: 3-5条
  - price: 1-2条
  - doc_structure: 1-2条
  - schedule_quality: 2-4条
  - other: 1-3条

---

## 🔧 临时诊断命令

### 快速检查文档状态：
```bash
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
SELECT 
    tpa.kind,
    tpa.bidder_name,
    tpa.kb_doc_id IS NOT NULL as has_kb_doc,
    (SELECT COUNT(*) 
     FROM doc_segments ds 
     JOIN document_versions dv ON ds.doc_version_id = dv.id
     JOIN documents d ON dv.document_id = d.id
     WHERE d.id = tpa.kb_doc_id) as segment_count
FROM tender_project_assets tpa
WHERE tpa.project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9'
  AND tpa.kind = 'bid'
ORDER BY tpa.created_at;
"
```

### 预期输出（修复后）：
```
 kind | bidder_name | has_kb_doc | segment_count 
------+-------------+------------+---------------
 bid  | 123         | t          |           150
 bid  | 123         | t          |           120
```

---

## 🎯 下一步行动

### 立即执行：

1. **用户操作**：
   ```
   1. 访问前端
   2. 进入项目
   3. 选择投标人 "123"
   4. 查看"文件管理"或"上传文件"区域
   5. 重新上传投标文件（如果之前上传失败）
   ```

2. **验证上传成功**：
   ```sql
   SELECT id, title, kb_doc_id, size_bytes 
   FROM tender_project_assets 
   WHERE project_id='...' AND kind='bid';
   ```

3. **清理旧数据**：
   ```sql
   DELETE FROM tender_bid_response_items 
   WHERE project_id='...' AND bidder_name='123';
   ```

4. **重新抽取**：
   - 点击"开始抽取"
   - 等待完成
   - 查看结果

5. **验收结果**：
   ```bash
   cd /aidata/x-llmapp1
   ./test_bid_response_v2.sh
   ```

---

## 📝 结论

**问题不在于抽取逻辑或 v2 实现，而在于源数据（投标文件）没有正确导入到知识库。**

✅ 代码逻辑正常  
✅ 数据库结构正常  
✅ v2 prompt 正常  
❌ **投标文件的 kb_doc_id 为 NULL**（根本原因）

**解决方案**：重新上传投标文件，确保 kb_doc_id 不为空。

