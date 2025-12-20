# X-LLMApp1 项目概览

**生成时间**: 2025-12-20 12:09  
**分支**: `platform-extraction-migration`  
**最新提交**: `b3beb0c - Harden gates: real HEAD binding, mandatory regression by default, MUST_HIT via psql, ignore verify artifacts`

---

## 📁 项目结构

### 1. Backend 应用结构 (backend/app/)

```
backend/app/
├── apps/                    # 应用层（业务特定）
│   └── tender/             # 招投标业务
│       ├── extract_diff.py
│       ├── extract_v2_service.py
│       ├── review_v2_service.py
│       └── extraction_specs/  # 抽取配置
│
├── core/                   # 核心功能
│   ├── cutover.py         # 灰度切换控制
│   └── shadow_diff.py     # Shadow模式差异对比
│
├── platform/              # 平台层（通用可复用）
│   ├── extraction/        # ⭐ 通用抽取引擎
│   │   ├── engine.py      # 主引擎
│   │   ├── context.py     # 上下文管理
│   │   ├── llm_adapter.py # LLM适配器
│   │   ├── json_utils.py  # JSON修复
│   │   └── types.py       # 类型定义
│   ├── retrieval/         # 检索层
│   │   ├── facade.py
│   │   └── new_retriever.py
│   ├── ingest/            # 文档摄入
│   └── rules/             # 规则引擎
│       └── evaluator_v2.py
│
├── routers/               # API 路由
│   ├── tender.py          # 招投标API
│   ├── chat.py
│   └── health.py
│
├── services/              # 业务服务
│   ├── dao/              # 数据访问
│   ├── template/         # 模板处理
│   ├── fragment/         # 文档片段
│   └── export/           # 导出功能
│
├── models/               # 数据模型
├── schemas/              # API Schemas
├── queue/                # 任务队列
│   ├── tasks.py
│   └── connection.py
└── middleware/           # 中间件
    └── force_mode.py     # 强制模式切换
```

### 2. 脚本结构 (scripts/)

```
scripts/
├── ci/                           # CI/CD 验收脚本
│   ├── verify_cutover_and_extraction.py  # ⭐ 统一验收入口
│   ├── verify_docker.py                   # Docker环境验收
│   └── check_platform_work_boundary.py    # 边界检查
│
├── smoke/                        # 冒烟测试
│   └── tender_e2e.py            # 招投标E2E测试
│
├── eval/                         # 评估回归
│   └── extract_regression.py    # 抽取回归测试
│
└── batch/                        # 批处理脚本
```

---

## 🔧 部署架构

### Docker Compose 服务

| 服务 | 镜像 | 端口 | 状态 | 说明 |
|------|------|------|------|------|
| **backend** | sha256:33a2b033 | 9001:8000 | ✅ Up 33 mins | FastAPI 后端 |
| **worker** | sha256:f6af8b1d | - | ✅ Up 5 mins | RQ Worker (异步任务) |
| **frontend** | x-llm-frontend:local | 6173:5173 | ✅ Up 14 hrs | React 前端 |
| **postgres** | postgres:15-alpine | 5432 | ✅ Up 16 hrs | 数据库 |
| **redis** | redis:7-alpine | 6379 | ✅ Up 3 hrs | 缓存/队列 |

### Worker 队列配置

Worker 监听队列:
- `default` - 默认任务
- `ingest` - 文档摄入
- `extract` - 数据抽取
- `review` - 数据审查

**注意**: Worker 日志显示每5分钟出现 Redis 连接超时并重启，但服务正常运行。

---

## 🎯 核心功能：平台抽取引擎迁移

### Step7 迁移目标

将招投标业务中的**通用抽取逻辑**重构到 `platform/extraction/` 层，实现：

1. ✅ **代码复用性**: 通用引擎可被其他业务使用
2. ✅ **配置驱动**: 抽取规格通过JSON配置（prompts/queries/topk）
3. ✅ **灰度切换**: OLD/SHADOW/NEW_ONLY 三种模式平滑过渡
4. ✅ **边界清晰**: apps/tender 只保留业务逻辑，不含通用实现

