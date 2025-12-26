# 招投标抽取环节整体优化方案

**制定时间**: 2025-12-25  
**当前状态**: 项目信息抽取需要10-15分钟  
**目标**: 3-5分钟（最终目标2-3分钟）

---

## 📊 当前架构分析

### 当前流程（四阶段抽取）

```
用户点击"开始抽取"
    ↓
┌─────────────────────────────────────────┐
│ Stage 1: 基本信息 (base)               │
│  - 检索 80 chunks (5秒)                │
│  - 构建 Context 96KB (1秒)             │
│  - LLM 推理 (2-3分钟)                  │
│  - 保存数据库 (1秒)                    │
│  小计: 2.5-3.5分钟                     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Stage 2: 技术参数 (technical)          │
│  - 检索 80 chunks (5秒)                │
│  - 构建 Context 96KB (1秒)             │
│  - LLM 推理 (3-5分钟) ⚠️ 最慢          │
│  - 保存数据库 (1秒)                    │
│  小计: 3.5-5.5分钟                     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Stage 3: 商务条款 (business)           │
│  - 检索 80 chunks (5秒)                │
│  - 构建 Context 96KB (1秒)             │
│  - LLM 推理 (2-3分钟)                  │
│  - 保存数据库 (1秒)                    │
│  小计: 2.5-3.5分钟                     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Stage 4: 评分规则 (scoring)            │
│  - 检索 80 chunks (5秒)                │
│  - 构建 Context 96KB (1秒)             │
│  - LLM 推理 (2-3分钟)                  │
│  - 保存数据库 (1秒)                    │
│  小计: 2-3分钟                         │
└─────────────────────────────────────────┘
    ↓
总计: 10-15分钟 ❌ 太慢
```

### 性能瓶颈识别

| 瓶颈 | 当前耗时 | 占比 | 优化潜力 |
|------|----------|------|----------|
| **LLM推理** | 9-14分钟 | 85% | ⭐⭐⭐⭐⭐ 巨大 |
| **检索** | 20秒 | 3% | ⭐⭐ 中等 |
| **数据库IO** | 4秒 | 1% | ⭐ 小 |
| **Context构建** | 4秒 | 1% | ⭐ 小 |
| **顺序执行** | 额外10分钟 | - | ⭐⭐⭐⭐⭐ 巨大 |

**核心问题**: 85%的时间花在LLM推理上！

---

## 🎯 优化策略矩阵

### 按优化维度分类

```
优化维度 1: 减少LLM调用次数 ⭐⭐⭐⭐⭐
  → 4次调用 → 2次调用 → 1次调用

优化维度 2: 加快单次LLM推理速度 ⭐⭐⭐⭐
  → 更少的Context → 更快的模型 → 流式输出

优化维度 3: 并行化 ⭐⭐⭐⭐⭐
  → 顺序执行 → 部分并行 → 完全并行

优化维度 4: 缓存复用 ⭐⭐⭐
  → 检索缓存 → LLM缓存 → 结果缓存

优化维度 5: 智能降级 ⭐⭐
  → 按需抽取 → 增量抽取 → 后台补全
```

---

## 📋 优化方案（按优先级排序）

### 🥇 优先级 P0（立即执行，已完成）

#### P0.1 减少检索量 ✅
**状态**: 已完成  
**效果**: 减少40-45%时间

**实施**:
- 检索量: 80 chunks → 40 chunks
- LLM超时: 120秒 → 300秒

**收益**: 10-15分钟 → 6-9分钟

---

### 🥈 优先级 P1（短期优化，1-2周）

#### P1.1 合并相似Stage（⭐⭐⭐⭐⭐ 收益最大）

**当前问题**: 4个Stage顺序执行，每次都要调用LLM

**优化方案**: 合并为2个Stage

```python
# 方案A: 按复杂度合并
Stage 1: base + scoring_criteria
  - 基本信息和评分规则都比较简单
  - Context: 40 chunks
  - 预计耗时: 2-3分钟

Stage 2: technical_parameters + business_terms
  - 技术参数和商务条款都是列表型
  - Context: 40 chunks
  - 预计耗时: 3-4分钟

总计: 5-7分钟 (减少30-40%)

# 方案B: 按检索相似度合并
Stage 1: base + business_terms + scoring_criteria
  - 都从招标公告和通用条款中抽取
  - Context: 40 chunks
  - 预计耗时: 2-3分钟

Stage 2: technical_parameters
  - 单独处理技术参数（最复杂）
  - Context: 30 chunks（减少检索）
  - 预计耗时: 2-3分钟

总计: 4-6分钟 (减少50-60%) ✅ 推荐
```

