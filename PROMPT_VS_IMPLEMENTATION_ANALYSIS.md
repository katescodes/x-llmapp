# Prompt 提示词 vs 程序实现 - 深度分析

## 🔍 问题：Prompt 是否有误导？程序流程是否已固定？

**结论：❌ Prompt 存在误导！✅ 程序流程与 Prompt 描述不一致！**

---

## 📋 Prompt 描述的流程（来自 `project_info_v3.md`）

### Prompt 声称的工作方式：

```markdown
# 项目信息抽取提示词 (v3 - 九大类)

你是招投标助手。请从"招标文件原文片段"中抽取项目信息。

**重要：本次执行仅抽取 Stage {CURRENT_STAGE} 的内容，禁止输出其他 Stage 的内容。**

## 执行阶段说明

当前共分为九个执行阶段（Stage），每次调用只能执行一个阶段：

- **Stage 1**：项目概览（project_overview）
- **Stage 2**：范围与标段（scope_and_lots）
- **Stage 3**：进度与递交（schedule_and_submission）
...
```

**Prompt 给 LLM 的印象：**
- ✅ 每次只处理一个 Stage
- ✅ 会收到"招标文件原文片段"
- ❌ **误导：LLM 认为它会收到完整的招标文件片段**

---

## 🔧 实际程序实现（代码逻辑）

### 1. **文档处理流程**

```python
# backend/app/platform/ingest/v2_service.py

# Step 1: 解析文档
parsed_doc = await parse_document(filename, file_bytes)

# Step 2: 分块（固定大小，1200 字符/块，重叠 150 字符）
chunks = chunk_document(
    url=asset_id,
    title=parsed_doc.title,
    text=parsed_doc.text,
    target_chars=1200,  # 每块 1200 字符
    overlap_chars=150,  # 重叠 150 字符
)

# Step 3: 向量化并存储到 Milvus
```

**关键点：**
- ❌ **LLM 永远不会收到"完整的招标文件"**
- ✅ **LLM 只会收到检索后的相关片段（~1200 字符/片段）**

---

### 2. **项目信息抽取流程（九阶段）**

```python
# backend/app/works/tender/extract_v2_service.py

# 定义九个阶段和对应的查询关键词
stages = [
    {
        "num": 1,
        "name": "项目概览",
        "key": "project_overview",
        "query": "招标公告 项目名称 项目编号 采购人 招标人 业主 代理机构..."
    },
    {
        "num": 2,
        "name": "范围与标段",
        "key": "scope_and_lots",
        "query": "项目范围 采购内容 采购清单 标段 包段 分包..."
    },
    # ... 其余 7 个阶段
]

# 每个阶段执行：
for stage in stages:
    # Step 1: 根据查询关键词检索相关片段
    result = await self.engine.run(
        spec=spec,  # 包含 queries 和 prompt
        retriever=self.retriever,
        llm=self.llm,
        project_id=project_id,
        stage=stage_num,
        stage_name=stage_name,
    )
```

---

### 3. **ExtractionEngine 的实际检索逻辑**

```python
# backend/app/platform/extraction/engine.py

async def _retrieve_chunks(self, spec, retriever, project_id, ...):
    """
    根据 spec.queries（字典）分别检索
    """
    all_chunks = []
    chunk_id_set = set()
    
    # ⚠️ 关键：对每个查询分别执行向量检索
    for query_name, query_text in queries_dict.items():
        # 向量检索：根据语义相似度找到最相关的片段
        query_chunks = await retriever.retrieve(
            query=query_text,
            project_id=project_id,
            doc_types=["tender"],
            top_k=spec.topk_per_query,  # 默认 30 条
        )
        
        # 去重合并
        for chunk in query_chunks:
            if chunk.chunk_id not in chunk_id_set:
                all_chunks.append(chunk)
                chunk_id_set.add(chunk.chunk_id)
    
    return all_chunks
```

**实际配置：**

```python
# backend/app/works/tender/extraction_specs/project_info_v2.py

queries: Dict[str, str] = {
    # 1. 项目概览
    "project_overview": "招标公告 项目名称 项目编号 采购人 招标人 业主 代理机构 联系人 电话 项目地点 资金来源 采购方式 预算金额 招标控制价 最高限价 控制价",
    
    # 2. 范围与标段
    "scope_and_lots": "项目范围 采购内容 采购清单 标段 包段 分包 标段划分 标段预算 标段编号",
    
    # 3. 进度与递交
    "schedule_and_submission": "投标截止时间 投标文件递交截止时间 开标时间 开标当日 开标地点 递交方式 递交地点 线上投标 线下投标 工期 交付期 实施周期 里程碑",
    
    # ... 其余 6 个查询
}

# 检索参数
top_k_per_query = 30  # 每个查询返回 30 个片段
top_k_total = 150     # 总共最多 150 个片段（9 类 × 平均 17 条）
```

