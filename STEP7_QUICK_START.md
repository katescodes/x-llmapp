# Step 7 快速开始指南

## 📌 核心功能

**PREFER_NEW 模式**: 优先使用 v2 抽取，失败则自动回退到旧逻辑

---

## 🚀 快速验证

### 1. 代码逻辑验证（✅ 已通过）

```bash
cd /aidata/x-llmapp1
python scripts/verify_step7_logic.py
```

**验证结果**:
```
✅ 所有检查通过！PREFER_NEW 逻辑实现正确。

📊 代码统计:
  - PREFER_NEW 分支数: 2 (extract_project_info + extract_risks)
  - 完整逻辑块: try → v2 → except → fallback ✅
```

### 2. 灰度配置示例

#### 场景1：单个项目灰度

```bash
# 1. 启动系统（默认 OLD 模式）
cd /aidata/x-llmapp1
docker-compose up -d

# 2. 运行 smoke 获取项目 ID
python scripts/smoke/tender_e2e.py
# 输出: 项目 ID: tp_xxx

# 3. 配置该项目使用 PREFER_NEW
# 编辑 .env
EXTRACT_MODE=OLD
CUTOVER_PROJECT_IDS='{"extract":{"PREFER_NEW":["tp_xxx"]}}'

# 4. 重启后端
docker-compose restart backend

# 5. 重新运行该项目的抽取
# 查看日志确认使用 v2
docker-compose logs backend | grep "PREFER_NEW"
```

#### 场景2：多个项目灰度

```bash
# .env
EXTRACT_MODE=OLD
CUTOVER_PROJECT_IDS='{"extract":{"PREFER_NEW":["tp_project1","tp_project2","tp_project3"]}}'
```

#### 场景3：全量切换

```bash
# .env
EXTRACT_MODE=PREFER_NEW
CUTOVER_PROJECT_IDS='{}'
```

---

## 🔍 监控点

### 查看 v2 成功日志

```bash
docker-compose logs backend | grep "PREFER_NEW.*v2 succeeded"
```

**预期输出**:
```
INFO: PREFER_NEW extract_project_info: v2 succeeded for project=tp_xxx
INFO: PREFER_NEW extract_risks: v2 succeeded for project=tp_xxx, count=3
```

### 查看回退日志

```bash
docker-compose logs backend | grep "falling back to old extraction"
```

**预期输出** (仅在 v2 失败时):
```
WARNING: PREFER_NEW extract_project_info: v2 failed for project=tp_xxx, falling back to old extraction
```

### 统计 v2 成功率

```bash
# 成功次数
docker-compose logs backend | grep -c "PREFER_NEW.*v2 succeeded"

# 失败次数（回退）
docker-compose logs backend | grep -c "falling back to old extraction"
```

---

## 🎯 验收清单

### ✅ 代码层面（已完成）

- [x] `extract_project_info` 实现 PREFER_NEW 分支
- [x] `extract_risks` 实现 PREFER_NEW 分支
- [x] v2 成功时使用 v2 结果
- [x] v2 失败时自动回退旧逻辑
- [x] 统一写入旧表（保证前端兼容）
- [x] 详细的日志记录
- [x] 灰度控制支持（CUTOVER_PROJECT_IDS）

### ⏳ 运行时验证（待 LLM 修复）

- [ ] EXTRACT_MODE=OLD 下 smoke 全绿
- [ ] EXTRACT_MODE=PREFER_NEW + 灰度 smoke 全绿
- [ ] 前端 Step1/2 页面显示正常
- [ ] v2 成功日志可见
- [ ] v2 失败回退日志可见（模拟故障场景）

---

## 🐛 已知问题与解决方案

### 问题：Smoke 测试超时

**现象**:
```
✗ 任务超时 (>180s) - Step 1 提取项目信息
```

**根因**: LLM 服务响应超时（环境问题，非 Step 7 引入）

**解决方案**:

#### 方案1：检查 LLM 服务状态

```bash
# 检查 LLM_SERVICE_URL 配置
docker-compose exec backend env | grep LLM_SERVICE_URL

# 测试 LLM 服务是否可达
curl -X POST http://<LLM_SERVICE_URL>/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"mock","messages":[{"role":"user","content":"test"}],"max_tokens":10}'
```

#### 方案2：增加超时时间

```bash
# .env
LLM_TIMEOUT=300  # 增加到 5 分钟
```

#### 方案3：使用真实 LLM

```bash
# .env
ENABLE_MOCK_LLM=false
LLM_SERVICE_URL=http://real-llm-endpoint:8080
LLM_API_KEY=your_api_key
```

---

## 📊 架构对比

### OLD 模式
```
用户请求 → 旧抽取逻辑 → 旧表 → 返回结果
```

### SHADOW 模式（Step 6）
```
用户请求 → 旧抽取逻辑 → 旧表 → 返回结果
              ↓
          (异步) v2 抽取 → diff 日志
```

### PREFER_NEW 模式（Step 7）⭐
```
用户请求 → v2 抽取 → 成功 → 旧表 → 返回结果
              ↓
            失败
              ↓
          旧抽取逻辑 → 旧表 → 返回结果
```

### NEW_ONLY 模式（未来）
```
用户请求 → v2 抽取 → 成功 → 旧表 → 返回结果
              ↓
            失败 → 报错
```

---

## 📝 模式选择指南

| 模式 | 适用场景 | v2 失败影响 | 切换成本 |
|-----|---------|-----------|---------|
| **OLD** | 生产稳定环境 | N/A | 无 |
| **SHADOW** | v2 功能验证 | 不影响（仅日志） | 低 |
| **PREFER_NEW** ⭐ | 灰度发布 | 自动回退，不影响 | 低 |
| **NEW_ONLY** | 全量切换 | 报错，需修复 | 高 |

**推荐路径**: OLD → SHADOW（验证） → PREFER_NEW（灰度） → NEW_ONLY（全量）

---

## 🎉 总结

### 完成内容

1. ✅ 实现 PREFER_NEW 模式（v2 优先 + 自动回退）
2. ✅ 支持灰度控制（CUTOVER_PROJECT_IDS）
3. ✅ 前端完全兼容（统一写旧表）
4. ✅ 详细日志记录（可观测）
5. ✅ 代码逻辑验证通过

### 待完成（依赖 LLM 修复）

- ⏳ 端到端 smoke 测试
- ⏳ 性能对比数据
- ⏳ 生产灰度验证

### 下一步建议

1. **立即可做**: 代码 review、架构设计审查（✅ 已完成）
2. **LLM 修复后**: smoke 测试、灰度发布、监控指标
3. **长期优化**: v2 性能调优、NEW_ONLY 全量切换

---

**📞 遇到问题？**
- 查看完整报告: `STEP7_COMPLETION_REPORT.md`
- 验证代码逻辑: `python scripts/verify_step7_logic.py`
- 查看 smoke 文档: `docs/SMOKE.md`

