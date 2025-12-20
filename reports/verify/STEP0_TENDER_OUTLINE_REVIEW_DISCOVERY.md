# Step 0: 招投标 outline/review 现状盘点

生成时间: 2025-12-20
任务: 将 semantic_outline 和 review 收口到 works/tender（容器内为 app/apps/tender）

## 一、容器路径映射关系

- 宿主机 `backend/app/works/tender` → 容器内 `app/apps/tender`  
- 宿主机 `backend/app/services` → 容器内 `app/services`  
- 宿主机 `backend/app/routers` → 容器内 `app/routers`

## 二、semantic_outline 现状

### 2.1 services/semantic_outline/ 真实文件列表

```
app/services/semantic_outline/
├── __init__.py (302 bytes)
├── outline_synthesis_service.py (13,026 bytes)
└── requirement_extraction_service.py (11,741 bytes)
```

### 2.2 TenderService 中目录生成函数

**位置**: `app/services/tender_service.py`

- **Line 4029**: `def generate_semantic_outline(self, project_id, mode="FAST", max_depth=5)`
  - 导入: `from app.services.semantic_outline import RequirementExtractionService, OutlineSynthesisService`
  - 导入: `from app.schemas.semantic_outline import ...`
  - 落库: `self.dao.create_semantic_outline()` → 表 `tender_semantic_outlines`
  - 落库: `self.dao.save_semantic_outline_nodes()` → 表 `tender_semantic_outline_nodes`

- **Line 4315**: `def get_semantic_outline(self, outline_id)`
  - 查询: `self.dao.get_semantic_outline(outline_id)`
  - 查询: `self.dao.get_semantic_outline_nodes(outline_id)`

- **Line 4386**: `def get_latest_semantic_outline(self, project_id)`
  - 查询: `self.dao.get_latest_semantic_outline(project_id)`

### 2.3 Router 中目录生成端点

**位置**: `app/routers/tender.py`

- **Line 1574**: `@router.post("/projects/{project_id}/semantic-outline")`  
  - 函数: `def generate_semantic_outline(...)`
  - 调用: `svc.generate_semantic_outline(project_id, mode=req.mode, max_depth=req.max_depth)`

- **Line 1635**: `@router.get("/projects/{project_id}/semantic-outline/latest")`  
  - 函数: `def get_latest_semantic_outline(project_id)`
  - 调用: `svc.get_latest_semantic_outline(project_id)`

- **Line 1670**: `@router.get("/projects/{project_id}/semantic-outline")`  
  - 函数: `def list_semantic_outlines(project_id)`
  - 调用: `dao.list_semantic_outlines(project_id)`

### 2.4 其他依赖

- `app/services/dao/tender_dao.py`:
  - `create_semantic_outline()` (line 1341)
  - `get_semantic_outline()` (line 1363)
  - `get_latest_semantic_outline()` (line 1375)
  - `list_semantic_outlines()` (line 1389)
  - `save_semantic_outline_nodes()` (line 1463)
  - `get_semantic_outline_nodes()` (line 1512)
  - `get_latest_semantic_outline_nodes()` (line 651) - export用

- `app/routers/export.py` (line 153, 181): 使用 `dao.get_latest_semantic_outline_nodes()` 导出
- `app/services/export/`: summary_backfill, tree_builder, export_service 都使用

## 三、review 现状

### 3.1 review 主入口定位

**主入口**: `app/services/tender_service.py` 的 `run_review()` (line 2122)

**NEW_ONLY v2入口**: `app/apps/tender/review_v2_service.py`
- **Class**: `ReviewV2Service` (line 53)
- **Method**: `async def run_review_v2()` (line 88)

### 3.2 TenderService.run_review() 实现

**位置**: `app/services/tender_service.py:2122`

**逻辑**:
1. 读取 cutover config，获取 `REVIEW_MODE`
2. **NEW_ONLY 分支** (line 2381):
   - `from app.apps.tender.review_v2_service import ReviewV2Service`
   - `review_v2 = ReviewV2Service(pool, self.llm)`
   - `v2_results = asyncio.run(review_v2.run_review_v2(...))`
   - 落库: `self.dao.replace_review_items(project_id, arr)`
   
3. **PREFER_NEW 分支** (line 2447):
   - 尝试 v2，失败则 fallback（但目前NEW_ONLY已强制）
   
