# LLM Orchestrator 验收测试用例

本文档提供 LLM 编排器功能的完整验收测试用例，确保"Extractor → Modular Answer → Parse Sections → Repair(可选) → 前端折叠渲染"的编排能力正常工作。

## 测试环境准备

### Docker Compose 启动（推荐）
```bash
cd /aidata/x-llmapp1

# 首次启动或代码有更新时，重新构建
docker-compose build

# 启动所有服务（后端 + 前端 + 数据库）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 服务访问地址
- **前端**：http://localhost:6173
- **后端**：http://localhost:9001
- **API 文档**：http://localhost:9001/docs

### 前置条件
1. Docker 和 Docker Compose 已安装
2. 后端已配置至少一个 LLM 模型（OpenAI 兼容或 Ollama）
3. 后端已配置 Embedding 服务（可选，非编排器必需）
4. 前端可以正常连接到后端 API（http://localhost:9001）

---

## 测试用例

### 用例 1：知识综述 - 美国税收政策百年演变

**目标**：验证 information 意图识别、时间线模块生成、详尽度控制

**测试步骤**：

1. 打开前端聊天界面
2. 在左侧边栏勾选 **"🎯 启用智能编排器（实验性）"**
3. 选择详尽度为 **"标准"**
4. 输入问题：
   ```
   美国税收政策百年演变历程
   ```
5. 点击发送

**预期结果**：

✅ **必须包含的模块**：
- **理解确认**（align_summary）：复述问题，确认理解"美国税收政策百年演变"
- **核心答案**（core_answer）：概述美国税收政策演变的关键阶段和主要特点
- **时间线**（timeline）：按时间顺序梳理重要事件（如 1913 年联邦所得税、1935 年社会保障税、二战期间扣缴制度等）
- **下一步**（next_steps）：建议进一步探索的方向

✅ **可选模块**（根据 LLM 生成情况）：
- **核心概念**（concepts）：关键术语解释
- **争议与口径**（controversy）：不同流派/观点
- **核对路径**（verification）：如何查证历史事实

✅ **前端渲染**：
- 每个模块显示为可折叠的卡片
- "理解确认"和"核心答案"默认展开
- 其他模块默认折叠
- 点击标题可切换展开/折叠

✅ **可选补充信息**（followups）：
- 显示黄色提示框，提示可补充的信息（≤3 个问题）
- 不阻塞答案生成

**验证方式**：
- 手动检查前端渲染的 sections 结构
- 检查浏览器开发者工具的 Network 标签，确认 `/api/chat/stream` 返回的 `result` 事件包含 `sections`、`followups`、`orchestrator_meta` 字段
- 确认 `orchestrator_meta.intent` 为 `"information"`
- 确认 `orchestrator_meta.detail_level` 为 `"normal"`

---

### 用例 2：排障 - 某接口 500 错误

**目标**：验证 troubleshoot 意图识别、检查清单和排障路径模块生成

**测试步骤**：

1. 确保编排器已启用
2. 选择详尽度为 **"标准"**
3. 输入问题：
   ```
   我的 Flask API 接口返回 500 错误，但日志里没有明确报错信息，应该如何排查？
   ```
4. 点击发送

**预期结果**：

✅ **必须包含的模块**：
- **理解确认**：复述问题（Flask API 500 错误，日志无明确信息）
- **核心答案**：直接给出排查思路概述
- **检查清单**（checklist）：逐项检查点（如检查日志配置、环境变量、依赖版本等）
- **执行步骤**（steps）：具体操作步骤（1. 启用详细日志，2. 检查依赖，3. 隔离测试等）

✅ **可选模块**：
- **常见陷阱**（pitfalls）：易错点（如未捕获的异常、数据库连接问题等）
- **下一步**：后续建议（如设置监控、添加单元测试等）

✅ **前端渲染**：
- 清单和步骤使用有序列表（1. 2. 3.）渲染
- 表格（如果有）使用 Markdown 表格语法

**验证方式**：
- 检查返回的 `orchestrator_meta.intent` 为 `"troubleshoot"`
- 确认至少包含 "检查清单" 或 "执行步骤" 模块
- 确认没有编造具体的错误代码或版本号（应该标注 [需核实]）

---

### 用例 3：选型 - OpenAI 兼容 vs Ollama

**目标**：验证 decision 意图识别、对比矩阵模块生成

**测试步骤**：

1. 确保编排器已启用
2. 选择详尽度为 **"标准"**
3. 输入问题：
   ```
   在自托管场景下，选择 OpenAI 兼容服务（如 vLLM）还是 Ollama？我主要考虑易用性和性能。
   ```
4. 点击发送

**预期结果**：

✅ **必须包含的模块**：
- **理解确认**：复述问题（自托管场景，OpenAI 兼容 vs Ollama，重点易用性和性能）
- **核心答案**：直接建议（如推荐场景、权衡点）
- **对比矩阵**（comparison）：表格对比 OpenAI 兼容服务和 Ollama 的优劣
- **下一步**：行动建议（如试用建议、文档链接）

✅ **对比矩阵示例格式**：

| 维度           | OpenAI 兼容（vLLM）    | Ollama                |
|----------------|------------------------|-----------------------|
| 易用性         | 需要配置环境           | 开箱即用              |
| 性能           | 高吞吐、适合生产       | 中等、适合本地测试    |
| 模型支持       | 主流开源模型           | 精选优化模型          |
| 生态兼容       | 广泛（OpenAI SDK）     | 专用 API              |

✅ **前端渲染**：
- Markdown 表格正确渲染为 HTML 表格
- 表格有边框和表头样式

**验证方式**：
- 检查返回的 `orchestrator_meta.intent` 为 `"decision"`
- 确认包含 "对比矩阵" 或 "对比与选择建议" 模块
- 确认没有编造数据（如具体性能数字应标注来源或 [示例数据]）

---

### 用例 4：详尽度切换 - brief vs detailed

**目标**：验证详尽度级别影响答案长度和模块数量

#### 测试 4.1：brief 模式

**测试步骤**：

1. 确保编排器已启用
2. 选择详尽度为 **"精简"**
3. 输入问题：
   ```
   Python 虚拟环境是什么？
   ```
4. 点击发送

**预期结果**：

✅ **输出特征**：
- **核心答案**明显较短（2-3 段落）
- 可选模块数量少（可能只有 "理解确认" + "核心答案" + "下一步"）
- 无冗余例子

#### 测试 4.2：detailed 模式

**测试步骤**：

1. 确保编排器已启用
2. 选择详尽度为 **"详细"**
3. 输入**相同问题**：
   ```
   Python 虚拟环境是什么？
   ```
4. 点击发送

**预期结果**：

✅ **输出特征**：
- **核心答案**明显更长（5-8 段落）
- 可选模块数量更多（如增加 "核心概念"、"示例与案例"、"常见陷阱"）
- 包含多个例子（如 venv、virtualenv、conda 的对比）
- 深入解释（如原理、使用场景、最佳实践）

**验证方式**：
- 对比两次返回的 `answer` 字段长度（detailed 应显著长于 brief）
- 对比两次返回的 `sections` 数量（detailed 应 ≥ brief）
- 检查 `orchestrator_meta.detail_level` 分别为 `"brief"` 和 `"detailed"`

#### 测试 4.3：文本关键词覆盖 UI 设置

**测试步骤**：

1. 确保编排器已启用
2. 选择详尽度为 **"标准"**
3. 输入问题（包含 brief 关键词）：
   ```
   简短说明一下 Docker 是什么，别解释太多
   ```
4. 点击发送

**预期结果**：

✅ **输出特征**：
- 尽管 UI 设置为 "标准"，但因为用户文本包含 "简短" 和 "别解释太多"，应识别为 brief
- 答案较短，无冗余内容
- 检查 `orchestrator_meta.detail_level` 为 `"brief"`

---

### 用例 5：信息不足场景 - 不阻塞回答

**目标**：验证编排器在信息不足时的兜底策略（先假设给答案，再提示澄清问题）

**测试步骤**：

1. 确保编排器已启用
2. 选择详尽度为 **"标准"**
3. 输入模糊问题：
   ```
   我想部署一个网站
   ```
4. 点击发送

**预期结果**：

✅ **核心答案**：
- **不会**直接回复"信息不足，无法回答"
- 会基于合理假设给出通用方案（如静态网站 vs 动态网站、云部署 vs 自托管等）
- 使用"如果是 A 情况则 X，如果是 B 情况则 Y"的分支覆盖

✅ **澄清问题**（followups）：
- 显示在黄色提示框中，**不阻塞答案**
- 提示补充信息，例如：
  - "是静态网站还是动态应用？"
  - "预计访问量是多少？（小流量/中等/高并发）"
  - "预算范围是多少？（免费/低成本/不限）"
- 澄清问题数量 ≤ 3

✅ **assumptions 字段**：
- 检查 `orchestrator_meta.assumptions` 包含假设说明（如 ["基于通用场景和最佳实践给出建议"]）

**验证方式**：
- 确认答案中没有"无法回答"或"信息不足"的拒绝性回复
- 确认 `followups` 字段存在且长度 ≤ 3
- 确认前端显示黄色提示框（非模态对话框，不阻塞）

---

## 向后兼容性测试

### 用例 6：未启用编排器 - 旧行为保持不变

**目标**：确保未启用编排器时，系统按原有流程工作

**测试步骤**：

1. 在左侧边栏**取消勾选**"🎯 启用智能编排器"
2. 输入问题：
   ```
   什么是 Kubernetes？
   ```
3. 点击发送

**预期结果**：

✅ **返回字段**：
- `answer` 字段存在且包含完整答案（Markdown 格式）
- `sections` 字段为 `null` 或不存在
- `followups` 字段为 `null` 或不存在
- `orchestrator_meta` 字段为 `null` 或不存在

✅ **前端渲染**：
- 使用传统气泡渲染（`MessageBubble` 组件）
- 答案显示为单一文本块，无折叠模块

**验证方式**：
- 检查 Network 标签，确认请求 body 中 `enable_orchestrator` 为 `false` 或不存在
- 检查响应中无 `sections` 字段
- 确认前端不显示 ModularAnswer 组件

---

### 用例 7：流式输出 - sections 在最终 result 中返回

**目标**：确保流式输出时，sections 和 followups 在最终 `result` 事件中正确返回

**测试步骤**：

1. 确保编排器已启用
2. 输入问题：
   ```
   RESTful API 设计最佳实践
   ```
3. 点击发送
4. 打开浏览器开发者工具，观察 Network → `/api/chat/stream` 的响应流

**预期结果**：

✅ **SSE 事件序列**：

1. **delta 事件**（多次）：
   ```
   event: delta
   data: {"text": "## 理解确认\n\n..."}
   ```
   - 逐块推送答案文本
   - 前端累积显示，但不解析 sections

2. **result 事件**（最后一次）：
   ```
   event: result
   data: {
     "answer": "完整答案文本...",
     "sources": [...],
     "sections": [
       {"id": "align_summary", "title": "理解确认", "markdown": "...", "collapsed": false},
       {"id": "core_answer", "title": "核心答案", "markdown": "...", "collapsed": false},
       ...
     ],
     "followups": ["..."],
     "orchestrator_meta": {...}
   }
   ```

✅ **前端行为**：
- 流式输出过程中，显示累积的文本
- 收到 `result` 事件后，切换为 ModularAnswer 渲染

**验证方式**：
- 确认 `delta` 事件不包含 `sections`
- 确认 `result` 事件包含完整的 `sections`、`followups`、`orchestrator_meta`
- 确认前端最终显示折叠卡片，而非文本块

---

## 边界情况测试

### 用例 8：Repair 触发 - LLM 输出格式不规范

**目标**：验证当 LLM 输出的 Markdown 不符合标准标题格式时，Repair 机制是否触发

**模拟方式**（后端手动测试）：

1. 暂时修改 `MODULAR_SYSTEM_PROMPT`，移除标题格式要求
2. 发送请求，观察后端日志
3. 检查是否触发 `repair_structure`
4. 恢复原 prompt

**预期行为**：
- 如果 `validate_sections` 失败（如缺少 "核心答案" 模块），后端应调用 `repair_structure`
- Repair 后的 sections 应符合标准格式
- 不引入新事实，只重排原内容

---

### 用例 9：空知识库 + 无联网 - 纯 LLM 模式

**目标**：验证编排器在无检索上下文时的表现

**测试步骤**：

1. 确保编排器已启用
2. 取消勾选所有知识库
3. 取消勾选联网搜索
4. 输入问题：
   ```
   Rust 语言的所有权系统如何工作？
   ```
5. 点击发送

**预期结果**：

✅ **答案生成**：
- 编排器正常工作，生成模块化答案
- 上下文字段为 "[无检索上下文]"
- 答案基于 LLM 自身知识，不依赖检索

✅ **没有崩溃或报错**

---

### 用例 10：多轮对话 - 历史上下文传递

**目标**：验证编排器在多轮对话中正确使用历史上下文

**测试步骤**：

1. 确保编排器已启用
2. 第一轮：输入
   ```
   什么是 GraphQL？
   ```
3. 等待回复
4. 第二轮：输入
   ```
   它和 REST 有什么区别？
   ```
5. 点击发送

**预期结果**：

✅ **第二轮答案**：
- **理解确认**应正确理解 "它" 指的是 GraphQL
- 答案应对比 GraphQL 和 REST（而非重新解释 GraphQL）

✅ **历史上下文**：
- 检查后端日志，确认 `history_for_llm` 包含第一轮对话
- 检查 Extractor 的输入包含历史对话摘要

---

## 性能验收标准

### 延迟要求

| 阶段             | 目标耗时       | 说明                               |
|------------------|----------------|------------------------------------|
| Extractor Call   | < 2 秒         | 需求抽取（非流式，512 tokens）     |
| Answer Call      | 首 token < 3 秒 | 流式输出，首 token 到达时间        |
| 完整流式输出     | 取决于答案长度 | 标准模式约 500-1000 tokens         |
| Parse Sections   | < 0.1 秒       | 正则解析，几乎瞬间                 |
| Repair Call      | < 3 秒         | 仅在 validate 失败时触发           |

### 兼容性检查清单

- [ ] 老前端（不传 `enable_orchestrator`）→ 后端正常返回 `answer`，无报错
- [ ] 新前端 + 老后端（无编排器服务）→ 降级为普通模式（通过 try-catch）
- [ ] 流式和非流式输出均正确返回 `sections`
- [ ] `answer` 字段始终存在，即使启用编排器（兼容旧客户端）

---

## 测试报告模板

测试完成后，请填写以下表格：

| 用例编号 | 用例名称               | 测试结果 | 备注                               |
|----------|------------------------|----------|------------------------------------|
| 1        | 知识综述 - 美国税收政策 | ✅ / ❌   | sections 包含 timeline             |
| 2        | 排障 - 接口 500 错误    | ✅ / ❌   | 包含 checklist 或 steps            |
| 3        | 选型 - OpenAI vs Ollama| ✅ / ❌   | 包含 comparison 表格               |
| 4.1      | brief 模式             | ✅ / ❌   | 答案简短，模块少                   |
| 4.2      | detailed 模式          | ✅ / ❌   | 答案详细，模块多                   |
| 4.3      | 文本关键词覆盖         | ✅ / ❌   | "简短" 关键词生效                  |
| 5        | 信息不足 - 不阻塞      | ✅ / ❌   | 给出假设答案 + followups           |
| 6        | 未启用编排器           | ✅ / ❌   | 旧行为保持                         |
| 7        | 流式输出               | ✅ / ❌   | sections 在 result 中              |
| 8        | Repair 触发            | ✅ / ❌   | 需手动模拟                         |
| 9        | 无检索上下文           | ✅ / ❌   | 纯 LLM 模式                        |
| 10       | 多轮对话               | ✅ / ❌   | 历史上下文正确传递                 |

---

## 已知限制和后续优化

### 当前限制

1. **Extractor 非流式**：需求抽取阶段需要等待 1-2 秒，用户可能感觉有延迟
   - **缓解**：前端可显示 "正在分析需求..." 的加载提示

2. **Repair 耗时**：当 LLM 输出格式不规范时，Repair 需要额外 2-3 秒
   - **缓解**：优化 MODULAR_SYSTEM_PROMPT，降低 Repair 触发率

3. **模型依赖**：编排器效果依赖 LLM 的指令遵循能力
   - **建议**：使用 GPT-4、Claude 或高质量开源模型（如 Qwen2.5、Llama3.1）

### 后续优化方向

- [ ] **并行化 Extractor**：将 Extractor 与 RAG 检索并行执行，减少总延迟
- [ ] **缓存 blueprint**：对常见意图类型缓存 blueprint 模板，跳过 Extractor
- [ ] **渐进式 Sections 渲染**：流式输出时，边生成边解析 sections（挑战：需要 LLM 按顺序输出完整模块）
- [ ] **自适应 detail_level**：根据用户历史偏好自动推荐详尽度
- [ ] **多语言支持**：当前仅支持中文 prompt，可扩展英文/多语言

---

## 附录：常见问题

### Q1: 为什么有时候 sections 为空？

**A**: 可能的原因：
1. LLM 未按要求输出 `## 标题` 格式
2. Repair 也失败了（LLM 质量不够）
3. 前端 `enable_orchestrator` 未传或为 `false`

