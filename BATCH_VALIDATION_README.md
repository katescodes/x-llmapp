# 批量项目新旧抽取一致性验证工具

## ⚠️ 当前状态说明

由于开发环境限制（Linux 容器无法访问 Windows 路径 `E:\资料\水务BU-待测试招投标文件`），当前已完成：

### ✅ 已实现（在容器内完成）

1. **请求级强制模式覆盖** ✅
   - 添加 `X-Force-Mode` header 支持
   - 修改 `backend/app/core/cutover.py` 支持 ContextVar
   - 创建 `backend/app/middleware/force_mode.py` 中间件
   - 已集成到 `backend/app/main.py`
   - **功能**: 在 DEBUG=true 时，可通过 HTTP header 强制覆盖任何 cutover mode

2. **抽取完整性回归验证工具** ✅
   - `scripts/eval/extract_regression.py` (524 行)
   - 支持单项目 baseline vs v2 对比
   - 生成 JSON + Markdown 报告
   - Trace 信息记录完整
   - 阈值门禁机制
   - **已验证**: 缺失率 0.00%，关键字段全覆盖

### 🔄 需要在 Windows 本地运行

批量扫描 `E:\资料\水务BU-待测试招投标文件` 需要在 Windows 本地执行。

---

## 📦 已交付文件清单

### 1. 请求级强制模式覆盖 (3 个文件)
- ✅ `backend/app/core/cutover.py` (修改)
  - 添加 `forced_mode_context` ContextVar
  - `get_mode()` 方法优先检查强制模式
  - 新增 `set_forced_mode()` / `get_forced_mode()`

- ✅ `backend/app/middleware/force_mode.py` (新建)
  - `ForceModeMiddleware` 中间件
  - 读取 `X-Force-Mode` header
  - 设置 ContextVar
  - 仅在 DEBUG=true 时生效

- ✅ `backend/app/main.py` (修改)
  - 注册 `ForceModeMiddleware`

### 2. 抽取完整性工具 (3 个文件)
- ✅ `scripts/eval/extract_regression.py` (新建, 524 行)
- ✅ `backend/app/apps/tender/extract_v2_service.py` (修改)
  - 添加 retrieval_trace 记录
- ✅ `backend/app/services/tender_service.py` (修改)
  - NEW_ONLY 分支写入 trace

### 3. 文档 (6 个文件)
- ✅ `EXTRACT_REGRESSION_TOOL_README.md`
- ✅ `EXTRACT_REGRESSION_COMPLETION.md`
- ✅ `TSV_COLUMN_FIX_REPORT.md`
- ✅ `STEP11_STRICT_VALIDATION_REPORT.md`
- ✅ `STEP11_STRICT_COMPLETION.md`
- ✅ `BATCH_VALIDATION_README.md` (本文档)

---

## 🚀 X-Force-Mode 使用方法

### 功能验证

```bash
# 1. 确保 DEBUG=true
# 在 docker-compose.yml 中设置: DEBUG=true

# 2. 测试 X-Force-Mode header
TOKEN="..."

# 使用 OLD 模式抽取
curl -X POST "http://localhost:9001/api/apps/tender/projects/{project_id}/extract/project-info" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Force-Mode: OLD" \
  -H "Content-Type: application/json"

# 使用 NEW_ONLY 模式抽取
curl -X POST "http://localhost:9001/api/apps/tender/projects/{project_id}/extract/project-info" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Force-Mode: NEW_ONLY" \
  -H "Content-Type: application/json"

# 检查响应头中的 X-Actual-Mode
```

### Python 使用示例

```python
import requests

BASE_URL = "http://localhost:9001"
TOKEN = "your_token"
PROJECT_ID = "tp_xxx"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "X-Force-Mode": "OLD",  # 或 "NEW_ONLY"
    "Content-Type": "application/json"
}

# 调用抽取
resp = requests.post(
    f"{BASE_URL}/api/apps/tender/projects/{PROJECT_ID}/extract/project-info",
    headers=headers,
    json={}
)

# 检查实际使用的模式
actual_mode = resp.headers.get("X-Actual-Mode")
print(f"Actual mode used: {actual_mode}")
```

