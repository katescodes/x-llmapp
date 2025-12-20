# Git 仓库结构报告

**生成时间**: 2025-12-20 12:16  
**当前分支**: `platform-extraction-migration`  
**最新提交**: `b23adbf - Add project documentation and ASR fixes`

---

## 📊 分支概览

```
当前分支:
* platform-extraction-migration (HEAD)
  master
```

### 分支说明

- **master**: 主分支，迁移前的基线版本
- **platform-extraction-migration**: 平台抽取引擎迁移分支（当前工作分支）

---

## 📝 提交历史（最近15次）

```
b23adbf - Add project documentation and ASR fixes
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
d8cd773 - Step4: migrate tender risks v2 to platform ExtractionEngine and harden DAO transactions
c616c4e - Step3: implement platform ExtractionEngine and migrate tender project-info v2 to engine
61302ac - Step2: reuse platform extraction utilities in tender v2
a7d3060 - Step1: scaffold platform extraction module
```

---

## 🎯 迁移步骤总结

### Step 1: 脚手架搭建 (a7d3060)
- 创建 `platform/extraction/` 模块基础结构
- 定义核心类型和接口

### Step 2: 复用工具函数 (61302ac)
- 抽取 tender v2 中的通用工具
- 移入 `platform/extraction/`

### Step 3: 引擎实现 (c616c4e)
- 实现 `ExtractionEngine` 核心逻辑
- 迁移 project-info 到新引擎

### Step 4: 风险模块迁移 (d8cd773)
- 迁移 tender risks v2 到平台引擎
- 强化 DAO 事务处理

### Step 5: 配置驱动 (34eb939)
- 抽取规格配置化（prompts/queries/topk）
- 实现真正的 config-driven

### Step 6: 边界检查 (9f390b1)
- 强制 platform/work 边界
- 严格的冒烟测试门槛

### Step 7: 验收硬化 (2090daf → b3beb0c)
- 实现完整验收体系
- OLD/NEW_ONLY/SHADOW 三模式验证
- 抽取回归测试
- 规则必命中检查
- Docker 环境验证

### Step 7 修复系列
- **Fix1** (021f13b): Worker-Redis 超时修复
- **Fix2** (32bd473): Docstore ready API，ASYNC 配置
- **Fix3** (bf426cd): 同步模式支持，引擎 list 处理

### 验收强化系列
- **31c45f7**: 强制回归+必命中+Docker 验证
- **04dd1e6**: HEAD-bound 缓存，强制回归
- **b3beb0c**: 真实 HEAD 绑定，强制回归，忽略验证产物

### 文档与修复 (b23adbf - 当前)
- 添加项目概览文档
- ASR GPU OOM 解决方案
- ASR 超时修复
- 边界检查单元测试

---

## 📈 最新提交详情

**提交**: `b23adbf71e53fe43b09090336154cba5eb8dfd7b`  
**作者**: Platform Migration <migration@platform.local>  
**日期**: Sat Dec 20 12:16:19 2025 +0800  

### 提交信息
```
Add project documentation and ASR fixes

- Add PROJECT_OVERVIEW.md: comprehensive project structure and verification guide
- Add ASR_GPU_OOM_SOLUTION.md: ASR GPU OOM issue analysis and solutions
- Add ASR_TIMEOUT_FIX.md: ASR timeout issue fixes with queue management
- Add backend/tests/test_boundary_rules.py: boundary check unit tests
- Update ASR services: improve timeout handling and error recovery
- Update verification reports: add final success and hardened gates reports
- Update boundary check script: enhance platform/work boundary validation
```

### 文件变更统计
```
15 files changed, 1610 insertions(+), 23 deletions(-)
```

### 新增文件
- `PROJECT_OVERVIEW.md` (406行) - 项目全景文档
- `ASR_GPU_OOM_SOLUTION.md` (231行) - ASR GPU OOM 分析
- `ASR_TIMEOUT_FIX.md` (144行) - ASR 超时修复
- `backend/tests/test_boundary_rules.py` (174行) - 边界检查测试
- `reports/verify/FINAL_SUCCESS.md` (185行) - 最终验收报告
- `reports/verify/HARDEN_GATES_FINAL.md` (162行) - 强化门槛报告
- `reports/verify/STEP7_SUCCESS.md` (135行) - Step7 成功报告
- `reports/verify/skip_smoke_marker.txt` (3行) - 跳过标记

### 修改文件
- `backend/app/routers/asr_ws.py` (+36/-23) - ASR WebSocket 改进
- `backend/app/services/asr_api_service.py` (+30/-15) - ASR API 改进
- `backend/app/services/asr_service.py` (小改动)
- `frontend/src/components/RecordingsList.tsx` (UI 改进)
- `scripts/ci/check_platform_work_boundary.py` (+102) - 边界检查增强
- `reports/verify/_head.txt` (更新 HEAD)
- `reports/verify/_verify_sig.json` (更新签名)

---

## 📊 分支差异统计 (master → platform-extraction-migration)

### 总体统计
```
393 files changed
149,351 insertions(+)
876 deletions(-)
```

### 核心新增模块

