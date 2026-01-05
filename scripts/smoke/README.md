# 招投标端到端 Smoke 测试

## 概述

端到端 Smoke 测试（冒烟测试）用于验证招投标全流程的核心功能是否正常工作。这是一个**闸门测试**，在进行任何重大改动之前或之后，都应该确保这个测试通过。

## 测试覆盖范围

测试覆盖了招投标系统的完整流程：

1. **创建项目** - `POST /api/apps/tender/projects`
2. **上传招标文件** - `POST /api/apps/tender/projects/{project_id}/assets/import` (kind=tender)
3. **Step 1: 提取项目信息** - `POST /api/apps/tender/projects/{project_id}/extract/project-info`
4. **Step 2: 识别风险** - `POST /api/apps/tender/projects/{project_id}/extract/risks`
5. **Step 3: 生成目录** - `POST /api/apps/tender/projects/{project_id}/directory/generate`
6. **Step 3.2: 自动填充样例** (可选) - `POST /api/apps/tender/projects/{project_id}/directory/auto-fill-samples`
7. **上传格式模板** (可选) - `POST /api/apps/tender/projects/{project_id}/directory/apply-format-template`
8. **上传投标文件** - `POST /api/apps/tender/projects/{project_id}/assets/import` (kind=bid)
9. **Step 5: 运行审查** - `POST /api/apps/tender/projects/{project_id}/review/run`
10. **导出 DOCX** - `GET /api/apps/tender/projects/{project_id}/export/docx`

## 目录结构

```
/aidata/x-llmapp1/
├── testdata/                          # 测试数据
│   ├── tender_sample.pdf             # 招标文件样例
│   ├── bid_sample.docx               # 投标文件样例
│   └── rules.yaml                    # 自定义规则样例（当前为空）
├── scripts/smoke/                     # Smoke 测试脚本
│   ├── README.md                     # 本文档
│   └── tender_e2e.py                 # 端到端测试主脚本
└── backend/
    ├── pytest.ini                    # pytest 配置
    └── tests/smoke/                  # pytest 测试
        ├── __init__.py
        └── test_tender_e2e.py        # pytest 封装
```

## 运行方式

### 方式 1: 直接运行 Python 脚本（推荐）

```bash
# 在项目根目录运行
cd /aidata/x-llmapp1
python scripts/smoke/tender_e2e.py
```

### 方式 2: 使用 pytest

```bash
# 在后端目录运行
cd /aidata/x-llmapp1/backend
pytest -m smoke

# 或者只运行 smoke 测试
pytest tests/smoke/test_tender_e2e.py -v
```

### 方式 3: 从前端运行（需要 npm）

```bash
cd /aidata/x-llmapp1/frontend
npm run smoke:tender
```

## 环境变量配置

可以通过环境变量自定义测试行为：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `BASE_URL` | `http://localhost:9001` | 后端服务地址 |
| `TOKEN` | (空) | 认证令牌，留空则自动登录 |
| `USERNAME` | `admin@example.com` | 登录用户名 |
| `PASSWORD` | `admin123` | 登录密码 |
| `TENDER_FILE` | `testdata/tender_sample.pdf` | 招标文件路径 |
| `BID_FILE` | `testdata/bid_sample.docx` | 投标文件路径 |
| `RULES_FILE` | `testdata/rules.yaml` | 自定义规则文件路径 |
| `FORMAT_TEMPLATE_FILE` | (空) | 格式模板文件路径（可选） |
| `SKIP_OPTIONAL` | `false` | 跳过可选步骤 |
| `KEEP_PROJECT` | `false` | 测试后保留项目（不清理） |

### 示例：使用自定义配置

```bash
# 使用自定义后端地址和跳过可选步骤
BASE_URL=http://192.168.1.100:9001 \
SKIP_OPTIONAL=true \
python scripts/smoke/tender_e2e.py

# 使用自定义文件
TENDER_FILE=/path/to/my/tender.pdf \
BID_FILE=/path/to/my/bid.docx \
python scripts/smoke/tender_e2e.py

# 保留测试项目（用于调试）
KEEP_PROJECT=true python scripts/smoke/tender_e2e.py
```

## 前置条件

### 1. 服务运行

确保所有服务正常运行：

```bash
# 使用 Docker Compose 启动
docker compose up -d --build

# 检查服务状态
docker compose ps

# 查看日志
docker compose logs -f backend
```

### 2. 测试数据

测试数据位于 `testdata/` 目录，已包含：
- `tender_sample.pdf` - 招标文件样例
- `bid_sample.docx` - 投标文件样例
- `rules.yaml` - 自定义规则样例

如需使用自己的测试文件，请放置在 `testdata/` 目录或通过环境变量指定路径。

### 3. Python 依赖

脚本依赖 `requests` 库：

```bash
pip install requests
```

如果使用 pytest：

```bash
pip install pytest
```

## 验收标准

### Step 0 验收标准（必须全部通过）

运行以下命令：

```bash
# 1. 启动服务
docker compose up -d --build

# 2. 运行 smoke 测试
python scripts/smoke/tender_e2e.py

# 3. (可选) 运行 pytest
cd backend && pytest -m smoke
```

**成功标准：**

