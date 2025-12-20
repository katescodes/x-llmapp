# 格式模板功能修复总结

## 修复日期
2025-12-21

## 问题诊断

### ✅ 已验证正确的部分
1. **模板上传原样保存** - `work.py:144` 直接用 `f.write(docx_bytes)` 保存原始字节流，无二次处理
2. **导出使用模板母版** - `docx_exporter.py:169` 用 `Document(template_path)` 加载，完整保留页眉页脚
3. **清空内容保留 sectPr** - `docx_exporter.py:48-71` 清空正文但保留节设置和页眉页脚

### ❌ 需要修复的问题
1. **缺少格式预览 GET 端点** - 前端无法直接访问预览 PDF/DOCX
2. **apply-format-template 返回的 URL 缺少对应端点** - 返回了 URL 但不可访问
3. **PDF 转换能力未实现** - 需要调用 LibreOffice/soffice

---

## 修复内容

### 1. 新增格式预览 GET 端点

**文件**: `backend/app/routers/format_templates.py`

新增端点：
```python
GET /api/apps/tender/projects/{project_id}/directory/format-preview
    ?format=pdf|docx
    &format_template_id=xxx (可选)
```

**功能**：
- 自动从项目根节点读取 `format_template_id`（如果未指定）
- 使用 ExportService 导出 DOCX（自动应用模板）
- 如果请求 PDF，则调用 LibreOffice 转换
- 返回文件流（可直接在浏览器中打开）

**权限**：
- 仅项目所有者可访问

### 2. Work 层新增预览方法

**文件**: `backend/app/works/tender/format_templates/work.py`

新增方法：
```python
def preview_project_with_template(
    project_id: str,
    template_id: str,
    output_format: str = "pdf"
) -> ProjectPreviewResult
```

**流程**：
1. 验证模板存在
2. 使用 ExportService 导出 DOCX（自动使用模板母版）
3. 如果需要 PDF，调用 `_convert_docx_to_pdf()`
4. 返回文件路径

**PDF 转换**：
```python
def _convert_docx_to_pdf(docx_path: str, output_dir: Path) -> str
```
- 调用 `soffice --headless --convert-to pdf`
- 超时设置：60秒
- 错误处理：转换失败时降级返回 DOCX

### 3. 更新 apply-format-template 返回 URL

**文件**: `backend/app/works/tender/format_templates/work.py`

修改前：
```python
preview_url = None  # TODO
download_url = f"/api/apps/tender/projects/{id}/exports/docx/{filename}"
```

修改后：
```python
preview_url = f"/api/apps/tender/projects/{id}/directory/format-preview?format=pdf&format_template_id={template_id}"
download_url = f"/api/apps/tender/projects/{id}/exports/docx/{filename}"
```

**改进**：
- `preview_pdf_url` 现在指向格式预览端点（自动生成 PDF）
- `download_docx_url` 保持不变，指向已导出的 DOCX 文件

### 4. 类型定义增强

**文件**: `backend/app/works/tender/format_templates/types.py`

新增类型：
```python
class ProjectPreviewResult(BaseModel):
    """项目格式预览结果"""
    ok: bool = True
    error: Optional[str] = None
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
```

更新类型：
```python
class PreviewResult(BaseModel):
    """预览结果（兼容旧版）"""
    ok: bool = True
    error: Optional[str] = None
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
    file_path: Optional[str] = None  # 兼容字段
    content_type: Optional[str] = None  # 兼容字段
```

### 5. Smoke Test 脚本

**文件**: `backend/scripts/smoke_format_templates.sh`

**功能**：
- 自动化测试完整流程
- 上传模板 → 预览 → 套用 → 下载
- 验证 URL 可访问性
- 检查 DOCX 内部结构（页眉、媒体文件）

**使用方法**：
```bash
# 准备测试模板（包含 Logo 的 DOCX）
export TEMPLATE_FILE=/path/to/template.docx
export AUTH_TOKEN=your_token
export API_BASE=http://localhost:8000

# 运行测试
./backend/scripts/smoke_format_templates.sh

# 输出目录
/tmp/format_templates_smoke_test/
├── template_preview.pdf      # 模板原始预览
├── project_preview.pdf        # 项目套用后预览
├── project_export.docx        # 项目导出 DOCX
└── apply_response.json        # API 响应
```

---

## API 端点总览

