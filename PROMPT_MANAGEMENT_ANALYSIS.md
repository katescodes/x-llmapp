# Prompt 管理功能使用情况分析报告

## 📊 数据库中的 Prompt 模板

当前数据库中有 **11 个 Prompt 模板**，分属 5 个模块：

| 模块 | 名称 | 版本 | 激活状态 | 内容长度 |
|------|------|------|----------|----------|
| **bid_response** | 投标响应要素抽取 V1 | 1 | ❌ 未激活 | 4,191 |
| **bid_response** | 投标响应要素抽取 V2 | 4 | ❌ 未激活 | 3,925 |
| **bid_response** | 投标响应要素抽取 V5 (norm_key版本) | 5 | ✅ **激活** | 6,660 |
| **directory** | 目录生成 v3（智能生成版）| 6 | ✅ **激活** | 4,426 |
| **project_info** | 招标信息提取 V3 | 2 | ✅ **激活** | 6,820 |
| **project_info** | 项目信息抽取v10（评分表优化）| 10 | ❌ 未激活 | 9,119 |
| **project_info** | 项目信息抽取v8(优化) | 9 | ❌ 未激活 | 9,121 |
| **project_info** | 项目信息提取（四阶段）| 7 | ❌ 未激活 | 11,625 |
| **requirements** | 招标要求抽取 V1 | 2 | ❌ 未激活 | 3,281 |
| **requirements** | 招标要求抽取 V3 (norm_key版本) | 3 | ✅ **激活** | 5,907 |
| **review** | 审核评估 v2 | 3 | ✅ **激活** | 1,322 |

---

## 🔍 实际使用情况分析

### ✅ **正在使用的模块（1 个）**

#### 1. **directory** 目录生成 ✅

**使用位置**：`backend/app/works/tender/schemas/directory_v2.py`

```python
# 第 62-96 行
async def build_directory_spec_async(pool=None) -> ExtractionSpec:
    """构建目录生成抽取规格（异步版本，从数据库加载）"""
    
    # 从数据库加载Prompt模板
    loader = PromptLoaderService(pool)
    prompt = await loader.get_active_prompt("directory")  # ✅ 从数据库加载
    
    if not prompt:
        raise PromptNotFoundError("directory")
```

**使用流程**：
1. 用户在前端点击"生成目录"
2. 后端调用 `build_directory_spec_async()`
3. 从数据库加载激活的 `directory` prompt
4. 使用 LLM 生成投标文件目录

**结论**：✅ **正在使用，有效！**

---

### ❌ **未使用的模块（4 个）**

#### 2. **project_info** 项目信息提取 ❌

**数据库状态**：有激活的 prompt（"招标信息提取 V3"）

**实际代码**：使用硬编码的 Checklist 配置文件

```python
# backend/app/works/tender/project_info_extractor.py

class ProjectInfoExtractor:
    def __init__(self, llm, checklist_path: Optional[str] = None):
        # 默认路径：硬编码的 YAML 文件
        self.checklist_path = Path(__file__).parent / "checklists" / "project_info_v1.yaml"
        
        # 加载配置
        self.config = self._load_checklist()  # ❌ 从 YAML 文件加载，不是数据库
```

**Checklist 文件**：`backend/app/works/tender/checklists/project_info_v1.yaml`（526 行）

**Prompt 构建**：
```python
# backend/app/works/tender/project_info_prompt_builder.py

class ProjectInfoPromptBuilder:
    def build_p0_prompt(self, context_text, context_info):
        # 基于 checklist 配置动态构建 prompt
        # ❌ 不使用数据库的 prompt_templates
```

**结论**：❌ **未使用数据库 prompt，使用 YAML checklist + 动态构建**

---

#### 3. **requirements** 招标要求提取 ❌

**数据库状态**：有激活的 prompt（"招标要求抽取 V3 (norm_key版本)"）

**实际代码**：使用硬编码的 `FrameworkPromptBuilder`

```python
# backend/app/works/tender/extract_v2_service.py

async def extract_requirements_v2(self, ...):
    # 使用框架式Prompt Builder
    from .framework_prompt_builder import FrameworkPromptBuilder
    
    prompt_builder = FrameworkPromptBuilder()  # ❌ 硬编码的类
    
    # 构建Prompt
    prompt = prompt_builder.build_prompt(context_text)  # ❌ 动态构建，不从数据库加载
```

