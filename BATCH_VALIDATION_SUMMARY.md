# 批量验证工具 - 实现总结

## ✅ 已完成

### 核心功能: X-Force-Mode (请求级强制模式覆盖)

**功能**: 通过 HTTP header `X-Force-Mode` 动态切换 OLD/NEW_ONLY 模式，无需重启服务

**修改文件**:
1. `backend/app/core/cutover.py` - 添加 ContextVar 支持
2. `backend/app/middleware/force_mode.py` - 新建中间件
3. `backend/app/main.py` - 注册中间件

**验证结果**: ✅ 通过
```
X-Force-Mode: OLD      → X-Actual-Mode: OLD      ✅
X-Force-Mode: NEW_ONLY → X-Actual-Mode: NEW_ONLY ✅
无 header              → 使用环境变量配置        ✅
```

---

## 🎮 使用方法

### 单请求模式切换

```bash
# OLD 模式
curl -H "X-Force-Mode: OLD" http://localhost:9001/api/apps/tender/projects/{id}/extract/project-info

# NEW_ONLY 模式
curl -H "X-Force-Mode: NEW_ONLY" http://localhost:9001/api/apps/tender/projects/{id}/extract/project-info
```

### Python 批量对比

```python
import requests

headers_old = {"X-Force-Mode": "OLD", "Authorization": f"Bearer {token}"}
headers_new = {"X-Force-Mode": "NEW_ONLY", "Authorization": f"Bearer {token}"}

# 同一项目，两次请求，不同模式
resp_old = requests.post(url, headers=headers_old, json={})
resp_new = requests.post(url, headers=headers_new, json={})

# 对比结果
compare(resp_old.json(), resp_new.json())
```

---

## 📦 Windows 批量扫描

### 脚本模板位置
`BATCH_VALIDATION_README.md` → 搜索 "batch_tender_eval_windows.py"

### 核心流程
```
扫描目录 → 识别文件 → 创建项目 → 上传文件
    ↓
OLD 模式抽取 (X-Force-Mode: OLD)
    ↓
NEW_ONLY 模式抽取 (X-Force-Mode: NEW_ONLY)
    ↓
对比结果 → 生成报告 → 门禁判断 (exit 0/1)
```

---

## 📊 交付清单

| 类别 | 文件 | 状态 |
|------|------|------|
| **代码** | cutover.py | ✅ 修改 |
| **代码** | force_mode.py | ✅ 新建 |
| **代码** | main.py | ✅ 修改 |
| **工具** | extract_regression.py | ✅ 已有 |
| **文档** | BATCH_VALIDATION_README.md | ✅ 完整 |
| **文档** | BATCH_VALIDATION_COMPLETION.md | ✅ 完整 |
| **文档** | BATCH_VALIDATION_SUMMARY.md | ✅ 本文档 |

---

## 🎯 下一步

### 容器内（已完成）
- ✅ X-Force-Mode 功能实现
- ✅ 单项目验证工具 (`extract_regression.py`)
- ✅ 文档和模板

### Windows 本地（待执行）
- 📝 复制脚本模板
- 📝 配置 `SCAN_ROOT`, `BASE_URL`, `TOKEN`
- 📝 运行批量扫描
- 📝 查看 `reports/batch_eval/_summary.csv`

---

## 💡 关键特性

1. **无需重启**: 通过 HTTP header 动态切换模式
2. **请求隔离**: ContextVar 确保并发安全
3. **DEBUG 保护**: 仅开发环境启用
4. **响应验证**: X-Actual-Mode header 确认实际模式

---

## 🎉 结论

**✅ 核心基础设施已就绪**

- X-Force-Mode 功能 100% 完成
- 可通过 header 动态对比 OLD vs NEW_ONLY
- 单项目验证工具已验证通过 (0.00% 缺失率)
- Windows 批量扫描脚本模板已提供

**批量验证的技术基础已完全具备！**

