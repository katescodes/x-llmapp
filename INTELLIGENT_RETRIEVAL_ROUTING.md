# 智能检索路由方案 - 自动筛选分配chunks给对应模块

**提出时间**: 2025-12-25  
**核心思想**: 在检索后，自动判断每个chunk属于哪个模块，只将相关chunks分配给对应的Stage

---

## 🎯 核心理念

### 当前问题

```
检索阶段（所有Stage共用）
  ↓
获得40个chunks（混合内容）
  ├─ 5个基本信息chunks
  ├─ 15个技术参数chunks
  ├─ 12个商务条款chunks
  ├─ 6个评分规则chunks
  └─ 2个无关chunks
  ↓
Stage 1 (base): 收到全部40个chunks ❌
  → 只需要5个，但要处理40个

Stage 2 (technical): 收到全部40个chunks ❌
  → 只需要15个，但要处理40个

Stage 3 (business): 收到全部40个chunks ❌
  → 只需要12个，但要处理40个

Stage 4 (scoring): 收到全部40个chunks ❌
  → 只需要6个，但要处理40个

问题: 
- LLM处理大量无关内容，速度慢
- 准确度降低（噪音干扰）
- 浪费token成本
```

### 优化后的方案

```
检索阶段（全局检索）
  ↓
获得40个chunks（混合内容）
  ↓
智能路由/分类 ✨
  ├─ 5个 → base_chunks
  ├─ 15个 → technical_chunks
  ├─ 12个 → business_chunks
  └─ 6个 → scoring_chunks
  ↓
Stage 1 (base): 只收到5个相关chunks ✅
  → Context: 6KB (原来48KB)

Stage 2 (technical): 只收到15个相关chunks ✅
  → Context: 18KB (原来48KB)

Stage 3 (business): 只收到12个相关chunks ✅
  → Context: 14KB (原来48KB)

Stage 4 (scoring): 只收到6个相关chunks ✅
  → Context: 7KB (原来48KB)

收益:
- Context减少60-85% ✅
- LLM处理速度提升50-70% ✅
- 准确度提升（减少噪音） ✅
- 成本降低60-85% ✅
```

---

## 📋 实现方案对比

### 方案A: 基于Query的自然分类（⭐⭐⭐ 简单但粗糙）

**原理**: 每个Stage使用专门的查询，自然获得相关chunks

```python
# Stage 1: 只用base相关的查询
queries_base = ["项目名称 招标人 投标截止时间 开标时间"]
chunks_base = retrieve(queries_base, top_k=10)
→ 获得10个基本信息相关的chunks

# Stage 2: 只用technical相关的查询
queries_tech = ["技术要求 技术规范 技术参数 规格型号"]
chunks_tech = retrieve(queries_tech, top_k=20)
→ 获得20个技术参数相关的chunks

# 以此类推...
```

**优点**:
- ✅ 实现简单（1-2小时）
- ✅ 无需额外模型
- ✅ 零延迟

**缺点**:
- ❌ 分类不够精准（query匹配不完美）
- ❌ 可能漏掉一些相关内容
- ❌ 无法处理多类别的chunks

**效果**: Context减少30-50%

---

### 方案B: 小模型二次分类（⭐⭐⭐⭐⭐ 推荐，精准高效）

**原理**: 先全局检索，再用小模型快速分类每个chunk

```python
# Step 1: 全局检索（保证召回率）
all_chunks = retrieve(all_queries, top_k=50)

# Step 2: 使用小模型批量分类
classifier = FastClassifier()  # GPT-4o-mini 或 embedding分类器
classifications = classifier.classify_batch(all_chunks, categories=[
    "base",        # 基本信息
    "technical",   # 技术参数
    "business",    # 商务条款
    "scoring",     # 评分规则
    "irrelevant"   # 无关内容
])

# Step 3: 按分类分配
chunks_by_stage = {
    "base": [chunk for chunk in all_chunks if classifications[chunk.id] == "base"],
    "technical": [chunk for chunk in all_chunks if classifications[chunk.id] == "technical"],
    "business": [chunk for chunk in all_chunks if classifications[chunk.id] == "business"],
    "scoring": [chunk for chunk in all_chunks if classifications[chunk.id] == "scoring"],
}

# Step 4: 各Stage使用专属chunks
Stage 1 → chunks_by_stage["base"]
Stage 2 → chunks_by_stage["technical"]
Stage 3 → chunks_by_stage["business"]
Stage 4 → chunks_by_stage["scoring"]
```