**Prompt 构建**：
```python
# backend/app/works/tender/framework_prompt_builder.py

class FrameworkPromptBuilder:
    def build_prompt(self, tender_context: str) -> str:
        """构建框架式提取prompt"""
        # 包含大量硬编码的 prompt 模板
        # ❌ 不使用数据库
```

**结论**：❌ **未使用数据库 prompt，使用硬编码的 FrameworkPromptBuilder**

---

#### 4. **bid_response** 投标响应提取 ❌

**数据库状态**：有激活的 prompt（"投标响应要素抽取 V5 (norm_key版本)"）

**实际代码**：使用硬编码的 `FrameworkBidResponseExtractor`

```python
# backend/app/works/tender/framework_bid_response_extractor.py

class FrameworkBidResponseExtractor:
    def build_extraction_prompt(self, dimension, requirements, bid_context):
        """构建维度级提取prompt"""
        
        # 维度说明（硬编码）
        dimension_desc = {
            "price": "价格维度 - 投标报价、费用明细、价格计算",
            "qualification": "资质维度 - 企业资质、人员资格、业绩要求",
            # ...
        }
        
        # 构建大量硬编码的 prompt 文本
        prompt = f"""# 任务：投标响应提取（{dim_desc}）
        
        ## 目标
        从投标文档中提取**所有对应该维度招标要求的响应内容**。
        ...
        """
        
        # ❌ 不使用数据库
        return prompt
```

**结论**：❌ **未使用数据库 prompt，使用硬编码的类方法构建**

---

#### 5. **review** 审核评估 ❌

**数据库状态**：有激活的 prompt（"审核评估 v2"）

**实际代码**：使用 `FrameworkBidResponseExtractor` 一体化提取+审核

```python
# backend/app/works/tender/unified_audit_service.py

class UnifiedAuditService:
    async def run_unified_audit(self, ...):
        # 使用 FrameworkBidResponseExtractor
        extractor = FrameworkBidResponseExtractor(self.llm, self.retriever)
        
        # 提取投标响应（prompt 硬编码在 extractor 中）
        responses = await extractor.extract_all_responses(...)
        
        # ❌ 不使用数据库的 review prompt
```

**结论**：❌ **未使用数据库 prompt，审核逻辑集成在响应提取中**

---

## 📋 总结表

| 模块 | 数据库状态 | 实际使用情况 | 替代方案 |
|------|-----------|-------------|----------|
| **directory** | ✅ 激活 | ✅ **正在使用** | - |
| **project_info** | ✅ 激活 | ❌ 未使用 | YAML checklist + 动态构建 |
| **requirements** | ✅ 激活 | ❌ 未使用 | FrameworkPromptBuilder 硬编码 |
| **bid_response** | ✅ 激活 | ❌ 未使用 | FrameworkBidResponseExtractor 硬编码 |
| **review** | ✅ 激活 | ❌ 未使用 | 集成在响应提取中 |

**使用率**：1/5 = **20%**

---

## 🎯 为什么不使用？

### 1. **架构演进**

系统经历了多次重构：
- **早期（v0.1-v0.2）**：使用数据库 prompt 管理
- **中期（v0.3-v0.4）**：引入 Checklist 框架（更灵活）
- **现在（v0.3.7+）**：使用 Checklist + 动态 Prompt 构建

### 2. **Checklist 方法的优势**

**项目信息提取**为什么使用 YAML checklist：
```yaml
# checklists/project_info_v1.yaml
stage_1:
  stage_name: "项目概览"
  checklist:
    - key: project_name
      label: "项目名称"
      required: true
    - key: bid_deadline
      label: "投标截止时间"
      required: true
```

**优点**：
- ✅ 结构化配置（字段定义 + 验证规则）
- ✅ 支持 P0/P1 两阶段提取
- ✅ 可编程处理（不只是文本）
- ✅ 版本控制在代码中（Git）

**数据库 Prompt 的局限**：
- ❌ 只能存储文本
- ❌ 不支持结构化配置
- ❌ 需要手动同步代码和 prompt

### 3. **动态构建的必要性**

**招标要求提取**为什么动态构建：
```python
# 需要根据上下文动态调整 prompt
def build_prompt(self, tender_context: str) -> str:
    # 1. 检测文档类型（工程/货物/服务）
    # 2. 根据类型调整提示词
    # 3. 嵌入实际的上下文文本
    # 4. 动态生成示例
    
    # 这些逻辑无法在静态 prompt 中实现
```

