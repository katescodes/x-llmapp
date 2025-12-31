# 投标响应提取效果分析与改进建议

## 📊 当前审核结果分析

最近一次审核（`tr_b7eca6fce98e4c7eb03d833d5c5129bb`）：
- ✅ 通过（pass）: 19 条
- ❌ 失败（fail）: 5 条
- ⚠️ 缺失（missing）: 20 条
- ⏳ 待定（pending）: 1 条

### 关键问题

**5 条 `fail` 记录的 `bid_response` 字段为空！**

示例失败记录：
```
requirement_id: auto_technical_040
requirement: 所有电气设备必须具备防雷击功能，防护等级不低于IP55。
bid_response: （空）
status: fail
```

这说明 LLM **没有从投标文件中找到对应内容**，而不是找到了但判断为不符合。

---

## 🔍 根本原因分析

### 1️⃣ 检索策略过于简单

当前代码（`framework_bid_response_extractor.py` 174-181行）：

```python
# 1. 构建查询词（从要求中提取关键词）
query_terms = []
for req in requirements:
    req_text = req.get("requirement_text", "")
    # 简单提取前50字符作为查询词
    query_terms.append(req_text[:50])

query = " ".join(query_terms[:5])  # 取前5个要求的文本
```

**问题**：
- ❌ 只取前 50 字符，可能丢失关键信息
- ❌ 只用前 5 个要求组成查询，其他要求的内容可能检索不到
- ❌ 没有针对性地提取关键词（如"防雷击"、"IP55"、"200万像素"等）

### 2️⃣ 检索数量可能不足

```python
bid_chunks = await self.retriever.retrieve(
    query=query,
    project_id=project_id,
    doc_types=["bid"],
    top_k=50  # 获取足够多的上下文
)
```

对于技术要求密集的项目，50 个 chunk 可能不够覆盖所有内容。

### 3️⃣ 上下文截断

```python
bid_context = "\n\n".join([
    f"[SEG:{chunk.chunk_id}] {chunk.text}"
    for chunk in bid_chunks[:30]  # 限制token数
])
```

即使检索到 50 个 chunk，也只用了前 30 个！

---

## 💡 改进建议

### 方案 1: 增强检索策略（推荐）

#### A. 多轮检索

```python
# 为每个维度做针对性检索
dimension_queries = {
    "technical": "技术参数 性能指标 规格要求 技术方案",
    "qualification": "资质证书 业绩案例 人员配置 企业资质",
    "commercial": "工期 质保 付款方式 违约责任",
    "price": "投标报价 价格明细 费用清单",
}

# 组合通用查询和维度查询
general_query = " ".join([req["requirement_text"][:100] for req in requirements[:10]])
dimension_query = dimension_queries.get(dimension, "")
combined_query = f"{dimension_query} {general_query}"

bid_chunks = await self.retriever.retrieve(
    query=combined_query,
    project_id=project_id,
    doc_types=["bid"],
    top_k=100  # 增加检索数量
)
```

#### B. 关键词提取

```python
import re

def extract_keywords(req_text):
    """提取技术参数、规格等关键词"""
    keywords = []
    
    # 提取数值+单位（如"IP55", "200万像素", "≥30天"）
    patterns = [
        r'IP\d+',  # IP等级
        r'\d+[万千]像素',  # 像素
        r'[≥≤><=]\s*\d+\s*[天年月]',  # 时间要求
        r'\d+%',  # 百分比
        r'RS\d+|Modbus|PROFINET',  # 通讯协议
    ]
    
    for pattern in patterns:
        keywords.extend(re.findall(pattern, req_text))
    
    return keywords
```

### 方案 2: 增加上下文窗口

```python
# 使用更多 chunk
bid_context = "\n\n".join([
    f"[SEG:{chunk.chunk_id}] {chunk.text}"
    for chunk in bid_chunks[:50]  # 从30增加到50
])
```

### 方案 3: 分批次提取（针对复杂项目）

```python
# 对于要求较多的维度（>10条），分批提取
MAX_REQS_PER_BATCH = 10

if len(requirements) > MAX_REQS_PER_BATCH:
    batches = [requirements[i:i+MAX_REQS_PER_BATCH] 
               for i in range(0, len(requirements), MAX_REQS_PER_BATCH)]
    
    all_responses = []
    for batch in batches:
        batch_responses = await self.extract_dimension_responses(
            project_id, dimension, batch, model_id
        )
        all_responses.extend(batch_responses)
    
    return all_responses
```