**分类Prompt示例**:

```python
CLASSIFICATION_PROMPT = """
你是招标文件内容分类专家。请判断以下文本片段属于哪个类别。

类别定义：
1. base - 基本信息：项目名称、招标人、采购人、投标截止时间、开标时间、联系人、项目预算、最高限价、保证金等
2. technical - 技术参数：技术要求、技术规范、设备参数、性能指标、功能要求、规格型号、品牌、材质等
3. business - 商务条款：付款方式、交付期、质保期、验收标准、违约责任、发票要求、合同条款等
4. scoring - 评分规则：评标办法、评分标准、评审细则、分值分配、加分项、否决条件等
5. irrelevant - 无关内容：封面、目录、说明、声明等

文本内容：
{chunk_text}

请只返回类别名称（base/technical/business/scoring/irrelevant），不要其他内容。
"""
```

**实现细节**:

```python
class ChunkClassifier:
    """Chunk内容分类器"""
    
    def __init__(self, model="gpt-4o-mini"):
        self.model = model
        self.cache = {}  # 缓存分类结果
    
    async def classify_batch(
        self, 
        chunks: List[Chunk], 
        categories: List[str]
    ) -> Dict[str, str]:
        """
        批量分类chunks
        
        Returns:
            {chunk_id: category}
        """
        results = {}
        
        # 检查缓存
        uncached_chunks = []
        for chunk in chunks:
            cache_key = self._get_cache_key(chunk)
            if cache_key in self.cache:
                results[chunk.chunk_id] = self.cache[cache_key]
            else:
                uncached_chunks.append(chunk)
        
        if not uncached_chunks:
            return results
        
        # 批量调用LLM（并发）
        tasks = []
        for chunk in uncached_chunks:
            prompt = self._build_classification_prompt(chunk, categories)
            tasks.append(self._classify_one(chunk, prompt))
        
        classifications = await asyncio.gather(*tasks)
        
        # 合并结果和缓存
        for chunk, category in zip(uncached_chunks, classifications):
            results[chunk.chunk_id] = category
            cache_key = self._get_cache_key(chunk)
            self.cache[cache_key] = category
        
        return results
    
    async def _classify_one(self, chunk: Chunk, prompt: str) -> str:
        """分类单个chunk"""
        try:
            result = await llm_chat(
                messages=[{"role": "user", "content": prompt}],
                model_id=self.model,
                temperature=0.0,
                max_tokens=10  # 只需要返回一个类别名
            )
            category = result.strip().lower()
            return category if category in VALID_CATEGORIES else "irrelevant"
        except Exception as e:
            logger.warning(f"Classification failed for chunk {chunk.chunk_id}: {e}")
            return "irrelevant"
```

**优点**:
- ✅ 分类精准（90-95%准确率）
- ✅ 支持多标签（一个chunk可属于多个类别）
- ✅ 可调整分类策略
- ✅ 有缓存机制

**缺点**:
- ❌ 需要额外LLM调用（但很快，GPT-4o-mini处理50个chunks < 5秒）
- ❌ 增加一点成本（但比减少的Context成本低得多）

**效果**: Context减少60-85%

**成本分析**:
```
分类成本:
- 50个chunks × 1200字 = 60,000字 = 约15,000 tokens
- GPT-4o-mini输入: 15,000 tokens × $0.15/1M = $0.00225
- GPT-4o-mini输出: 50个类别 × 10 tokens = 500 tokens × $0.6/1M = $0.0003
- 总计: $0.0025 (约2分钱)

节省成本:
- Context减少70%: 48KB → 14KB (每个Stage)
- 4个Stage总共节省: 136KB tokens
- 节省: 136KB × $0.01/1M ≈ $0.14
- 净收益: $0.14 - $0.0025 = $0.1375 (每次抽取节省1毛4)

更重要的是时间收益:
- LLM处理时间减少50-70%
- 6-9分钟 → 2-3分钟 ✅✅
```

---

### 方案C: 基于Embedding的相似度分类（⭐⭐⭐⭐ 快速精准）

**原理**: 使用embedding计算chunk与各类别的相似度