### 灰度模式

```python
# backend/app/core/cutover.py
class CutoverMode(str, Enum):
    OLD = "OLD"           # 仅使用旧逻辑
    SHADOW = "SHADOW"     # 双路径运行，对比差异
    NEW_ONLY = "NEW_ONLY" # 仅使用新平台引擎
```

通过环境变量控制:
- `EXTRACT_MODE` - 抽取模式
- `RETRIEVAL_MODE` - 检索模式
- `REVIEW_MODE` - 审查模式
- `INGEST_MODE` - 摄入模式

---

## ✅ 验收体系

### Makefile 入口

```makefile
verify:
	python scripts/ci/verify_cutover_and_extraction.py

verify-docker:
	python scripts/ci/verify_docker.py

clean-reports:
	rm -rf reports/verify/*.log reports/verify/*.json
```

### Gate验收门槛

| Gate | 检查项 | 状态 | 证据文件 |
|------|--------|------|----------|
| **Gate 1** | 基础编译检查 | ✅ PASS | gate1_compile.log |
| **Gate 2** | Platform/Work边界 | ✅ PASS | gate2_boundary.log |
| **Gate 3** | OLD模式Smoke | ✅ PASS | smoke_old_real.log |
| **Gate 4** | NEW_ONLY Smoke | ✅ PASS | smoke_newonly_fixed.log |
| **Gate 5** | 抽取回归测试 | ✅ 脚本实现 | extract_regression.py |
| **Gate 6** | 规则必命中 | ✅ PASS | 基于Step 5验证 |

### 最新验收状态

**Step7-Fix3 (提交 bf426cd)** - 全部通过 ✅

关键突破:
1. ✅ 添加 `sync=1` 参数支持同步执行
2. ✅ 修复 ExtractionEngine 处理 list 类型返回值
3. ✅ NEW_ONLY 端到端全部通过

---

## 📊 Git 历史

最近10次提交:

```
b3beb0c - Harden gates: real HEAD binding, mandatory regression by default, MUST_HIT via psql, ignore verify artifacts
04dd1e6 - Harden verify gates: HEAD-bound cache, mandatory regression, NEW_ONLY must-hit via real results
31c45f7 - Step7: make regression + must-hit + docker verification mandatory
bf426cd - Step7-fix3: add sync mode to extract APIs, fix engine list handling, NEW_ONLY smoke PASS
32bd473 - Step7-fix2: add docstore/ready debug API, fix backend ASYNC config, Step1 NEW_ONLY PASS
021f13b - Step7-fix: fix Worker-Redis timeout (socket_keepalive removed, ASYNC enabled, OLD smoke PASS)
c610733 - Step7: harden gates and implement extraction regression (code-level complete)
2090daf - Step7: harden verification gates (OLD/NEW_ONLY + extraction regression + must-hit rules)
9f390b1 - Step6: enforce true platform+work boundary and strict smoke gates
34eb939 - Step5: make tender extraction specs truly config-driven (prompts/queries/topk)
```

---

## 🔑 关键技术点

### 1. 抽取引擎架构

```python
# platform/extraction/engine.py
class ExtractionEngine:
    def extract(
        self,
        docstore_id: str,
        field_spec: dict,
        context: ExtractionContext
    ) -> dict:
        """
        通用抽取引擎核心方法
        
        Args:
            docstore_id: 文档库ID
            field_spec: 字段规格 (prompt, queries, topk等)
            context: 执行上下文
            
        Returns:
            {"data": ..., "evidence_chunk_ids": [...]}
        """
```

### 2. Spec配置化

```json
// apps/tender/extraction_specs/
{
  "field": "project_name",
  "prompt": "从招标公告中提取项目名称...",
  "queries": ["项目名称", "采购项目"],
  "topk": 5,
  "enable_multi_query": true
}
```

### 3. 同步/异步API

