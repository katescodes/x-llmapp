# PDF范本提取增强方案 - 支持表格+文字混合提取

**目标**: 提取范本的完整原文（包括表格和文字），并填充到目录正文

---

## 🎯 核心思路

### 当前问题

1. **标题识别不完整**
   - 标题可能在段落中（段落文本）
   - 标题也可能在表格中（表格第一行）
   - 当前只检测段落，遗漏表格中的标题

2. **内容提取不完整**
   - 只记录了start_index和end_index
   - 没有提取实际的内容（文字、表格）
   - 目录正文是空的

3. **格式丢失**
   - 表格应该保持表格格式
   - 文字应该保持段落格式
   - 当前只是纯文本

---

## 🛠️ 增强方案

### Phase 1: 增强标题识别（支持表格+段落）

#### 1.1 从段落中识别标题（现有逻辑）

```python
# 已有逻辑，继续保留
for it in seg:
    if it.get("type") == "paragraph":
        text = it.get("text", "").strip()
        if H1.match(text) or _has_kw(text, SAMPLE_KW):
            heads.append((idx, title, ftype, score))
```

#### 1.2 从表格中识别标题（新增）

```python
# ✅ 新增：从表格中识别标题
for it in seg:
    if it.get("type") == "table":
        table_text = it.get("text", "")
        
        # 尝试多种方式提取标题：
        # 方式1: 表格第一行
        first_line = table_text.split("\n")[0].strip()
        
        # 方式2: 表格第一列（如果是目录表格）
        # 例如：
        # | 一、开标一览表 | （页码） |
        # | 二、投标函     | （页码） |
        
        # 方式3: 表格单元格（扫描所有单元格）
        all_lines = table_text.split("\n")
        
        for line in all_lines[:10]:  # 只检查前10行
            line_clean = _clean_title(line)  # 去除点号、括号
            
            if H1.match(line_clean) or _has_kw(line_clean, SAMPLE_KW):
                # 找到标题
                heads.append((idx, line_clean, ftype, 8.0))
                break  # 每个表格只取第一个匹配的标题
```

#### 1.3 标题清理函数

```python
def _clean_title(text: str) -> str:
    """
    清理标题文本：
    - 去除尾部的点号（……）
    - 去除尾部的括号内容（页码）
    - 去除表格分隔符（|）
    """
    text = text.strip()
    
    # 去除表格分隔符
    text = text.replace("|", "").strip()
    
    # 去除尾部的"………………（页码）"
    text = re.sub(r'[…\.]+\s*[（\(][^）\)]*[）\)]\s*$', '', text)
    
    # 去除尾部的"………………"
    text = re.sub(r'[…\.]+\s*$', '', text)
    
    # 去除尾部的空白和特殊字符
    text = text.strip()
    
    return text
```

---

### Phase 2: 增强内容提取（提取原文）

#### 2.1 Fragment数据结构增强

```python
# 当前Fragment结构：
fragment = {
    "title": "一、开标一览表",
    "start_body_index": 10,
    "end_body_index": 15,
    "confidence": 0.85,
    "strategy": "rule_based"
}

# ✅ 增强后的Fragment结构：
fragment = {
    "title": "一、开标一览表",
    "start_body_index": 10,
    "end_body_index": 15,
    "confidence": 0.85,
    "strategy": "rule_based",
    
    # ✅ 新增：原文内容
    "content": {
        "type": "mixed",  # "text" | "table" | "mixed"
        "items": [
            {
                "type": "paragraph",
                "text": "...",
                "html": "<p>...</p>"
            },
            {
                "type": "table",
                "text": "...",
                "html": "<table>...</table>",
                "rows": 5,
                "cols": 3
            }
        ],
        "html": "<div>...</div>",  # 完整的HTML（用于前端渲染）
        "text": "..."  # 纯文本（用于搜索）
    }
}
```

#### 2.2 内容提取逻辑

