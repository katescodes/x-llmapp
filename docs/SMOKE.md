# 招投标 Smoke 测试闸门

> 完整的端到端测试，验证招投标系统核心功能

## 快速开始

```bash
# 1. 启动全栈服务
docker compose up -d --build

# 2. 运行 Smoke 测试
python scripts/smoke/tender_e2e.py
```

## 验收标准

✅ **Step 0 必须通过以下测试：**

1. 脚本成功执行，退出码为 0
2. 所有步骤显示 `✓` 成功标记
3. 最终输出 "所有测试通过！"
4. 连续运行 2-3 次均通过（稳定性验证）

## 测试覆盖范围

本 Smoke 测试覆盖完整的招投标流程：

| 步骤 | API 端点 | 说明 |
|------|---------|------|
| 创建项目 | `POST /api/apps/tender/projects` | 创建新的招投标项目 |
| 上传招标文件 | `POST /api/apps/tender/projects/{id}/assets/import` | 上传 tender 文件 |
| Step 1 | `POST /api/apps/tender/projects/{id}/extract/project-info` | 提取项目信息 |
| Step 2 | `POST /api/apps/tender/projects/{id}/extract/risks` | 识别风险 |
| Step 3 | `POST /api/apps/tender/projects/{id}/directory/generate` | 生成目录 |
| Step 3.2 | `POST /api/apps/tender/projects/{id}/directory/auto-fill-samples` | 自动填充样例（可选） |
| 上传投标文件 | `POST /api/apps/tender/projects/{id}/assets/import` | 上传 bid 文件 |
| Step 5 | `POST /api/apps/tender/projects/{id}/review/run` | 运行审查 |
| 导出 | `GET /api/apps/tender/projects/{id}/export/docx` | 导出 DOCX |

## 环境配置

通过环境变量自定义测试行为：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BASE_URL` | `http://localhost:9001` | 后端服务地址 |
| `TOKEN` | (空) | 认证令牌，留空则自动登录 |
| `USERNAME` | `admin` | 登录用户名 |
| `PASSWORD` | `admin123` | 登录密码 |
| `TENDER_FILE` | `testdata/tender_sample.pdf` | 招标文件路径 |
| `BID_FILE` | `testdata/bid_sample.docx` | 投标文件路径 |
| `RULES_FILE` | `testdata/rules.yaml` | 自定义规则文件 |
| `FORMAT_TEMPLATE_FILE` | (空) | 格式模板（可选） |
| `SKIP_OPTIONAL` | `false` | 跳过可选步骤 |
| `KEEP_PROJECT` | `false` | 保留测试项目 |

### 示例用法

```bash
# 使用自定义后端地址
BASE_URL=http://192.168.2.17:9001 python scripts/smoke/tender_e2e.py

# 快速测试（跳过可选步骤）
SKIP_OPTIONAL=true python scripts/smoke/tender_e2e.py

# 保留项目用于调试
KEEP_PROJECT=true python scripts/smoke/tender_e2e.py

# 使用自定义测试文件
TENDER_FILE=/path/to/custom.pdf BID_FILE=/path/to/custom.docx python scripts/smoke/tender_e2e.py
```

## 测试数据

测试数据位于 `testdata/` 目录：

```
testdata/
├── tender_sample.pdf      # 招标文件样例 (752 KB)
├── bid_sample.docx        # 投标文件样例 (33 MB)
├── rules.yaml             # 自定义规则样例（空规则）
└── README.md              # 测试数据说明
```

**注意：** 按照 Step 0 要求，如果需要 `testdata/tender/` 子目录，可以创建软链接：

```bash
# 创建 tender 子目录并链接文件（可选）
mkdir -p testdata/tender
cd testdata/tender
ln -s ../tender_sample.pdf tender.pdf
ln -s ../bid_sample.docx bid.docx
ln -s ../rules.yaml rules.yaml
```

当前实现直接使用 `testdata/` 根目录的文件，无需重复拷贝。

## 运行方式

### 方式 1: 直接运行（推荐）

```bash
cd /aidata/x-llmapp1
python scripts/smoke/tender_e2e.py
```

### 方式 2: 使用 pytest

```bash
cd /aidata/x-llmapp1/backend
pytest -m smoke -v
```

### 方式 3: 前端 npm 脚本

```bash
cd /aidata/x-llmapp1/frontend
npm run smoke:tender
```

