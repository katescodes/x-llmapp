# Prompt数据库加载功能 - 修复报告

## ❌ 问题诊断

### 原始问题
用户报告："项目信息开始抽取：抽取失败: Error: 权限不足"

初步判断为token过期，但进一步检查发现更深层的问题：**Prompt一直从文件加载，数据库中的修改不生效**。

### 根本原因

`backend/app/services/prompt_loader.py` 存在两个致命bug：

#### Bug 1: 数据库API不匹配
```python
# ❌ 错误：使用 asyncpg 的API
async with self.pool.acquire() as conn:
    row = await conn.fetchrow(...)

# ✅ 正确：使用 psycopg 的API
with self.pool.connection() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (module,))
        row = cur.fetchone()
```

**原因**：项目使用的是 `psycopg` (同步库)，而不是 `asyncpg` (异步库)

#### Bug 2: 查询字段名错误
```python
# ❌ 错误：查询 module_id 字段
WHERE module_id = %s

# ✅ 正确：查询 module 字段
WHERE module = %s
```

**原因**：数据库表 `prompt_templates` 的字段名是 `module`，不是 `module_id`

### 影响
- ❌ 所有prompt都从文件fallback加载
- ❌ 数据库中的prompt修改不生效
- ❌ 用户在界面编辑prompt后，系统仍使用旧文件
- ❌ 没有明确的日志说明prompt来源

---

## ✅ 修复内容

### 1. backend/app/services/prompt_loader.py

#### 修复内容
```python
from psycopg.rows import dict_row  # ✅ 新增导入

async def get_active_prompt(self, module: str) -> Optional[str]:
    query = """
        SELECT content 
        FROM prompt_templates 
        WHERE module = %s AND is_active = TRUE  # ✅ 字段改为 module
        ORDER BY version DESC 
        LIMIT 1
    """
    
    try:
        # ✅ 使用 psycopg 同步API
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (module,))
                row = cur.fetchone()
    
        if row:
            content = row["content"]
            # ✅ 新增详细日志
            logger.info(f"✅ [PromptLoader] Loaded prompt for module '{module}' from DATABASE, length={len(content)}")
            print(f"✅ [PromptLoader] Loaded prompt for module '{module}' from DATABASE, length={len(content)}")
            return content
        else:
            logger.warning(f"⚠️ [PromptLoader] No active prompt found for module '{module}' in database")
            print(f"⚠️ [PromptLoader] No active prompt found for module '{module}' in database")
            return None
    except Exception as e:
        logger.error(f"❌ [PromptLoader] Error loading prompt for module '{module}': {e}", exc_info=True)
        print(f"❌ [PromptLoader] Error loading prompt for module '{module}': {e}")
        return None
```

#### 关键改进
- ✅ API从 `asyncpg` 改为 `psycopg`
- ✅ 字段从 `module_id` 改为 `module`
- ✅ 添加详细日志（logger + print）
- ✅ 添加异常捕获和错误处理
- ✅ 显示prompt长度信息

### 2. backend/app/works/tender/extraction_specs/project_info_v2.py

#### 修复内容
```python
async def build_project_info_spec_async(pool=None) -> ExtractionSpec:
    import logging
    logger = logging.getLogger(__name__)
    
    # 尝试从数据库加载prompt
    prompt = None
    if pool:
        try:
            from app.services.prompt_loader import PromptLoaderService
            loader = PromptLoaderService(pool)
            prompt = await loader.get_active_prompt("project_info")
            if prompt:
                # ✅ 新增成功日志
                logger.info(f"✅ [Prompt] Loaded from DATABASE for project_info, length={len(prompt)}")
                print(f"✅ [Prompt] Loaded from DATABASE for project_info, length={len(prompt)}")
        except Exception as e:
            # ✅ 新增错误日志
            logger.warning(f"⚠️ [Prompt] Failed to load from database: {e}")
            print(f"⚠️ [Prompt] Failed to load from database: {e}")
    
    # Fallback：从文件加载
    if not prompt:
        prompt = _load_prompt("project_info_v2.md")
        # ✅ 新增fallback日志
        logger.info(f"📁 [Prompt] Using FALLBACK (file) for project_info, length={len(prompt)}")
        print(f"📁 [Prompt] Using FALLBACK (file) for project_info, length={len(prompt)}")
```

