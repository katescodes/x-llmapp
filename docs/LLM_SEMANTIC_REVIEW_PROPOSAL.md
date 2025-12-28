# LLM语义审核方案设计文档

## 一、方案概览

### 核心思路

```
招标要求 + 投标响应 → LLM语义判断 → 审核结果
```

### 设计目标

| 目标 | 指标 | 说明 |
|------|------|------|
| **准确率** | ≥85% | 接近人工审核水平 |
| **速度** | <5分钟 | 69个要求可接受 |
| **成本** | <¥5/次 | 控制在合理范围 |
| **稳定性** | 99%+ | 可靠的生产环境 |

## 二、架构设计

### 2.1 整体架构

```
┌────────────────────────────────────────────────────────────┐
│                  LLM语义审核引擎                             │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  输入层                                                      │
│  ┌──────────────┐          ┌──────────────┐               │
│  │招标要求(69条)│          │投标响应(12条) │               │
│  └──────┬───────┘          └──────┬───────┘               │
│         │                          │                        │
│         └──────────┬───────────────┘                        │
│                    ↓                                        │
│  预处理层                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ 1. 按维度分组                            │               │
│  │ 2. 向量相似度粗筛                        │               │
│  │ 3. 构建匹配候选集                        │               │
│  └─────────────────┬───────────────────────┘               │
│                    ↓                                        │
│  LLM判断层 (三种策略)                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │策略A：逐项判断│  │策略B：批量判断│  │策略C：混合判断│    │
│  │准确率最高    │  │速度最快      │  │平衡方案(推荐)│    │
│  │速度最慢      │  │成本最低      │  │              │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            ↓                                │
│  后处理层                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ 1. 解析LLM输出                           │               │
│  │ 2. 置信度评估                            │               │
│  │ 3. 结果归一化                            │               │
│  └─────────────────┬───────────────────────┘               │
│                    ↓                                        │
│  输出层                                                      │
│  ┌─────────────────────────────────────────┐               │
│  │ 审核结果: PASS/WARN/FAIL + 理由 + 证据   │               │
│  └─────────────────────────────────────────┘               │
└────────────────────────────────────────────────────────────┘
```

### 2.2 三种策略对比

#### 策略A：逐项精确判断

```python
# 伪代码
for requirement in requirements:
    # 找候选响应
    candidates = find_best_candidates(requirement, responses, top_k=3)
    
    # 单独判断每个要求
    result = await llm.judge_single(
        requirement=requirement,
        candidates=candidates
    )
```

**特点：**
- ✅ 准确率最高（90-95%）
- ❌ 速度慢（69次LLM调用 × 3秒 ≈ 3-4分钟）
- ❌ 成本高（69次 × 500 tokens ≈ ¥8-10）

#### 策略B：批量打包判断

```python
# 伪代码
for dimension in dimensions:
    reqs = requirements_by_dimension[dimension]
    resps = responses_by_dimension[dimension]
    
    # 批量判断一个维度
    results = await llm.judge_batch(
        requirements=reqs,
        responses=resps
    )
```

**特点：**
- ✅ 速度快（5次LLM调用 × 5秒 ≈ 30秒）
- ✅ 成本低（5次 × 2000 tokens ≈ ¥2-3）
- ❌ 准确率中等（75-80%）
- ⚠️ 可能遗漏细节

#### 策略C：混合智能判断（推荐）⭐

```python
# 伪代码
# 第1步：向量相似度粗筛
similarity_results = vector_match_all(requirements, responses)

# 第2步：分层判断
for req, candidates, sim_score in similarity_results:
    if sim_score < 0.5:
        # 明显不匹配，直接FAIL
        result = "FAIL"
    elif sim_score > 0.9:
        # 高度匹配，LLM快速确认
        result = await llm.quick_verify(req, candidates[0])
    else:
        # 不确定，LLM详细判断
        result = await llm.detailed_judge(req, candidates)
```

**特点：**
- ✅ 准确率高（85-90%）
- ✅ 速度适中（约20-30次LLM调用 ≈ 1-2分钟）
- ✅ 成本适中（¥3-5）
- ✅ 最佳平衡方案

## 三、技术实现方案（策略C - 推荐）

### 3.1 数据流设计

```
Step 1: 向量相似度初筛（5秒）
  ├─ 为所有requirements和responses生成embedding
  ├─ 计算相似度矩阵
  └─ 为每个requirement找top-3候选响应

Step 2: 分层LLM判断（1-2分钟）
  ├─ 高置信度（sim >= 0.9）: 20个 → 快速确认（简单prompt）
  ├─ 中置信度（0.5 <= sim < 0.9）: 30个 → 详细判断（完整prompt）
  └─ 低置信度（sim < 0.5）: 19个 → 直接FAIL（无需LLM）

Step 3: 结果汇总（1秒）
  └─ 合并所有判断结果
```

### 3.2 Prompt设计

#### Prompt 1: 快速确认（高置信度场景）

