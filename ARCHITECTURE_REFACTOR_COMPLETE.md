# 架构重构与Legacy清理完成报告

## 执行日期
2025-12-20

## 分支
`tender-remove-legacy`

## 完成的工作

### Step 1-6: 架构重构（已完成）
✅ **Step 1**: DocStoreService下沉到platform/docstore  
✅ **Step 2**: parse_document下沉到platform/ingest  
✅ **Step 3**: milvus_docseg_store下沉到platform/vectorstore  
✅ **Step 4**: retrieval统一到platform/retrieval (legacy作为provider)  
✅ **Step 5**: works/tender成为唯一Work入口，apps/tender变为shim  
✅ **Step 6**: DocStore为NEW_ONLY真理源，KB写入被隔离  

### Legacy清理（本次完成）

#### A. 旧接口隔离
- ✅ 创建 `routers/legacy/tender_legacy.py` 包含所有弃用接口
- ✅ 从 `routers/tender.py` 移除 `list_legacy_documents` 
- ✅ 添加 `LEGACY_TENDER_APIS_ENABLED=false` 环境变量控制
- ✅ 默认不挂载legacy路由，旧接口运行时不可见

#### B. 旧实现删除
- ✅ `_ingest_to_kb()` 方法改为直接抛出错误
- ✅ `upload_tender_file()` 删除 OLD/SHADOW/PREFER_NEW 分支
- ✅ 强制要求 INGEST_MODE=NEW_ONLY
- ✅ 删除所有 kb_documents/kb_chunks 写入路径

#### C. 重复文件清理
删除的重复文件：
- `backend/app/apps/tender/extract_v2_service.py`
- `backend/app/apps/tender/review_v2_service.py`
- `backend/app/apps/tender/extract_diff.py`
- `backend/app/apps/tender/review_diff.py`
- `backend/app/apps/tender/extraction_specs/` (整个目录)
- `backend/app/apps/tender/prompts/` (整个目录)
- `backend/app/apps/tender/contracts/` (整个目录)
- `frontend/src/components/TenderWorkspace_header.tsx.tmp`
- 4个 `.bak` 备份文件

保留的shim文件（向后兼容）：
- `backend/app/apps/tender/__init__.py` - re-export works.tender
- `backend/app/services/tender/*.py` - re-export works.tender.snippet
- `backend/app/services/retrieval/*.py` - re-export platform.retrieval.providers.legacy
- `backend/app/services/platform/docstore_service.py` - re-export platform.docstore
- `backend/app/services/documents/parser.py` - re-export platform.ingest.parser
- `backend/app/services/vectorstore/milvus_docseg_store.py` - re-export platform.vectorstore

## 验证结果

### ✅ 边界检查
```
检查1: Work层导入边界... ✓ PASS
检查2: apps/tender 边界... ✓ PASS
检查3: platform/ 不应导入 app.services... ✓ PASS
```

### ✅ 编译检查
所有Python文件编译通过，无语法错误

### ✅ Git提交
```
commit 812e0c5
feat: quarantine legacy tender APIs and remove OLD/SHADOW ingest paths
- 25 files changed, 416 insertions(+), 1561 deletions(-)
```

## 架构现状

### 清晰的分层结构

```
app/
├── platform/              # 基座（不依赖services，除legacy provider）
│   ├── docstore/         # 文档存储（DocStore表）
│   ├── ingest/          # 入库服务
│   ├── extraction/      # 抽取引擎
│   ├── retrieval/       # 检索门面
│   │   ├── new_retriever.py
│   │   ├── facade.py
│   │   └── providers/legacy/  # Legacy检索（允许依赖services）
│   ├── vectorstore/     # 向量存储
│   └── rules/          # 规则引擎
│
├── works/               # Work层（业务编排）
│   └── tender/         # 招投标Work（唯一实现）
│       ├── snippet/
│       ├── extraction_specs/
│       ├── prompts/
│       └── contracts/
│
├── routers/            # API路由
│   ├── tender.py       # 新接口
│   └── legacy/         # 旧接口（默认不挂载）
│       └── tender_legacy.py
│
└── services/           # 服务层（逐步下沉或弃用）
    ├── tender_service.py  # 只支持NEW_ONLY
    ├── platform/          # 保留的业务服务
    └── [shims]           # 兼容性shim
```

### 数据流（NEW_ONLY模式）

```
上传文件 → platform/ingest/v2_service.py
         ↓
         DocStore (documents/document_versions/doc_segments)
         ↓
         Milvus (doc_segments向量)

检索 → platform/retrieval/facade.py → new_retriever.py
     ↓
     DocStore + Milvus混合检索

抽取 → works/tender/extract_v2_service.py
     ↓
     platform/extraction/engine.py
```

## 待办事项（可选）

1. **删除更多SHADOW代码** (非关键)：
   - `extract_project_info()` 中的 SHADOW 分支
   - `extract_risks()` 中的 SHADOW 分支
   - `run_review()` 中的 SHADOW 分支

2. **KB系统处理** (chat功能仍在使用)：
   - kb_documents/kb_chunks 表保留给chat系统
   - tender系统已完全隔离，不再写入

3. **测试覆盖**：
   - 添加更多NEW_ONLY模式的集成测试
   - 验证所有tender功能在NEW_ONLY下正常工作

## 建议

1. **立即行动**：
   - 将 `tender-remove-legacy` 分支合并到主分支
   - 在生产环境确保 `LEGACY_TENDER_APIS_ENABLED=false`
   - 确保所有环境变量设置为 `INGEST_MODE=NEW_ONLY`

2. **监控**：
   - 监控是否有代码尝试调用已删除的方法（会收到RuntimeError）
   - 确认没有遗留的OLD模式调用

3. **文档**：
   - 更新API文档，移除legacy接口
   - 更新部署文档，说明只支持NEW_ONLY模式

## 总结

✅ 所有6个架构重构步骤完成  
✅ Legacy接口已隔离（默认禁用）  
✅ 旧实现已删除（只支持NEW_ONLY）  
✅ 重复文件已清理  
✅ 边界检查通过  
✅ 代码编译通过  
✅ Git提交干净  

**架构现在是清晰的"平台+Work"模式，tender系统完全使用DocStore，不再有KB混乱。**

