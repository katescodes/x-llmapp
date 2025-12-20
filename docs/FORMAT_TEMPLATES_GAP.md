# 格式模板接口缺口清单 (Format Templates Gap Analysis)

> **生成时间**: 2025-12-21  
> **目标**: 对齐前端真实接口需求与后端实现状态

---

## 📋 执行摘要

### ✅ 后端路由配置确认

**Tender Router Prefix**: `/api/apps/tender` ✅  
**Template Analysis Router Prefix**: `/api/apps/tender/templates` ✅

来源：
- `backend/app/main.py:264` - `app.include_router(tender.router)`
- `backend/app/routers/tender.py:42` - `router = APIRouter(prefix="/api/apps/tender", tags=["tender"])`
- `backend/app/routers/template_analysis.py:26` - `router = APIRouter(prefix="/api/apps/tender/templates", tags=["template-analysis"])`

### 🎯 接口对齐状态

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 完全匹配 | 12 | 前后端路径、方法、返回结构完全一致 |
| ⚠️ 需要注意 | 3 | 路由存在但需要验证响应结构或行为 |
| ❌ 缺失 | 0 | 无缺失接口 |

---

## 🔍 前端接口清点

### 1️⃣ FormatTemplatesPage.tsx (格式模板管理页面)

#### 1.1 列出所有格式模板
```typescript
GET /api/apps/tender/format-templates
```
**调用位置**: `FormatTemplatesPage.tsx:62`  
**期望返回**: `Array<FormatTemplate>`
```typescript
interface FormatTemplate {
  id: string;
  name: string;
  description?: string;
  is_public: boolean;
  owner_id: string;
  template_storage_path: string;
  analysis_json?: any;
  template_spec_analyzed_at?: string;
  created_at: string;
  updated_at: string;
}
```
**后端状态**: ✅ **已实现** - `tender.py:1234`

---

#### 1.2 获取格式模板详情
```typescript
GET /api/apps/tender/format-templates/{templateId}
```
**调用位置**: `FormatTemplatesPage.tsx:86`  
**期望返回**: `FormatTemplate`  
**后端状态**: ✅ **已实现** - `tender.py:1241`

---

#### 1.3 获取格式模板样式规格
```typescript
GET /api/apps/tender/format-templates/{templateId}/spec
```
**调用位置**: 
- `FormatTemplatesPage.tsx:87`
- `TenderWorkspace.tsx:337`
- `templateApi.ts:42`

**期望返回**: 样式规格对象
```typescript
interface TemplateSpec {
  style_hints?: {
    [styleName: string]: {
      fontSize?: string;
      bold?: boolean;
      italic?: boolean;
      underline?: boolean;
      color?: string;
      alignment?: string;
      lineSpacing?: number;
      indentLeft?: string;
      // ... 其他样式属性
    }
  };
  // 其他规格字段
}
```
**后端状态**: ✅ **已实现** - `tender.py:1269`

---

#### 1.4 获取格式模板分析摘要
```typescript
GET /api/apps/tender/format-templates/{templateId}/analysis-summary
```
**调用位置**: `FormatTemplatesPage.tsx:88`  
**期望返回**: 分析摘要对象  
**后端状态**: ✅ **已实现** - `tender.py:1376`

---

#### 1.5 获取格式模板解析摘要
```typescript
GET /api/apps/tender/format-templates/{templateId}/parse-summary
```
**调用位置**: 
- `FormatTemplatesPage.tsx:89`
- `FormatTemplatesPage.tsx:291`

**期望返回**: 解析摘要对象
```typescript
interface ParseSummary {
  sections?: Array<any>;
  variants?: Array<any>;
  headingLevels?: Array<any>;
  // ... 其他解析信息
}
```
**后端状态**: ✅ **已实现** - `tender.py:1507`

---

#### 1.6 获取模板分析结果（LLM分析）
```typescript
GET /api/apps/tender/templates/{templateId}/analysis
```
**调用位置**: `FormatTemplatesPage.tsx:90`  
**期望返回**: 模板分析对象
```typescript
interface TemplateAnalysis {
  templateName: string;
  confidence: number;
  warnings: string[];
  anchorsCount: number;
  hasContentMarker: boolean;
  keepBlocksCount: number;
  deleteBlocksCount: number;
  headingStyles: Record<string, any>;
  bodyStyle?: any;
  blocksSummary: {
    total: number;
    paragraphs: number;
    tables: number;
    // ...
  };
}
```
**后端状态**: ✅ **已实现** - `template_analysis.py:189`  
**注意**: 此接口在 `template_analysis` 路由下，完整路径为 `/api/apps/tender/templates/{templateId}/analysis`

---