```python
def extract_fragment_content(
    items: List[Dict[str, Any]], 
    start_idx: int, 
    end_idx: int
) -> Dict[str, Any]:
    """
    提取fragment的完整内容（包括表格和文字）
    
    Args:
        items: PDF的所有items
        start_idx: fragment起始索引
        end_idx: fragment结束索引
    
    Returns:
        {
            "type": "mixed",
            "items": [...],
            "html": "...",
            "text": "..."
        }
    """
    content_items = []
    text_parts = []
    html_parts = []
    
    # 提取start_idx到end_idx之间的所有items
    for it in items[start_idx:end_idx]:
        item_type = it.get("type")
        
        if item_type == "paragraph":
            # 段落文本
            text = it.get("text", "").strip()
            if text:
                content_items.append({
                    "type": "paragraph",
                    "text": text,
                    "html": f"<p>{text}</p>"
                })
                text_parts.append(text)
                html_parts.append(f"<p>{text}</p>")
        
        elif item_type == "table":
            # 表格
            table_text = it.get("text", "").strip()
            table_html = _convert_table_to_html(it)  # 转换为HTML表格
            
            if table_text:
                content_items.append({
                    "type": "table",
                    "text": table_text,
                    "html": table_html,
                    "rows": table_text.count("\n") + 1,
                    "cols": len(table_text.split("\n")[0].split("|")) if "|" in table_text else 1
                })
                text_parts.append(table_text)
                html_parts.append(table_html)
    
    # 判断内容类型
    has_table = any(it["type"] == "table" for it in content_items)
    has_text = any(it["type"] == "paragraph" for it in content_items)
    
    if has_table and has_text:
        content_type = "mixed"
    elif has_table:
        content_type = "table"
    else:
        content_type = "text"
    
    return {
        "type": content_type,
        "items": content_items,
        "html": "\n".join(html_parts),
        "text": "\n\n".join(text_parts)
    }

def _convert_table_to_html(table_item: Dict[str, Any]) -> str:
    """
    将PDF表格转换为HTML表格
    
    简单版本：将文本按行列分割后生成HTML
    完整版本：使用pdfplumber或其他库提取表格结构
    """
    table_text = table_item.get("text", "")
    lines = table_text.split("\n")
    
    html = ['<table border="1" style="border-collapse: collapse; width: 100%;">']
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        
        # 按 | 分割单元格（如果有）
        cells = [c.strip() for c in line.split("|") if c.strip()]
        
        # 第一行作为表头
        if i == 0 and cells:
            html.append("<thead><tr>")
            for cell in cells:
                html.append(f"<th>{cell}</th>")
            html.append("</tr></thead>")
        else:
            html.append("<tr>")
            for cell in cells:
                html.append(f"<td>{cell}</td>")
            html.append("</tr>")
    
    html.append("</table>")
    return "".join(html)
```

---

### Phase 3: 数据库存储增强

#### 3.1 tender_sample_fragments表扩展

```sql
-- 当前结构
CREATE TABLE tender_sample_fragments (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    start_body_index INTEGER NOT NULL,
    end_body_index INTEGER NOT NULL,
    confidence FLOAT,
    strategy VARCHAR
);

-- ✅ 增强后的结构
ALTER TABLE tender_sample_fragments 
ADD COLUMN content_type VARCHAR(20);  -- "text" | "table" | "mixed"

ADD COLUMN content_html TEXT;  -- 富文本HTML（用于渲染）

ADD COLUMN content_text TEXT;  -- 纯文本（用于搜索）

ADD COLUMN content_items JSONB;  -- 详细的items结构
```

#### 3.2 存储逻辑

```python
def upsert_fragment_with_content(
    dao: TenderDAO,
    project_id: str,
    fragment: Dict[str, Any],
    items: List[Dict[str, Any]]
) -> str:
    """
    存储fragment，包括完整内容
    """
    # 提取内容
    content = extract_fragment_content(
        items,
        fragment["start_body_index"],
        fragment["end_body_index"]
    )
    
    # 存储到数据库
    fragment_id = dao.upsert_tender_sample_fragment(
        project_id=project_id,
        title=fragment["title"],
        start_body_index=fragment["start_body_index"],
        end_body_index=fragment["end_body_index"],
        confidence=fragment["confidence"],
        strategy=fragment["strategy"],
        
        # ✅ 新增字段
        content_type=content["type"],
        content_html=content["html"],
        content_text=content["text"],
        content_items=json.dumps(content["items"], ensure_ascii=False)
    )
    
    return fragment_id
```