#### 关键改进
- ✅ 添加详细日志，明确标识数据库/文件来源
- ✅ 添加prompt长度信息
- ✅ 添加异常捕获和日志

---

## 📊 数据库状态验证

### 当前数据库中的prompt

```sql
SELECT id, module, name, version, is_active, LENGTH(content) as content_length, updated_at
FROM prompt_templates
WHERE module = 'project_info'
ORDER BY version DESC;
```

**查询结果**：
```
           id           |    module    |      name       | version | is_active | content_length |         updated_at         
------------------------+--------------+-----------------+---------+-----------+----------------+----------------------------
 prompt_project_info_v2 | project_info | 项目信息提取 v2 |       3 | t         |           7521 | 2025-12-25 12:37:23.799509
```

✅ 确认：
- 模块: `project_info`
- 版本: `v3`
- 状态: `激活 (is_active=true)`
- 大小: `7521 字节`
- 更新时间: `2025-12-25 12:37:23`

---

## 🧪 测试步骤

### 步骤1：清除浏览器缓存并重新登录

解决"权限不足"错误：

1. 访问 http://localhost:3000
2. 按 **F12** 打开控制台
3. 在Console执行：
   ```javascript
   localStorage.clear(); location.reload();
   ```
4. 登录：`admin` / `admin123`

### 步骤2：监控后端日志（新开终端）

```bash
docker logs -f localgpt-backend 2>&1 | grep -E "Prompt|PromptLoader"
```

### 步骤3：执行项目信息抽取

1. 进入"测试"项目
2. 点击"开始抽取"按钮

### 步骤4：查看日志输出

#### 预期日志（从数据库加载）✅
```
✅ [PromptLoader] Loaded prompt for module 'project_info' from DATABASE, length=7521
✅ [Prompt] Loaded from DATABASE for project_info, length=7521
```

#### 如果看到fallback日志 ⚠️
```
⚠️ [PromptLoader] No active prompt found for module 'project_info' in database
📁 [Prompt] Using FALLBACK (file) for project_info, length=xxxxx
```
说明数据库连接有问题，需要检查连接池配置。

#### 如果看到错误日志 ❌
```
❌ [PromptLoader] Error loading prompt for module 'project_info': xxxxx
```
说明SQL查询或字段有问题。

---

## 🔄 验证prompt修改生效流程

### 完整测试流程

1. **在系统设置中修改prompt**
   - 访问：系统设置 → Prompt管理 → 项目信息提取
   - 修改内容（例如：添加一行注释）
   - 点击"保存"

2. **验证数据库更新**
   ```bash
   docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
   SELECT version, LENGTH(content), updated_at
   FROM prompt_templates
   WHERE module = 'project_info' AND is_active = TRUE
   ORDER BY version DESC LIMIT 1;
   "
   ```
   应该看到版本号+1（v4）

3. **重新执行抽取**
   - 再次点击"开始抽取"
   - 查看日志确认使用新版本

4. **验证结果**
   - 检查抽取结果是否按新prompt执行
   - 查看基本信息、技术参数、商务条款的变化

---

## 📋 核心代码对比

### prompt_loader.py

#### ❌ 修复前（Bug代码）
```python
async def get_active_prompt(self, module: str) -> Optional[str]:
    # 错误1：使用 asyncpg API
    async with self.pool.acquire() as conn:
        # 错误2：字段名错误
        row = await conn.fetchrow(
            "SELECT content FROM prompt_templates WHERE module_id = $1 AND is_active = TRUE ...",
            module
        )
    
    if row:
        # 错误3：缺少详细日志
        logger.info(f"Loaded prompt for module '{module}' from database")
        return row["content"]
    else:
        logger.warning(f"No active prompt found for module '{module}'")
        return None
```