**排查**：
- 检查后端日志，搜索 "Requirements extracted" 和 "Orchestrator: Generated X sections"
- 检查 Network 请求，确认 `enable_orchestrator: true`

---

### Q2: 如何调整模块数量？

**A**: 修改 `INTENT_BLUEPRINTS` 中的模块列表：

```python
# backend/app/schemas/orchestrator.py
INTENT_BLUEPRINTS = {
    IntentType.INFORMATION: [
        "align_summary",
        "core_answer",
        "timeline",  # 可删除此行，减少模块
        "sources",
    ],
    ...
}
```

---

### Q3: 如何禁用 Repair？

**A**: 修改 `orchestrator_service.py`：

```python
# 在 parse_sections_from_answer 中，移除 repair 逻辑
def parse_sections_from_answer(self, answer, blueprint_modules):
    sections = self._parse_sections_from_markdown(answer, blueprint_modules)
    # 注释掉 validate 和 repair
    # if not self._validate_sections(sections):
    #     sections = await self.repair_structure(answer, blueprint_modules)
    return sections
```

---

## 结语

完成以上测试后，LLM 编排器功能应具备生产就绪能力。如遇问题，请查阅：

- 后端日志：`/aidata/x-llmapp1/backend/logs/`
- 前端控制台：浏览器 F12 → Console
- 本文档：`/aidata/x-llmapp1/docs/LLM_ORCHESTRATOR_TESTS.md`

祝测试顺利！🚀
