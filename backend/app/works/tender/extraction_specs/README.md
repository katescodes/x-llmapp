# Extraction Specs - Prompt 加载策略

## 🎯 设计原则

**核心原则**：所有 `extraction_specs` 必须通过 **module 名称** 加载活跃的 prompt，而不是硬编码特定版本ID。

这样确保：
- ✅ 用户在系统设置中修改 prompt 后**立即生效**
- ✅ 版本号（如 v1、v2）只是文件名标识符，不影响实际加载逻辑
- ✅ 统一的 prompt 管理机制，便于维护

---

## 📋 统一的加载模式

### ✅ 正确的做法

```python
async def build_xxx_spec_async(pool=None) -> ExtractionSpec:
    """构建抽取规格"""
    if not pool:
        raise ValueError("pool参数是必需的，无法从数据库加载prompt")
    
    # ✅ 只通过 module 名称加载活跃版本
    from app.services.prompt_loader import PromptLoaderService
    loader = PromptLoaderService(pool)
    prompt = await loader.get_active_prompt("module_name")  # 使用 module 名称
    
    if not prompt:
        raise PromptNotFoundError("module_name")
    
    logger.info(f"✅ [Prompt] Loaded from DATABASE for module_name")
    
    return ExtractionSpec(
        prompt=prompt,
        queries={...},
        ...
    )
```

### ❌ 错误的做法

```python
# ❌ 不要硬编码 prompt ID
prompt = await loader.get_prompt_by_id("prompt_xxx_v2_001")

# ❌ 不要尝试多种加载方式（先ID后module）
try:
    prompt = await loader.get_prompt_by_id("prompt_xxx_v2_001")
except:
    prompt = await loader.get_active_prompt("xxx")
```

**为什么错误**：
- 即使用户在系统设置中修改了活跃 prompt
- 如果数据库中仍存在旧的固定ID版本
- 系统会优先使用旧版本，导致用户的修改不生效

---

## 📁 当前文件清单

| 文件名 | Module 名称 | 状态 | 说明 |
|--------|-------------|------|------|
| `bid_response_v2.py` | `bid_response` | ✅ 已修复 | 投标响应要素抽取 |
| `requirements_v1.py` | `requirements` | ✅ 正确 | 招标要求抽取 |
| `project_info_v2.py` | `project_info` | ✅ 正确 | 项目信息抽取 |
| `directory_v2.py` | `directory` | ✅ 正确 | 目录生成 |

---

## 🔧 Prompt 管理流程

### 1. 数据库表结构

```sql
-- prompt_templates 表
CREATE TABLE prompt_templates (
    id TEXT PRIMARY KEY,           -- 唯一ID（如 prompt_bid_response_v2_001）
    module TEXT NOT NULL,          -- 模块名称（如 bid_response）
    version INT DEFAULT 1,         -- 版本号
    is_active BOOLEAN DEFAULT TRUE,-- 是否活跃
    name TEXT,                     -- 显示名称
    description TEXT,              -- 描述
    content TEXT NOT NULL,         -- Prompt 内容
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 索引：快速查找活跃 prompt
CREATE INDEX idx_prompt_templates_module_active 
ON prompt_templates(module, is_active, version DESC);
```

### 2. 加载逻辑（PromptLoaderService）

```python
class PromptLoaderService:
    async def get_active_prompt(self, module: str) -> Optional[str]:
        """
        获取指定 module 的活跃 prompt
        
        查询规则：
        - WHERE module = ? AND is_active = true
        - ORDER BY version DESC
        - LIMIT 1
        
        这样确保：
        1. 只返回活跃的 prompt
        2. 如果有多个活跃版本，返回最新版本
        3. 用户在系统设置中修改 is_active 后立即生效
        """
        ...
```

### 3. 用户修改 Prompt 的流程

1. **系统管理 → Prompt 管理**
2. 找到对应的 module（如 `bid_response`）
3. 点击"编辑"修改 prompt 内容
4. 保存后，系统会：
   - 创建新的 prompt 记录（新版本号）
   - 将新版本设置为 `is_active=true`
   - 将旧版本设置为 `is_active=false`
5. **下次调用时自动使用新版本**

---

## 🚀 最佳实践

### 1. 新增 extraction spec 时

```python
# 步骤1: 在 prompt_templates 表中创建 prompt 记录
INSERT INTO prompt_templates (
    id, module, version, is_active, name, content
) VALUES (
    'prompt_new_feature_001',  -- ID 可以包含版本信息
    'new_feature',              -- ✅ module 名称是关键
    1,
    true,
    '新功能抽取 V1',
    '...'  -- prompt 内容
);

# 步骤2: 创建 extraction spec 文件
# backend/app/works/tender/extraction_specs/new_feature_v1.py

async def build_new_feature_spec_async(pool=None) -> ExtractionSpec:
    loader = PromptLoaderService(pool)
    prompt = await loader.get_active_prompt("new_feature")  # ✅ 使用 module 名称
    ...
```

### 2. 升级 extraction spec 时

```python
# 不需要修改代码！
# 只需要在数据库中：
# 1. 插入新版本的 prompt（version=2, is_active=true）
# 2. 将旧版本设置为 is_active=false

# extraction spec 代码保持不变，自动使用新版本
```

### 3. 回滚到旧版本时

```python
# 不需要修改代码！
# 只需要在数据库中：
# 1. 将新版本设置为 is_active=false
# 2. 将旧版本设置为 is_active=true

# extraction spec 代码保持不变，自动切换到旧版本
```

---

## ⚠️ 注意事项

1. **文件名中的版本号（v1、v2）只是标识符**
   - 文件名：`bid_response_v2.py`
   - Module名称：`bid_response`（没有 v2）
   - 加载代码：`get_active_prompt("bid_response")`

2. **一个 module 同时只能有一个活跃版本**
   - 数据库中可以保留多个版本的历史记录
   - 但只有一个 `is_active=true`
   - 系统自动选择活跃版本

3. **不要在代码中硬编码 prompt ID**
   - ❌ `get_prompt_by_id("prompt_bid_response_v2_001")`
   - ✅ `get_active_prompt("bid_response")`

4. **prompt 内容存储在数据库，不在代码文件中**
   - 代码只负责定义 queries、topk 等配置
   - prompt 内容由 PromptLoaderService 从数据库加载
   - 用户可以通过系统设置界面修改 prompt

---

## 📊 验证清单

在修改或新增 extraction spec 时，请确认：

- [ ] 使用 `get_active_prompt(module_name)` 加载 prompt
- [ ] 不使用 `get_prompt_by_id(...)` 硬编码ID
- [ ] module 名称与数据库 `prompt_templates.module` 一致
- [ ] 代码中不包含 prompt 内容文本
- [ ] 测试：在系统设置中修改 prompt 后，新版本生效

---

## 🎉 总结

**统一的 Prompt 管理策略**：
1. ✅ 代码通过 **module 名称** 加载
2. ✅ Prompt 内容存储在 **数据库**
3. ✅ 用户通过 **系统设置** 修改
4. ✅ 修改后 **立即生效**
5. ✅ 支持 **版本管理** 和 **回滚**

这样实现了代码与配置的分离，提升了系统的灵活性和可维护性。

