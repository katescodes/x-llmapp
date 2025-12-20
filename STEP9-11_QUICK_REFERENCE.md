# Step 9-11 快速参考指南

## Step 9: Docker 验证（make verify-docker）

### 目的
确保 CI 脚本和测试在 Docker 环境中正确运行。

### 快速验证
```bash
cd /aidata/x-llmapp1

# 清理旧报告
make clean-reports

# 运行 Docker 验证
make verify-docker
```

### 预期结果
```
Step 1: 启动 Docker Compose 服务... ✓
Step 2: 等待 Backend 就绪... ✓
Step 3: 运行边界检查... ✓
Step 4: 运行 pytest（关键测试）... ✓
  - test_tender_outline_imports.py ✓
  - test_newonly_never_writes_kb.py ✓
Step 5: 运行完整验收... ✓

✓ Docker 验证通过！
```

### 故障排查
如果失败，日志会自动导出到：
- `reports/verify/docker_backend.log`
- `reports/verify/docker_worker.log`
- `reports/verify/docker_postgres.log`
- `reports/verify/docker_redis.log`

---

## Step 10: Smoke 测试优化

### 目的
让 smoke 测试可按步骤运行，避免超时。

### 快速运行（推荐 - 跳过 export）
```bash
cd /aidata/x-llmapp1

# Gate4 建议配置
SMOKE_STEPS=upload,project_info,risks,outline,review \
  python scripts/smoke/tender_e2e.py
```

### 完整运行
```bash
# 所有步骤
python scripts/smoke/tender_e2e.py

# 自定义超时
SMOKE_TIMEOUT=900 python scripts/smoke/tender_e2e.py
```

### 门槛版测试（最快）
```bash
# NEW_ONLY gate 测试
python scripts/smoke/tender_newonly_gate.py
```

### 可用步骤
- `upload` - 上传招标文件
- `project_info` - 提取项目信息
- `risks` - 提取风险
- `outline` - 生成目录
- `autofill` - 自动填充样例
- `upload_bid` - 上传投标文件
- `review` - 运行审查
- `export` - 导出 DOCX（最慢，可跳过）

### 环境变量
```bash
BASE_URL=http://localhost:9001      # Backend URL
SMOKE_STEPS=upload,project_info     # 步骤过滤
SMOKE_TIMEOUT=600                   # 超时（秒）
SKIP_OPTIONAL=true                  # 跳过可选步骤
```

---

## Step 11A: Legacy API 验证

### 目的
确保旧接口已被隔离，默认不可访问。

### 快速验证
```bash
cd /aidata/x-llmapp1
bash verify_step11a.sh
```

### 预期结果
```
✓ Legacy endpoint 返回 404（不可访问）
✓ 新接口 /api/apps/tender/projects 可访问（返回 200）
✓ docker-compose.yml 正确设置 LEGACY_TENDER_APIS_ENABLED=false
```

### 手动测试

**测试 1: Legacy endpoint 应该 404**
```bash
curl -I http://localhost:9001/api/apps/tender/_legacy/projects/test/documents

# 预期: HTTP/1.1 404 Not Found
```

**测试 2: 新接口应该可访问**
```bash
# 登录
TOKEN=$(curl -s -X POST http://localhost:9001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 访问新接口
curl -I -H "Authorization: Bearer $TOKEN" \
  http://localhost:9001/api/apps/tender/projects

# 预期: HTTP/1.1 200 OK
```

### 启用 Legacy APIs（不推荐）
```bash
# 1. 修改 docker-compose.yml
#    将 LEGACY_TENDER_APIS_ENABLED=false 改为 true

# 2. 重启服务
docker-compose restart backend

# 3. 验证 legacy endpoint 可访问
curl -I http://localhost:9001/api/apps/tender/_legacy/projects/test/documents
# 现在应该返回 200/405 而不是 404
```

---

## 综合验证流程

### 完整验证（推荐顺序）

```bash
cd /aidata/x-llmapp1

# 1. Step 8: LLM 可追踪性
curl -s http://localhost:9001/api/_debug/llm/ping | python3 -m json.tool

# 2. Step 9: Docker 验证
make clean-reports
make verify-docker

# 3. Step 10: Smoke 测试（门槛版）
python scripts/smoke/tender_newonly_gate.py

# 4. Step 11A: Legacy API 隔离
bash verify_step11a.sh
```

### CI/CD 集成建议

```yaml
# GitHub Actions / GitLab CI 示例
steps:
  - name: Docker Verification
    run: make verify-docker
    timeout-minutes: 10
  
  - name: Smoke Test (Fast)
    run: |
      SMOKE_STEPS=upload,project_info,risks,outline,review \
      SMOKE_TIMEOUT=600 \
      python scripts/smoke/tender_e2e.py
    timeout-minutes: 15
  
  - name: Legacy API Check
    run: bash verify_step11a.sh
    timeout-minutes: 2
```

---

## 故障排查速查表

### Docker 验证失败

**问题**: Backend 未就绪
```bash
# 检查日志
docker-compose logs backend --tail=100

# 检查服务状态
docker-compose ps

# 重启服务
docker-compose restart backend
```

**问题**: pytest 失败
```bash
# 查看详细 pytest 输出
docker-compose exec backend pytest -v /repo/backend/tests/test_tender_outline_imports.py

# 检查路径映射
docker-compose exec backend ls -la /repo/backend/tests/
```

### Smoke 测试超时

**解决方案 1**: 使用步骤过滤
```bash
# 跳过 export（最慢的步骤）
SMOKE_STEPS=upload,project_info,risks,outline,review python scripts/smoke/tender_e2e.py
```

**解决方案 2**: 增加超时
```bash
SMOKE_TIMEOUT=900 python scripts/smoke/tender_e2e.py
```

**解决方案 3**: 使用门槛版测试
```bash
python scripts/smoke/tender_newonly_gate.py
```

### Legacy API 意外可访问

**检查配置**:
```bash
# 检查环境变量
docker-compose exec backend printenv | grep LEGACY

# 检查 docker-compose.yml
grep LEGACY_TENDER_APIS_ENABLED docker-compose.yml

# 确保设置为 false
docker-compose down
# 修改 docker-compose.yml: LEGACY_TENDER_APIS_ENABLED=false
docker-compose up -d
```

---

## 性能基准

### 预期耗时（参考）

| 测试项 | 耗时 | 说明 |
|--------|------|------|
| LLM Ping | <2s | MOCK 模式更快 |
| Docker Verification | ~2-5min | 包含启动时间 |
| Smoke Gate (快速) | ~2-3min | 跳过 export |
| Smoke 完整 | ~5-8min | 包含 export |
| Legacy API Check | <10s | 简单 HTTP 测试 |

### 优化建议

1. **并行运行**:  不同 gate 可以并行（如果资源足够）
2. **缓存 Docker 镜像**: 减少构建时间
3. **使用 MOCK_LLM**: 开发时加快测试速度
4. **步骤过滤**: 只测试修改相关的部分

---

## 相关文档

- `STEP8_COMPLETION_SUMMARY.md` - Step 8 LLM 追踪性
- `STEP9-11_COMPLETION_SUMMARY.md` - Step 9-11 详细总结
- `reports/verify/STEP7_DOCKER_VERIFICATION_SUMMARY.md` - Step 7 验证报告
- `reports/verify/STEP8_LLM_VERIFICATION_REPORT.md` - Step 8 验证报告

---

**最后更新**: 2025-12-20  
**维护人**: AI Assistant (Claude Sonnet 4.5)