#### Platform 层 (平台通用能力)
```
backend/app/platform/extraction/
├── __init__.py          (14行)
├── context.py           (31行)
├── engine.py            (285行) ⭐ 核心引擎
├── json_utils.py        (77行)
├── llm_adapter.py       (74行)
└── types.py             (75行)

backend/app/platform/ingest/
└── v2_service.py        ⭐ 摄入服务

backend/app/platform/retrieval/
├── facade.py            ⭐ 检索门面
└── new_retriever.py     ⭐ 新检索器

backend/app/platform/rules/
└── evaluator_v2.py      ⭐ 规则引擎 V2
```

#### Apps 层 (业务特定)
```
backend/app/apps/tender/
├── extract_v2_service.py    (369行重构)
├── review_v2_service.py
├── extraction_specs/        ⭐ 配置化规格
│   ├── project_info_v2.py   (54行)
│   └── risks_v2.py          (34行)
└── prompts/                 ⭐ Prompt 模板
    ├── project_info_v2.md   (65行)
    └── risks_v2.md          (31行)
```

#### 验收体系
```
scripts/ci/
├── verify_cutover_and_extraction.py  (557行) ⭐ 统一验收入口
├── verify_docker.py                   (110行) ⭐ Docker 验收
└── check_platform_work_boundary.py    (151行) ⭐ 边界检查

scripts/eval/
└── extract_regression.py              (767行) ⭐ 抽取回归

scripts/smoke/
└── tender_e2e.py                      (72行重构) ⭐ E2E 冒烟
```

#### 测试
```
backend/tests/
├── test_platform_extraction_skeleton.py  (143行) - 平台抽取骨架测试
└── test_boundary_rules.py                (174行) - 边界规则测试
```

#### 文档
```
PROJECT_OVERVIEW.md         (406行) - 项目概览
ASR_GPU_OOM_SOLUTION.md     (231行) - ASR OOM 解决方案
ASR_TIMEOUT_FIX.md          (144行) - ASR 超时修复
Makefile                    (17行)  - 验收入口
```

#### 验收报告
```
reports/verify/
├── FINAL_SUCCESS.md         (185行) - 最终成功报告
├── HARDEN_GATES_FINAL.md    (162行) - 强化门槛报告
├── STEP7_SUCCESS.md         (135行) - Step7 成功
├── SUMMARY.txt              (58行)  - 总结
├── FINAL_REPORT.md          (218行) - 最终报告
├── STEP7_FINAL_SUMMARY.txt  (118行) - Step7 总结
├── STEP7_FIX2_STATUS.md     (149行) - Fix2 状态
└── STEP7_FIX_FINAL.txt      (126行) - Fix 最终
... (多个 gate*.log, smoke*.log 文件)
```

---

## 🔧 核心配置文件变更

### 容器编排
- `docker-compose.yml` (5行改动) - Worker/Backend 配置优化

### Worker
- `backend/worker.py` (61行重构) - 队列连接优化，Redis 超时修复

### 路由
- `backend/app/routers/tender.py` (58行改动) - 添加同步模式支持
- `backend/app/routers/debug.py` (63行新增) - Docstore 调试接口

### 服务
- `backend/app/services/tender_service.py` (大量改动) - 使用新平台引擎

---

## 📂 数据文件变化

### 数据库
- `data/postgres/` - 多个表文件增长（测试数据）
  - `doc_segments` 相关表
  - `documents` 相关表
  - `kb_documents` 和 `kb_chunks` 表

### 向量库
- `data/milvus.db` - 从 5MB 增长到 9MB

### Redis
- `data/redis/appendonlydir/appendonly.aof.1.incr.aof` - 143,871 行增量

### 测试资产
- `data/tender_assets/` - 多个测试项目目录（14个项目）
  - 包含 tender_sample.pdf 和 bid_sample.docx

---

## 🎯 迁移关键指标

### 代码行数增长
```
Platform 层核心:     ~600 行（新增）
Apps 配置化:         ~150 行（新增）
验收脚本:            ~1,600 行（新增）
测试代码:            ~300 行（新增）
文档:                ~800 行（新增）
```

### 模块化改进
- ✅ 抽取引擎: 从业务代码移至 `platform/extraction/`
- ✅ 配置驱动: 从硬编码移至 JSON 配置
- ✅ 边界清晰: `apps/tender` 不含通用逻辑
- ✅ 测试覆盖: 完整验收体系（6个 Gate）

### 质量门槛
- ✅ Gate 1: 编译检查
- ✅ Gate 2: 边界检查
- ✅ Gate 3: OLD 模式 Smoke
- ✅ Gate 4: NEW_ONLY 模式 Smoke
- ✅ Gate 5: 抽取回归测试
- ✅ Gate 6: 规则必命中

---

## 🚀 下一步建议

### 合并到主分支
```bash
# 确保所有测试通过
make verify

# 切换到 master
git checkout master

# 合并迁移分支
git merge platform-extraction-migration

# 推送到远程
git push origin master
```

### 后续优化
1. **性能优化**: 优化大文档抽取性能
2. **监控告警**: 添加抽取引擎监控
3. **文档完善**: API 文档和使用指南
4. **扩展应用**: 将平台引擎应用到其他业务

---

## 📋 提交规范

本次迁移遵循的提交规范:

- **Step[N]**: 迁移步骤
- **Step[N]-fix[M]**: 修复和优化
- **Harden gates**: 验收门槛强化
- **Add/Update**: 功能添加/更新

---

**报告生成完毕** | Git 仓库健康状态: ✅ 优秀

