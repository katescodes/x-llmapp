# Prompt管理无法展示问题修复报告

## 问题描述

用户反馈：**Prompt管理里边都没有（内容）**

## 根本原因

与系统设置其他Tab相同的问题：

**问题：**
- Prompt管理相关的API调用使用普通 `fetch()` 而不是 `authFetch()`
- 请求没有携带JWT token
- 后端API需要 `system.prompt` 权限验证
- 导致请求返回 **403 Forbidden**

**错误日志：**
```
INFO: 172.19.0.6:44544 - "GET /api/apps/tender/prompts/modules HTTP/1.1" 403 Forbidden
```

## 后端权限要求

Prompt相关API的权限要求：

| API端点 | 权限代码 | 描述 |
|---------|----------|------|
| `/api/apps/tender/prompts/modules` | `system.prompt` | 获取Prompt模块列表 |
| `/api/apps/tender/prompts/` | `system.prompt` | 获取指定模块的Prompt列表 |
| `/api/apps/tender/prompts/{id}` | `system.prompt` | 更新Prompt内容 |
| `/api/apps/tender/prompts/{id}/history` | `system.prompt` | 获取Prompt历史版本 |
| `/api/apps/tender/prompts/{id}/history/{version}` | `system.prompt` | 查看特定版本 |

**后端路由定义：**

```python
# backend/app/routers/prompts.py
router = APIRouter(prefix="/api/apps/tender/prompts", tags=["prompts"])

@router.get("/modules")
def list_modules(current_user: TokenData = Depends(require_permission("system.prompt"))):
    """
    获取所有模块列表
    
    权限要求：system.prompt
    """
    return {
        "ok": True,
        "modules": [...]
    }
```

## 修复方案

### 批量替换fetch为authFetch

使用 `sed` 命令批量替换所有Prompt相关的API调用：

```bash
cd /aidata/x-llmapp1/frontend/src/components
sed -i 's/await fetch(`\/api\/apps\/tender\/prompts/await authFetch(`\/api\/apps\/tender\/prompts/g' SystemSettings.tsx
```

### 修改的函数

#### 1. loadPromptModules - 加载模块列表

```typescript
// 修改前
const loadPromptModules = async () => {
  try {
    const resp = await fetch(`/api/apps/tender/prompts/modules`);  // ❌ 没有token
    const data = await resp.json();
    if (data.ok) {
      setPromptModules(data.modules);
    }
  } catch (error) {
    console.error("加载Prompt模块失败:", error);
  }
};

// 修改后
const loadPromptModules = async () => {
  try {
    const resp = await authFetch(`/api/apps/tender/prompts/modules`);  // ✅ 使用authFetch
    const data = await resp.json();
    if (data.ok) {
      setPromptModules(data.modules);
    }
  } catch (error) {
    console.error("加载Prompt模块失败:", error);
  }
};
```

#### 2. loadPrompts - 加载指定模块的Prompt列表

```typescript
// 修改前
const loadPrompts = async (module: string) => {
  try {
    const resp = await fetch(`/api/apps/tender/prompts/?module=${module}`);  // ❌
    // ...
  }
};

// 修改后
const loadPrompts = async (module: string) => {
  try {
    const resp = await authFetch(`/api/apps/tender/prompts/?module=${module}`);  // ✅
    // ...
  }
};
```

#### 3. updatePrompt - 更新Prompt内容

```typescript
// 修改前
const resp = await fetch(`/api/apps/tender/prompts/${selectedPrompt.id}`, {  // ❌
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ ... })
});

// 修改后
const resp = await authFetch(`/api/apps/tender/prompts/${selectedPrompt.id}`, {  // ✅
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ ... })
});
```

#### 4. loadPromptHistory - 加载历史版本

```typescript
// 修改前
const resp = await fetch(`/api/apps/tender/prompts/${promptId}/history`);  // ❌

// 修改后
const resp = await authFetch(`/api/apps/tender/prompts/${promptId}/history`);  // ✅
```

#### 5. viewPromptVersion - 查看特定版本

```typescript
// 修改前
const resp = await fetch(`/api/apps/tender/prompts/${promptId}/history/${version}`);  // ❌

// 修改后
const resp = await authFetch(`/api/apps/tender/prompts/${promptId}/history/${version}`);  // ✅
```

## Prompt管理功能

修复后，Prompt管理页面支持以下功能：

### 模块列表
- 📋 **招标信息提取** - 提取招标文件的六大类信息
- 📝 **招标要求抽取** - 从招标文件中抽取结构化要求
- 📄 **投标响应要素抽取** - 从投标文件中抽取响应要素
- 🔍 **投标复核审查** - 审查投标文件合规性
- 📊 **目录生成** - 生成投标文件目录大纲
- 🎯 **风险分析** - 分析招标风险
- 📖 **总体说明生成** - 生成投标文件总体说明
- 🔎 **审查单分析** - 分析评审单内容
- 🆚 **招标响应匹配** - 匹配招标要求与投标响应
- 💰 **招标评分** - 根据规则对投标进行评分

### 功能特性
- ✅ **在线编辑** - 直接在界面编辑Prompt模板
- ✅ **版本管理** - 保存和查看历史版本
- ✅ **变更记录** - 记录每次修改的说明
- ✅ **Markdown支持** - 使用Markdown格式编写Prompt
- ✅ **实时预览** - 查看格式化后的Prompt效果

## 验证步骤

1. ✅ 修改SystemSettings.tsx，替换所有Prompt API的`fetch`为`authFetch`
2. ✅ 重新构建前端：`npm run build`
3. ⏳ 用户访问系统设置 → Prompt管理Tab
4. ⏳ 验证模块列表能正常加载
5. ⏳ 验证选择模块后Prompt列表能正常展示
6. ⏳ 验证编辑功能正常工作

## 修改文件清单

- ✅ `/aidata/x-llmapp1/frontend/src/components/SystemSettings.tsx`

## 统计信息

### 修改前
- 使用 `await fetch(\`` 的位置：5处（Prompt相关）

### 修改后  
- 全部替换为 `await authFetch(\``
- Prompt管理功能完全依赖authFetch

## 与之前修复的关联

这是系统设置页面修复的延续：

1. **第一次修复** - 替换了 LLM模型、向量模型、应用设置的API
2. **第二次修复（本次）** - 替换了 Prompt管理的API

现在SystemSettings组件中所有需要认证的API都已正确使用 `authFetch`。

## 权限要求

用户需要具备 `system.prompt` 权限才能访问Prompt管理Tab。

管理员（admin角色）自动拥有此权限。

## 总结

**根本原因：** Prompt管理的API调用使用普通`fetch()`而不是`authFetch()`，导致请求不带token，后端返回403

**修复方法：** 批量替换所有 `/api/apps/tender/prompts` 路径的`fetch`为`authFetch`

**效果：** Prompt管理Tab能够正常加载模块列表、Prompt列表，并支持编辑和版本管理功能