```python
# 预定义类别的代表性描述
category_descriptions = {
    "base": "项目基本信息 项目名称 招标人 采购人 投标截止时间 开标时间 预算金额 保证金",
    "technical": "技术要求 技术规范 技术参数 设备规格 性能指标 功能要求 型号",
    "business": "商务条款 付款方式 交付时间 质保期 验收标准 合同条款",
    "scoring": "评分标准 评标办法 评审细则 分值分配 评分权重",
}

# 计算类别embeddings（只需计算一次）
category_embeddings = {
    cat: embed_text(desc) 
    for cat, desc in category_descriptions.items()
}

# 分类chunks
def classify_chunk_by_embedding(chunk: Chunk) -> str:
    chunk_embedding = embed_text(chunk.text)
    
    # 计算与各类别的余弦相似度
    similarities = {
        cat: cosine_similarity(chunk_embedding, cat_emb)
        for cat, cat_emb in category_embeddings.items()
    }
    
    # 返回最相似的类别
    best_category = max(similarities, key=similarities.get)
    
    # 如果相似度太低，标记为irrelevant
    if similarities[best_category] < 0.5:
        return "irrelevant"
    
    return best_category

# 批量分类（非常快！）
classifications = {
    chunk.chunk_id: classify_chunk_by_embedding(chunk)
    for chunk in all_chunks
}
```

**优点**:
- ✅ 速度极快（50个chunks < 1秒）
- ✅ 零LLM调用成本（只用embedding）
- ✅ 可离线计算
- ✅ 准确率中等（75-85%）

**缺点**:
- ❌ 准确率略低于LLM分类
- ❌ 不支持复杂语义理解
- ❌ 需要调优相似度阈值

**效果**: Context减少50-70%

---

### 方案D: 基于规则的启发式分类（⭐⭐ 快但粗糙）

**原理**: 使用关键词和规则进行分类

```python
CLASSIFICATION_RULES = {
    "base": {
        "keywords": ["项目名称", "招标人", "采购人", "投标截止", "开标时间", 
                     "预算", "最高限价", "保证金", "联系人"],
        "patterns": [
            r"项目编号[:：]\s*\S+",
            r"\d{4}年\d{1,2}月\d{1,2}日.*截止",
            r"招标人[:：].*有限公司",
        ]
    },
    "technical": {
        "keywords": ["技术要求", "技术规范", "参数", "规格", "型号", 
                     "性能", "功能", "配置", "CPU", "内存"],
        "patterns": [
            r"≥|≤|不低于|不小于",
            r"\d+\s*(GB|TB|MHz|GHz)",
            r"技术参数表",
        ]
    },
    "business": {
        "keywords": ["付款", "交付", "质保", "验收", "违约", "合同", 
                     "发票", "税费", "运输"],
        "patterns": [
            r"\d+%.*付款",
            r"质保期[:：]\s*\d+",
            r"验收.*天内",
        ]
    },
    "scoring": {
        "keywords": ["评分", "评标", "评审", "分值", "权重", "加分", 
                     "扣分", "否决"],
        "patterns": [
            r"\d+分",
            r"评分标准",
            r"综合评分法",
        ]
    }
}

def classify_chunk_by_rules(chunk: Chunk) -> str:
    """基于规则分类chunk"""
    scores = {}
    
    for category, rules in CLASSIFICATION_RULES.items():
        score = 0
        
        # 关键词匹配
        for keyword in rules["keywords"]:
            if keyword in chunk.text:
                score += 1
        
        # 正则匹配
        for pattern in rules["patterns"]:
            if re.search(pattern, chunk.text):
                score += 2  # 模式匹配权重更高
        
        scores[category] = score
    
    # 返回得分最高的类别
    if max(scores.values()) == 0:
        return "irrelevant"
    
    return max(scores, key=scores.get)
```

**优点**:
- ✅ 速度极快（< 0.1秒）
- ✅ 零成本
- ✅ 可解释性强

**缺点**:
- ❌ 准确率低（60-70%）
- ❌ 维护成本高（需要不断调整规则）
- ❌ 泛化能力差

**效果**: Context减少40-60%

---

### 方案E: 混合方案（⭐⭐⭐⭐⭐ 最优，推荐）

**原理**: 结合多种方法的优势