---

## 🔧 快速修复方案

### 修改 1: 提升检索数量和质量

```python
# 在 extract_dimension_responses 方法中

# 1. 构建更好的查询
dimension_keywords = {
    "technical": "技术 参数 规格 性能 指标",
    "qualification": "资质 证书 业绩 人员",
    "commercial": "工期 质保 付款 违约",
    "price": "报价 价格 费用 清单",
}

# 组合维度关键词和要求文本
req_texts = [req.get("requirement_text", "")[:100] for req in requirements[:10]]
dim_keyword = dimension_keywords.get(dimension, "")
query = f"{dim_keyword} " + " ".join(req_texts)

# 2. 增加检索数量
bid_chunks = await self.retriever.retrieve(
    query=query,
    project_id=project_id,
    doc_types=["bid"],
    top_k=80  # 从50增加到80
)

# 3. 使用更多上下文
bid_context = "\n\n".join([
    f"[SEG:{chunk.chunk_id}] {chunk.text}"
    for chunk in bid_chunks[:40]  # 从30增加到40
])
```

### 修改 2: 增强 LLM max_tokens

```python
llm_response = await self.llm.achat(
    messages=messages,
    model_id=model_id,
    response_format={"type": "json_object"},
    temperature=0.1,
    max_tokens=12000  # 从8000增加到12000
)
```

---

## 📈 预期改进效果

### 当前效果
- 总计 45 条要求
- 提取成功: 24 条（19 pass + 5 fail但有内容）= 53%
- 提取失败: 21 条（5 fail无内容 + 16 missing） = 47%

### 改进后预期
- 提取成功率: 70-80%
- 减少"missing"和空响应的情况
- 提升技术参数密集型要求的匹配率

---

## 🎯 实施建议

### 优先级 1（立即实施）
1. ✅ 增加 `top_k` 从 50 → 80
2. ✅ 增加上下文使用量从 30 → 40
3. ✅ 增加 `max_tokens` 从 8000 → 12000

### 优先级 2（短期优化）
1. ⏳ 添加维度关键词到查询
2. ⏳ 提取要求中的技术参数关键词

### 优先级 3（长期优化）
1. 🔄 实现分批次提取（针对>15条要求的维度）
2. 🔄 实现多轮检索策略
3. 🔄 添加智能关键词提取

---

## 💻 快速实施代码

修改文件：`backend/app/works/tender/framework_bid_response_extractor.py`

```python
# 行 174-195 修改为：

# 1. 构建增强查询
dimension_keywords = {
    "technical": "技术参数 性能指标 规格要求",
    "qualification": "资质证书 业绩案例 企业资质",
    "commercial": "工期 质保期 付款方式",
    "price": "投标报价 价格明细",
}

req_texts = [req.get("requirement_text", "")[:100] for req in requirements[:10]]
dim_keyword = dimension_keywords.get(dimension, "")
query = f"{dim_keyword} " + " ".join(req_texts)

# 2. 检索投标文档相关内容
try:
    bid_chunks = await self.retriever.retrieve(
        query=query,
        project_id=project_id,
        doc_types=["bid"],
        top_k=80  # 增加到80
    )
    
    logger.info(f"Retrieved {len(bid_chunks)} bid chunks for dimension {dimension}")
except Exception as e:
    logger.error(f"Failed to retrieve bid chunks: {e}")
    bid_chunks = []

# 行 210-214 修改为：

# 3. 拼接上下文
bid_context = "\n\n".join([
    f"[SEG:{chunk.chunk_id}] {chunk.text}"
    for chunk in bid_chunks[:40]  # 增加到40
])

# 行 228 修改为：

llm_response = await self.llm.achat(
    messages=messages,
    model_id=model_id,
    response_format={"type": "json_object"},
    temperature=0.1,
    max_tokens=12000  # 增加到12000
)
```

---

## ✅ 总结

**当前问题**：检索策略太简单，导致技术要求密集的内容检索不到

**根本原因**：
1. 查询构建过于简单（只取前50字符）
2. 检索数量不足（top_k=50）
3. 上下文截断过多（只用30个chunk）

**解决方案**：
1. 增强检索策略（添加维度关键词）
2. 增加检索数量和上下文
3. 提升 LLM token 限制

**预期改进**：提取成功率从 53% 提升到 70-80%