## 故障排查

### 连接被拒绝

```
✗ 创建项目失败: Connection refused
```

**解决方案：**
1. 检查服务状态：`docker compose ps`
2. 查看后端日志：`docker compose logs backend`
3. 验证健康检查：`curl http://localhost:9001/health`
4. 重启服务：`docker compose restart backend`

### 认证失败

```
✗ 登录失败: 401 Unauthorized
```

**解决方案：**
1. 检查用户名密码配置
2. 确认 `backend/env.example` 中的默认用户
3. 尝试手动登录测试：
   ```bash
   curl -X POST http://localhost:9001/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin123"}'
   ```

### 任务超时

```
✗   任务超时 (>300s)
```

**解决方案：**
1. 检查 LLM 服务配置：`docker compose logs backend | grep -i llm`
2. 查看后台任务状态
3. 增加超时时间（修改环境变量或脚本）
4. 使用 `SKIP_OPTIONAL=true` 跳过耗时步骤

### 文件不存在

```
✗ 文件不存在: testdata/tender_sample.pdf
```

**解决方案：**
1. 验证文件存在：`ls -la testdata/`
2. 使用绝对路径：`TENDER_FILE=/absolute/path/to/file.pdf`
3. 检查文件权限

## 开发流程要求

### ⚠️ 重要：进入下一步开发前

**必须确保 Smoke 测试通过！**

```bash
# 1. 拉取最新代码
git pull

# 2. 重新构建服务
docker compose up -d --build

# 3. 运行 Smoke 测试
python scripts/smoke/tender_e2e.py

# 4. 验证稳定性（连续运行 2-3 次）
python scripts/smoke/tender_e2e.py
python scripts/smoke/tender_e2e.py
```

### ⚠️ 重要：提交代码前

**必须确保 Smoke 测试通过！**

```bash
# 1. 运行 Smoke 测试
python scripts/smoke/tender_e2e.py

# 2. 通过则可以提交
git add .
git commit -m "your changes"
git push

# 3. 失败则不要提交！先修复问题
```

## 设计原则

本 Smoke 测试闸门遵循以下原则：

1. **不修改业务逻辑** - 仅验证现有功能
2. **不破坏现有功能** - 所有现有 API 保持不变
3. **默认不启用新路径** - 可选功能可跳过
4. **必须跑通才进入下一步** - 作为开发闸门

## 集成测试架构

```
┌─────────────────────────────────────────────┐
│           Smoke 测试闸门 (Step 0)            │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │   scripts/smoke/tender_e2e.py       │   │
│  │   (主测试脚本)                       │   │
│  └─────────────────┬───────────────────┘   │
│                    │                        │
│  ┌─────────────────┴───────────────────┐   │
│  │  backend/tests/smoke/               │   │
│  │  (pytest 封装)                       │   │
│  └─────────────────┬───────────────────┘   │
│                    │                        │
│  ┌─────────────────┴───────────────────┐   │
│  │  frontend/package.json              │   │
│  │  ("smoke:tender" 脚本)              │   │
│  └─────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

## Cutover 控制 & 灰度测试

### 灰度入库到指定项目 (Step 5)

**PREFER_NEW 模式**：优先使用新入库链路，失败自动回退旧链路。

```bash
# 1. 运行一次 Smoke 测试，获取项目 ID
python scripts/smoke/tender_e2e.py

# 脚本会打印：
# ═══════════════════════════════════════════════════════════
#   项目 ID: tp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#   灰度测试用法: CUTOVER_PROJECT_IDS=tp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# ═══════════════════════════════════════════════════════════

# 2. 设置灰度配置（docker-compose.yml）
CUTOVER_PROJECT_IDS=tp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
INGEST_MODE=PREFER_NEW

# 3. 重启服务
docker compose restart backend

# 4. 再次运行 Smoke 测试
python scripts/smoke/tender_e2e.py

