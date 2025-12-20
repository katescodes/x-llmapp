# 格式模板 Smoke Test 使用说明

## 快速开始

### 1. 准备测试模板

准备一个包含 Logo/页眉的 Word 文档（.docx）：

```bash
# 示例：使用项目中已有的模板
export TEMPLATE_FILE=/path/to/your/template.docx
```

**模板要求**：
- 必须是 `.docx` 格式（不支持 `.doc`）
- 建议包含页眉、Logo、页脚（用于验证保留效果）
- 建议包含多级标题样式（h1-h3）

### 2. 配置环境变量

```bash
# API 地址（默认 http://localhost:8000）
export API_BASE=http://localhost:8000

# 认证 Token
export AUTH_TOKEN=your_jwt_token

# 测试模板文件路径
export TEMPLATE_FILE=./test_template.docx
```

### 3. 运行测试

```bash
cd /aidata/x-llmapp1
./backend/scripts/smoke_format_templates.sh
```

### 4. 查看结果

测试完成后，输出文件位于：

```
/tmp/format_templates_smoke_test/
├── template_preview.pdf      # 模板原始预览（验证模板完整性）
├── project_preview.pdf        # 项目套用后预览（验证 PDF 转换）
├── project_export.docx        # 项目导出 DOCX（验证页眉 Logo）
└── apply_response.json        # API 响应（验证 URL 正确性）
```

---

## 测试步骤详解

### Step 0: 检查模板文件
- 验证 `$TEMPLATE_FILE` 存在
- 确认文件格式为 `.docx`

### Step 1: 创建测试项目
- 调用 `POST /api/apps/tender/projects`
- 如果失败，尝试获取现有项目

### Step 2: 上传格式模板
- 调用 `POST /api/apps/tender/format-templates`
- multipart/form-data 上传文件
- 验证返回 `template_id`

### Step 3: 获取模板预览 (PDF)
- 调用 `GET /api/apps/tender/format-templates/{id}/preview?format=pdf`
- 下载到 `template_preview.pdf`
- **人工验证**：确认 Logo/页眉存在

### Step 4: 套用格式模板 (JSON)
- 调用 `POST /api/apps/tender/projects/{id}/directory/apply-format-template?return_type=json`
- 验证返回 `ok: true`
- 验证返回 `preview_pdf_url` 和 `download_docx_url`

### Step 5: 下载预览 PDF
- 访问 `preview_pdf_url`
- 下载到 `project_preview.pdf`
- **人工验证**：确认页眉、Logo、内容完整性

### Step 6: 下载 DOCX
- 访问 `download_docx_url`
- 下载到 `project_export.docx`
- **自动检查**：
  - 文件可打开
  - 包含 `word/header` 部分
  - 包含 `word/media/` 部分（Logo）
- **人工验证**：确认页眉 Logo 存在

---

## 验收标准

### ✅ 自动验证
- [x] 所有 API 调用返回 2xx
- [x] `apply-format-template` 返回 `ok: true`
- [x] 返回的 URL 可访问（HTTP 200）
- [x] 下载的文件非空
- [x] DOCX 内部包含 `word/header` 和 `word/media/`

### ✅ 人工验证
- [ ] `template_preview.pdf` - 模板原始 Logo 存在
- [ ] `project_preview.pdf` - 套用后 Logo 存在
- [ ] `project_export.docx` - 打开后页眉 Logo 存在
- [ ] 文档样式与模板一致

---

## 故障排查

### 问题 1: `command not found: soffice`

**原因**：Docker 容器内未安装 LibreOffice

**解决**：
```bash
docker exec -it backend bash
apt update && apt install -y libreoffice-writer
```

或修改 `Dockerfile`：
```dockerfile
RUN apt-get update && apt-get install -y \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*
```

### 问题 2: PDF 下载失败 (HTTP 500)

**原因**：PDF 转换失败

**检查日志**：
```bash
docker logs backend | grep -i "pdf\|soffice"
```

**可能原因**：
- LibreOffice 未安装
- DOCX 格式损坏
- 磁盘空间不足

### 问题 3: DOCX 页眉 Logo 丢失

**检查点**：

1. 验证模板原始文件：
```bash
unzip -l $TEMPLATE_FILE | grep word/header
unzip -l $TEMPLATE_FILE | grep word/media
```

2. 验证存储的模板：
```bash
docker exec backend ls -lh /app/storage/tender/format_templates/
docker exec backend unzip -l /app/storage/tender/format_templates/xxx.docx | grep word/header
```

3. 检查代码是否重写了模板：
```bash
# 应该找不到任何 Document().save() 覆盖模板文件的代码
grep -rn "Document().save" backend/app/works/tender/format_templates/
```

### 问题 4: 认证失败 (HTTP 401)

**原因**：`AUTH_TOKEN` 无效或过期

**解决**：

1. 获取新 Token：
```bash
# 如果有登录接口
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' \
  | jq -r .access_token
```

2. 或临时禁用认证（仅用于测试）：
```python
# backend/app/routers/format_templates.py
# 注释掉 user=Depends(get_current_user_sync)
```

---

## 高级用法

### 清理测试数据

默认情况下，测试不会删除创建的项目和模板。如需自动清理：

```bash
CLEANUP=yes ./backend/scripts/smoke_format_templates.sh
```

### 批量测试多个模板

```bash
for template in templates/*.docx; do
  echo "Testing $template..."
  TEMPLATE_FILE="$template" ./backend/scripts/smoke_format_templates.sh
done
```

### 并发测试（压力测试）

```bash
# 并发10个请求
seq 10 | xargs -P10 -I{} ./backend/scripts/smoke_format_templates.sh
```

### 保存测试报告

```bash
./backend/scripts/smoke_format_templates.sh 2>&1 | tee /tmp/smoke_test_report.log
```

---

## CI/CD 集成

### GitHub Actions 示例

```yaml
name: Smoke Test - Format Templates

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: testdb
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Install LibreOffice
        run: |
          sudo apt-get update
          sudo apt-get install -y libreoffice-writer
      
      - name: Build Docker images
        run: docker-compose build
      
      - name: Start services
        run: docker-compose up -d
      
      - name: Wait for backend
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:8000/health; do sleep 2; done'
      
      - name: Run smoke test
        env:
          TEMPLATE_FILE: ./tests/fixtures/test_template.docx
          AUTH_TOKEN: ${{ secrets.TEST_AUTH_TOKEN }}
        run: ./backend/scripts/smoke_format_templates.sh
      
      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: smoke-test-results
          path: /tmp/format_templates_smoke_test/
```

---

## 相关文档

- [格式模板功能修复总结](../../docs/FORMAT_TEMPLATES_FIX_SUMMARY.md)
- [格式模板缺口分析](../../docs/FORMAT_TEMPLATES_GAP.md)
- [API 文档](../../docs/API.md)

---

## 联系支持

如遇到问题，请提供以下信息：

1. 测试日志：`/tmp/format_templates_smoke_test/*.log`
2. API 响应：`/tmp/format_templates_smoke_test/apply_response.json`
3. Docker 日志：`docker logs backend`
4. 环境信息：`docker --version`, `python --version`