1. ✅ 所有步骤都打印 `✓` 成功标记
2. ✅ 最终打印 "所有测试通过！"
3. ✅ 脚本退出码为 0
4. ✅ 生成的 DOCX 文件可下载或返回成功

**如果失败：**

1. 🔴 查看失败步骤的错误信息
2. 🔴 检查服务日志：`docker compose logs backend`
3. 🔴 确认测试文件存在且格式正确
4. 🔴 确认后端服务可访问：`curl http://localhost:9001/health`

## 输出示例

成功运行的输出示例：

```
============================================================
  招投标端到端 Smoke 测试
============================================================

ℹ Backend URL: http://localhost:9001
ℹ Tender File: testdata/tender_sample.pdf
ℹ Bid File: testdata/bid_sample.docx
ℹ Skip Optional: False

ℹ 正在登录...
✓ 登录成功 (user: admin@example.com)

ℹ Step 0: 创建项目...
✓ 项目创建成功 (ID: tp_xxx)

ℹ 上传招标文件: testdata/tender_sample.pdf
✓ 招标文件上传成功 (asset_id: ast_xxx)

ℹ Step 1: 提取项目信息...
ℹ   任务已提交 (run_id: run_xxx)
ℹ   进度: 50.0% - extracting...
✓   任务完成: success
✓ Step 1 完成

ℹ Step 2: 提取风险...
ℹ   任务已提交 (run_id: run_xxx)
ℹ   进度: 50.0% - analyzing...
✓   任务完成: success
✓ Step 2 完成

[... 更多步骤 ...]

============================================================
  ✓ 所有测试通过！
============================================================
```

## 故障排查

### 问题 1: 连接被拒绝

```
✗ 创建项目失败: Connection refused
```

**解决方案：**
1. 检查后端服务是否运行：`docker compose ps`
2. 检查端口映射：`docker compose port backend 8000`
3. 尝试访问健康检查：`curl http://localhost:9001/health`

### 问题 2: 认证失败

```
✗ 登录失败: 401 Unauthorized
```

**解决方案：**
1. 检查用户名密码是否正确
2. 确认用户已创建（首次运行时可能需要注册）
3. 尝试手动登录：`curl -X POST http://localhost:9001/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin@example.com","password":"admin123"}'`

### 问题 3: 任务超时

```
✗   任务超时 (>300s)
```

**解决方案：**
1. 检查后端日志：`docker compose logs backend`
2. 检查 LLM 服务是否正常
3. 增加超时时间（修改脚本中的 `timeout` 参数）

### 问题 4: 文件不存在

```
✗ 文件不存在: /aidata/x-llmapp1/testdata/tender_sample.pdf
```

**解决方案：**
1. 检查测试文件是否存在：`ls -la testdata/`
2. 使用绝对路径或设置环境变量：`TENDER_FILE=/absolute/path/to/file.pdf`

## CI/CD 集成

### GitHub Actions 示例

```yaml
name: Smoke Tests

on: [push, pull_request]

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Start services
        run: docker compose up -d --build
      
      - name: Wait for backend
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:9001/health; do sleep 2; done'
      
      - name: Run smoke tests
        run: python scripts/smoke/tender_e2e.py
      
      - name: Cleanup
        if: always()
        run: docker compose down -v
```

### GitLab CI 示例

```yaml
smoke_test:
  stage: test
  script:
    - docker compose up -d --build
    - sleep 30  # 等待服务启动
    - python scripts/smoke/tender_e2e.py
  after_script:
    - docker compose down -v
```

## 扩展与定制

### 添加自定义步骤

在 `tender_e2e.py` 中添加新的测试函数：

```python
def test_custom_feature(token: str, project_id: str) -> bool:
    """测试自定义功能"""
    log_info("测试自定义功能...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/apps/tender/projects/{project_id}/custom",
            headers={"Authorization": f"Bearer {token}"},
            json={"param": "value"},
            timeout=10
        )
        resp.raise_for_status()
        log_success("自定义功能测试通过")
        return True
    except Exception as e:
        log_error(f"自定义功能测试失败: {e}")
        return False
```

然后在 `main()` 函数中调用：

```python
# 在适当位置添加
test_custom_feature(token, project_id)
```

### 使用自定义测试数据

1. 准备测试文件
2. 放置在 `testdata/` 目录
3. 通过环境变量指定

```bash
TENDER_FILE=testdata/my_tender.pdf \
BID_FILE=testdata/my_bid.docx \
python scripts/smoke/tender_e2e.py
```

## 注意事项

1. **不修改业务逻辑**：此测试仅验证现有功能，不应修改任何业务代码
2. **清理测试数据**：默认情况下会清理测试项目，可通过 `KEEP_PROJECT=true` 保留
3. **并发运行**：多个测试可能会创建多个项目，注意资源占用
4. **LLM 依赖**：测试依赖 LLM 服务，确保 LLM 配置正确
5. **网络依赖**：需要网络连接访问后端服务

## 版本历史

- **v1.0.0** (2025-12-19) - 初始版本
  - 完整的招投标流程测试
  - 支持可选步骤跳过
  - pytest 集成
  - 前端 npm 脚本支持

## 联系与支持

如有问题或建议，请联系开发团队或提交 Issue。
