# 5. 验证结果
# - 查看日志确认使用了 v2 入库
# - 或通过 debug 接口查看：
#   curl "http://localhost:9001/api/_debug/ingest/v2?asset_id=xxx" -H "Authorization: Bearer $TOKEN"
```

### Cutover 模式说明

| 模式 | 行为 | 用途 |
|------|------|------|
| `OLD` | 仅旧入库 | 默认模式，不影响现有功能 |
| `SHADOW` | 旧入库成功后，同步跑新入库 | 对比新旧入库结果，新入库失败不影响主流程 |
| `PREFER_NEW` | 先跑新入库，成功则不跑旧；失败回退旧入库 | 灰度切换，确保业务连续性 |
| `NEW_ONLY` | 仅新入库，失败直接抛错 | 完全切换到新链路 |

### Meta 记录

每个资产的 `meta_json` 会记录入库模式和状态：

```json
{
  "ingest_mode_used": "PREFER_NEW",
  "ingest_v2_status": "success",
  "ingest_v2_segments": 41,
  "ingest_v2_fallback_to_legacy": false,
  "doc_version_id": "dv_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

**Fallback 情况：**

```json
{
  "ingest_mode_used": "PREFER_NEW",
  "ingest_v2_status": "failed_fallback",
  "ingest_v2_error": "...",
  "ingest_v2_fallback_to_legacy": true
}
```

### Debug 接口

```bash
# 1. 获取 token
TOKEN=$(curl -s -X POST http://localhost:9001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access_token')

# 2. 查看 cutover 配置
curl "http://localhost:9001/api/_debug/cutover?project_id=tp_xxx" \
  -H "Authorization: Bearer $TOKEN" | jq

# 3. 查看入库状态
curl "http://localhost:9001/api/_debug/ingest/v2?asset_id=ta_xxx" \
  -H "Authorization: Bearer $TOKEN" | jq

# 4. 测试新检索器
curl "http://localhost:9001/api/_debug/retrieval/test?query=test&project_id=tp_xxx&doc_types=tender&top_k=3" \
  -H "Authorization: Bearer $TOKEN" | jq
```

## Step 6+7: 抽取模式切换（EXTRACT_MODE）

### 模式说明

- **OLD** (默认): 仅使用旧抽取逻辑
- **SHADOW**: 旧抽取为准，同时运行 v2 并记录差异（v2 失败不影响主流程）
- **PREFER_NEW**: 优先使用 v2 抽取，失败则回退到旧逻辑
- **NEW_ONLY**: 仅使用 v2 抽取（失败则报错）

### 灰度控制

使用 `CUTOVER_PROJECT_IDS` 灰度控制特定项目：

**场景1：全局 SHADOW，特定项目 PREFER_NEW**

```bash
# .env
EXTRACT_MODE=SHADOW
CUTOVER_PROJECT_IDS='{"extract":{"PREFER_NEW":["tp_abc123"]}}'
```

**场景2：全局 OLD，特定项目 PREFER_NEW**

```bash
# .env
EXTRACT_MODE=OLD
CUTOVER_PROJECT_IDS='{"extract":{"PREFER_NEW":["tp_abc123","tp_def456"]}}'
```

### 验收测试

**1. EXTRACT_MODE=OLD（默认模式）**

```bash
# .env
EXTRACT_MODE=OLD

# 运行 smoke test
cd /aidata/x-llmapp1
python scripts/smoke/tender_e2e.py
```

预期：✅ 全绿（Step 1/2 使用旧抽取）

**2. EXTRACT_MODE=SHADOW（对比模式）**

```bash
# .env
EXTRACT_MODE=SHADOW

# 运行 smoke test
python scripts/smoke/tender_e2e.py
```

预期：
- ✅ 全绿（旧抽取为准）
- 📊 日志中出现 diff 记录：
  ```
  SHADOW extract_project_info: project_id=tp_xxx has_diff=True/False
  SHADOW extract_risks: project_id=tp_xxx old_count=3 new_count=3 has_diff=True/False
  ```

**3. EXTRACT_MODE=PREFER_NEW（灰度模式）**

```bash
# .env
EXTRACT_MODE=OLD
CUTOVER_PROJECT_IDS='{"extract":{"PREFER_NEW":["<smoke_project_id>"]}}'

# 运行 smoke test（会获得并灰度该项目）
python scripts/smoke/tender_e2e.py
```

预期：
- ✅ 全绿（v2 抽取成功）
- ✅ 前端 Step1/2 页面显示正常（因为写入了旧表）
- 📊 日志显示：
  ```
  PREFER_NEW extract_project_info: trying v2 for project=tp_xxx
  PREFER_NEW extract_project_info: v2 succeeded for project=tp_xxx
  PREFER_NEW extract_risks: v2 succeeded for project=tp_xxx, count=3
  ```

**Fallback 场景：v2 失败自动回退**

如果 v2 抽取失败（例如 Milvus 连接断开），系统自动回退到旧逻辑：

```
PREFER_NEW extract_project_info: v2 failed for project=tp_xxx, falling back to old extraction
```

### 监控点

- **Shadow Diff 日志**: 查看 v2 与旧抽取的差异
- **Fallback 频率**: 监控 v2 失败率（健康状态应 < 1%）
- **性能对比**: v2 检索耗时 vs 旧逻辑

## 后续步骤（Step 1+）

只有在 Smoke 测试通过后，才能进入后续步骤：

- **Step 1**: Cutover 控制体系 ✅
- **Step 2**: DocStore 双写准备 ✅
- **Step 3**: (预留)
- **Step 4**: 新入库/分片/向量化链路 ✅
- **Step 5**: 入库切到 PREFER_NEW (灰度) ✅
- **Step 6**: Step1/Step2 抽取的新实现 (EXTRACT_MODE=SHADOW) ✅
- **Step 7**: Step1/Step2 抽取切到 PREFER_NEW (灰度) ✅
- **Step 8**: 新检索接入业务 (RETRIEVAL_MODE=SHADOW)
- **Step 9**: 逐步迁移所有功能到新链路
- ...

## Step 9: 规则链路切换（RULES_MODE）

### 配置说明

**RULES_MODE**: 规则评估器切换模式

- **OLD**: 使用旧规则评估器（或不执行，如果未启用）
- **SHADOW**: 旧评估器为准，同时运行 v2 并记录差异（Step 9）
- **PREFER_NEW**: 优先使用 v2 评估器，失败则回退到旧评估器
- **NEW_ONLY**: 仅使用 v2 评估器（失败则报错）

### 灰度控制示例

**场景1：全局 SHADOW，特定项目 PREFER_NEW**

```bash
# .env
RULES_MODE=SHADOW
CUTOVER_PROJECT_IDS='{"rules":{"PREFER_NEW":["tp_abc123"]}}'
```

**场景2：全局 OLD，特定项目 PREFER_NEW**

```bash
# .env
RULES_MODE=OLD
CUTOVER_PROJECT_IDS='{"rules":{"PREFER_NEW":["tp_abc123","tp_def456"]}}'
```

### 验收测试

**1. RULES_MODE=OLD（默认模式）**

```bash
# .env
RULES_MODE=OLD

# 运行 smoke test
cd /aidata/x-llmapp1
python scripts/smoke/tender_e2e.py
```

预期：✅ 全绿（使用旧规则评估器或不执行规则）

**2. RULES_MODE=SHADOW（对比模式）**

```bash
# .env
RULES_MODE=SHADOW

# 运行 smoke test
python scripts/smoke/tender_e2e.py
```

预期：
- ✅ 全绿（旧评估器为准）
- 📊 日志中出现 diff 记录（如果项目有规则文件）：
  ```
  SHADOW rules (old): 5 findings
  SHADOW rules (v2): 6 findings (old=5, diff=1)
  ```

**3. RULES_MODE=PREFER_NEW（灰度模式）**

```bash
# .env
RULES_MODE=OLD
CUTOVER_PROJECT_IDS='{"rules":{"PREFER_NEW":["<smoke项目ID>"]}}'

# 运行 smoke test
python scripts/smoke/tender_e2e.py
```

预期：
- ✅ 全绿
- 📊 日志：
  ```
  PREFER_NEW rules: trying v2 for project=tp_xxx
  PREFER_NEW rules: v2 succeeded, 6 findings
  ```
  或（如果 v2 失败）：
  ```
  PREFER_NEW rules: v2 failed, falling back to old
  PREFER_NEW rules: fallback succeeded, 5 findings
  ```

### 注意事项

1. **规则文件可选**: 如果项目没有上传规则文件，规则评估器不会运行
2. **新索引依赖**: v2 评估器使用新检索器，需要 `INGEST_MODE` 至少为 `SHADOW` 以确保新索引有数据
3. **优雅降级**: PREFER_NEW 模式下，v2 失败会自动回退到旧评估器，不影响业务

---

## Step 11: NEW_ONLY 收口

### NEW_ONLY 切换顺序建议

按以下顺序逐个启用 NEW_ONLY 模式，每切换一个都运行 smoke test 验证全绿后再切下一个。

#### 阶段 1: RETRIEVAL_MODE=NEW_ONLY

```bash
# .env 或 docker-compose.yml
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=OLD  # 其他保持 OLD 或 PREFER_NEW
EXTRACT_MODE=OLD
REVIEW_MODE=OLD
RULES_MODE=OLD

# 重启并测试
docker-compose up -d backend
python scripts/smoke/tender_e2e.py
```

**预期**: ✅ Smoke 全绿（检索强制使用新检索器）

---

#### 阶段 2: INGEST_MODE=NEW_ONLY

```bash
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=NEW_ONLY
EXTRACT_MODE=OLD
REVIEW_MODE=OLD
RULES_MODE=OLD

# 重启并测试
docker-compose up -d backend
python scripts/smoke/tender_e2e.py
```

**预期**: ✅ Smoke 全绿（入库强制使用新索引）

---

#### 阶段 3: EXTRACT_MODE=NEW_ONLY

```bash
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=NEW_ONLY
EXTRACT_MODE=NEW_ONLY
REVIEW_MODE=OLD
RULES_MODE=OLD

# 重启并测试
docker-compose up -d backend
python scripts/smoke/tender_e2e.py
```

**预期**: ✅ Smoke 全绿（Step 1/2 强制使用 v2 抽取）

---

#### 阶段 4: REVIEW_MODE=NEW_ONLY

```bash
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=NEW_ONLY
EXTRACT_MODE=NEW_ONLY
REVIEW_MODE=NEW_ONLY
RULES_MODE=OLD

# 重启并测试
docker-compose up -d backend
python scripts/smoke/tender_e2e.py
```

**预期**: ✅ Smoke 全绿（Step 5 强制使用 v2 审核）

---

#### 阶段 5: RULES_MODE=NEW_ONLY

```bash
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=NEW_ONLY
EXTRACT_MODE=NEW_ONLY
REVIEW_MODE=NEW_ONLY
RULES_MODE=NEW_ONLY

# 重启并测试
docker-compose up -d backend
python scripts/smoke/tender_e2e.py
```

**预期**: ✅ Smoke 全绿（规则评估强制使用 v2）

---

### 全链路 NEW_ONLY 最终验收

**最终配置**:
```bash
RETRIEVAL_MODE=NEW_ONLY
INGEST_MODE=NEW_ONLY
EXTRACT_MODE=NEW_ONLY
REVIEW_MODE=NEW_ONLY
RULES_MODE=NEW_ONLY
```

**验收标准**:
- ✅ Smoke test 全绿
- ✅ 所有步骤强制使用 v2 实现
- ✅ 无回退到旧逻辑
- ✅ 失败信息清晰可查

### NEW_ONLY 失败排查

**如果某个 NEW_ONLY 测试失败**:

1. **查看运行日志**:
```bash
docker-compose logs backend | grep "NEW_ONLY.*failed"
```

2. **查询运行状态**:
```bash
curl http://localhost:9001/api/apps/tender/runs/<run_id>
```

3. **检查新索引数据**:
```bash
curl "http://localhost:9001/api/_debug/retrieval/test?query=test&project_id=<project_id>"
```

4. **常见失败原因**:
   - 新索引无数据 → 确保 `INGEST_MODE` 至少为 `SHADOW`
   - LLM 服务不可用 → 检查 LLM 配置
   - 新检索无结果 → 检查 `doc_types` 过滤是否正确

### 回退方案

**如果 NEW_ONLY 失败率高，回退到 PREFER_NEW**:
```bash
RETRIEVAL_MODE=PREFER_NEW
INGEST_MODE=PREFER_NEW
EXTRACT_MODE=PREFER_NEW
REVIEW_MODE=PREFER_NEW
RULES_MODE=PREFER_NEW
```

---

## 参考文档

- [完整文档](../SMOKE_TEST.md)
- [快速开始](../QUICK_START_SMOKE.md)
- [脚本详细说明](../scripts/smoke/README.md)
- [测试数据说明](../testdata/README.md)
- [系统架构文档](../系统架构文档.md)

## 版本信息

- **版本**: 1.0.0
- **创建日期**: 2025-12-19
- **维护**: 开发团队
- **状态**: ✅ 生产就绪

---

**重要提醒**: 本文档描述的是 Step 0 - Smoke 测试闸门。后续所有开发都必须在此闸门保护下进行。