---

## 🚨 **核心矛盾：Prompt 的误导**

### ❌ **Prompt 说的（误导性）：**

> "你是招投标助手。请从'招标文件原文片段'中抽取项目信息。"

**LLM 的理解：**
- 我会收到完整的招标文件（或大段的原文片段）
- 我可以自由浏览和定位信息
- 我可以看到文档的整体结构

### ✅ **实际发生的（真实流程）：**

```
原始招标文件（300 页 PDF）
    ↓
【解析】→ 纯文本
    ↓
【分块】→ ~250 个片段（每片段 ~1200 字符）
    ↓
【向量化】→ 存储到 Milvus
    ↓
【抽取 Stage 1】
    ├─ 查询: "招标公告 项目名称 项目编号 采购人..."
    ├─ 向量检索: 找到最相关的 30 个片段
    ├─ 构建上下文:
    │   「CHUNK-abc123」
    │   第一章 投标人须知前附表
    │   1. 项目名称: XX市智慧城市平台建设项目
    │   ...
    │   「CHUNK-def456」
    │   招标人: XX市政府
    │   ...
    ├─ LLM 输入: Prompt + 这 30 个片段（约 36,000 字符）
    └─ LLM 输出: project_overview 的 JSON
```

**LLM 实际收到的：**
- ❌ **不是完整文件**
- ✅ **只是检索后的相关片段集合**
- ✅ **片段可能来自文档的不同位置**
- ✅ **片段是基于语义相似度排序的**

---

## 📊 **对比表格**

| 维度 | Prompt 描述 | 实际实现 | 一致性 |
|------|------------|---------|-------|
| **数据来源** | "招标文件原文片段" | 向量检索后的相关片段 | ❌ 不一致 |
| **片段完整性** | 暗示是连续的原文 | 分散的、去重的片段 | ❌ 不一致 |
| **片段选择** | 未说明如何选择 | 基于语义相似度 Top-K | ❌ 未说明 |
| **片段数量** | 未说明 | 每个 Stage 约 30-150 条 | ❌ 未说明 |
| **片段大小** | 未说明 | 固定 ~1200 字符/片段 | ❌ 未说明 |
| **分阶段执行** | 明确说明九个阶段 | 九个阶段 | ✅ 一致 |
| **每次只抽取一个 Stage** | 明确说明 | 是的 | ✅ 一致 |
| **输出格式** | JSON 结构 | JSON 结构 | ✅ 一致 |
| **证据链** | 要求填写 evidence_chunk_ids | 确实会返回 | ✅ 一致 |

---

## 🔍 **Prompt 应该如何修改？**

### **建议修改 1：明确说明数据来源**

**现有（误导性）：**
```markdown
你是招投标助手。请从"招标文件原文片段"中抽取项目信息。
```

**建议修改为：**
```markdown
你是招投标助手。请从"检索到的相关文档片段"中抽取项目信息。

**重要说明：**
- 你将收到若干个已分块的文档片段（每个片段约 1200 字符）
- 这些片段是通过语义相似度检索得到的，最相关的排在前面
- 片段可能来自招标文件的不同章节
- 每个片段都标记了 `<chunk id="xxx">` 作为唯一标识
- 请仔细阅读所有片段，提取相关信息
- **宁可少，不要错**：只提取有明确证据的信息
- **必须记录证据**：所有提取的信息都要填写 evidence_chunk_ids
```

---

### **建议修改 2：明确检索策略**

**新增章节：**
```markdown
## 📋 检索策略说明（供理解上下文）

系统会针对当前 Stage 执行语义检索：

### Stage 1: 项目概览
**检索关键词：** 招标公告、项目名称、项目编号、采购人、代理机构、联系人、预算金额、招标控制价

**预期片段来源：**
- 招标公告（封面）
- 第一章 投标人须知前附表
- 项目概况
- 采购需求

**检索数量：** Top 30 个最相关片段

### Stage 2: 范围与标段
**检索关键词：** 项目范围、采购内容、标段、包段、标段划分、标段预算

...（类似说明）
```

---

### **建议修改 3：调整抽取原则**

