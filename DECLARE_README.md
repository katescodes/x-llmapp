# 🚀 申报书（Declare）应用 - 快速上手

## ✅ 当前状态

- **后端**: ✅ 100%完成（13个API端点已部署）
- **前端API**: ✅ 100%完成（TypeScript类型+方法封装）
- **前端UI**: 🟡 95%完成（DeclareWorkspace待对接真实API）
- **数据库**: ✅ 已迁移（9张表）
- **测试**: ✅ 验收脚本已就绪

---

## 🎯 核心能力

申报书应用支持完整的申报文档自动生成流程：

1. **上传文件** - 申报通知、企业信息、技术资料
2. **智能分析** - 自动抽取申报条件、材料清单、时间节点
3. **目录生成** - 从通知模板自动提取申报书目录结构
4. **内容填充** - 基于企业和技术资料自动填充章节
5. **文档生成** - 生成完整申报书并导出为DOCX

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│  DeclareWorkspace → declareApi → Backend APIs       │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│              Backend FastAPI Router                  │
│     /api/apps/declare/* (13 endpoints)              │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│              DeclareService (Business Logic)         │
│  - import_assets()                                   │
│  - extract_requirements()                            │
│  - generate_directory()                              │
│  - autofill_sections()                               │
│  - generate_document()                               │
└─────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────┬─────────────────────────────┐
│   DeclareDAO          │   Platform Services         │
│   (PostgreSQL)        │   - IngestV2Service         │
│   - declare_projects  │   - RetrievalFacade         │
│   - declare_assets    │   - ExtractionEngine        │
│   - declare_runs      │   - DeclareExtractV2Service │
│   - ...9 tables       │                             │
└───────────────────────┴─────────────────────────────┘
```

---

## 📁 文件结构

```
backend/
├── migrations/
│   └── 025_create_declare_tables.sql        # 数据库迁移
├── app/
│   ├── routers/
│   │   └── declare.py                       # API路由 (13 endpoints)
│   ├── services/
│   │   ├── dao/
│   │   │   └── declare_dao.py              # 数据访问层
│   │   ├── declare_service.py              # 业务逻辑层
│   │   └── export/
│   │       └── declare_docx_exporter.py    # DOCX导出
│   └── works/declare/
│       ├── extract_v2_service.py           # V2抽取服务
│       ├── extraction_specs/               # 抽取规格
│       │   ├── requirements_v2.py
│       │   ├── directory_v2.py
│       │   └── section_autofill_v2.py
│       ├── schemas/                         # Pydantic模型
│       │   ├── requirements_v2.py
│       │   ├── directory_v2.py
│       │   ├── section_v2.py
│       │   └── writer_v2.py
│       └── prompts/                         # LLM提示词
│           ├── requirements_v2.md
│           ├── directory_v2.md
│           ├── section_autofill_v2.md
│           └── document_writer_v2.md

frontend/
└── src/
    ├── api/
    │   ├── declareApi.ts                   # 真实API封装
    │   └── declareApiProvider.ts           # Mock/Real切换
    └── components/
        └── DeclareWorkspace.tsx            # 主界面组件

验收脚本/
├── verify_declare_api.sh                    # 快速API验证
└── verify_declare_mvp.sh                    # 完整E2E验收

文档/
├── DECLARE_CODE_DELIVERY.md                 # 代码交付总结
├── DECLARE_FRONTEND_INTEGRATION_GUIDE.md    # 前端对接指南
└── DECLARE_IMPLEMENTATION_COMPLETE.md       # 实施完成报告
```

---

## 🚀 快速开始

### 1. 验证后端（已完成）

```bash
# 快速验证API
./verify_declare_api.sh

# 预期输出: ✅ 13个 declare 端点已注册
```

### 2. 前端对接（待完成）

```bash
# 设置环境变量
cd frontend
echo "VITE_DECLARE_USE_MOCK=0" >> .env.local

# 启动前端
npm run dev

# 访问
open http://localhost:6173
```

### 3. 完整测试流程

1. 访问申报书入口
2. 创建新项目
3. 上传申报通知（notice）
4. 上传企业信息（company，可选）
5. 点击"分析申报要求" → 等待成功
6. 点击"生成申报书目录" → 查看目录树
7. 点击"自动填充内容" → 查看章节内容
8. 点击"生成申报书" → 等待成功
9. 点击"导出Word" → 下载DOCX文件

---

## 📋 API端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/apps/declare/projects` | 创建项目 |
| GET | `/api/apps/declare/projects` | 列出项目 |
| GET | `/api/apps/declare/projects/{id}` | 获取项目详情 |
| POST | `/api/apps/declare/projects/{id}/assets/import` | 上传文件 |
| GET | `/api/apps/declare/projects/{id}/assets` | 列出文件 |
| POST | `/api/apps/declare/projects/{id}/extract/requirements?sync=0\|1` | 抽取要求 |
| GET | `/api/apps/declare/projects/{id}/requirements` | 获取要求 |
| POST | `/api/apps/declare/projects/{id}/directory/generate?sync=0\|1` | 生成目录 |
| GET | `/api/apps/declare/projects/{id}/directory/nodes` | 获取目录 |
| POST | `/api/apps/declare/projects/{id}/sections/autofill?sync=0\|1` | 填充章节 |
| GET | `/api/apps/declare/projects/{id}/sections` | 获取章节 |
| POST | `/api/apps/declare/projects/{id}/document/generate?sync=0\|1` | 生成文档 |
| GET | `/api/apps/declare/projects/{id}/export/docx` | 导出DOCX |
| GET | `/api/apps/declare/runs/{run_id}` | 查询任务状态 |

---

## 🔑 核心概念

### Run模式

与tender应用一致，支持两种模式：

**同步模式（sync=1）**
```typescript
const run = await declareApi.extractRequirements(projectId, { sync: 1 });
// run.status === 'success' || 'failed'
// 直接返回最终结果
```

**异步模式（sync=0，默认）**
```typescript
const run = await declareApi.extractRequirements(projectId, { sync: 0 });
// run.status === 'running'
// 需要轮询 getRun(run.run_id) 直到 success/failed

// 使用轮询工具
const finalRun = await declareApi.pollDeclareRun(run.run_id, {
  onTick: (r) => {
    console.log(`进度: ${r.progress * 100}%`);
    console.log(`状态: ${r.message}`);
  }
});
```

### 数据流

```
上传文件 → IngestV2 → PostgreSQL (documents/doc_segments)
                         ↓
              RetrievalFacade (检索相关片段)
                         ↓
              ExtractionEngine (LLM抽取+Schema校验)
                         ↓
              DeclareService (业务逻辑处理)
                         ↓
              DeclareDAO (保存结果到declare_*)
```

---

## 🎓 技术特性

### 1. 平台化集成
- ✅ **IngestV2Service** - 统一文件入库
- ✅ **RetrievalFacade** - 统一检索接口
- ✅ **ExtractionEngine** - 统一LLM抽取
- ✅ **Cutover支持** - 灰度切换

### 2. 数据完整性
- ✅ **版本化存储** - directory_versions, sections_versions
- ✅ **is_active标记** - 避免delete+insert空窗
- ✅ **证据追踪** - evidence_chunk_ids, retrieval_trace
- ✅ **Schema校验** - Pydantic严格验证，禁止假成功

### 3. API设计
- ✅ **RESTful风格** - 清晰的资源路径
- ✅ **统一Run模式** - 与tender一致的异步任务
- ✅ **完整类型定义** - TypeScript全覆盖
- ✅ **错误处理规范** - status=failed + error详情

### 4. 可测试性
- ✅ **Mock/Real切换** - 环境变量控制
- ✅ **自动化验收** - verify_declare_mvp.sh
- ✅ **API快速验证** - verify_declare_api.sh

---

## 🛠️ 环境变量

### 后端
```bash
# ExtractionEngine模式
EXTRACT_MODE=NEW_ONLY

# 检索参数
DECLARE_REQUIREMENTS_TOPK_PER_QUERY=30
DECLARE_REQUIREMENTS_TOPK_TOTAL=120
DECLARE_DIRECTORY_TOPK_PER_QUERY=30
DECLARE_DIRECTORY_TOPK_TOTAL=120
DECLARE_SECTION_TOPK_PER_QUERY=20
DECLARE_SECTION_TOPK_TOTAL=80

# 存储路径
DECLARE_STORAGE_DIR=./data/declare/documents
```

### 前端
```bash
# Mock/Real切换 (0=真实API, 1=Mock)
VITE_DECLARE_USE_MOCK=0
```

---

## 📊 数据库表

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| declare_projects | 项目表 | id, kb_id, name, owner_id |
| declare_assets | 资产表 | id, project_id, kind, kb_document_id |
| declare_runs | 任务表 | id, project_id, task_type, status |
| declare_requirements | 要求表 | project_id (PK), data_json, evidence |
| declare_directory_versions | 目录版本 | version_id, project_id, is_active |
| declare_directory_nodes | 目录节点 | id, version_id, parent_id, title |
| declare_sections_versions | 章节版本 | version_id, project_id, is_active |
| declare_sections | 章节内容 | id, version_id, node_id, content_md |
| declare_documents | 导出记录 | id, project_id, file_path |

---

## 🐛 问题排查

### 常见问题

**Q: 后端API 404**
```bash
# 验证API是否注册
./verify_declare_api.sh
# 如果失败，检查 docker-compose logs backend
```

**Q: 数据库表不存在**
```bash
# 执行迁移
docker-compose exec -T postgres psql -U localgpt -d localgpt \
  < backend/migrations/025_create_declare_tables.sql
```

**Q: 前端API调用CORS错误**
```bash
# 确认前端和后端在同一域名
# 或检查 backend CORS 配置
```

**Q: LLM输出解析失败**
```bash
# 查看 run.result_json.error
# 通常是 ExtractionParseError 或 ExtractionSchemaError
# 检查LLM配置和Prompt
```

---

## 📖 相关文档

- **[DECLARE_CODE_DELIVERY.md](./DECLARE_CODE_DELIVERY.md)** - 代码交付总结
- **[DECLARE_FRONTEND_INTEGRATION_GUIDE.md](./DECLARE_FRONTEND_INTEGRATION_GUIDE.md)** - 前端对接指南
- **[DECLARE_IMPLEMENTATION_COMPLETE.md](./DECLARE_IMPLEMENTATION_COMPLETE.md)** - 实施完成报告

---

## 🎯 下一步

### 立即可做
1. ✅ 后端API已完成，可开始前端对接
2. 📋 参考 `DECLARE_FRONTEND_INTEGRATION_GUIDE.md` 更新DeclareWorkspace
3. 🧪 完成后运行完整E2E测试

### 短期优化
4. 🎨 优化UI/UX（loading、进度条、错误提示）
5. ✏️ 支持章节手动编辑
6. 🔀 支持目录拖拽排序

### 长期规划
7. 📊 申报书质量评分
8. 🤖 AI辅助撰写优化
9. 📚 申报模板管理
10. 🔄 批量申报项目

---

## 📞 技术支持

遇到问题？按以下顺序排查：

1. 运行 `./verify_declare_api.sh` 验证后端
2. 检查 `docker-compose logs backend` 查看错误
3. 查看浏览器Console和Network
4. 参考相关文档排查具体问题

---

**当前版本**: v1.0.0  
**最后更新**: 2024-12-21  
**状态**: ✅ 后端完成，前端待对接  
**下一步**: 前端DeclareWorkspace对接真实API

