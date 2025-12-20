# Smoke 测试快速开始

## 一键运行

\`\`\`bash
# 1. 启动服务
docker compose up -d --build

# 2. 运行测试
python scripts/smoke/tender_e2e.py
\`\`\`

## 预期结果

✅ 成功：
\`\`\`
============================================================
  ✓ 所有测试通过！
============================================================
\`\`\`

❌ 失败：查看错误日志，修复问题后重试

## 详细文档

- [完整文档](SMOKE_TEST.md)
- [详细说明](scripts/smoke/README.md)

## 环境要求

- Docker & Docker Compose
- Python 3.x
- 已配置 LLM 服务

## 常用命令

\`\`\`bash
# 跳过可选步骤（快速测试）
SKIP_OPTIONAL=true python scripts/smoke/tender_e2e.py

# 保留测试项目（调试用）
KEEP_PROJECT=true python scripts/smoke/tender_e2e.py

# 使用 pytest
cd backend && pytest -m smoke
\`\`\`