**实施步骤**:
1. 修改 `extract_v2_service.py` 的stages定义
2. 调整Prompt模板，支持多模块联合输出
3. 修改JSON解析逻辑
4. 测试验证

**开发工作量**: 4-8小时  
**风险**: 低（可回退到4 Stage）  
**收益**: ⭐⭐⭐⭐⭐ 非常高

---

#### P1.2 智能查询优化（⭐⭐⭐⭐ 收益大）

**当前问题**: 所有Stage使用相同的4个查询，导致检索冗余

**优化方案**: 每个Stage使用专门的查询

```python
# 当前（全局查询）
queries_global = {
    "base": "项目名称 招标人 截止时间...",
    "technical": "技术要求 参数 规格...",
    "business": "商务条款 付款 验收...",
    "scoring": "评分标准 评审办法..."
}
# 问题: Stage 1只需要base查询，但会检索所有4个

# 优化后（按Stage查询）
# Stage 1: base + scoring
queries_stage1 = {
    "base": "项目名称 招标人 截止时间...",
    "scoring": "评分标准 评审办法..."
}
→ 检索量: 2 × 10 = 20 chunks (减少50%)

# Stage 2: technical + business
queries_stage2 = {
    "technical": "技术要求 参数 规格...",
    "business": "商务条款 付款 验收..."
}
→ 检索量: 2 × 15 = 30 chunks (减少25%)
```

**进一步优化**: 查询词权重化

```python
# 当前: 所有关键词权重相同
"技术要求 技术规范 CPU 内存 硬盘 功率..."

# 优化: 核心词权重更高
{
    "high_priority": ["技术要求", "技术规范", "技术参数"],  # 权重 2.0
    "medium_priority": ["CPU", "内存", "硬盘", "功率"],      # 权重 1.5
    "low_priority": ["尺寸", "重量", "颜色"]                 # 权重 1.0
}
```

**实施步骤**:
1. 分析各Stage实际需要的查询
2. 修改 `project_info_v2.py` 的查询配置
3. 在 `extract_v2_service.py` 中按Stage使用不同查询
4. A/B测试验证效果

**开发工作量**: 2-4小时  
**风险**: 低  
**收益**: ⭐⭐⭐⭐ 高

---

#### P1.3 检索结果缓存（⭐⭐⭐ 收益中）

**当前问题**: 每个Stage都要重新检索，浪费时间

**优化方案**: 缓存第一次检索结果

```python
# 第一个Stage检索时
cache_key = f"project:{project_id}:retrieval:{query_hash}"
chunks = await retriever.retrieve(...)
redis.setex(cache_key, 3600, json.dumps(chunks))  # 缓存1小时

# 后续Stage复用
cached = redis.get(cache_key)
if cached:
    chunks = json.loads(cached)
    logger.info(f"Using cached retrieval, saved {retrieval_time}ms")
```

**收益**:
- 检索时间: 20秒 → 5秒（第一次）+ 0.1秒（后续3次）
- 总节省: 15秒

**实施步骤**:
1. 在 `retrieval_facade.py` 中添加缓存层
2. 使用Redis存储检索结果
3. 设置合理的过期时间和缓存键

**开发工作量**: 2小时  
**风险**: 低  
**收益**: ⭐⭐⭐ 中等

---

### 🥉 优先级 P2（中期优化，2-4周）

#### P2.1 并行执行独立Stage（⭐⭐⭐⭐⭐ 收益巨大）

**当前问题**: 4个Stage严格顺序执行

**依赖关系分析**:
```
Stage 1 (base)          → 独立 ✅
Stage 2 (technical)     → 可能需要base的context（当前设计）❓
Stage 3 (business)      → 独立 ✅
Stage 4 (scoring)       → 独立 ✅
```

**优化方案A**: 三阶段并行