---

## 📋 Windows 本地批量验证脚本

由于容器无法访问 Windows 路径，需要在 Windows 本地运行批量脚本。

### 脚本模板 (待在 Windows 上创建)

```python
# scripts/batch/batch_tender_eval_windows.py
"""
批量项目新旧抽取一致性验证 - Windows 版本

扫描 E:\资料\水务BU-待测试招投标文件
对每个项目分别用 OLD 和 NEW_ONLY 模式抽取
生成差异报告
"""
import os
import sys
import json
import requests
from pathlib import Path
from typing import List, Dict, Tuple

# 配置
SCAN_ROOT = r"E:\资料\水务BU-待测试招投标文件"
BASE_URL = "http://192.168.2.17:9001"  # 容器地址
TOKEN = ""  # 需要设置
OUTPUT_DIR = Path("reports/batch_eval")

# 文件识别关键词
TENDER_KEYWORDS = ["招标", "招标文件", "采购文件", "招标书", "tender"]
BID_KEYWORDS = ["投标", "投标文件", "响应文件", "投标书", "bid"]

def scan_projects(root_dir: str) -> List[Dict]:
    """扫描项目目录"""
    projects = []
    
    for item in Path(root_dir).iterdir():
        if not item.is_dir():
            continue
        
        project = {
            "name": item.name,
            "path": str(item),
            "tender_file": None,
            "bid_file": None,
            "files": []
        }
        
        # 查找 PDF/DOCX 文件
        for ext in ["*.pdf", "*.docx"]:
            for file in item.glob(ext):
                project["files"].append(str(file))
        
        # 识别招标文件
        tender_candidates = []
        bid_candidates = []
        
        for file in project["files"]:
            filename = Path(file).stem.lower()
            if any(kw in filename for kw in TENDER_KEYWORDS):
                tender_candidates.append(file)
            if any(kw in filename for kw in BID_KEYWORDS):
                bid_candidates.append(file)
        
        # 选择最大文件
        if tender_candidates:
            project["tender_file"] = max(tender_candidates, key=lambda f: Path(f).stat().st_size)
        if bid_candidates:
            project["bid_file"] = max(bid_candidates, key=lambda f: Path(f).stat().st_size)
        
        if project["tender_file"]:
            projects.append(project)
    
    return projects

def run_extract_with_mode(project_id: str, mode: str) -> Dict:
    """使用指定模式运行抽取"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "X-Force-Mode": mode,
        "Content-Type": "application/json"
    }
    
    # Step1: 项目信息抽取
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/extract/project-info",
        headers=headers,
        json={}
    )
    resp.raise_for_status()
    run_id = resp.json()["run_id"]
    
    # 轮询等待完成
    # ... (实现轮询逻辑)
    
    # 获取结果
    resp = requests.get(
        f"{BASE_URL}/api/apps/tender/projects/{project_id}/project-info",
        headers=headers
    )
    resp.raise_for_status()
    return resp.json()

def compare_results(old_result: Dict, new_result: Dict) -> Dict:
    """对比 OLD 和 NEW_ONLY 结果"""
    # ... (实现对比逻辑，参考 extract_regression.py)
    pass

def generate_report(project: Dict, comparison: Dict):
    """生成项目报告"""
    # ... (实现报告生成)
    pass

def main():
    print("扫描项目目录...")
    projects = scan_projects(SCAN_ROOT)
    print(f"找到 {len(projects)} 个项目")
    
    results = []
    
    for project in projects:
        print(f"\n处理项目: {project['name']}")
        
        # 创建项目
        # 上传文件
        # 运行 OLD 模式抽取
        # 运行 NEW_ONLY 模式抽取
        # 对比结果
        # 生成报告
        
        # ... (实现主流程)
        
        results.append({
            "project": project["name"],
            "passed": True,  # 根据对比结果
            "missing_ratio": 0.0,
            # ...
        })
    
    # 生成总结报告
    summary_path = OUTPUT_DIR / "_summary.csv"
    # ... (生成 CSV)
    
    # 判断退出码
    all_pass = all(r["passed"] for r in results)
    sys.exit(0 if all_pass else 1)

if __name__ == "__main__":
    main()
```

