# 格式范本内容提取功能

## 📋 功能概述

已为格式范本提取系统增加了**纯文本内容提取**功能，现在不仅提取范本的标题，还会提取完整的范本内容（包括段落和表格）。

## ✨ 新增功能

### 1. **数据库字段**
- 新增 `content_text` 字段（TEXT类型）
- 存储范本的纯文本内容
- 支持全文搜索索引（使用PostgreSQL GIN索引）

### 2. **内容提取函数**
新增 `blocks_to_text()` 函数，将结构化的 blocks 转换为纯文本：

**支持的内容类型：**
- ✅ 段落文本（type="p"）
- ✅ 表格内容（type="table"）
  - 表格标记：`[表格开始]` / `[表格结束]`
  - 表头和数据行都会提取
  - 使用 `|` 分隔单元格
  - 使用 `-` 作为表头分隔线

**可选参数：**
- `include_tables=True`：包含表格内容（默认）
- `include_tables=False`：仅提取文本段落

### 3. **API 响应增强**

#### 列表接口（预览模式）
- `GET /api/apps/tender/projects/{project_id}/format-snippets`
- 返回前500字符 + "..."（避免响应过大）

#### 详情接口（完整内容）
- `GET /api/apps/tender/format-snippets/{snippet_id}`
- 返回完整的 `content_text`

**响应示例：**
```json
{
  "id": "snip_abc123",
  "title": "货物报价一览表",
  "norm_key": "price_list",
  "content_text": "附件2：货物报价一览表\n\n项目名称：_______________\n\n[表格开始]\n序号 | 货物名称 | 规格型号 | 单位 | 数量 | 单价（元） | 总价（元） | 备注\n--------------------------------------------------\n1 |  |  |  |  |  |  | \n...",
  "blocks_json": [...],
  "confidence": 0.9
}
```

## 🎯 适用场景

### 1. **纯文本范本**
如：投标函、授权委托书、承诺书

**示例输出：**
```
投标函

致：XX采购单位

我方愿意参加贵方组织的（项目名称）招标，投标总价为人民币（大写）：          元（￥          元）。

我方承诺在投标有效期内不修改、撤销投标文件。

投标人：（盖章）

日期：    年    月    日
```

### 2. **表格型范本**
如：报价一览表、开标一览表、偏离表

**示例输出：**
```
附件2：货物报价一览表

项目名称：_______________

[表格开始]
序号 | 货物名称 | 规格型号 | 单位 | 数量 | 单价（元） | 总价（元） | 备注
--------------------------------------------------
1 |  |  |  |  |  |  | 
2 |  |  |  |  |  |  | 
3 |  |  |  |  |  |  | 
合计 |  |  |  |  |  |  | 
[表格结束]

投标总价（大写）：__________________元

投标人：（盖章）________________

日期：____年____月____日
```

### 3. **复杂表格范本**
如：商务偏离表（包含多个表格和说明文字）

**支持特性：**
- ✅ 多个表格依次提取
- ✅ 表格前后的说明文字
- ✅ 表格内的换行内容
- ✅ 自动清理多余空行

## 🔧 技术实现

### 提取流程
```
招标文档 → 结构化blocks → 范本切片 → 纯文本提取 → 数据库保存
                ↓              ↓            ↓
            extract_blocks  slice_blocks  blocks_to_text
```

### 关键代码位置

1. **文本转换函数**
   - 文件：`backend/app/works/tender/snippet/doc_blocks.py`
   - 函数：`blocks_to_text(blocks, include_tables=True)`

2. **提取逻辑**
   - 文件：`backend/app/works/tender/snippet/snippet_extract.py`
   - 位置：`extract_format_snippets()` 函数中
   - 在构建范本记录时调用 `blocks_to_text()`

3. **数据库保存**
   - 文件：`backend/app/works/tender/snippet/snippet_extract.py`
   - 函数：`save_snippets_to_db()`
   - INSERT 语句包含 `content_text` 字段

4. **API Schema**
   - 文件：`backend/app/routers/tender_snippets.py`
   - Schema：`SnippetOut`、`SnippetDetailOut`
   - 包含 `content_text` 字段

## 📊 数据库变更

### 迁移文件
```sql
-- 文件：migrations/018_add_content_text_to_snippets.sql

ALTER TABLE tender_format_snippets 
ADD COLUMN IF NOT EXISTS content_text TEXT DEFAULT '';

-- 全文搜索索引
CREATE INDEX IF NOT EXISTS idx_tender_format_snippets_content_text 
    ON tender_format_snippets USING gin(to_tsvector('simple', content_text));
```

### 执行迁移
```bash
# 在数据库中执行迁移脚本
psql -U localgpt -d localgpt -f backend/migrations/018_add_content_text_to_snippets.sql
```

## 🧪 测试验证

### 运行测试
```bash
# 基础文本提取测试
python backend/test_snippet_content_extraction.py

# 表格型范本测试
python backend/test_table_snippet.py
```

### 测试覆盖
- ✅ 纯文本段落提取
- ✅ 单个表格提取
- ✅ 多个表格提取
- ✅ 混合内容（文本+表格）
- ✅ 空行清理
- ✅ include_tables 参数

## 💡 使用建议

### 前端展示
1. **列表预览**：显示前200字符
2. **详情查看**：显示完整内容
3. **表格渲染**：识别 `[表格开始]` 和 `[表格结束]` 标记，可以渲染为实际表格

### 搜索功能
利用全文搜索索引快速查找范本：
```sql
SELECT * FROM tender_format_snippets 
WHERE to_tsvector('simple', content_text) @@ to_tsquery('simple', '报价');
```

### 内容对比
- 对比不同招标项目的同类范本差异
- 快速查看范本要求的具体内容

## 📈 性能优化

1. **存储效率**
   - 仅在提取时计算一次
   - 避免每次查询时重新转换

2. **查询优化**
   - 列表接口：不返回 `blocks_json`，仅返回截断的 `content_text`
   - 详情接口：返回完整的 `blocks_json` 和 `content_text`

3. **索引支持**
   - GIN 全文搜索索引加速关键词查找
   - 普通索引支持按项目、范本类型查询

## 🎉 总结

现在格式范本提取系统不仅识别范本边界和标题，还能：
- ✅ 提取完整的纯文本内容（包括表格）
- ✅ 支持预览和详情查看
- ✅ 支持全文搜索
- ✅ 适配各种范本类型（文本、表格、混合）
- ✅ 提供清晰的表格标记便于前端渲染

这为后续的范本内容分析、智能填充、内容对比等功能奠定了基础！
