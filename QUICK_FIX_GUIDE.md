# 🛠️ 范本提取问题 - 快速解决指南

**问题**: 点击"生成目录"后，提示"未抽取到范本"  
**影响**: 目录节点无法自动填充格式文档

---

## ⚡ 快速解决（3步）

### Step 1: 检查招标书文档

**打开招标书DOCX，按 `Ctrl+F` 搜索**:
```
"投标文件格式"
"投标文件样表"
"附件"
```

**找到后，尝试复制里面的文字**:
- ✅ **能复制** → 文档格式正常，继续Step 2
- ❌ **不能复制** → 文档是扫描件，需要OCR转换

---

### Step 2: 使用诊断工具

```bash
cd /aidata/x-llmapp1
./diagnose_fragments.sh
```

**查看输出，重点关注**:
```
upserted_fragments: 0    ← ❌ 这个应该 > 0
warnings: ["未能抽取到范本片段"]  ← 查看具体警告
```

---

### Step 3: 应用解决方案

根据诊断结果：

#### 情况A: 文档是扫描件（不能复制文字）

**解决方案**: 使用OCR转换

1. **使用WPS Office**（推荐）:
   ```
   打开PDF → 特色功能 → PDF转Word → OCR识别
   ```

2. **使用在线工具**:
   - https://www.ilovepdf.com/zh-cn/ocr-pdf
   - https://smallpdf.com/cn/pdf-to-word

3. **转换后重新上传**

---

#### 情况B: 找不到"投标文件格式"章节

**解决方案**: 确认招标书完整性

1. 检查是否上传了完整文件
2. 有些招标书将格式文档单独成册
3. 尝试搜索其他关键词：
   ```
   "响应文件格式"
   "投标文件组成"
   "表格样表"
   ```

---

#### 情况C: 能复制文字，但未提取到

**解决方案**: 使用内置范本库（系统自动）

**说明**:
- 系统会自动使用内置范本库作为兜底
- 包含8种常见格式：投标函、授权书、报价表等
- 虽然不是项目特定，但保证基本功能可用

**验证**:
```bash
# 查看是否启用了内置范本库
docker-compose logs backend | grep "使用内置范本库"
```

---

## 📊 当前状态检查

### 快速诊断命令

```bash
# 方法1: 使用诊断脚本
./diagnose_fragments.sh

# 方法2: 手动查看日志
docker-compose logs backend | grep -E "auto_fill_samples|upserted_fragments" | tail -30
```

### 关键指标

| 指标 | 期望值 | 说明 |
|------|--------|------|
| `upserted_fragments` | > 0 | 实际入库的范本数 |
| `attached_sections` | > 0 | 填充的目录节点数 |
| `llm_used` | true | 是否使用LLM增强定位 |
| `warnings` | [] | 警告信息（应为空）|

---

## 🔧 高级解决方案

### 方案1: 查看详细日志

```bash
cd /aidata/x-llmapp1

# 1. 查看最近的auto_fill_samples执行
docker-compose logs backend | grep -A 50 "auto_fill_samples" | tail -100

# 2. 查看范本提取器日志
docker-compose logs backend | grep "extractor" | tail -50

# 3. 查看LLM定位日志
docker-compose logs backend | grep "llm spans" | tail -20
```

---

### 方案2: 重新触发提取

**前端操作**:
1. 进入项目
2. 点击"自动填充范本"按钮
3. 观察提示信息

**预期结果**:
```
✅ 成功: "本次抽取 12 条范本（库内共 12 条），挂载 18 个章节"
❌ 失败: "未能抽取到范本片段，已使用内置范本库"
```

---

### 方案3: 手动验证文档

**步骤**:
1. 打开招标书DOCX
2. 找到"投标文件格式"章节
3. 检查以下内容：
   - [ ] 标题清晰可见
   - [ ] 包含格式表格（投标函、授权书等）
   - [ ] 文字可以复制
   - [ ] 表格结构完整

4. 如果以上都满足，但仍未提取到：
   - 可能是标题格式不标准
   - 可能需要启用LLM增强定位

---

## 💡 预防措施

### 上传招标书时

**建议**:
1. ✅ 使用可编辑的DOCX（不是PDF扫描件）
2. ✅ 确保文件完整（包含"投标文件格式"章节）
3. ✅ 文字可复制（不是图片）
4. ✅ 标题清晰（使用Heading样式更佳）

**检查清单**:
```
□ 文件格式: DOCX ✓
□ 可复制文字: 是 ✓
□ 包含格式章节: 是 ✓
□ 文件大小: < 50MB ✓
```

---

## 📞 需要帮助？

### 提供以下信息

如果问题仍未解决，请提供：

1. **招标书信息**:
   - 文件名
   - 文件大小
   - 是否能复制文字

2. **诊断日志**:
   ```bash
   ./diagnose_fragments.sh > diagnosis.log
   ```
   提供 `diagnosis.log` 文件

3. **问题描述**:
   - 期望：能提取到XX个范本
   - 实际：提取到0个
   - "投标文件格式"章节位置：第XX页

---

## 📚 相关文档

- 📖 **详细诊断指南**: `FRAGMENT_EXTRACTION_TROUBLESHOOTING.md`
- 📖 **功能增强报告**: `AUTO_FILL_ENHANCEMENT_IMPLEMENTATION.md`
- 📖 **测试指南**: `TESTING_GUIDE.md`

---

## ✅ 问题解决确认

**问题解决后，验证**:

```bash
# 1. 查看提取数量
docker-compose logs backend | grep "upserted_fragments" | tail -5

# 预期输出（示例）:
# "upserted_fragments": 12,    ← ✅ > 0

# 2. 查看填充数量
docker-compose logs backend | grep "attached_sections" | tail -5

# 预期输出（示例）:
# "attached_sections": 18,     ← ✅ > 0
```

**前端验证**:
- 点击目录节点，查看是否有正文内容
- 部分节点应显示"已填充"标识

---

**文档版本**: v1.0  
**更新时间**: 2025-12-25  
**适用场景**: 范本提取失败的快速诊断与解决

