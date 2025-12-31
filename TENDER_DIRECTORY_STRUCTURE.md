# Tender 模块目录结构分类

## 📁 `/backend/app/works/tender/`

---

## 1️⃣ 核心服务层 (Core Services)
> 主要的业务逻辑和编排服务

```
extract_v2_service.py          # 核心提取服务：项目信息、招标要求、目录生成
review_v3_service.py            # 审核服务V3
unified_audit_service.py        # 统一审核服务
review_pipeline_v3.py           # 审核流水线V3
```

**说明**：
- `extract_v2_service.py` 是最核心的服务，编排了所有提取功能
- V3 系列是审核功能的新架构

---

## 2️⃣ 项目信息提取 (Project Info Extraction - Checklist Framework)
> 基于 Checklist 的项目信息提取框架（新架构）

```
checklists/
  ├── project_info_v1.yaml       # 项目信息提取清单（6个阶段）
  └── engineering_v1.yaml         # 工程项目专用清单
  
project_info_extractor.py        # 项目信息提取编排器
project_info_prompt_builder.py   # Prompt 构建器（P0+P1）
checklist_loader.py              # Checklist 加载器
```

**说明**：
- 这是项目信息提取的**新架构**
- 采用 YAML 清单 + P0/P1 两阶段提取
- 支持 6 个阶段的并行/串行提取

---

## 3️⃣ 目录生成 (Directory Generation - Multi-Stage Hybrid)
> 多阶段混合目录生成框架（新架构）

```
directory_fast_builder.py        # 阶段1：快速构建器（基于规则，无LLM）
schemas/directory_v2.py           # 阶段2：LLM生成 Spec + Schema 定义
directory_augment_v1.py           # 阶段3：目录增强（补充必填节点）
directory_refinement_rule.py     # 阶段4-A：规则细化（评分标准、资格审查）
directory_bracket_parser.py      # 阶段4-B：括号解析（生成L4子节点）
template_matcher.py              # 阶段5：格式范本匹配与填充
```

**说明**：
- 五阶段流水线：Fast Builder → LLM 补充 → 增强 → 细化 → 范本填充
- 优先使用规则快速构建，不足时才调用 LLM
- `schemas/directory_v2.py` 包含 Schema 定义和 LLM Spec 构建器

---

## 4️⃣ 招标要求提取 (Requirements Extraction - Framework)
> 招标要求提取框架（新架构）

```
framework_prompt_builder.py      # Framework Prompt 构建器
checklist_prompt_builder.py      # Checklist Prompt 构建器
requirement_postprocessor.py     # 要求项后处理器
simple_rule_parser.py            # 简单规则解析器
tender_context_retriever.py      # 上下文检索器
```

**说明**：
- 采用"标准清单 + P1 补充"的框架
- 支持基于 Checklist 的结构化提取

---

## 5️⃣ 审核与评审 (Review & Audit)
> 投标文件审核和评审功能

```
review/
  ├── audit_keys.py              # 审核维度定义
  └── review_dimensions.py       # 评审维度定义

review_v3_service.py             # 审核服务V3
unified_audit_service.py         # 统一审核服务（已重构为使用 ReviewPipelineV3）
review_pipeline_v3.py            # 审核流水线V3
review_report_enhancer.py        # 审核报告增强器
```

**说明**：
- V3 是审核功能的新架构
- 支持多维度审核和报告生成
- `unified_audit_service.py` 已重构为使用 `ReviewPipelineV3`，替代已删除的 `framework_bid_response_extractor`
- 审核流程：加载要求 → ReviewPipelineV3 → 统计分析 → 生成报告

---

## 6️⃣ 格式范本管理 (Format Templates - ✅ 正在使用)
> 投标文件格式范本管理

```
format_templates/
  ├── types.py                   # 范本类型定义
  └── work.py                    # 范本工作流（CRUD + 管理）

template_matcher.py              # 范本匹配器（目录生成阶段5使用）
```

**说明**：
- ✅ **正在使用**：
  - `format_templates/`：提供格式范本的 CRUD API（创建、列表、更新、删除）
  - `template_matcher.py`：在目录生成阶段5自动匹配和填充范本
- **两者关系**：
  - `format_templates/`：管理范本数据（存储在数据库和文件系统）
  - `template_matcher.py`：使用范本数据进行智能匹配和填充
- **独立功能，需保留**

---

## 7️⃣ 风险分析 (Risk Analysis)
> 投标风险分析功能

```
risk/
  ├── risk_analysis_service.py   # 风险分析服务
  └── __init__.py

schemas/risk_analysis.py         # 风险分析 Schema 定义
```

**说明**：
- 分析投标项目的潜在风险
- 生成风险报告

---

## 8️⃣ 价格明细提取 (Price Detail Extraction)
> 价格相关信息提取

```
price_detail_extractor.py        # 价格明细提取器
```

**说明**：
- 提取投标报价、价格明细等信息

---

## 9️⃣ 文档片段管理 (Document Snippets)
> 文档片段提取和定位

```
snippet/
  ├── doc_blocks.py              # 文档块定义
  ├── snippet_extract.py         # 片段提取器
  ├── snippet_llm.py             # LLM 片段提取
  └── snippet_locator.py         # 片段定位器
```

**说明**：
- 管理文档片段的提取、定位和引用
- 支持证据链追溯

---

## 🔟 文档导出 (Document Export)
> Word 文档样式映射

```
docx_style_mapper.py             # DOCX 样式映射器
```

**说明**：
- 处理导出 Word 文档的样式映射

---

## 1️⃣1️⃣ Schema 定义 (Schemas)
> 数据结构和验证