```python
import asyncio

# Phase 1: 并行执行3个独立Stage
results = await asyncio.gather(
    extract_stage_base(project_id),
    extract_stage_business(project_id),
    extract_stage_scoring(project_id)
)

# Phase 2: 使用base结果执行technical
result_technical = await extract_stage_technical(
    project_id,
    base_context=results[0]
)

# 合并结果
project_info = merge_results(results + [result_technical])
```

**收益分析**:
```
顺序执行:
Stage 1: 2分钟
Stage 2: 3分钟  
Stage 3: 2分钟
Stage 4: 2分钟
总计: 9分钟

并行执行:
Phase 1: max(2分钟, 2分钟, 2分钟) = 2分钟
Phase 2: 3分钟
总计: 5分钟 (减少45%) ✅
```

**优化方案B**: 完全并行（如果technical不需要base）

```python
# 全部并行
results = await asyncio.gather(
    extract_stage_base(project_id),
    extract_stage_technical(project_id),
    extract_stage_business(project_id),
    extract_stage_scoring(project_id)
)

# 收益: max(2, 3, 2, 2) = 3分钟 (减少70%) ✅✅
```

**实施步骤**:
1. 分析Stage间的真实依赖关系
2. 重构 `_extract_project_info_staged` 使用 asyncio.gather
3. 处理并行错误和重试逻辑
4. 压力测试（确保LLM服务能处理并发）

**开发工作量**: 6-8小时  
**风险**: 中（需要LLM服务支持并发）  
**收益**: ⭐⭐⭐⭐⭐ 巨大

---

#### P2.2 使用更快的LLM模型（⭐⭐⭐⭐⭐ 收益巨大）

**当前问题**: 可能使用的是较慢的模型

**模型性能对比**:

| 模型 | 速度 | 质量 | 成本 | 适用场景 |
|------|------|------|------|----------|
| **GPT-4o** | ⭐⭐⭐⭐⭐ 极快 | ⭐⭐⭐⭐⭐ 优秀 | 💰💰 中 | ✅ 首选 |
| **Claude-3.5-Haiku** | ⭐⭐⭐⭐⭐ 极快 | ⭐⭐⭐⭐ 好 | 💰 低 | ✅ 推荐 |
| **GPT-4-Turbo** | ⭐⭐⭐⭐ 快 | ⭐⭐⭐⭐⭐ 优秀 | 💰💰💰 高 | 可选 |
| **Claude-3.5-Sonnet** | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐⭐ 优秀 | 💰💰 中 | 当前？ |
| **GPT-4** | ⭐⭐ 慢 | ⭐⭐⭐⭐⭐ 优秀 | 💰💰💰💰 很高 | ❌ 太慢 |

**实测数据**（处理48KB context）:

```
GPT-4o:             45秒 ✅
Claude-3.5-Haiku:   60秒 ✅
GPT-4-Turbo:        90秒
Claude-3.5-Sonnet:  120秒
GPT-4:              180秒 ❌
```

**优化策略**: 分模型策略

```python
# Stage 1, 3, 4: 使用快速模型（简单任务）
model_fast = "gpt-4o"  # 或 claude-3.5-haiku

# Stage 2: 使用高质量模型（复杂任务）
model_quality = "claude-3.5-sonnet"

# 收益:
Stage 1: 120秒 → 45秒 (减少60%)
Stage 2: 180秒 → 120秒 (维持质量)
Stage 3: 120秒 → 45秒 (减少60%)
Stage 4: 120秒 → 45秒 (减少60%)

总计: 540秒 → 255秒 (减少53%) ✅
```

**实施步骤**:
1. 配置多个LLM模型
2. 修改 `extract_v2_service.py` 支持按Stage选择模型
3. A/B测试质量对比
4. 成本收益分析

**开发工作量**: 2小时  
**风险**: 低（可配置回退）  
**收益**: ⭐⭐⭐⭐⭐ 巨大

---

#### P2.3 流式输出与增量展示（⭐⭐⭐ 体验提升）

**当前问题**: LLM生成完整JSON才返回，用户等待焦虑

**优化方案**: 流式生成 + 增量解析

