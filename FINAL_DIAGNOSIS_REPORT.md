# 投标响应抽取问题 - 最终诊断报告

## 问题现象
投标响应抽取始终只返回 **3条** 数据（每个维度各1条），无法达到预期的 20-40 条。

## 完整排查过程

### ✅ 已排除的问题

1. **数据源问题** ✅
   - 投标文件存在，共70个分段（68+2）
   - 检索功能正常，返回56个chunks
   - 上下文长度69535字符，足够完整

2. **代码逻辑问题** ✅
   - `max_tokens`正确设置为64000
   - `module_name="bid_response"`正确传递
   - Prompt已明确要求"提取所有内容，至少20-40条"

3. **Prompt问题** ✅ (部分)
   - 已在多处强调"全面性第一"
   - 已说明示例只是格式参考
   - 已要求每个维度输出多条

### ❌ 根本原因

**LLM服务器端输出长度限制**

关键证据：
```
prompt_tokens: 55712
completion_tokens: 2768  ← 始终停在这个值附近
total_tokens: 58480

max_tokens请求: 64000
实际返回: ~2768 tokens
```

无论如何修改代码和Prompt，LLM始终只返回约2768个tokens的输出，导致JSON被截断在第3个response处。

###根本原因分析

可能的限制点：
1. **LLM模型本身限制**: 模型训练时的最大输出长度限制
2. **服务器配置**: LLM服务部署时的`max_new_tokens`配置
3. **Context Window饱和**: prompt_tokens(55712) + completion_tokens(2768) = 58480，可能接近模型的实际context window上限

## 解决方案

### 方案1: 分批提取（推荐）

**原理**: 将56个chunks分成2-3批，每批调用LLM提取一部分响应，最后合并

**优点**:
- 不依赖LLM服务器配置
- 可靠性高
- 可以提取更全面的内容

**缺点**:
- API调用次数增加（成本增加）
- 总耗时增加

**实现要点**:
```python
# 1. 将chunks分批（每批20-25个）
chunk_batches = [all_chunks[i:i+25] for i in range(0, len(all_chunks), 25)]

# 2. 每批调用LLM
all_responses = []
for batch in chunk_batches:
    result = await engine.run(spec, retriever, llm, chunks=batch, ...)
    all_responses.extend(result.data['responses'])

# 3. 去重合并
unique_responses = deduplicate_by_content(all_responses)
```

### 方案2: 联系LLM服务提供商

要求调整服务器配置：
- 增加`max_new_tokens`或`max_output_tokens`
- 确认模型的实际context window和输出限制

### 方案3: 更换LLM模型

使用支持更长输出的模型（如GPT-4，Claude 3等商业模型）

## 建议

**立即可行**: 实施方案1（分批提取）
- 预计2小时开发 + 测试
- 能稳定达到20-40条输出

**中期优化**: 并行方案1 + 方案2
- 保持分批提取作为兜底
- 如果LLM服务商能解除限制，可以恢复单次调用

## 附：对比数据

| 任务 | Chunks | Context长度 | Completion Tokens | 输出条数 |
|------|--------|-------------|-------------------|----------|
| 投标响应 | 56 | 69535 | 2768 | 3条 ❌ |
| 招标要求 | ? | ? | ? | 0条（未测试）|
| 风险识别 | ? | ? | ? | 0条 |

*注: 招标要求和风险识别在当前项目中也是0条，说明可能都存在类似问题。*