**现有：**
```markdown
### 抽取原则
1. **宁可少，不要错**：只抽取有明确证据的信息
2. **宁可空，不要猜**：没有证据的字段留空字符串
3. **仅引用权威位置**：招标公告 / 封面 / 项目概况等
4. **不要推断**：不要基于其他信息推断时间、金额等
5. **证据必须准确**：必须填写 evidence_chunk_ids
```

**建议修改为：**
```markdown
### 抽取原则
1. **宁可少，不要错**：只抽取有明确证据的信息
2. **宁可空，不要猜**：没有证据的字段留空字符串
3. **从检索片段中提取**：只从提供的片段中提取，不依赖外部知识
4. **跨片段综合**：相关信息可能分散在多个片段中，需要综合判断
5. **不要推断**：不要基于其他信息推断时间、金额等
6. **证据必须准确**：必须填写 evidence_chunk_ids（使用 <chunk id="xxx"> 中的 id）
7. **片段不完整时**：如果检索到的片段不包含某些信息，对应字段留空
```

---

## 🎯 **程序流程是否固定？**

### ✅ **是的，程序流程已高度固定：**

1. **文档分块大小固定**：1200 字符/块，重叠 150 字符
2. **检索策略固定**：Top-K 向量检索
3. **查询关键词固定**：九个 Stage 的查询词写死在代码中
4. **检索数量固定**：每个查询 30 条，总共最多 150 条
5. **分阶段执行固定**：必须按 1-9 顺序执行
6. **增量更新固定**：每完成一个 Stage 就写入数据库

### 🔧 **可配置参数（环境变量）：**

```python
# 可通过环境变量覆盖
V3_PROJECT_INFO_QUERIES_JSON  # 九个查询的 JSON 配置
V3_RETRIEVAL_TOPK_PER_QUERY   # 每个查询的 Top-K（默认 30）
V3_RETRIEVAL_TOPK_TOTAL       # 总共 Top-K（默认 150）
```

### 🔒 **无法通过 Prompt 改变的：**

- ❌ 检索策略（固定为向量检索）
- ❌ 分块大小（固定为 1200 字符）
- ❌ 执行顺序（固定为 1-9）
- ❌ 数据合并逻辑（固定在代码中）

---

## 💡 **对 LLM 的实际影响**

### **误导的后果：**

1. **LLM 可能期待更完整的上下文**
   - Prompt 说"从招标文件原文片段中抽取"
   - LLM 可能认为会看到更连贯的内容
   - 实际上片段是分散的、去重的

2. **LLM 可能不理解为什么信息不完整**
   - 如果某个信息不在检索到的片段中
   - LLM 不知道是检索问题还是文档真的没有

3. **LLM 可能不理解证据链的重要性**
   - Prompt 只是要求"填写 evidence_chunk_ids"
   - 但没有说明为什么、如何使用

---

## ✅ **改进建议总结**

### **1. 更新 Prompt（高优先级）**
- ✅ 明确说明数据来源是"检索片段"而非"原文"
- ✅ 说明片段是如何选择的（语义检索）
- ✅ 说明片段可能不连续、不完整
- ✅ 强调跨片段综合的重要性

### **2. 增强检索可见性（中优先级）**
- ✅ 在 Prompt 中附加检索元信息：
  ```
  ## 本次检索信息
  - 检索关键词：项目名称、项目编号、采购人...
  - 检索到片段数：30 个
  - 片段总字符数：~36,000 字符
  - 检索策略：向量相似度 Top-30
  ```

### **3. 优化检索策略（低优先级）**
- 考虑混合检索（关键词 + 向量）
- 考虑动态调整 Top-K
- 考虑片段重排序（Reranking）

---

## 📌 **总结**

### ❌ **Prompt 存在误导：**
- 声称从"招标文件原文片段"抽取
- 实际是从"向量检索后的分散片段"抽取
- 未说明片段的选择、大小、完整性

### ✅ **程序流程已固定：**
- 分块大小固定（1200 字符）
- 检索策略固定（Top-K 向量）
- 执行顺序固定（九阶段）
- 只有少量参数可通过环境变量配置

### 🎯 **建议：**
1. **立即更新 Prompt**，明确说明检索机制
2. 增加检索元信息输出
3. 长期考虑优化检索策略

---

**文档生成时间：** 2025-12-26
**相关文件：**
- `backend/app/works/tender/prompts/project_info_v3.md`
- `backend/app/works/tender/extract_v2_service.py`
- `backend/app/platform/extraction/engine.py`
- `backend/app/services/segmenter/chunker.py`