---

### Phase 4: 目录正文填充增强

#### 4.1 OutlineSampleAttacher增强

```python
class OutlineSampleAttacher:
    def attach_fragment_to_node(
        self,
        node_id: str,
        fragment: Dict[str, Any]
    ):
        """
        将fragment的内容填充到目录节点的正文
        """
        # 获取fragment的完整内容
        content_html = fragment.get("content_html", "")
        content_text = fragment.get("content_text", "")
        content_type = fragment.get("content_type", "text")
        
        # 更新节点的body
        self.dao.update_directory_node_body(
            node_id=node_id,
            body_html=content_html,  # HTML格式（用于前端渲染）
            body_text=content_text,  # 纯文本（用于编辑）
            body_source="EXTRACTED_FRAGMENT",
            fragment_id=fragment["id"]
        )
        
        # 更新节点的bodyMeta
        self.dao.update_directory_node_meta(
            node_id=node_id,
            meta={
                "source": "EXTRACTED_FRAGMENT",
                "fragmentId": fragment["id"],
                "hasContent": True,
                "contentType": content_type,  # "text" | "table" | "mixed"
                "extractedAt": datetime.now().isoformat()
            }
        )
```

---

### Phase 5: 前端渲染增强

#### 5.1 目录节点显示

```tsx
// TenderWorkspace.tsx
function DirectoryNodeBody({ node }: { node: DirectoryNode }) {
  const contentType = node.bodyMeta?.contentType || "text";
  
  if (contentType === "table" || contentType === "mixed") {
    // 渲染HTML（包含表格）
    return (
      <div 
        className="node-body-html"
        dangerouslySetInnerHTML={{ __html: node.bodyHtml || "" }}
      />
    );
  } else {
    // 渲染纯文本
    return (
      <pre className="node-body-text">
        {node.bodyText || ""}
      </pre>
    );
  }
}
```

#### 5.2 样式优化

```css
/* 表格样式 */
.node-body-html table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
}

.node-body-html th,
.node-body-html td {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}

.node-body-html th {
  background-color: #f5f5f5;
  font-weight: bold;
}

/* 文本样式 */
.node-body-text {
  white-space: pre-wrap;
  font-family: monospace;
  padding: 10px;
  background: #f9f9f9;
  border-radius: 4px;
}
```

---

## 📊 实施计划

### Step 1: 增强标题识别（1小时）

**文件**: `backend/app/services/fragment/pdf_sample_detector.py`

1. 添加`_clean_title()`函数
2. 修改`detect_pdf_fragments()`，增加表格标题识别
3. 测试：能识别表格中的标题

**预期结果**:
```python
# 测试1项目应该识别到8个标题
fragments = detect_pdf_fragments(items, ...)
assert len(fragments) == 8
```

---

### Step 2: 增强内容提取（1.5小时）

**文件**: `backend/app/services/fragment/pdf_content_extractor.py` (新文件)

1. 创建`extract_fragment_content()`函数
2. 创建`_convert_table_to_html()`函数
3. 测试：能提取表格和文字

**预期结果**:
```python
content = extract_fragment_content(items, 10, 15)
assert content["type"] in ["text", "table", "mixed"]
assert content["html"]  # 有HTML内容
assert content["text"]  # 有纯文本内容
```

---

### Step 3: 数据库扩展（30分钟）

**文件**: `backend/app/migrations/xxx_add_fragment_content.sql` (新文件)

1. 编写迁移脚本
2. 添加新字段（content_type, content_html, content_text, content_items）
3. 执行迁移

**执行**:
```bash
# 应用迁移
docker-compose exec backend alembic upgrade head

# 或手动执行SQL
docker-compose exec postgres psql -U localgpt -d localgpt < migration.sql
```

