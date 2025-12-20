# 端到端 Smoke 测试闸门

## 快速开始

```bash
# 1. 启动服务
docker compose up -d --build

# 2. 运行 smoke 测试
python scripts/smoke/tender_e2e.py

# 或使用 pytest
cd backend && pytest -m smoke
```

## 验收标准（Step 0）

✅ **必须通过以下测试才能进入下一步开发：**

1. 服务启动成功：`docker compose up -d --build`
2. Smoke 测试通过：`python scripts/smoke/tender_e2e.py`
3. 脚本退出码为 0
4. 所有步骤标记为成功 (✓)

## 测试覆盖

本 Smoke 测试覆盖招投标完整流程：

- ✅ 创建项目
- ✅ 上传招标文件
- ✅ Step 1: 提取项目信息
- ✅ Step 2: 识别风险
- ✅ Step 3: 生成目录
- ✅ Step 3.2: 自动填充样例（可选）
- ✅ 上传格式模板（可选）
- ✅ 上传投标文件
- ✅ Step 5: 运行审查
- ✅ 导出 DOCX

## 目录结构

```
/aidata/x-llmapp1/
├── testdata/                          # 测试数据
│   ├── tender_sample.pdf             # 招标文件样例
│   ├── bid_sample.docx               # 投标文件样例
│   └── rules.yaml                    # 自定义规则样例
├── scripts/smoke/                     # Smoke 测试
│   ├── README.md                     # 详细文档
│   └── tender_e2e.py                 # 测试脚本
└── backend/
    ├── pytest.ini                    # pytest 配置
    └── tests/smoke/                  # pytest 测试
        └── test_tender_e2e.py
```

## 配置选项

通过环境变量配置测试：

```bash
# 使用自定义后端地址
BASE_URL=http://192.168.1.100:9001 python scripts/smoke/tender_e2e.py

# 跳过可选步骤（加快测试）
SKIP_OPTIONAL=true python scripts/smoke/tender_e2e.py

# 保留测试项目（用于调试）
KEEP_PROJECT=true python scripts/smoke/tender_e2e.py
```

完整配置选项请参考：[scripts/smoke/README.md](scripts/smoke/README.md)

## 故障排查

### 服务无法启动

```bash
# 检查服务状态
docker compose ps

# 查看日志
docker compose logs backend

# 重启服务
docker compose restart
```

### 测试失败

```bash
# 检查后端健康状态
curl http://localhost:9001/health

# 查看详细日志
python scripts/smoke/tender_e2e.py 2>&1 | tee smoke.log

# 保留项目用于调试
KEEP_PROJECT=true python scripts/smoke/tender_e2e.py
```

## 开发流程

### 进入下一步开发前

**必须确保 Smoke 测试通过！**

```bash
# 1. 拉取最新代码
git pull

# 2. 重新构建并启动
docker compose up -d --build

# 3. 运行 smoke 测试
python scripts/smoke/tender_e2e.py

# 4. 如果通过，可以继续开发
# 如果失败，修复问题后重新测试
```

### 提交代码前

**必须确保 Smoke 测试通过！**

```bash
# 1. 运行 smoke 测试
python scripts/smoke/tender_e2e.py

# 2. 如果通过，可以提交
git add .
git commit -m "your changes"
git push

# 3. 如果失败，不要提交！先修复问题
```

## CI/CD 集成

建议在 CI/CD 流程中加入 Smoke 测试：

```yaml
# .github/workflows/smoke.yml
name: Smoke Tests
on: [push, pull_request]
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Start services
        run: docker compose up -d --build
      - name: Run smoke tests
        run: python scripts/smoke/tender_e2e.py
```

## 重要提醒

⚠️ **本 Smoke 测试是闸门测试**

- 不修改任何业务逻辑
- 只验证现有功能
- 必须在每次重大改动后运行
- 失败则不能进入下一步开发

## 更多信息

详细文档请参考：[scripts/smoke/README.md](scripts/smoke/README.md)

---

**创建日期**: 2025-12-19  
**版本**: 1.0.0  
**维护**: 开发团队