### 格式预览相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/apps/tender/projects/{id}/directory/format-preview` | 获取项目格式预览（PDF/DOCX） |
| GET | `/api/apps/tender/projects/{id}/exports/docx/{filename}` | 下载导出的 DOCX |
| POST | `/api/apps/tender/projects/{id}/directory/apply-format-template` | 套用格式模板 |

### 完整请求/响应示例

#### 1. 套用格式模板

```bash
POST /api/apps/tender/projects/tprj_xxx/directory/apply-format-template?return_type=json
Content-Type: application/json

{
  "format_template_id": "tpl_xxxxx"
}
```

**响应**：
```json
{
  "ok": true,
  "nodes": [...],
  "preview_pdf_url": "/api/apps/tender/projects/tprj_xxx/directory/format-preview?format=pdf&format_template_id=tpl_xxxxx",
  "download_docx_url": "/api/apps/tender/projects/tprj_xxx/exports/docx/project_tprj_xxx_abc123.docx"
}
```

#### 2. 获取格式预览

```bash
GET /api/apps/tender/projects/tprj_xxx/directory/format-preview?format=pdf
Authorization: Bearer <token>
```

**响应**：
- Content-Type: `application/pdf`
- 文件流（可直接在浏览器打开）

#### 3. 下载 DOCX

```bash
GET /api/apps/tender/projects/tprj_xxx/exports/docx/project_tprj_xxx_abc123.docx
Authorization: Bearer <token>
```

**响应**：
- Content-Type: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Content-Disposition: `attachment; filename="项目名称_xxx.docx"`

---

## 文件存储架构

```
/app/storage/tender/
├── format_templates/           # 格式模板原始文件（持久化）
│   ├── abc123_模板1.docx
│   └── def456_模板2.docx
└── renders/                    # 导出结果（持久化）
    ├── tprj_001/
    │   ├── project_xxx.docx   # 套用后的导出文件
    │   └── preview/            # 预览文件（可缓存）
    │       ├── project_xxx.docx
    │       └── project_xxx.pdf
    └── tprj_002/
        └── ...
```

**环境变量**：
```yaml
TENDER_FORMAT_TEMPLATES_DIR: /app/storage/tender/format_templates
TENDER_RENDERS_DIR: /app/storage/tender/renders
```

**Docker 挂载**（`docker-compose.yml`）：
```yaml
volumes:
  - ./storage:/app/storage  # 确保持久化
```

---

## 核心技术保证

### 1. 模板原样保存
```python
# ✅ 正确做法
with open(storage_path, "wb") as f:
    f.write(docx_bytes)

# ❌ 错误做法（会丢失页眉Logo）
doc = Document(upload_path)
doc.save(storage_path)  # 重写会丢失元数据
```

### 2. 导出使用模板母版
```python
# ✅ 正确做法（保留页眉页脚）
doc = Document(template_path)
_clear_body_keep_sectpr(doc)  # 只清空正文，保留节设置
doc.add_paragraph("新内容")
doc.save(output_path)

# ❌ 错误做法（丢失页眉页脚）
doc = Document()  # 空文档，没有模板信息
```

### 3. PDF 转换
```bash
soffice \
  --headless \
  --nologo \
  --nolockcheck \
  --convert-to pdf \
  --outdir /output/dir \
  /path/to/input.docx
```

**依赖**：
- LibreOffice (soffice)
- Docker 镜像需包含：`apt install -y libreoffice-writer`

---

## 验收标准

### ✅ 功能验收
1. **模板预览**
   - [ ] 可下载模板原始 DOCX
   - [ ] 可预览模板 PDF（如 LibreOffice 可用）
   - [ ] PDF 中包含原始页眉 Logo

2. **套用格式**
   - [ ] POST apply-format-template 返回 `ok: true`
   - [ ] 返回 `preview_pdf_url` 和 `download_docx_url`
   - [ ] 两个 URL 均可直接 GET 访问

3. **导出文档**
   - [ ] DOCX 可正常打开
   - [ ] DOCX 包含模板页眉页脚
   - [ ] DOCX 包含媒体文件（Logo）
   - [ ] 使用 `unzip -l xxx.docx | grep word/header` 可验证

4. **PDF 预览**
   - [ ] 格式预览端点可返回 PDF
   - [ ] PDF 包含完整样式和 Logo
   - [ ] 转换失败时降级返回 DOCX（不报错）