---

### Step 4: 存储逻辑更新（1小时）

**文件**: 
- `backend/app/services/fragment/fragment_extractor.py`
- `backend/app/services/dao/tender_dao.py`

1. 修改`extract_and_upsert_summary()`，调用内容提取
2. 修改`upsert_tender_sample_fragment()`，支持新字段
3. 测试：fragments能正确存储

---

### Step 5: 目录填充更新（1小时）

**文件**: `backend/app/services/fragment/outline_attacher.py`

1. 修改`attach_fragment_to_node()`，填充HTML内容
2. 修改`_attach_fragment_body()`，支持新字段
3. 测试：目录节点能显示表格

---

### Step 6: 前端渲染更新（1小时）

**文件**: `frontend/src/components/TenderWorkspace.tsx`

1. 修改目录节点渲染逻辑
2. 支持HTML渲染（表格）
3. 添加CSS样式
4. 测试：前端能正确显示表格

---

### Step 7: 集成测试（30分钟）

1. 重启后端：`docker-compose restart backend`
2. 触发提取：调用`auto_fill_samples` API
3. 验证结果：
   - ✅ 识别8个fragments
   - ✅ 每个fragment有完整内容
   - ✅ 目录节点显示表格/文字
   - ✅ 前端渲染正确

---

## 🎯 预期效果

### 修复前

```json
{
  "fragments_detected": 0,
  "attached_sections": 4,
  "nodes": [
    {
      "title": "开标一览表",
      "bodyMeta": {
        "source": "BUILTIN_SAMPLE",
        "hasContent": true
      },
      "bodyText": "固定的内置模板内容"
    }
  ]
}
```

### 修复后

```json
{
  "fragments_detected": 8,
  "attached_sections": 8,
  "nodes": [
    {
      "title": "开标一览表",
      "bodyMeta": {
        "source": "EXTRACTED_FRAGMENT",
        "contentType": "table",
        "hasContent": true
      },
      "bodyHtml": "<table><tr><th>项目</th><th>金额</th></tr>...</table>",
      "bodyText": "项目 | 金额\n设备采购 | 100万\n..."
    },
    {
      "title": "投标函",
      "bodyMeta": {
        "source": "EXTRACTED_FRAGMENT",
        "contentType": "text",
        "hasContent": true
      },
      "bodyHtml": "<p>致：XXX采购人</p><p>我方...</p>",
      "bodyText": "致：XXX采购人\n我方..."
    }
  ]
}
```

---

## 📝 技术要点

### 1. 表格识别的挑战

- PDF表格可能有边框，也可能无边框
- 表格单元格可能合并
- 表格可能跨页

**解决方案**: 
- 使用pdfplumber的表格识别（更准确）
- 或使用简单的文本解析（快速）

### 2. HTML安全性

- 用户可能上传恶意PDF
- HTML注入风险

**解决方案**:
- 使用`bleach`库清理HTML
- 只允许白名单标签（table, tr, td, th, p等）

```python
import bleach

ALLOWED_TAGS = ['table', 'tr', 'td', 'th', 'thead', 'tbody', 'p', 'br', 'strong', 'em']
ALLOWED_ATTRS = {'table': ['border', 'style'], 'td': ['colspan', 'rowspan']}

def sanitize_html(html: str) -> str:
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)
```

### 3. 性能优化

- 内容提取可能很慢（大表格）
- HTML生成占用内存

**解决方案**:
- 限制单个fragment的最大size（如：100KB）
- 异步处理（后台任务）
- 缓存提取结果

---

## 🚀 总结

**核心改进**:
1. ✅ 支持从表格和段落中识别标题
2. ✅ 提取fragment的完整原文（表格+文字）
3. ✅ 存储为富文本（HTML）
4. ✅ 前端渲染表格

**预计工作量**: 6-7小时

**优先级**: ⭐⭐⭐⭐⭐ 高（用户明确需求）

**风险**: 低（逻辑清晰，技术可行）