```python
QUICK_VERIFY_PROMPT = """
# 任务
快速判断投标响应是否满足招标要求。

# 招标要求
{requirement_text}

# 投标响应
{response_text}

# 输出格式（JSON）
{{
  "judgment": "PASS" | "WARN" | "FAIL",
  "confidence": 0.0-1.0,
  "reason": "一句话说明原因"
}}

# 判断标准
- PASS: 响应完全满足要求
- WARN: 响应基本满足但有小瑕疵
- FAIL: 响应不满足要求

请直接输出JSON，不要其他内容。
"""
```

**估算：**
- 输入tokens: ~200
- 输出tokens: ~50
- 成本/次: ~¥0.01
- 时间/次: ~1秒

#### Prompt 2: 详细判断（中置信度场景）

```python
DETAILED_JUDGE_PROMPT = """
# 任务
详细判断投标响应是否满足招标要求。

# 招标要求
**ID**: {requirement_id}
**维度**: {dimension}
**类型**: {"硬性要求" if is_hard else "建议性要求"}
**内容**: {requirement_text}

# 投标响应候选（按相似度排序）
## 候选1（相似度: {sim_1}）
{response_1_text}

## 候选2（相似度: {sim_2}）
{response_2_text}

## 候选3（相似度: {sim_3}）
{response_3_text}

# 判断步骤
1. 分析招标要求的核心诉求
2. 评估每个候选响应的匹配程度
3. 选择最匹配的响应
4. 给出最终判断和详细理由

# 输出格式（JSON）
{{
  "analysis": "招标要求的核心诉求是...",
  "best_match_index": 1 | 2 | 3 | null,
  "match_score": 0.0-1.0,
  "judgment": "PASS" | "WARN" | "FAIL",
  "reason": "详细说明为什么这样判断",
  "evidence": "引用响应中的关键内容作为证据",
  "confidence": 0.0-1.0
}}

# 判断标准
- PASS (match_score >= 0.85): 响应完全满足要求，内容充分、准确
- WARN (0.70 <= match_score < 0.85): 响应基本满足但有不足
- FAIL (match_score < 0.70): 响应不满足要求或答非所问

请严格按照JSON格式输出，不要添加其他内容。
"""
```

**估算：**
- 输入tokens: ~800
- 输出tokens: ~200
- 成本/次: ~¥0.05
- 时间/次: ~3秒

### 3.3 性能优化

#### 优化1：并发请求

```python
import asyncio

# 批量并发请求LLM
async def batch_llm_judge(tasks):
    # 限制并发数为10
    semaphore = asyncio.Semaphore(10)
    
    async def limited_task(task):
        async with semaphore:
            return await llm.judge(task)
    
    results = await asyncio.gather(*[
        limited_task(task) for task in tasks
    ])
    
    return results
```

**效果：**
- 串行：30次 × 3秒 = 90秒
- 并发10：30次 / 10 × 3秒 ≈ 9秒
- **提速10倍**

#### 优化2：缓存机制

```python
# 缓存相同内容的判断结果
cache = {}

def judge_with_cache(requirement_text, response_text):
    cache_key = hash(requirement_text + response_text)
    
    if cache_key in cache:
        return cache[cache_key]
    
    result = await llm.judge(requirement_text, response_text)
    cache[cache_key] = result
    
    return result
```

**效果：**
- 避免重复判断
- 节省20-30%成本

#### 优化3：流式输出

```python
# 使用LLM的流式API
async def judge_with_stream(requirement, response):
    result = ""
    
    async for chunk in llm.stream_chat(prompt):
        result += chunk
        # 实时显示进度
        update_progress(result)
    
    return parse_result(result)
```

**效果：**
- 更好的用户体验
- 实时反馈进度

### 3.4 成本估算

#### 测试2项目（69个要求）

```
场景分析：
  高置信度（sim >= 0.9）: 15个
    └─ 使用快速确认
    └─ 15次 × 250 tokens × ¥0.00004/token = ¥0.15

  中置信度（0.5 <= sim < 0.9）: 35个
    └─ 使用详细判断
    └─ 35次 × 1000 tokens × ¥0.00004/token = ¥1.40

  低置信度（sim < 0.5）: 19个
    └─ 直接FAIL，无LLM调用
    └─ ¥0

总成本：¥0.15 + ¥1.40 = ¥1.55/次

并发优化后时间：
  快速确认：15次 / 10 × 1秒 = 2秒
  详细判断：35次 / 10 × 3秒 = 11秒
  总时间：约15秒
```

## 四、实现步骤

### Phase 1: 基础框架（2-3天）

```
1. 创建 LLMSemanticReviewer 类
2. 实现向量相似度计算
3. 实现prompt模板
4. 实现LLM调用封装
```

### Phase 2: 核心逻辑（3-4天）

```
1. 实现分层判断逻辑
2. 实现结果解析和归一化
3. 实现错误处理和重试
4. 实现进度反馈
```

### Phase 3: 优化和测试（2-3天）

```
1. 实现并发控制
2. 实现缓存机制
3. 性能测试和调优
4. 准确率测试
```

### Phase 4: 集成和部署（1-2天）

```
1. 集成到ReviewV3Service
2. 更新前端UI
3. 文档编写
4. 生产环境部署
```