4. **SHADOW 分支** (line 2498):
   - 同时跑新旧，对比结果（目前NEW_ONLY已强制）

5. **ReviewCase 双写** (line 2537):
   - `from app.services.platform.reviewcase_service import ReviewCaseService`
   - 如果启用规则评估器，写入 `review_cases` 表

### 3.3 Router 中审核端点

**位置**: `app/routers/tender.py`

- **Line 836**: `@router.post("/projects/{project_id}/review")`
  - 函数: `def run_review(project_id, req: ReviewRunReq)`
  - 调用: `svc.run_review(project_id, model_id=req.model_id, run_id=run_id, owner_id=...)`

- **Line 895**: `@router.get("/projects/{project_id}/review")`
  - 函数: 返回审核结果列表
  - 调用: `dao.list_review_items(project_id)`

- **Line 932**: 导出端点可能读取 `review_findings` (ReviewCase表)

### 3.4 review_v2_service.py 现状

**位置**: `app/apps/tender/review_v2_service.py`

**特点**:
- ✅ 已有 `ReviewV2Service` 类
- ✅ 已有 `run_review_v2()` 方法
- ❌ **缺少** `extraction_specs/review_v2.py` (queries/topk/doc_types 配置)
- ❌ **缺少** `prompts/review_v2.md` (LLM prompt)
- ❌ **缺少** MUST_HIT_001 兜底规则

**当前实现**:
- 直接硬编码检索逻辑（line 121, 146）
- 硬编码审核规则和LLM调用
- 返回格式: `List[Dict]` 对齐 `tender_review_items` 表字段

### 3.5 DAO 和数据库

- `app/services/dao/tender_dao.py`:
  - `replace_review_items()` (line 696): 删除+插入 `tender_review_items`
  - `list_review_items()` (line 726): 查询 `tender_review_items`

- 表结构:
  - `tender_review_items`: 存储审核结果
  - `review_cases`: ReviewCase 系统表（旁路双写，可选）

### 3.6 其他依赖

- `app/queue/tasks.py` (line 214): 异步任务也调用 `review_v2.run_review_v2()`
- `app/services/platform/reviewcase_service.py`: ReviewCase 服务（独立功能）
- `app/services/project_delete/cleaners.py` (line 276, 303): 删除项目时清理 review_items

## 四、依赖关系图

```
Router (tender.py)
    ↓
TenderService
    ↓
    ├─ semantic_outline → services/semantic_outline/* (需迁移)
    └─ run_review → apps/tender/review_v2_service.py (已在works，需补齐spec)

当前 works/tender (容器内 app/apps/tender):
├── extract_v2_service.py ✅ (有spec+prompt)
├── review_v2_service.py ⚠️ (缺spec+prompt)
├── extraction_specs/
│   ├── project_info_v2.py ✅
│   └── risks_v2.py ✅
└── prompts/
    ├── project_info_v2.md ✅
    └── risks_v2.md ✅
```

## 五、迁移计划总结

### 需要迁移到 works/tender:

1. **semantic_outline (完整目录)**:
   - `services/semantic_outline/` → `works/tender/outline/`
   - 新增统一入口: `outline_v2_service.py`
   - 保留旧目录作为shim

2. **review 配置化**:
   - 新增: `extraction_specs/review_v2.py`
   - 新增: `prompts/review_v2.md`
   - 改造: `review_v2_service.py` 使用spec+prompt
   - 新增: MUST_HIT_001 兜底规则

### Router 需调整:

- `tender.py` 的 outline 端点: 改调 `works.tender.outline.outline_v2_service`
- `tender.py` 的 review 端点: 确保只调 `works.tender.review_v2_service`

### 保持不变:

- DAO 接口不变（`tender_dao.py`）
- 数据库表结构不变
- API 返回格式不变（前端兼容）

## 六、验收要点

- [ ] `services/semantic_outline/` 变为shim，真实实现在 `works/tender/outline/`
- [ ] Router 不再 `import app.services.semantic_outline`
- [ ] Router 不再 `import app.services.*review*`（除ReviewCase旁路）
- [ ] `review_v2_service.py` 使用spec驱动，有MUST_HIT_001兜底
- [ ] 所有API返回格式不变
- [ ] `make verify-docker` Gate1/Gate2 PASS

