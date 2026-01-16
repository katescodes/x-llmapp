# 🚀 范本插入功能修复 - 快速开始

## 问题现象

AI生成标书时，**没有将范本（投标函、授权委托书等格式文件）插入到标书正文中**。

## 快速解决（3步）

### 📋 步骤1：诊断问题

```bash
cd /aidata/x-llmapp1/backend
python scripts/fix_template_insertion.py --diagnose --all
```

### 🔧 步骤2：一键修复

```bash
python scripts/fix_template_insertion.py --fix --all
```

### 🔄 步骤3：重新生成目录

在前端界面：
1. 打开项目
2. 进入"步骤2：提取信息" → "投标目录"
3. 点击"生成目录"按钮

## ✅ 验证成功

生成完成后，在"步骤3：AI生成标书"中：
- 点击"投标函"、"授权委托书"等节点
- 应该能看到自动填充的范本内容

## 📖 详细文档

完整的问题分析、解决方案和技术细节，请查看：
- [完整修复指南](/aidata/x-llmapp1/docs/FIX_TEMPLATE_INSERTION.md)

## 💡 提示

- ✅ 新上传的文档会自动识别范本，无需手动操作
- ✅ 修复脚本可以重复运行，不会重复标记
- ✅ 只有旧项目需要运行修复脚本

## ❓ 问题反馈

如果修复后仍有问题，请查看日志：
```bash
tail -f /app/tender_service_debug.log
```

或查看完整文档中的"常见问题"章节。