---

## 💡 建议

### 方案 1：保留 directory，清理其他（推荐）✅

**操作**：
1. ✅ 保留 `directory` 模块（正在使用）
2. ❌ 删除或标记为"已废弃"：
   - `project_info` 的 3 个 prompt
   - `requirements` 的 2 个 prompt
   - `bid_response` 的 3 个 prompt
   - `review` 的 1 个 prompt

**理由**：
- 避免混淆（数据库有 prompt，但实际不使用）
- 减少维护成本
- 清理历史遗留

**SQL 操作**：
```sql
-- 方案 A：删除（如果确认不需要）
DELETE FROM prompt_templates 
WHERE module IN ('project_info', 'requirements', 'bid_response', 'review');

-- 方案 B：标记为废弃（保留历史）
UPDATE prompt_templates 
SET is_active = false, 
    name = name || ' [已废弃-系统不再使用]'
WHERE module IN ('project_info', 'requirements', 'bid_response', 'review');
```

### 方案 2：迁移到数据库 Prompt（不推荐）❌

**工作量**：
1. 重构 `project_info` → 支持数据库 prompt
2. 重构 `requirements` → 支持数据库 prompt
3. 重构 `bid_response` → 支持数据库 prompt
4. 重构 `review` → 支持数据库 prompt

**问题**：
- ❌ 失去 Checklist 的结构化能力
- ❌ 失去动态构建的灵活性
- ❌ 大量重构工作（高风险）

### 方案 3：混合模式（当前状态）✅

**保持现状**：
- `directory` 使用数据库 prompt（适合纯文本 prompt）
- 其他功能使用 Checklist/动态构建（需要结构化配置）

**优点**：
- ✅ 各取所长
- ✅ 无需重构

**缺点**：
- ⚠️ 数据库中有无用的 prompt（造成混淆）

---

## 🛠️ 清理建议（推荐执行）

### 1. 标记废弃的 Prompt

```sql
-- 标记为废弃，但保留历史记录
UPDATE prompt_templates 
SET 
    is_active = false,
    name = name || ' [已废弃]',
    description = '此 Prompt 已不再使用，系统已切换到 Checklist 框架'
WHERE module IN ('project_info', 'requirements', 'bid_response', 'review');
```

### 2. 更新前端提示

在 `SystemSettings.tsx` 的 Prompt 管理 tab 中添加提示：

```tsx
{currentTab === 'prompts' && (
  <div className="alert alert-warning">
    ⚠️ <strong>注意</strong>：目前只有"目录生成"功能使用数据库 Prompt。
    其他功能（项目信息、招标要求、投标响应、审核）已切换到 Checklist 框架，
    不再使用此处的 Prompt 模板。
  </div>
)}
```

### 3. 清理数据库（可选）

如果确认不需要历史记录，可以直接删除：

```sql
DELETE FROM prompt_templates 
WHERE module IN ('project_info', 'requirements', 'bid_response', 'review');

DELETE FROM prompt_history
WHERE prompt_id IN (
    SELECT id FROM prompt_templates 
    WHERE module IN ('project_info', 'requirements', 'bid_response', 'review')
);
```

---

## 📊 最终结论

### ✅ 保留
- **directory** 模块的 Prompt 管理功能 → 正在使用，保持不变

### ❌ 废弃或删除
- **project_info** 模块 → 使用 YAML checklist
- **requirements** 模块 → 使用 FrameworkPromptBuilder
- **bid_response** 模块 → 使用 FrameworkBidResponseExtractor
- **review** 模块 → 集成在响应提取中

### 📝 建议操作
1. 执行 SQL 标记废弃的 prompt
2. 更新前端添加说明
3. 更新系统文档
4. 考虑是否删除无用数据

---

## 🔄 未来考虑

如果将来需要让其他功能支持数据库 Prompt，需要：

1. **设计混合架构**：
   - Prompt 模板存储在数据库（可编辑）
   - Checklist 配置存储在 YAML（结构化）
   - 运行时组合两者

2. **示例**：
   ```python
   # 从数据库加载基础 prompt
   base_prompt = await loader.get_active_prompt("project_info")
   
   # 从 YAML 加载 checklist
   checklist = load_checklist("project_info_v1.yaml")
   
   # 动态组合
   final_prompt = build_prompt(base_prompt, checklist, context)
   ```

但目前这个需求不明确，建议保持现状。