```
schemas/
  ├── tender_info_v3.py          # 项目信息 Schema V3（6个阶段）
  ├── directory_v2.py            # 目录生成 Schema V2 + LLM Spec 构建器
  ├── risk_analysis.py           # 风险分析 Schema
  └── validators.py              # 通用验证器
```

**说明**：
- 定义所有数据结构的 Pydantic Schema
- 提供验证和序列化功能
- `directory_v2.py` 特别重要，包含 LLM Spec 构建器

---

## 1️⃣2️⃣ 语义大纲 (Semantic Outline - ✅ 正在使用)
> 基于要求项的语义大纲生成

```
outline/
  ├── outline_synthesis_service.py      # 大纲合成服务
  ├── outline_v2_service.py             # 大纲服务V2（主入口）
  └── requirement_extraction_service.py # 要求项提取服务
```

**说明**：
- ✅ **正在使用**：API 路由 `/projects/{project_id}/generate-outline` 调用此模块
- 功能：从招标要求提取要求项，并合成多级语义目录
- **与目录生成的区别**：
  - 目录生成（`directory_*`）：生成投标文件的章节目录结构
  - 语义大纲（`outline`）：从招标要求生成结构化的要求项大纲
- **独立功能，需保留**

---

## 📊 架构总结

### ✅ 新架构模块（正在使用）
1. ✅ **项目信息提取 (Checklist Framework)**：`project_info_*` + `checklists/`
2. ✅ **目录生成 (Multi-Stage Hybrid)**：`directory_*` + `template_matcher.py`
3. ✅ **招标要求提取 (Framework)**：`framework_*` + `checklist_*`
4. ✅ **审核服务 (V3)**：`review_*` + `review/`
5. ✅ **Schema V3**：`schemas/tender_info_v3.py`, `schemas/directory_v2.py`
6. ✅ **语义大纲生成**：`outline/`（独立功能，与目录生成互补）
7. ✅ **格式范本管理**：`format_templates/`（数据管理） + `template_matcher.py`（匹配填充）

### ✅ 支撑模块（持续使用）
1. ✅ **snippet/**：文档片段管理
2. ✅ **risk/**：风险分析
3. ✅ **price_detail_extractor.py**：价格提取
4. ✅ **docx_style_mapper.py**：文档导出

### ✅ 核心服务（编排层）
1. ✅ **extract_v2_service.py**：核心提取编排服务
2. ✅ **review_v3_service.py**：审核服务
3. ✅ **unified_audit_service.py**：统一审核服务

---

## ✅ 最终结论

**所有模块都在使用中，无需删除！**

### 架构清晰度说明：

1. **项目信息提取** vs **目录生成** vs **语义大纲**：
   - **项目信息提取**：提取项目基本信息、资格、评分、商务、技术、文件准备等 6 个维度
   - **目录生成**：生成投标文件的章节目录（商务标、技术标、价格标）
   - **语义大纲**：从招标要求中提取并组织要求项的结构化大纲

2. **格式范本管理** vs **范本匹配**：
   - **format_templates/**：提供范本的 CRUD 管理（存储、查询、更新）
   - **template_matcher.py**：在目录生成时自动匹配和填充范本内容

3. **所有模块分工明确，功能互补，无重复代码**

---

## 📁 模块功能对照表

| 模块 | 功能 | API 端点 | 状态 |
|------|------|----------|------|
| **项目信息提取** | 提取项目基本信息、资格、评分等 | `/projects/{id}/extract/project-info` | ✅ 新架构 |
| **招标要求提取** | 提取招标文件的所有要求项 | `/projects/{id}/extract/requirements` | ✅ 新架构 |
| **目录生成** | 生成投标文件目录结构 | `/projects/{id}/extract/directory` | ✅ 新架构 |
| **投标响应提取** | 提取投标文件的响应要素 | `/projects/{id}/extract-bid-responses-framework` | ✅ v0.3.7 已恢复 |
| **语义大纲生成** | 从要求项生成结构化大纲 | `/projects/{id}/generate-outline` | ✅ 使用中 |
| **审核服务** | 审核投标文件完整性 | `/projects/{id}/audit/unified` | ✅ V3 架构（需先提取响应） |
| **风险分析** | 分析投标风险 | `/projects/{id}/risk-analysis` | ✅ 使用中 |
| **格式范本管理** | 管理格式范本 CRUD | `/format-templates/*` | ✅ 使用中 |
| **文档片段管理** | 提取和定位文档片段 | 内部服务 | ✅ 使用中 |
| **价格明细提取** | 提取价格信息 | 内部服务 | ✅ 使用中 |
| **文档导出** | Word 文档样式映射 | 内部服务 | ✅ 使用中 |

---

## 🔄 数据流关系图

```
招标文件上传
    ↓
┌───────────────────────────────────────────────┐
│  文档解析 & 片段化 (snippet/)                 │
└───────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────┐
│  提取层 (extract_v2_service.py)               │
│  ├─ 项目信息提取 (project_info_*)             │
│  ├─ 招标要求提取 (framework_*)                │
│  ├─ 目录生成 (directory_*)                    │
│  ├─ 价格提取 (price_detail_extractor)         │
│  └─ 语义大纲生成 (outline/)                   │
└───────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────┐
│  增强层                                        │
│  ├─ 格式范本匹配 (template_matcher)           │
│  ├─ 风险分析 (risk/)                          │
│  └─ 审核服务 (review_v3_service)              │
└───────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────┐
│  输出层                                        │
│  ├─ 结构化数据 (schemas/)                     │
│  ├─ 审核报告 (review_report_enhancer)         │
│  └─ Word 文档导出 (docx_style_mapper)         │
└───────────────────────────────────────────────┘
```