#### 1.7 预览格式模板文档
```typescript
GET /api/apps/tender/format-templates/{templateId}/preview?format={format}&ts={timestamp}
```
**调用位置**: `FormatTemplatesPage.tsx:129`  
**查询参数**: 
- `format`: `pdf` | `docx`
- `ts`: 时间戳（用于缓存破坏）

**期望返回**: 文件流 (Content-Type: `application/pdf` 或 `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)  
**后端状态**: ✅ **已实现** - `tender.py:1524`

---

#### 1.8 创建格式模板
```typescript
POST /api/apps/tender/format-templates
Content-Type: multipart/form-data

FormData {
  name: string;
  description?: string;
  is_public: boolean;
  file: File;
  model_id?: string;
}
```
**调用位置**: `FormatTemplatesPage.tsx:187`  
**期望返回**: `FormatTemplate`  
**后端状态**: ✅ **已实现** - `tender.py:1095`

---

#### 1.9 删除格式模板
```typescript
DELETE /api/apps/tender/format-templates/{templateId}
```
**调用位置**: `FormatTemplatesPage.tsx:207`  
**期望返回**: 204 No Content  
**后端状态**: ✅ **已实现** - `tender.py:1450`

---

#### 1.10 更新格式模板元数据
```typescript
PUT /api/apps/tender/format-templates/{templateId}
Content-Type: application/json

{
  name?: string;
  description?: string;
  is_public?: boolean;
}
```
**调用位置**: `FormatTemplatesPage.tsx:224`  
**期望返回**: `FormatTemplate`  
**后端状态**: ✅ **已实现** - `tender.py:1258`

---

#### 1.11 替换格式模板文件
```typescript
PUT /api/apps/tender/format-templates/{templateId}/file
Content-Type: multipart/form-data

FormData {
  file: File;
}
```
**调用位置**: `FormatTemplatesPage.tsx:249`  
**期望返回**: 成功响应  
**后端状态**: ✅ **已实现** - `tender.py:1420`

---

#### 1.12 强制重新分析格式模板
```typescript
POST /api/apps/tender/format-templates/{templateId}/analyze?force=true
Content-Type: multipart/form-data

FormData {
  file: File;
  force: 'true';
}
```
**调用位置**: `FormatTemplatesPage.tsx:276`  
**期望返回**: 成功响应  
**后端状态**: ✅ **已实现** - `tender.py:1389`

---

#### 1.13 触发确定性解析
```typescript
POST /api/apps/tender/format-templates/{templateId}/parse?force=true
```
**调用位置**: `FormatTemplatesPage.tsx:290`  
**期望返回**: 成功响应  
**后端状态**: ✅ **已实现** - `tender.py:1488`

---

#### 1.14 重新分析模板（使用LLM）
```typescript
POST /api/apps/tender/templates/{templateId}/reanalyze
```
**调用位置**: `FormatTemplatesPage.tsx:316`  
**期望返回**: 分析结果  
**后端状态**: ✅ **已实现** - `template_analysis.py:342`  
**注意**: 此接口在 `template_analysis` 路由下，完整路径为 `/api/apps/tender/templates/{templateId}/reanalyze`

---

### 2️⃣ TenderWorkspace.tsx (投标工作区)

#### 2.1 列出格式模板
```typescript
GET /api/apps/tender/format-templates
```
**调用位置**: `TenderWorkspace.tsx:271`  
**期望返回**: `Array<{ id: string; name: string }>`  
**后端状态**: ✅ **已实现** - `tender.py:1234`

---

#### 2.2 获取格式模板样式规格
```typescript
GET /api/apps/tender/format-templates/{templateId}/spec
```
**调用位置**: `TenderWorkspace.tsx:337`  
**期望返回**: 样式规格对象  
**后端状态**: ✅ **已实现** - `tender.py:1269`

---

#### 2.3 套用格式模板到项目目录
```typescript
POST /api/apps/tender/projects/{projectId}/directory/apply-format-template?return_type=json
Content-Type: application/json

{
  format_template_id: string;
}
```
**调用位置**: `TenderWorkspace.tsx:686`  
**查询参数**: `return_type=json` (也支持 `file` 用于直接下载)  
**期望返回**: 
```typescript
{
  ok: boolean;
  detail?: string;
  nodes?: Array<DirectoryNode>;
  preview_pdf_url?: string;
  download_docx_url?: string;
}
```
**后端状态**: ✅ **已实现** - `tender.py:577`

---

### 3️⃣ TemplateManagement.tsx (模板管理组件)

#### 3.1 列出格式模板
```typescript
GET /api/apps/tender/format-templates
```
**调用位置**: `TemplateManagement.tsx:40`  
**后端状态**: ✅ **已实现** - `tender.py:1234`

---

#### 3.2 创建格式模板
```typescript
POST /api/apps/tender/format-templates
```
**调用位置**: `TemplateManagement.tsx:75`  
**后端状态**: ✅ **已实现** - `tender.py:1095`

---

#### 3.3 删除格式模板
```typescript
DELETE /api/apps/tender/format-templates/{templateId}
```
**调用位置**: `TemplateManagement.tsx:101`  
**后端状态**: ✅ **已实现** - `tender.py:1450`

---

#### 3.4 下载格式模板文件
```typescript
GET /api/apps/tender/format-templates/{templateId}/file
```
**调用位置**: `TemplateManagement.tsx:113`  
**期望返回**: Blob (文件流)  
**后端状态**: ✅ **已实现** - `tender.py:1467`

---

## ⚠️ 需要注意的接口

### 1. 模板分析接口 (跨路由)

**接口**: `GET /api/apps/tender/templates/{templateId}/analysis`  
**问题**: 此接口在 `template_analysis` 路由器中定义，路径为 `/api/apps/tender/templates`，与 `tender` 路由器的 `format-templates` 路径不一致。

**前端调用**:
- `FormatTemplatesPage.tsx:90` - 使用 `/api/apps/tender/templates/{templateId}/analysis`

**后端实现**:
- `template_analysis.py:189` - `@router.get("/{template_id}/analysis")`
- 完整路径: `/api/apps/tender/templates/{templateId}/analysis` ✅

**结论**: ✅ **路径正确**，前端使用的是 `/templates/` 而非 `/format-templates/`，与后端路由一致。

---

### 2. 重新分析接口 (跨路由)

**接口**: `POST /api/apps/tender/templates/{templateId}/reanalyze`  
**问题**: 同样在 `template_analysis` 路由器中，使用 `/templates/` 路径。

**前端调用**:
- `FormatTemplatesPage.tsx:316` - 使用 `/api/apps/tender/templates/{templateId}/reanalyze`

**后端实现**:
- `template_analysis.py:342` - `@router.post("/{template_id}/reanalyze")`
- 完整路径: `/api/apps/tender/templates/{templateId}/reanalyze` ✅

**结论**: ✅ **路径正确**

---

### 3. 套用格式模板返回格式

**接口**: `POST /api/apps/tender/projects/{projectId}/directory/apply-format-template`

**前端期望**:
```typescript
const data = await api.post(
  `/api/apps/tender/projects/${currentProject.id}/directory/apply-format-template?return_type=json`,
  { format_template_id: selectedFormatTemplateId }
);

// 期望字段:
{
  ok: boolean;
  detail?: string;
  nodes?: Array<DirectoryNode>;
  preview_pdf_url?: string;
  download_docx_url?: string;
}
```

**后端实现**: `tender.py:577`
- 支持 `return_type` 参数 (`json` 或 `file`)
- 返回结构需要验证是否包含所有期望字段

**建议**: 
1. 验证返回的 JSON 是否包含 `preview_pdf_url` 和 `download_docx_url`
2. 确认 `nodes` 数组返回格式是否符合前端期望

---

## 🎯 路由架构说明

系统采用**双路由器架构**处理格式模板相关功能：

### 1. Tender Router (`/api/apps/tender`)
**文件**: `backend/app/routers/tender.py`  
**职责**: 格式模板的 CRUD 操作、文件管理、样式解析

**端点前缀**: `/format-templates`
- GET    `/format-templates` - 列出模板
- POST   `/format-templates` - 创建模板
- GET    `/format-templates/{id}` - 获取详情
- PUT    `/format-templates/{id}` - 更新元数据
- DELETE `/format-templates/{id}` - 删除模板
- GET    `/format-templates/{id}/spec` - 获取样式规格
- GET    `/format-templates/{id}/file` - 下载文件
- PUT    `/format-templates/{id}/file` - 替换文件
- GET    `/format-templates/{id}/preview` - 预览文档
- POST   `/format-templates/{id}/analyze` - 强制分析
- POST   `/format-templates/{id}/parse` - 确定性解析
- GET    `/format-templates/{id}/parse-summary` - 解析摘要
- GET    `/format-templates/{id}/analysis-summary` - 分析摘要

### 2. Template Analysis Router (`/api/apps/tender/templates`)
**文件**: `backend/app/routers/template_analysis.py`  
**职责**: 基于 LLM 的模板智能分析

**端点前缀**: `/templates`
- GET  `/templates/{id}/analysis` - 获取LLM分析结果
- POST `/templates/{id}/reanalyze` - 重新进行LLM分析

### 设计原因

1. **职责分离**: 
   - `format-templates` 处理样式规则、文档结构等确定性操作
   - `templates` 处理需要 LLM 推理的智能分析

2. **路径区分**:
   - `/format-templates/` - 确定性操作
   - `/templates/` - 智能分析操作

---

## ✅ 完整接口清单

| 序号 | 方法 | 路径 | 前端调用 | 后端实现 | 状态 |
|------|------|------|----------|----------|------|
| 1 | GET | `/api/apps/tender/format-templates` | FormatTemplatesPage:62<br>TenderWorkspace:271<br>TemplateManagement:40 | tender.py:1234 | ✅ |
| 2 | POST | `/api/apps/tender/format-templates` | FormatTemplatesPage:187<br>TemplateManagement:75 | tender.py:1095 | ✅ |
| 3 | GET | `/api/apps/tender/format-templates/{id}` | FormatTemplatesPage:86 | tender.py:1241 | ✅ |
| 4 | PUT | `/api/apps/tender/format-templates/{id}` | FormatTemplatesPage:224 | tender.py:1258 | ✅ |
| 5 | DELETE | `/api/apps/tender/format-templates/{id}` | FormatTemplatesPage:207<br>TemplateManagement:101 | tender.py:1450 | ✅ |
| 6 | GET | `/api/apps/tender/format-templates/{id}/spec` | FormatTemplatesPage:87<br>TenderWorkspace:337<br>templateApi:42 | tender.py:1269 | ✅ |
| 7 | GET | `/api/apps/tender/format-templates/{id}/file` | TemplateManagement:113 | tender.py:1467 | ✅ |
| 8 | PUT | `/api/apps/tender/format-templates/{id}/file` | FormatTemplatesPage:249 | tender.py:1420 | ✅ |
| 9 | GET | `/api/apps/tender/format-templates/{id}/preview` | FormatTemplatesPage:129 | tender.py:1524 | ✅ |
| 10 | POST | `/api/apps/tender/format-templates/{id}/analyze` | FormatTemplatesPage:276 | tender.py:1389 | ✅ |
| 11 | POST | `/api/apps/tender/format-templates/{id}/parse` | FormatTemplatesPage:290 | tender.py:1488 | ✅ |
| 12 | GET | `/api/apps/tender/format-templates/{id}/parse-summary` | FormatTemplatesPage:89,291 | tender.py:1507 | ✅ |
| 13 | GET | `/api/apps/tender/format-templates/{id}/analysis-summary` | FormatTemplatesPage:88 | tender.py:1376 | ✅ |
| 14 | GET | `/api/apps/tender/templates/{id}/analysis` | FormatTemplatesPage:90 | template_analysis.py:189 | ✅ |
| 15 | POST | `/api/apps/tender/templates/{id}/reanalyze` | FormatTemplatesPage:316 | template_analysis.py:342 | ✅ |
| 16 | POST | `/api/apps/tender/projects/{id}/directory/apply-format-template` | TenderWorkspace:686 | tender.py:577 | ⚠️ |

**图例**:
- ✅ 完全匹配
- ⚠️ 需要验证响应结构或行为
- ❌ 缺失（当前无缺失接口）

---

## 🔧 建议和后续行动

### 1. 验证响应结构
- [ ] 测试 `apply-format-template` 接口的 JSON 响应是否包含所有前端期望字段
- [ ] 验证 `preview_pdf_url` 和 `download_docx_url` 的 URL 格式和可访问性

### 2. 文档完善
- [ ] 为 `template_analysis` 路由器添加 OpenAPI 文档说明
- [ ] 统一前端 API 调用的错误处理机制

### 3. 性能优化建议
- [ ] 考虑为大型模板文件的分析操作添加后台任务队列
- [ ] 为预览文件添加缓存机制（基于 `ts` 参数）

### 4. 安全性检查
- [ ] 验证所有文件上传接口的文件类型和大小限制
- [ ] 确认权限控制（`is_public` 和 `owner_id`）在所有端点正确实施

---

## 📊 统计信息

- **总接口数**: 16
- **完全匹配**: 15 (93.75%)
- **需要注意**: 1 (6.25%)
- **缺失接口**: 0 (0%)
- **前端组件**: 4 个
- **后端路由器**: 2 个
- **涉及文件**: 
  - 前端: 5 个 TypeScript 文件
  - 后端: 2 个 Python 路由文件

---

## 📝 结论

✅ **前后端接口对齐状态良好**

1. **所有前端调用的接口都已在后端实现**
2. **路由前缀配置正确**: `/api/apps/tender`
3. **双路由器架构合理**: 确定性操作和智能分析分离
4. **仅需验证一个接口的响应结构**: `apply-format-template`

建议在继续开发前进行以下验证：
- 运行端到端测试验证 `apply-format-template` 的 JSON 响应
- 确认所有文件预览和下载功能在 Docker 环境中正常工作
- 验证跨路由器的接口调用（`/templates/` vs `/format-templates/`）在前端是否清晰区分

---

**文档生成完毕** ✓