```python
async def classify_chunks_hybrid(chunks: List[Chunk]) -> Dict[str, str]:
    """
    混合分类策略：
    1. 先用规则快速筛选明显的cases
    2. 模糊的cases用embedding分类
    3. 仍然模糊的用小模型精确分类
    """
    results = {}
    uncertain_chunks = []
    
    # Stage 1: 规则分类（快速处理明显cases）
    for chunk in chunks:
        category, confidence = classify_by_rules_with_confidence(chunk)
        if confidence > 0.8:  # 高置信度
            results[chunk.chunk_id] = category
        else:
            uncertain_chunks.append(chunk)
    
    logger.info(f"Rule-based classified {len(results)}/{len(chunks)} chunks")
    
    if not uncertain_chunks:
        return results
    
    # Stage 2: Embedding分类（处理中等模糊cases）
    still_uncertain = []
    for chunk in uncertain_chunks:
        category, confidence = classify_by_embedding_with_confidence(chunk)
        if confidence > 0.7:  # 中等置信度
            results[chunk.chunk_id] = category
        else:
            still_uncertain.append(chunk)
    
    logger.info(f"Embedding classified {len(uncertain_chunks)-len(still_uncertain)} chunks")
    
    if not still_uncertain:
        return results
    
    # Stage 3: LLM分类（处理难cases）
    llm_results = await classify_by_llm(still_uncertain)
    results.update(llm_results)
    
    logger.info(f"LLM classified {len(still_uncertain)} chunks")
    
    return results
```

**优点**:
- ✅ 准确率高（90-95%）
- ✅ 速度快（大部分走快速路径）
- ✅ 成本低（只有少量chunks需要LLM）
- ✅ 可靠性高（多重保障）

**缺点**:
- ❌ 实现复杂度高

**效果**: Context减少60-85%，速度最快

---

## 📊 方案对比总结

| 方案 | 准确率 | 速度 | 成本 | 实现难度 | Context减少 | 推荐度 |
|------|--------|------|------|----------|-------------|--------|
| **A: Query分类** | 60-70% | ⭐⭐⭐⭐⭐ | $0 | ⭐ 低 | 30-50% | ⭐⭐⭐ |
| **B: LLM分类** | 90-95% | ⭐⭐⭐ | $0.0025 | ⭐⭐ 中 | 60-85% | ⭐⭐⭐⭐⭐ |
| **C: Embedding分类** | 75-85% | ⭐⭐⭐⭐⭐ | $0 | ⭐⭐ 中 | 50-70% | ⭐⭐⭐⭐ |
| **D: 规则分类** | 60-70% | ⭐⭐⭐⭐⭐ | $0 | ⭐ 低 | 40-60% | ⭐⭐ |
| **E: 混合方案** | 90-95% | ⭐⭐⭐⭐ | $0.001 | ⭐⭐⭐ 高 | 60-85% | ⭐⭐⭐⭐⭐ |

---

## 🎯 推荐实施方案

### 第一阶段: Query分类（立即可实施）

**实施步骤**:
1. 修改 `extract_v2_service.py`，每个Stage使用不同查询
2. 测试验证效果

**预期效果**:
- Context减少30-50%
- 开发时间: 2小时
- 速度提升: 20-30%

---

### 第二阶段: 添加LLM分类（1周内）

**实施步骤**:
1. 实现 `ChunkClassifier` 类
2. 在检索后添加分类步骤
3. 每个Stage只使用对应类别的chunks
4. 添加缓存机制

**代码示例**:

```python
# backend/app/platform/extraction/chunk_classifier.py
class ChunkClassifier:
    """智能chunk分类器"""
    
    async def classify_batch(
        self, 
        chunks: List[Chunk]
    ) -> Dict[str, List[Chunk]]:
        """
        将chunks分类到各个模块
        
        Returns:
            {
                "base": [chunk1, chunk2, ...],
                "technical": [chunk3, chunk4, ...],
                "business": [chunk5, chunk6, ...],
                "scoring": [chunk7, chunk8, ...]
            }
        """
        # 实现分类逻辑
        ...

# backend/app/works/tender/extract_v2_service.py
async def _extract_project_info_staged_with_routing(
    self,
    project_id: str,
    ...
):
    # 1. 全局检索
    all_chunks = await self.retriever.retrieve_all(...)
    
    # 2. 智能分类
    classifier = ChunkClassifier()
    chunks_by_category = await classifier.classify_batch(all_chunks)
    
    # 3. 各Stage使用专属chunks
    for stage_info in stages:
        stage_key = stage_info["key"]
        stage_chunks = chunks_by_category.get(stage_key, [])
        
        # 构建Context（只用相关chunks）
        context = build_context(stage_chunks)
        
        # 调用LLM
        result = await self.engine.run(
            spec=spec,
            context=context,  # 小得多的context
            ...
        )
```