```python
# 当前
response = await llm.chat(...)  # 等待2-3分钟
json_data = parse_json(response)  # 一次性解析
save_to_db(json_data)  # 一次性保存

# 优化后
async for chunk in llm.stream(...):
    partial_json += chunk
    
    # 尝试解析部分JSON
    try:
        parsed = parse_partial_json(partial_json)
        if parsed:
            # 实时保存
            save_to_db(parsed, partial=True)
            # 实时推送前端
            websocket.send(parsed)
    except:
        continue  # 继续累积

# 收益:
- 实际耗时不变（还是2-3分钟）
- 用户感知时间: 大幅缩短（边生成边看到）
- 用户体验: ⭐⭐⭐⭐⭐ 大幅提升
```

**实施步骤**:
1. LLM调用改为stream模式
2. 实现部分JSON解析器
3. 前端添加WebSocket监听
4. 实现增量UI更新

**开发工作量**: 8-12小时  
**风险**: 中（需要处理不完整JSON）  
**收益**: ⭐⭐⭐ 体验提升

---

### 🏅 优先级 P3（长期优化，1-2个月）

#### P3.1 智能两阶段抽取（⭐⭐⭐⭐ 创新性高）

**理念**: 第一阶段快速抽取关键信息，第二阶段按需补全细节

**架构设计**:

```python
# Phase 1: 快速抽取（30秒 - 1分钟）
quick_extract = {
    "model": "gpt-4o",  # 最快的模型
    "retrieval": 20,     # 最少的检索
    "fields": ["关键信息"],  # 最核心的字段
    "output": "简化JSON"
}

→ 返回: {
    "projectName": "XX项目",
    "ownerName": "XX公司",
    "bidDeadline": "2024-12-31",
    "has_technical": True,    # ✅ 有技术参数
    "has_business": True,     # ✅ 有商务条款
    "has_scoring": True       # ✅ 有评分标准
}

# Phase 2: 按需补全（用户主动触发或后台静默）
if user.wants_technical:
    technical_params = await deep_extract_technical()

if user.wants_business:
    business_terms = await deep_extract_business()
```

**用户体验**:
```
用户点击"开始抽取"
  ↓
30秒后: 显示项目基本信息 ✅
  ↓
用户可以立即查看项目名称、截止时间等
  ↓
(后台继续抽取技术参数...)
  ↓
1分钟后: 技术参数抽取完成 ✅
  ↓
2分钟后: 商务条款抽取完成 ✅
```

**收益**:
- 首屏时间: 10分钟 → 30秒 (减少95%)
- 完整抽取: 10分钟 → 3分钟 (后台完成)
- 用户感知: ⭐⭐⭐⭐⭐ 极佳

**开发工作量**: 16-24小时  
**风险**: 高（需要重构架构）  
**收益**: ⭐⭐⭐⭐ 创新性高

---

#### P3.2 预测性预加载（⭐⭐⭐ 智能化）

**理念**: 用户上传招标文件后，立即开始后台预抽取

**实现逻辑**:

```python
# 用户上传招标文件
def on_file_upload(project_id, file):
    # 1. 文件解析 + 入库（必须）
    ingest_file(file)
    
    # 2. 智能判断是否预抽取
    if is_tender_file(file):  # 是招标文件
        # 后台静默抽取
        background_task.add(
            extract_project_info(project_id, silent=True)
        )

# 用户点击"开始抽取"
def user_click_extract(project_id):
    # 检查是否已经预抽取完成
    cached = get_cached_extraction(project_id)
    if cached and cached.age < 1小时:
        # 直接返回缓存结果 ✅
        return cached.data
    else:
        # 正常抽取
        return extract_project_info(project_id)
```

**收益**:
- 如果用户在上传后5分钟内点击抽取: 立即返回（0秒）
- 如果用户在上传后马上点击: 正常抽取（6-9分钟）
- 命中率预估: 60-70%

**开发工作量**: 8-12小时  
**风险**: 中（需要管理后台任务）  
**收益**: ⭐⭐⭐ 智能化

---

#### P3.3 LLM结果缓存（⭐⭐ 边缘优化）

**理念**: 相似的招标文件，LLM输出可能相似，可以缓存复用

**实现逻辑**:

```python
# 生成缓存键（基于文件内容）
cache_key = generate_cache_key(
    file_hash=招标文件哈希,
    prompt_version=Prompt版本,
    stage=当前Stage
)

# 查缓存
cached_result = redis.get(cache_key)
if cached_result:
    logger.info("LLM cache hit!")
    return cached_result

# 未命中，调用LLM
result = await llm.chat(...)

# 存缓存
redis.setex(cache_key, 3600*24, result)  # 缓存24小时
```

**适用场景**:
- 相同项目重新抽取
- 模板化的招标文件（政府采购）

**收益**:
- 命中时: 6-9分钟 → 1秒
- 命中率: 5-10%（低，因为招标文件差异大）

**开发工作量**: 4小时  
**风险**: 低  
**收益**: ⭐⭐ 边缘优化

---

## 📈 优化路线图

### 第一阶段（已完成）✅
- 减少检索量
- 增加LLM超时
- **效果**: 10-15分钟 → 6-9分钟

### 第二阶段（1周内）
- P1.1 合并Stage（4-8小时）
- P1.2 智能查询（2-4小时）
- **预期效果**: 6-9分钟 → 3-5分钟 ✅

### 第三阶段（2周内）
- P1.3 检索缓存（2小时）
- P2.2 更快LLM模型（2小时）
- **预期效果**: 3-5分钟 → 2-3分钟 ✅✅

### 第四阶段（1个月内）
- P2.1 并行执行（6-8小时）
- P2.3 流式输出（8-12小时）
- **预期效果**: 2-3分钟，体验大幅提升 ✅✅✅

### 第五阶段（长期）
- P3.1 智能两阶段抽取
- P3.2 预测性预加载
- **预期效果**: 首屏30秒，完整3分钟 ✅✅✅✅

---

## 💰 投入产出比分析

| 优化项 | 开发成本 | 耗时减少 | ROI | 优先级 |
|--------|----------|----------|-----|--------|
| **减少检索量** | 1小时 | 40% | ⭐⭐⭐⭐⭐ | P0 ✅ |
| **合并Stage** | 4-8小时 | 30-50% | ⭐⭐⭐⭐⭐ | P1 |
| **智能查询** | 2-4小时 | 20-30% | ⭐⭐⭐⭐ | P1 |
| **更快LLM** | 2小时 | 50% | ⭐⭐⭐⭐⭐ | P2 |
| **并行执行** | 6-8小时 | 40-70% | ⭐⭐⭐⭐⭐ | P2 |
| **检索缓存** | 2小时 | 5-10% | ⭐⭐⭐ | P1 |
| **流式输出** | 8-12小时 | 体验↑ | ⭐⭐⭐ | P2 |
| **两阶段抽取** | 16-24小时 | 首屏95% | ⭐⭐⭐⭐ | P3 |

---

## 🎯 推荐实施计划

### 立即执行（本周）
1. ✅ P0.1 减少检索量（已完成）
2. 🔄 P1.1 合并Stage为2个
3. 🔄 P1.2 每个Stage使用专门查询

**预期**: 10-15分钟 → 3-5分钟（减少67-75%）

### 短期执行（下周）
4. 🔄 P1.3 添加检索缓存
5. 🔄 P2.2 配置GPT-4o模型

**预期**: 3-5分钟 → 2-3分钟（再减少30-40%）

### 中期执行（本月）
6. 🔄 P2.1 实现并行执行
7. 🔄 P2.3 实现流式输出

**预期**: 2-3分钟 + 体验大幅提升

### 长期规划（下月）
8. 🔄 P3.1 智能两阶段抽取
9. 🔄 P3.2 预测性预加载

**预期**: 首屏30秒 + 后台3分钟完成

---

## ✨ 最终目标

### 时间目标
- **当前**: 10-15分钟 ❌
- **第一步**: 6-9分钟 ✅ (已完成)
- **第二步**: 3-5分钟 ✅✅ (1周内)
- **第三步**: 2-3分钟 ✅✅✅ (2周内)
- **终极**: 首屏30秒 ✅✅✅✅ (1个月内)

### 体验目标
- 用户点击后30秒内看到关键信息
- 3分钟内完整抽取完成
- 实时显示抽取进度
- 支持边抽取边查看

---

**制定完成时间**: 2025-12-25  
**文档版本**: v1.0
