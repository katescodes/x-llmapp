# 🔄 更新数据库中的 Prompt（九大类→六大类）

## ✅ **文件已更新**

- ✅ `backend/app/works/tender/prompts/project_info_v3.md`（六大类版本）
- ✅ `scripts/init_v3_prompts.sql`（描述已更新）
- ✅ `scripts/update_v3_prompt_to_db.py`（更新脚本）

---

## 📋 **需要执行的操作**

### **方法 1：通过前端 Prompt 管理界面更新（推荐）**

1. **打开前端应用**
   ```
   浏览器访问：http://localhost:3000
   ```

2. **进入系统设置**
   ```
   点击：系统设置 → Prompt 管理
   ```

3. **找到 project_info_v3 模块**
   ```
   搜索：project_info_v3
   ```

4. **编辑并替换内容**
   - 点击"编辑"按钮
   - 复制 `backend/app/works/tender/prompts/project_info_v3.md` 的全部内容
   - 粘贴到编辑框
   - 更新描述为："从招标文件中提取六大类结构化信息（项目概况【含范围、进度、保证金】、投标人资格、评审与评分、商务条款、技术要求、文件编制）"
   - 点击"保存"

5. **激活新版本**
   - 确保 `is_active` 为 `true`
   - 如果有旧版本，设置为不激活

---

### **方法 2：使用 SQL 脚本更新（快速）**

已生成好的 SQL 文件：`/tmp/update_v3_prompt_final.sql`

#### **执行步骤：**

```bash
# 方式 A：如果有 postgres 用户权限
psql -U postgres -d x-llmapp1 -f /tmp/update_v3_prompt_final.sql

# 方式 B：如果数据库不需要用户名
psql -d x-llmapp1 -f /tmp/update_v3_prompt_final.sql

# 方式 C：通过应用数据库连接
# 在应用后台执行 SQL
```

#### **验证更新成功：**

```sql
SELECT 
    id, 
    module, 
    name, 
    LENGTH(content) as content_length,
    is_active,
    updated_at
FROM prompt_templates 
WHERE module = 'project_info_v3';
```

**预期结果：**
```
id                          | prompt_project_info_v3_001
module                      | project_info_v3
name                        | 招标信息提取 V3（六大类）
content_length             | 6820
is_active                   | true
```

---

### **方法 3：使用 Python 脚本更新（如果环境支持）**

```bash
cd /aidata/x-llmapp1
python3 scripts/update_v3_prompt_to_db.py
```

**注意：** 需要确保 Python 环境中已安装 `psycopg_pool` 或 `psycopg2`。

---

## 🔍 **验证更新**

### **1. 检查数据库**

```sql
-- 查看 prompt 内容
SELECT 
    module,
    name,
    LEFT(content, 100) as content_preview,
    LENGTH(content) as length,
    is_active
FROM prompt_templates 
WHERE module = 'project_info_v3';
```

**检查点：**
- ✅ `name` 应包含"六大类"
- ✅ `content` 开头应为："# 项目信息抽取提示词 (v3 - 六大类)"
- ✅ `length` 应约为 6800 字符
- ✅ `is_active` 应为 `true`

---

### **2. 检查系统设置界面**

1. 打开前端 → 系统设置 → Prompt 管理
2. 找到 `project_info_v3`
3. 点击查看详情
4. 检查内容：
   - ✅ 标题显示"六大类"
   - ✅ 阶段说明显示 6 个 Stage
   - ✅ Stage 1 包含范围、进度、保证金字段

---

### **3. 测试抽取功能**

1. 打开招投标工作台
2. 选择一个项目
3. 点击"Step 1: 项目信息抽取" → "开始抽取"
4. 观察进度：
   - ✅ 显示 6 个阶段（不再是 9 个）
   - ✅ Stage 1: 项目概况
   - ✅ Stage 2: 投标人资格
   - ✅ Stage 3: 评审与评分
   - ✅ Stage 4: 商务条款
   - ✅ Stage 5: 技术要求
   - ✅ Stage 6: 文件编制
5. 抽取完成后检查结果：
   - ✅ 项目概况包含范围、进度、保证金数据
   - ✅ 显示"项目概况（含范围、进度、保证金）"

---

## 🚨 **常见问题**

### **Q1: 数据库连接失败**

**解决：**
- 检查数据库是否运行：`ps aux | grep postgres`
- 检查连接字符串：`postgresql://localhost/x-llmapp1`
- 尝试使用不同的用户名/密码

---

### **Q2: Prompt 管理界面找不到模块**

**原因：** 数据库中没有 `project_info_v3` 记录

**解决：**
1. 手动执行 SQL 脚本（方法2）
2. 或使用初始化脚本：
   ```bash
   psql -d x-llmapp1 -f scripts/init_v3_prompts.sql
   ```

---

### **Q3: 抽取时仍显示 9 个阶段**

**原因：** 
1. 后端未重启，仍使用旧的 prompt
2. 数据库中的 prompt 未更新

**解决：**
1. 确认数据库 prompt 已更新
2. **重启后端服务**
3. 清除浏览器缓存
4. 重新抽取

---

### **Q4: 抽取结果为空**

**原因：** LLM 可能不适应新的 prompt 格式

**解决：**
1. 检查后端日志：`tail -f backend/logs/app.log`
2. 查看是否有 LLM 调用错误
3. 验证 prompt 格式正确（JSON 示例）
4. 检查检索到的文档片段是否足够

---

## ✅ **完成清单**

- [ ] 数据库中的 prompt 已更新
- [ ] 系统设置界面显示六大类
- [ ] 后端服务已重启
- [ ] 测试抽取功能正常
- [ ] 项目概况包含完整数据（范围+进度+保证金）

---

## 📞 **需要帮助？**

如遇到问题，请检查：
1. `backend/logs/app.log` - 后端日志
2. 浏览器控制台 - 前端错误
3. 数据库日志 - SQL 执行情况

---

**文档更新时间：** 2025-12-26  
**相关提交：** ce4e1bc