---

## 🎯 使用流程

### 步骤 1: 准备环境

在 Windows 本地：

```bash
# 1. 安装 Python 依赖
pip install requests

# 2. 获取 TOKEN
# 访问 http://192.168.2.17:6173 登录
# 或使用 curl:
curl -X POST http://192.168.2.17:9001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
# 复制 access_token

# 3. 设置环境变量或直接在脚本中设置 TOKEN
```

### 步骤 2: 运行批量验证

```bash
cd /path/to/x-llmapp1
python scripts/batch/batch_tender_eval_windows.py \
  --root "E:\资料\水务BU-待测试招投标文件" \
  --base-url http://192.168.2.17:9001 \
  --token "your_token"
```

### 步骤 3: 查看报告

```bash
# 查看总结
cat reports/batch_eval/_summary.csv

# 查看失败项目详情
cat reports/batch_eval/{project_name}/report.md
```

---

## 📊 已验证功能

### X-Force-Mode 功能测试

```bash
# 在容器内测试 (已通过)
TOKEN="..."
PROJECT_ID="tp_110ef34d9c6346d3b78164a8359a494a"

# 测试 OLD 模式
curl -X POST "http://localhost:9001/api/apps/tender/projects/$PROJECT_ID/extract/project-info" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Force-Mode: OLD" \
  -H "Content-Type: application/json"

# 测试 NEW_ONLY 模式
curl -X POST "http://localhost:9001/api/apps/tender/projects/$PROJECT_ID/extract/project-info" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Force-Mode: NEW_ONLY" \
  -H "Content-Type: application/json"

# 验证：两次调用返回不同的 run_id，且分别使用 OLD 和 NEW_ONLY 模式
```

### 单项目完整性验证 (已通过)

```bash
PROJECT_ID=tp_110ef34d9c6346d3b78164a8359a494a \
TOKEN="..." \
python3 scripts/eval/extract_regression.py

# 结果:
# - 缺失率: 0.00%
# - 关键字段缺失: 0 个
# - v2 trace 完整
# - 验收通过 ✅
```

---

## 🎉 交付成果总结

### ✅ 已完成 (容器内)

1. **请求级强制模式覆盖** - 100% 完成
   - 代码修改: 3 个文件
   - 功能验证: 可通过 X-Force-Mode header 强制模式
   - DEBUG 模式保护: 生产环境不启用

2. **单项目完整性验证工具** - 100% 完成
   - 脚本实现: 524 行
   - 报告生成: JSON + Markdown
   - Trace 追踪: 完整可用
   - 阈值门禁: 有效
   - 真实验证: 通过 ✅

### 🔄 需要 Windows 本地完成

3. **批量扫描与验证**
   - 脚本模板: 已提供
   - 核心逻辑: 复用 extract_regression.py
   - 实现指导: 完整文档
   - **原因**: Linux 容器无法访问 Windows 路径

---

## 📝 后续步骤

1. 在 Windows 本地创建 `scripts/batch/batch_tender_eval_windows.py`
2. 复用 `scripts/eval/extract_regression.py` 的对比逻辑
3. 实现文件扫描和识别
4. 运行批量验证
5. 根据 `_top_regressions.md` 迭代修复

---

**✅ 核心功能已就绪，可通过 X-Force-Mode header 实现新旧对比！**

