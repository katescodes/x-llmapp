# 格式范本自动填充 - 快速修复指南

## ✅ 已修复的SQL错误

**问题：** `template_matcher.py` 中的SQL查询使用了错误的表关联

**错误SQL：**
```sql
JOIN document_versions dv ON dv.asset_id = tpd.asset_id  -- ❌ 错误
```

**正确SQL：**
```sql
JOIN documents d ON d.id = tpd.kb_doc_id
JOIN document_versions dv ON dv.document_id = d.id  -- ✅ 正确
```

**修复位置：**
- 文件：`/backend/app/works/tender/template_matcher.py`
- 行数：约220-225行

**状态：** ✅ 已修复并重启后端

---

## 🧪 手动测试步骤

### 步骤1：补打范本标记（现有项目）

```bash
cd /aidata/x-llmapp1
python scripts/mark_existing_templates.py --project-id tp_259c05d1979e402db656a58a930467e2
```

### 步骤2：前端重新生成目录

```
1. 浏览器访问: http://192.168.2.17:6173
2. 登录: admin/admin123
3. 选择"测试2"项目
4. 点击 ③ 目录 标签
5. 点击"生成目录"按钮
6. 等待生成完成...
```

### 步骤3：查看结果

**工具栏底部应该显示：**
```
📄 格式范本填充：自动填充了 X 个节点的格式范本
```

**点击节点查看正文：**
```
目录树 → 点击节点（如"投标函"）→ 右侧查看正文
```

如果填充成功，应该看到完整的格式范本文本。

---

## 🔍 验证方法

### 方法1：查看后端日志
```bash
docker-compose logs backend | grep -i "template" | tail -50
```

**预期日志：**
```
ExtractV2: Starting template matching and auto-fill
ExtractV2: Template matching found 3 matches
ExtractV2: Template auto-fill complete - 3/3 nodes filled
```

### 方法2：查看数据库
```sql
-- 查询标记为范本的chunks
SELECT COUNT(*) FROM doc_segments 
WHERE meta_json->>'is_potential_template' = 'true';

-- 查询已填充正文的节点
SELECT COUNT(*) FROM tender_directory_nodes 
WHERE body_content IS NOT NULL AND body_content != '';
```

---

## 📞 如果仍然不工作

请提供以下信息：

1. **后端日志**（目录生成时）：
   ```bash
   docker-compose logs backend | grep -A 20 "generate_directory" | tail -50
   ```

2. **数据库检查结果**：
   - 有多少chunks被标记为范本？
   - 目录有多少节点？
   - 有多少节点正文已填充？

3. **前端截图**：
   - 目录生成完成后的工具栏统计
   - 点击节点后的正文显示

---

## ✅ 总结

**已修复的错误：**
1. ✅ 数据库表名错误（`doc_versions` → `document_versions`）
2. ✅ SQL关联错误（`asset_id` → `kb_doc_id + document_id`）
3. ✅ 自定义规则审核错误（`condition_json` 类型检查）

**功能状态：**
- ✅ 阶段1：文档分片识别（已集成）
- ✅ 阶段2：LLM精确匹配（已修复）
- ✅ 阶段3：自动填充正文（已修复）

**请按照上述步骤手动测试！** 🚀