**总工期：8-12天**

## 五、API设计

### 5.1 请求接口

```python
POST /api/apps/tender/projects/{project_id}/review/run

{
  "bidder_name": "123",
  "review_mode": "llm_semantic",  # 新增参数
  "custom_rule_pack_ids": [...],
  "llm_config": {
    "model_id": "gpt-4",
    "temperature": 0.0,
    "enable_cache": true,
    "concurrency": 10
  }
}
```

### 5.2 响应接口

```python
{
  "review_mode": "llm_semantic",
  "requirement_count": 69,
  "response_count": 12,
  
  "llm_stats": {
    "total_calls": 50,
    "cache_hits": 5,
    "avg_confidence": 0.87,
    "total_cost": 1.55,
    "total_time": 15.2
  },
  
  "finding_count": 69,
  "pass_count": 28,
  "warn_count": 8,
  "fail_count": 33,
  
  "items": [
    {
      "requirement_id": "business_001",
      "requirement_text": "不得转包、分包的承应",
      "result": "PASS",
      "confidence": 0.95,
      "reason": "投标人明确承诺不转包、不分包，表述清晰",
      "evidence": "我司承诺不进行任何形式的转包或分包",
      "matched_response_id": "resp_001",
      "evaluator": "llm_semantic",
      "llm_model": "gpt-4"
    },
    ...
  ]
}
```

## 六、风险和应对

### 6.1 风险清单

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| LLM API不稳定 | 中 | 高 | 实现重试机制+降级方案 |
| 成本超预算 | 低 | 中 | 智能分层+缓存优化 |
| 准确率不达标 | 低 | 高 | Prompt优化+人工校验 |
| 速度过慢 | 中 | 中 | 并发优化+流式输出 |

### 6.2 降级方案

```python
# 当LLM不可用时，降级到向量相似度
if llm_available():
    result = await llm_semantic_review(...)
else:
    logger.warning("LLM unavailable, fallback to vector similarity")
    result = vector_similarity_review(...)
```

## 七、监控指标

### 7.1 实时监控

```python
metrics = {
    # 性能指标
    "avg_response_time": 15.2,  # 秒
    "p95_response_time": 18.5,
    "p99_response_time": 22.1,
    
    # 成本指标
    "avg_cost_per_review": 1.55,  # 元
    "total_tokens_used": 38750,
    "cache_hit_rate": 0.15,
    
    # 质量指标
    "avg_confidence": 0.87,
    "low_confidence_rate": 0.08,  # <0.7的比例
    "human_override_rate": 0.12,  # 人工修改率
    
    # 可用性指标
    "success_rate": 0.99,
    "llm_timeout_rate": 0.005,
    "llm_error_rate": 0.003
}
```

## 八、对比方案

### 当前方案 vs LLM方案

| 维度 | 当前（维度匹配） | LLM语义（混合策略） | 提升 |
|------|----------------|-------------------|------|
| **准确率** | 40-50% | 85-90% | +80% |
| **速度** | <1秒 | 15-30秒 | -30倍 |
| **成本** | ¥0 | ¥1-2/次 | +¥1-2 |
| **覆盖率** | 100% | 100% | - |
| **可解释性** | ⭐⭐ | ⭐⭐⭐⭐⭐ | +150% |

### ROI分析

```
人工审核成本：
  审核员工资：¥200/小时
  审核时间：2小时/项目
  成本：¥400/项目

LLM审核成本：
  LLM费用：¥2/项目
  人工复核（减少80%工作量）：¥80/项目
  总成本：¥82/项目

节省：¥318/项目（79.5%）
```

## 九、实施建议

### 阶段1：验证阶段（1-2周）
- ✅ 选择10个测试项目
- ✅ 对比LLM结果 vs 人工结果
- ✅ 调优prompt和策略
- ✅ 验证准确率 >= 85%

### 阶段2：试点阶段（2-4周）
- ✅ 20%项目使用LLM审核
- ✅ 收集用户反馈
- ✅ 优化性能和成本
- ✅ 建立监控体系

### 阶段3：推广阶段（1-2个月）
- ✅ 逐步扩大到100%项目
- ✅ 持续优化和迭代
- ✅ 建立最佳实践

## 十、决策建议

### 推荐方案：混合智能审核（策略C）

**理由：**
1. ✅ 准确率提升至85-90%（满足生产要求）
2. ✅ 速度15-30秒（用户可接受）
3. ✅ 成本¥1-2/次（性价比高）
4. ✅ ROI明确（节省80%人工成本）
5. ✅ 技术可行（2周内可实现）

**前置条件：**
- 需要LLM API（OpenAI或国产大模型）
- 需要embedding模型（可用开源模型）
- 需要约2周开发时间

---

## 下一步

请确认：
1. 是否采用**混合智能审核方案（策略C）**？
2. LLM选择：OpenAI GPT-4 还是国产大模型（如讯飞星火、文心一言）？
3. 开发时间：是否接受2周的开发周期？
4. 成本预算：是否接受¥1-2/次的审核成本？

确认后我将开始编写代码实现。

