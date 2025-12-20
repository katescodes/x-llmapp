# 格式模板功能修复 - 快速指南

## 🎯 问题现状
- ✅ **已修复**：`GET /api/apps/tender/format-templates` 的 500 错误
- ✅ **已实现**：格式预览 GET 端点
- ✅ **已加固**：前端错误处理和 fallback 机制

## 🚀 快速验证

### 1. 确认后端已更新并重启

```bash
# 检查容器内的文件是否已更新
docker exec localgpt-backend grep -A 3 "def _get_pool" /app/app/routers/format_templates.py

# 应该看到：
# def _get_pool(request: Request) -> ConnectionPool:
#     """从 postgres 模块获取连接池"""
#     from app.services.db.postgres import _get_pool as get_sync_pool
#     return get_sync_pool()

# 如果不对，执行：
docker cp backend/app/routers/format_templates.py localgpt-backend:/app/app/routers/format_templates.py
docker restart localgpt-backend && sleep 5
```

### 2. 测试格式模板列表接口

```bash
# 使用有效的 token（从浏览器 F12 Network 中获取）
TOKEN="your_actual_token"

curl -X GET http://localhost:9001/api/apps/tender/format-templates \
  -H "Authorization: Bearer $TOKEN"

# 应该返回：[] 或模板列表
# 不应该返回：500 Internal Server Error
```

### 3. 前端测试

1. 刷新浏览器（Ctrl + Shift + R）
2. 打开 TenderWorkspace
3. 查看格式模板列表 - 应该正常加载
4. 如果没有模板，上传一个测试模板
5. 套用格式 - 应该显示成功 Toast
6. 切换到格式预览 Tab - 应该看到预览或友好提示

---

## 📋 完整功能清单

### ✅ 已实现
- [x] 模板原样保存（不重写 DOCX）
- [x] 导出使用模板母版（保留页眉页脚）
- [x] 格式预览 GET 端点
- [x] apply-format-template 返回 URL
- [x] PDF 转换（需 LibreOffice）
- [x] 前端 Fallback URL
- [x] 错误可视化（Toast）
- [x] 格式预览空状态
- [x] Smoke Test 脚本
- [x] 完整文档

### ⏳ 待用户验证
- [ ] 端到端流程：上传 → 套用 → 预览 → 下载
- [ ] DOCX 页眉 Logo 是否保留
- [ ] PDF 预览是否正常

---

## 🔧 常见问题

### Q1: 前端仍然报 500 错误

**A**: 清除浏览器缓存（Ctrl + Shift + R）并重启后端：

```bash
docker restart localgpt-backend
```

### Q2: PDF 预览失败

**A**: 检查 LibreOffice 是否已安装：

```bash
docker exec localgpt-backend which soffice

# 如未安装：
docker exec localgpt-backend apt update
docker exec localgpt-backend apt install -y libreoffice-writer
```

### Q3: DOCX 页眉 Logo 丢失

**A**: 验证模板文件是否原样保存：

```bash
# 进入容器
docker exec -it localgpt-backend bash

# 检查模板文件结构
unzip -l /app/storage/tender/format_templates/xxx.docx | grep word/header
unzip -l /app/storage/tender/format_templates/xxx.docx | grep word/media
```

### Q4: 格式预览 Tab 显示空白

**A**: 这是正常的空状态提示，点击"重新生成预览"按钮即可。

---

## 📚 详细文档

- [完整修复总结](./COMPLETE_FIX_SUMMARY.md) - 所有修改的汇总
- [后端修复详情](./FORMAT_TEMPLATES_FIX_SUMMARY.md) - 后端技术细节
- [前端兜底详情](./FRONTEND_FIX_SUMMARY.md) - 前端错误处理
- [Smoke Test 说明](../backend/scripts/README_SMOKE_TEST.md) - 自动化测试

---

## 🎯 下一步

1. **验证基本功能**
   ```bash
   # 运行 smoke test
   ./backend/scripts/smoke_format_templates.sh
   ```

2. **端到端测试**
   - 上传包含 Logo 的模板
   - 套用到项目
   - 查看预览
   - 下载 DOCX

3. **反馈问题**
   - 如果遇到问题，提供：
     * 浏览器控制台截图
     * 后端日志：`docker logs localgpt-backend --tail 100`
     * 重现步骤

---

## ✅ 验收检查清单

### 后端
- [ ] `GET /api/apps/tender/format-templates` 返回 200
- [ ] 上传模板成功（POST）
- [ ] 套用格式返回 `preview_pdf_url` 和 `download_docx_url`
- [ ] 格式预览端点可访问

### 前端
- [ ] 格式模板列表正常显示
- [ ] 套用格式成功提示（绿色 Toast）
- [ ] 格式预览 Tab 正常切换
- [ ] 错误提示清晰（红色 Toast + 详细信息）

### 文件完整性
- [ ] 模板文件包含 `word/header`
- [ ] 模板文件包含 `word/media`（Logo）
- [ ] 导出的 DOCX 包含页眉页脚
- [ ] PDF 预览正常显示

---

**修复完成时间**: 2025-12-21  
**修复状态**: ✅ 核心功能已实现，等待用户验证

