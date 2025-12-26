# Prompt在线管理系统实施文档

## 功能概述

实现Prompt模板的在线管理，用户可以通过Web界面直接编辑和保存各个模块的提示词，修改后立即生效，无需重新部署程序。

### 核心功能
1. ✅ **在线编辑**：Web界面直接编辑Markdown格式的Prompt
2. ✅ **版本管理**：自动保存历史版本，支持回溯
3. ✅ **即时生效**：保存后下次提取时自动使用最新版本
4. ✅ **Fallback机制**：数据库无数据时自动使用文件版本
5. ✅ **多模块支持**：项目信息、风险识别、目录生成、审核评估

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│           前端 - Prompt管理页面                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 模块选择     │  │ 版本列表     │  │ 编辑器       │ │
│  │ (4个模块)    │  │ (历史版本)   │  │ (Markdown)   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              API - /api/apps/tender/prompts             │
│  GET /modules    GET /    GET /{id}    PUT /{id}       │
│  GET /{id}/history    GET /{id}/history/{version}      │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│           数据库 - prompt_templates表                    │
│  id, module, name, description, content, version        │
│                                                          │
│           数据库 - prompt_history表                      │
│  id, prompt_id, content, version, change_note           │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│         PromptLoaderService - 加载服务                   │
│  get_active_prompt(module) → 最新Prompt                │
│  get_prompt_with_fallback() → 数据库 or 文件            │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│         ExtractionEngine - 提取引擎                      │
│  使用最新Prompt执行信息提取                             │
└─────────────────────────────────────────────────────────┘
```

---

## 数据库设计

### 表1：prompt_templates（Prompt模板表）
```sql
CREATE TABLE prompt_templates (
    id TEXT PRIMARY KEY,                 -- prompt_project_info_v2
    module TEXT NOT NULL,                -- project_info, risks, directory, review
    name TEXT NOT NULL,                  -- 项目信息提取 v2
    description TEXT,                    -- 描述
    content TEXT NOT NULL,               -- Prompt内容（Markdown）
    version INT DEFAULT 1,               -- 当前版本号
    is_active BOOLEAN DEFAULT TRUE,      -- 是否激活
    created_by TEXT,
    updated_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 表2：prompt_history（变更历史表）
```sql
CREATE TABLE prompt_history (
    id TEXT PRIMARY KEY,                 -- hist_xxx
    prompt_id TEXT NOT NULL,             -- 关联的prompt_templates.id
    content TEXT NOT NULL,               -- 历史版本内容
    version INT NOT NULL,                -- 版本号
    changed_by TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_note TEXT,                    -- 变更说明
    FOREIGN KEY (prompt_id) REFERENCES prompt_templates(id)
);
```

---

## API接口

### 1. 获取模块列表
```http
GET /api/apps/tender/prompts/modules
```

**响应**：
```json
{
  "ok": true,
  "modules": [
    {
      "id": "project_info",
      "name": "项目信息提取",
      "description": "提取项目基本信息、技术参数、商务条款、评分标准",
      "icon": "📋"
    },
    {
      "id": "risks",
      "name": "风险识别",
      "description": "识别招标文件中的法律、技术、商务、合规风险",
      "icon": "⚠️"
    },
    {
      "id": "directory",
      "name": "目录生成",
      "description": "自动生成投标文件语义大纲和章节结构",
      "icon": "📑"
    },
    {
      "id": "review",
      "name": "审核评估",
      "description": "对投标文件进行合规性和完整性审核",
      "icon": "✓"
    }
  ]
}
```

### 2. 获取Prompt列表
```http
GET /api/apps/tender/prompts/?module=project_info&active_only=true
```

**响应**：
```json
{
  "ok": true,
  "prompts": [
    {
      "id": "prompt_project_info_v2",
      "module": "project_info",
      "name": "项目信息提取 v2",
      "description": "提取项目基本信息、技术参数...",
      "content": "# 项目信息抽取提示词...",
      "version": 3,
      "is_active": true,
      "created_at": "2025-12-25T10:00:00Z",
      "updated_at": "2025-12-25T12:00:00Z"
    }
  ]
}
```

### 3. 获取Prompt详情
```http
GET /api/apps/tender/prompts/{prompt_id}
```

### 4. 更新Prompt
```http
PUT /api/apps/tender/prompts/{prompt_id}
```

**请求体**：
```json
{
  "content": "# 更新后的Prompt内容...",
  "change_note": "修改提取逻辑，增加XX字段"
}
```

**响应**：
```json
{
  "ok": true,
  "message": "Prompt updated",
  "version": 4
}
```

### 5. 查看历史版本
```http
GET /api/apps/tender/prompts/{prompt_id}/history
```

**响应**：
```json
{
  "ok": true,
  "history": [
    {
      "id": "hist_xxx",
      "version": 3,
      "change_note": "修改XX逻辑",
      "changed_at": "2025-12-25T11:00:00Z"
    },
    {
      "id": "hist_yyy",
      "version": 2,
      "change_note": "添加YY字段",
      "changed_at": "2025-12-24T15:00:00Z"
    }
  ]
}
```

### 6. 获取指定版本
```http
GET /api/apps/tender/prompts/{prompt_id}/history/{version}
```

---

## 部署步骤

### 步骤1：执行数据库迁移
```bash
cd /aidata/x-llmapp1
docker exec localgpt-postgres psql -U localgpt -d localgpt -f /aidata/x-llmapp1/backend/migrations/027_prompt_templates.sql
```

### 步骤2：初始化Prompt数据
```bash
cd /aidata/x-llmapp1/backend
docker exec localgpt-backend python /app/scripts/init_prompts.py
```

**这个脚本会**：
- 读取现有的4个prompt文件（project_info_v2.md, risks_v2.md, directory_v2.md, review_v2.md）
- 将内容导入到`prompt_templates`表中
- 设置初始版本为v1

### 步骤3：重新部署后端和前端
```bash
cd /aidata/x-llmapp1
docker-compose build backend frontend
docker-compose up -d --no-deps backend frontend
```

### 步骤4：访问Prompt管理页面
```
http://localhost:3000/prompt-management
```

---

## 使用流程

### 用户操作流程
```
1. 登录系统
   ↓
2. 进入"Prompt管理"页面
   ↓
3. 选择模块（如"项目信息提取"）
   ↓
4. 点击"编辑"按钮
   ↓
5. 修改Prompt内容（Markdown格式）
   ↓
6. 填写变更说明（如"增加XX字段提取"）
   ↓
7. 点击"保存"
   ↓
8. 系统自动创建新版本（v2 → v3）
   ↓
9. 下次点击"开始提取"时，自动使用最新版本
```

### 系统执行流程
```
用户点击"开始提取"
  ↓
后端调用extract_project_info_v2()
  ↓
build_project_info_spec_async(pool)
  ↓
PromptLoaderService.get_active_prompt("project_info")
  ↓
查询数据库：SELECT content FROM prompt_templates 
            WHERE module='project_info' AND is_active=TRUE
  ↓
找到最新版本 → 使用数据库内容
找不到 → 使用文件fallback (project_info_v2.md)
  ↓
ExtractionEngine.run(spec)
  ↓
调用LLM，使用最新Prompt进行提取
```

---

## 文件清单

### 后端文件

#### 1. 数据库迁移
- `backend/migrations/027_prompt_templates.sql` ✅
  - 创建`prompt_templates`表
  - 创建`prompt_history`表
  - 创建索引

#### 2. API路由
- `backend/app/routers/prompts.py` ✅
  - GET /modules - 模块列表
  - GET / - Prompt列表
  - GET /{id} - Prompt详情
  - PUT /{id} - 更新Prompt
  - GET /{id}/history - 历史版本
  - GET /{id}/history/{version} - 指定版本

#### 3. 服务层
- `backend/app/services/prompt_loader.py` ✅
  - `PromptLoaderService.get_active_prompt(module)` - 从数据库加载
  - `PromptLoaderService.get_prompt_with_fallback()` - 带fallback的加载

#### 4. 提取规格修改
- `backend/app/works/tender/extraction_specs/project_info_v2.py` ✅
  - 新增`build_project_info_spec_async(pool)` - 异步版本，支持数据库加载
  - 保留`build_project_info_spec()` - 同步版本，向后兼容

#### 5. 提取服务修改
- `backend/app/works/tender/extract_v2_service.py` ✅
  - 修改`extract_project_info_v2()`使用异步spec构建器

#### 6. 初始化脚本
- `backend/scripts/init_prompts.py` ✅
  - 从文件读取现有Prompt
  - 导入到数据库

#### 7. 主应用修改
- `backend/app/main.py` ✅
  - 注册`prompts.router`

### 前端文件

#### 1. Prompt管理页面
- `frontend/src/components/PromptManagementPage.tsx` ✅
  - 模块选择
  - Prompt列表
  - 编辑器（textarea with Markdown）
  - 版本历史
  - 保存/取消/查看历史

---

## 核心代码示例

### PromptLoader加载逻辑
```python
# backend/app/services/prompt_loader.py
class PromptLoaderService:
    async def get_active_prompt(self, module: str) -> Optional[str]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT content
                FROM prompt_templates
                WHERE module = $1 AND is_active = TRUE
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                module
            )
        
        if row:
            logger.info(f"Loaded prompt for '{module}' from database")
            return row["content"]
        else:
            logger.warning(f"No prompt found for '{module}'")
            return None
```

### Spec构建逻辑
```python
# backend/app/works/tender/extraction_specs/project_info_v2.py
async def build_project_info_spec_async(pool=None) -> ExtractionSpec:
    # 尝试从数据库加载
    prompt = None
    if pool:
        try:
            loader = PromptLoaderService(pool)
            prompt = await loader.get_active_prompt("project_info")
        except Exception as e:
            print(f"Failed to load from DB: {e}")
    
    # Fallback：从文件加载
    if not prompt:
        prompt = _load_prompt("project_info_v2.md")
    
    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=50,
        topk_total=200,
    )
```

### 提取服务调用
```python
# backend/app/works/tender/extract_v2_service.py
async def extract_project_info_v2(self, project_id: str, ...):
    # 使用异步版本，支持数据库加载
    spec = await build_project_info_spec_async(self.pool)
    
    result = await self.engine.run(
        spec=spec,
        retriever=self.retriever,
        llm=self.llm,
        project_id=project_id,
        ...
    )
    
    return result
```

---

## 扩展其他模块

当前已实现`project_info`模块，要扩展其他模块（risks, directory, review），只需：

### 步骤1：创建异步spec构建器
```python
# backend/app/works/tender/extraction_specs/risks_v2.py
async def build_risks_spec_async(pool=None) -> ExtractionSpec:
    prompt = None
    if pool:
        try:
            loader = PromptLoaderService(pool)
            prompt = await loader.get_active_prompt("risks")
        except:
            pass
    
    if not prompt:
        prompt = _load_prompt("risks_v2.md")
    
    return ExtractionSpec(prompt=prompt, queries=..., ...)
```

### 步骤2：修改服务调用
```python
# backend/app/works/tender/extract_v2_service.py
async def extract_risks_v2(self, ...):
    spec = await build_risks_spec_async(self.pool)  # 使用异步版本
    result = await self.engine.run(spec=spec, ...)
    return result
```

### 步骤3：初始化数据
```python
# backend/scripts/init_prompts.py
# 已包含risks, directory, review的初始化逻辑
```

---

## 测试验证

### 测试1：编辑Prompt
1. 访问 http://localhost:3000/prompt-management
2. 选择"项目信息提取"
3. 点击"编辑"
4. 在content末尾添加测试文字：`<!-- 测试修改 -->`
5. 填写变更说明："测试功能"
6. 点击"保存"
7. 验证版本号增加（v1 → v2）

### 测试2：Prompt生效
1. 进入一个项目
2. 点击"重新提取基本信息"
3. 查看后端日志：
```
[INFO] Loaded prompt for 'project_info' from database
[INFO] ExtractV2: extract_project_info start project_id=xxx
```
4. 确认使用了数据库中的Prompt

### 测试3：历史版本
1. 点击"查看历史"
2. 看到版本列表（v1, v2, ...）
3. 点击某个历史版本
4. 确认可以加载到编辑器

### 测试4：Fallback机制
1. 清空数据库中的prompt_templates表
2. 重新提取信息
3. 查看日志：
```
[WARN] No prompt found for 'project_info'
[INFO] Using fallback prompt for module 'project_info'
```
4. 确认使用了文件版本

---

## 优势

### 1. 无需部署
- ✅ 修改Prompt不需要重启服务
- ✅ 不需要编辑服务器上的文件
- ✅ 不需要Docker重新构建

### 2. 版本管理
- ✅ 自动保存每次修改
- ✅ 可以随时回滚到历史版本
- ✅ 有变更说明，便于追溯

### 3. 安全性
- ✅ 支持变更审批（可扩展）
- ✅ 有操作日志
- ✅ 可以设置权限控制

### 4. 灵活性
- ✅ 支持多模块独立管理
- ✅ 支持A/B测试（可扩展）
- ✅ 支持不同项目使用不同Prompt（可扩展）

---

## 注意事项

### 1. 数据库备份
- 定期备份`prompt_templates`表
- 防止误删重要Prompt

### 2. Markdown格式
- 确保用户编辑时保持Markdown格式正确
- 可以添加格式验证（future）

### 3. 性能优化
- 当前每次提取都查询数据库
- 可以添加Redis缓存（future）

### 4. 权限控制
- 当前所有用户都可以编辑
- 可以添加角色权限（future）

---

## 未来扩展

### 1. Prompt测试
- 在线测试Prompt效果
- 不影响生产环境

### 2. A/B测试
- 同时运行多个版本
- 比较效果差异

### 3. 自动优化
- 根据提取结果自动优化Prompt
- 使用强化学习

### 4. 多租户
- 不同客户使用不同Prompt
- 隔离数据

---

**实施日期**：2025-12-25  
**实施状态**：✅ 设计完成，等待部署  
**下一步**：执行部署步骤

