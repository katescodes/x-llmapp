# AI 自动生成申报书功能 - 快速参考

## 🎯 功能说明

点击前端"🤖 AI 生成申报书"按钮，系统会自动为空章节生成 1000-2500 字的专业内容。

## ✅ 已完成

- ✅ 3 个后端文件改造完成
- ✅ 默认启用自动生成
- ✅ 无需修改前端代码
- ✅ 立即可用

## 🚀 使用方式

### 前端操作

1. 登录系统
2. 创建/打开申报项目
3. 完成步骤 1-4（上传文件、生成目录等）
4. 进入步骤 5
5. **点击"🤖 AI 生成申报书"**
6. 等待生成完成（5-15 分钟）
7. 点击"📥 导出 DOCX"

### API 调用

```bash
# 生成（启用自动生成）
POST /api/apps/declare/projects/{id}/document/generate?sync=1

# 导出
GET /api/apps/declare/projects/{id}/export/docx
```

## 📊 效果

### 改造前
```
标题：项目建设背景
内容：（待补充）
```

### 改造后
```
标题：项目建设背景
内容：
随着制造业数字化转型的深入推进，传统生产管理模式...
（共 1200+ 字，8-12 段）
```

## 🔧 修改的文件

1. `backend/app/services/export/declare_docx_exporter.py`
2. `backend/app/services/declare_service.py`
3. `backend/app/routers/declare.py`

## 📈 性能

- 每个章节：15-25 秒
- 10 个章节：3-5 分钟
- 30 个章节：8-12 分钟

## ⚠️ 注意

1. 需要配置 LLM 模型
2. 生成内容是初稿，需人工审核
3. 【待补】处需补充具体数据

## 📚 详细文档

- **完整说明**：`docs/AI_GENERATE_IMPLEMENTATION_COMPLETE.md`
- **实现总结**：`FINAL_IMPLEMENTATION_SUMMARY.md`
- **集成对应**：`docs/INTEGRATION_WITH_AI_BUTTON.md`

## 🎉 立即体验

点击前端"🤖 AI 生成申报书"按钮，开始体验！