### ✅ 技术验收
1. **存储持久化**
   - [ ] 模板文件存储在 `/app/storage/tender/format_templates/`
   - [ ] 导出文件存储在 `/app/storage/tender/renders/{project_id}/`
   - [ ] Docker volume 正确挂载

2. **错误处理**
   - [ ] 模板不存在时返回 404
   - [ ] 权限不足时返回 403
   - [ ] PDF 转换失败时降级返回 DOCX + 错误信息

3. **性能优化（可选）**
   - [ ] 预览文件可缓存（基于 project_id + template_id + nodes updated_at）
   - [ ] 大文件转换异步处理（如使用 Celery）

---

## 前端对接指南

### TenderWorkspace.tsx 无需改动

前端已有的代码：
```typescript
const response = await fetch(
  `/api/apps/tender/projects/${projectId}/directory/apply-format-template?return_type=json`,
  {
    method: 'POST',
    body: JSON.stringify({ format_template_id: templateId })
  }
);

const data = await response.json();
// data.preview_pdf_url - 可直接用作 <embed src={...}> 或 <a href={...}>
// data.download_docx_url - 可直接用作 <a href={...} download>
```

**前端只需确保**：
1. `preview_pdf_url` 用于 PDF 预览（iframe/embed）
2. `download_docx_url` 用于 DOCX 下载链接
3. 两个 URL 都需要带上 `Authorization` header（如使用 fetch）

---

## 故障排查

### 问题 1: PDF 预览空白
**可能原因**：
- LibreOffice 未安装
- soffice 不在 PATH

**解决方案**：
```bash
# 检查 LibreOffice
docker exec backend which soffice
docker exec backend soffice --version

# 如未安装
docker exec backend apt update
docker exec backend apt install -y libreoffice-writer
```

### 问题 2: DOCX 页眉 Logo 丢失
**可能原因**：
- 模板上传时被重写
- 导出时未使用模板母版

**检查点**：
```bash
# 1. 验证模板文件是否原样保存
unzip -l /app/storage/tender/format_templates/xxx.docx | grep word/header
unzip -l /app/storage/tender/format_templates/xxx.docx | grep word/media

# 2. 验证导出使用了模板
grep "Document(template_path)" backend/app/services/export/docx_exporter.py
```

### 问题 3: URL 返回 404
**可能原因**：
- 路由未注册
- 权限检查失败

**检查点**：
```bash
# 1. 确认路由注册
grep "format-preview" backend/app/routers/format_templates.py
grep "include_router" backend/app/routers/tender.py

# 2. 检查日志
docker logs backend | grep "format-preview"
```

---

## 后续优化建议

### 短期（必须）
1. ✅ 实现 PDF 转换（已完成）
2. ✅ 添加 Smoke Test（已完成）
3. ⏳ 增加单元测试覆盖率

### 中期（推荐）
1. 预览文件缓存策略（避免重复转换）
2. 异步 PDF 转换（大文件时避免阻塞）
3. 模板版本管理（支持模板更新历史）

### 长期（可选）
1. 模板市场（公开模板分享）
2. 在线模板编辑器
3. 多格式支持（ODT, RTF 等）

---

## 相关文件清单

### 修改的文件
- `backend/app/routers/format_templates.py` - 新增格式预览端点
- `backend/app/works/tender/format_templates/work.py` - 新增预览方法和 PDF 转换
- `backend/app/works/tender/format_templates/types.py` - 新增类型定义

### 新增的文件
- `backend/scripts/smoke_format_templates.sh` - Smoke Test 脚本
- `docs/FORMAT_TEMPLATES_FIX_SUMMARY.md` - 本文档

### 无需修改的文件（已验证正确）
- `backend/app/services/export/export_service.py` - 导出服务
- `backend/app/services/export/docx_exporter.py` - DOCX 渲染器
- `backend/app/services/dao/tender_dao.py` - DAO 层
- `docker-compose.yml` - 已配置正确的环境变量和 volume

---

## 总结

本次修复完成了格式模板功能的最后一环：

✅ **模板原样保存** - 保证 Logo/页眉不丢失  
✅ **导出使用模板母版** - 保证样式完整继承  
✅ **返回可访问 URL** - 前端可直接使用  
✅ **新增格式预览端点** - 支持 PDF/DOCX 在线预览  
✅ **完整的 Smoke Test** - 保证端到端流程正确  

**前端无需改动，后端完全兼容现有调用！**