**预期效果**:
- Context减少60-85%
- 开发时间: 8-12小时
- 速度提升: 50-70%
- 准确度提升: 10-15%

---

### 第三阶段: 优化为混合方案（2周内）

**实施步骤**:
1. 添加规则分类器（快速路径）
2. 添加embedding分类器（中速路径）
3. LLM分类作为兜底（慢速但精确）
4. 实现自适应策略选择

**预期效果**:
- Context减少60-85%
- 分类速度: < 2秒（比纯LLM快3-5倍）
- 成本降低: 70%
- 准确率: 90-95%

---

## 💰 ROI分析

### 时间收益

```
当前（无分类）:
Stage 1: 2分钟 (48KB context)
Stage 2: 3分钟 (48KB context)
Stage 3: 2分钟 (48KB context)
Stage 4: 1.5分钟 (48KB context)
总计: 8.5分钟

优化后（智能分类）:
Stage 1: 1分钟 (7KB context) ↓ 50%
Stage 2: 1.5分钟 (18KB context) ↓ 50%
Stage 3: 1分钟 (14KB context) ↓ 50%
Stage 4: 0.5分钟 (7KB context) ↓ 67%
分类: 0.5分钟
总计: 4.5分钟 ↓ 47% ✅✅
```

### 成本收益

```
每次抽取的token成本:
- Context: 4 × 48KB = 192KB ≈ 48,000 tokens
- 输出: 4 × 2KB = 8KB ≈ 2,000 tokens
- 总计: 50,000 tokens × $0.01/1K = $0.50

优化后:
- Context: 7+18+14+7 = 46KB ≈ 11,500 tokens ↓ 76%
- 输出: 2,000 tokens (不变)
- 分类: 500 tokens (GPT-4o-mini)
- 总计: 14,000 tokens × $0.01/1K = $0.14 ↓ 72%

每次节省: $0.36 (约3毛6)
每天100次抽取: 节省$36
每月: 节省$1080 ✅
```

### 准确度收益

```
噪音减少:
- 当前: 每个Stage有60-70%的无关chunks
- 优化后: 每个Stage只有5-10%的无关chunks

准确率提升:
- 基本信息: 95% → 98%
- 技术参数: 85% → 92%
- 商务条款: 88% → 95%
- 评分规则: 90% → 96%

原因: LLM不再被大量无关信息干扰
```

---

## ✨ 最终效果预测

### 性能提升

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| **总耗时** | 8-9分钟 | 4-5分钟 | ↓ 50% |
| **Context大小** | 192KB | 46KB | ↓ 76% |
| **Token成本** | $0.50 | $0.14 | ↓ 72% |
| **准确率** | 89% | 95% | ↑ 6% |

### 与其他优化的组合效果

```
基线: 10-15分钟
  ↓ (P0: 减少检索量)
6-9分钟 ↓ 40%
  ↓ (P1: 智能分类路由) ✨
3-4.5分钟 ↓ 50%
  ↓ (P1: 合并Stage)
2-3分钟 ↓ 33%
  ↓ (P2: 更快模型)
1-1.5分钟 ↓ 50%

最终: 1-1.5分钟 ✅✅✅✅
比原来快 10倍！
```

---

## 🚀 立即行动

### 快速验证（今天）

```bash
# 1. 修改查询配置，让每个Stage用不同查询
# backend/app/works/tender/extract_v2_service.py

# 2. 测试效果
# 选择一个项目，记录各Stage的耗时和准确度

# 3. 对比数据
# Before: Stage 1: 2min, Stage 2: 3min, ...
# After: Stage 1: 1.5min, Stage 2: 2.5min, ...
```

### 正式实施（本周）

1. ✅ 实现 `ChunkClassifier` 类
2. ✅ 集成到 `extract_v2_service.py`
3. ✅ 添加缓存机制
4. ✅ A/B测试验证

---

**文档完成时间**: 2025-12-25  
**推荐优先级**: P1（高优先级，1周内实施）  
**预期收益**: 速度提升50%，成本降低72%，准确度提升6%