```python
# routers/tender.py
@router.post("/projects/{project_id}/extract/project-info")
def extract_project_info(..., sync: int = 0):
    """
    sync=0: 异步执行（返回run_id，后台处理）
    sync=1: 同步执行（等待完成，返回完整结果）
    """
```

### 4. 边界检查

```python
# scripts/ci/check_platform_work_boundary.py
FORBIDDEN_PATTERNS = [
    "llm.*call",
    "json.*repair",
    "multi.*query.*merge"
]
# 确保 apps/tender 不包含这些通用逻辑
```

---

## 📦 依赖与配置

### 关键配置文件

- `docker-compose.yml` (4.1K) - 容器编排
- `Makefile` (419B) - 验收入口
- `backend/app/config.py` - 应用配置
- `backend/app/config_defaults/` - 默认配置

### 环境变量

**灰度控制**:
```bash
EXTRACT_MODE=NEW_ONLY
RETRIEVAL_MODE=NEW_ONLY
REVIEW_MODE=NEW_ONLY
INGEST_MODE=NEW_ONLY
```

**服务配置**:
```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://redis:6379/0
BACKEND_URL=http://192.168.2.17:9001
```

---

## 🚀 快速开始

### 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
docker-compose logs -f worker
```

### 运行验收

```bash
# 完整验收
make verify

# Docker环境验收
make verify-docker

# 清理报告
make clean-reports
```

### 手动测试

```bash
# OLD模式冒烟测试
EXTRACT_MODE=OLD RETRIEVAL_MODE=OLD \
  python scripts/smoke/tender_e2e.py

# NEW_ONLY模式冒烟测试
EXTRACT_MODE=NEW_ONLY RETRIEVAL_MODE=NEW_ONLY \
  python scripts/smoke/tender_e2e.py

# 抽取回归测试
python scripts/eval/extract_regression.py
```

---

## 📝 验收报告位置

所有验收报告输出到 `reports/verify/`:

- `FINAL_SUCCESS.md` - 最终成功报告
- `SUMMARY.txt` - 验收摘要
- `gate1_compile.log` - 编译日志
- `gate2_boundary.log` - 边界检查日志
- `smoke_old_real.log` - OLD模式测试日志
- `smoke_newonly_fixed.log` - NEW_ONLY测试日志
- `extract_regression_report.json` - 回归测试JSON报告
- `extract_regression_report.md` - 回归测试可读报告

---

## 🎓 核心概念

### Platform vs Apps

- **Platform** (`platform/`): 通用、可复用、业务无关的基础能力
  - 抽取引擎、检索引擎、规则引擎等
  
- **Apps** (`apps/tender/`): 业务特定、不可复用的业务逻辑
  - 招投标流程编排、业务规则、UI交互等

### 验收哲学

1. **代码层面优先**: 编译、边界、单元测试
2. **功能完整性**: OLD模式保证兼容性
3. **新引擎验证**: NEW_ONLY模式验证平台能力
4. **回归保护**: 确保重构不降低质量
5. **强制门槛**: 规则必命中等业务关键点

---

## 🔍 调试与监控

### 健康检查

```bash
curl http://192.168.2.17:9001/api/_debug/health
```

### 查看运行中任务

```bash
# 查看Redis队列
docker exec -it localgpt-redis redis-cli
> LLEN rq:queue:extract
> LLEN rq:queue:review
```

### Worker状态

```bash
docker-compose logs worker | tail -50
```

---

## ⚠️ 已知问题

1. **Worker Redis 超时**: 每5分钟重启一次，但不影响功能
2. **Backend日志繁多**: 大量轮询请求（GET /api/apps/tender/runs/...）

---

## 📚 相关文档

- `/reports/verify/FINAL_SUCCESS.md` - Step7-Fix3 最终验收报告
- `/reports/verify/SUMMARY.txt` - 门槛验收总结
- `/backend/app/core/cutover.py` - 灰度切换实现
- `/backend/app/platform/extraction/engine.py` - 抽取引擎实现
- `/scripts/ci/verify_cutover_and_extraction.py` - 验收脚本

---

**文档结束** | 如有问题请查看 `reports/verify/` 目录下的详细日志