#### ✅ 修复后（正确代码）
```python
async def get_active_prompt(self, module: str) -> Optional[str]:
    query = """
        SELECT content 
        FROM prompt_templates 
        WHERE module = %s AND is_active = TRUE 
        ORDER BY version DESC 
        LIMIT 1
    """
    
    try:
        # 正确1：使用 psycopg API
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # 正确2：字段名为 module，使用 %s 占位符
                cur.execute(query, (module,))
                row = cur.fetchone()
    
        if row:
            content = row["content"]
            # 正确3：详细日志，包含长度
            logger.info(f"✅ [PromptLoader] Loaded prompt for module '{module}' from DATABASE, length={len(content)}")
            print(f"✅ [PromptLoader] Loaded prompt for module '{module}' from DATABASE, length={len(content)}")
            return content
        else:
            logger.warning(f"⚠️ [PromptLoader] No active prompt found for module '{module}' in database")
            print(f"⚠️ [PromptLoader] No active prompt found for module '{module}' in database")
            return None
    except Exception as e:
        # 正确4：异常捕获和错误日志
        logger.error(f"❌ [PromptLoader] Error loading prompt for module '{module}': {e}", exc_info=True)
        print(f"❌ [PromptLoader] Error loading prompt for module '{module}': {e}")
        return None
```

---

## 🎯 预期效果

### 修复前 ❌
- Prompt一直从文件加载
- 用户界面修改prompt不生效
- 无法知道prompt来源
- 每次修改prompt需要更新代码文件并重启

### 修复后 ✅
- ✅ Prompt从数据库加载
- ✅ 用户界面修改prompt立即生效
- ✅ 日志明确显示prompt来源和版本
- ✅ 支持prompt在线编辑，无需重启
- ✅ 支持prompt版本管理和回滚
- ✅ 如果数据库连接失败，自动fallback到文件

---

## 🔍 故障排查指南

### 问题1: 日志显示"No active prompt found"

**可能原因**：
- 数据库中该模块的prompt不存在
- prompt的`is_active`字段为`false`

**解决方案**：
```bash
# 检查数据库
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT * FROM prompt_templates WHERE module = 'project_info';
"

# 如果不存在，从界面创建
# 如果is_active=false，更新为true：
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
UPDATE prompt_templates SET is_active = TRUE WHERE module = 'project_info';
"
```

### 问题2: 日志显示"Error loading prompt"

**可能原因**：
- 数据库连接池配置错误
- SQL语法错误
- 权限问题

**解决方案**：
```bash
# 检查后端日志
docker logs localgpt-backend --tail 100 | grep -A 5 "Error loading prompt"

# 检查数据库连接
docker exec localgpt-backend python -c "
from app.services.db.postgres import _get_pool
pool = _get_pool()
with pool.connection() as conn:
    print('✅ Database connection OK')
"
```

### 问题3: 修改prompt后不生效

**可能原因**：
- 新版本的`is_active`未设置为`true`
- 旧版本仍然是`active`

**解决方案**：
```bash
# 查看所有版本
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT id, version, is_active, updated_at 
FROM prompt_templates 
WHERE module = 'project_info' 
ORDER BY version DESC;
"

# 激活最新版本，停用旧版本
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
UPDATE prompt_templates SET is_active = FALSE WHERE module = 'project_info';
UPDATE prompt_templates 
SET is_active = TRUE 
WHERE module = 'project_info' AND version = (
    SELECT MAX(version) FROM prompt_templates WHERE module = 'project_info'
);
"
```

---

## 📝 总结

### 修复范围
- ✅ 修复了数据库API不匹配问题（asyncpg → psycopg）
- ✅ 修复了查询字段名错误（module_id → module）
- ✅ 增强了日志输出，明确标识prompt来源
- ✅ 添加了异常处理和错误日志
- ✅ 完善了fallback机制

### 影响范围
- ✅ 项目信息提取（project_info）
- ✅ 风险识别（risks）
- ✅ 目录生成（directory）
- ✅ 审核评估（review）
- ✅ 所有使用`PromptLoaderService`的模块

### 下一步建议
1. **测试所有模块**：依次测试risks、directory、review模块的prompt加载
2. **监控日志**：持续监控日志，确认所有prompt都从数据库加载
3. **压力测试**：在高并发场景下测试数据库连接池性能
4. **文档更新**：更新开发文档，说明prompt管理的最佳实践

---

**修复时间**：2025-12-25  
**修复人员**：AI Assistant  
**状态**：✅ 已完成，待用户测试验证  
**后端状态**：✅ 已重启

