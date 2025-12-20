# LLM Orchestrator 文档索引

## 📚 文档导航

### 🚀 快速开始
- **[快速入门指南](./LLM_ORCHESTRATOR_QUICKSTART.md)**
  - 5 分钟体验编排器
  - 基本使用示例
  - 常见问题解答
  - **推荐首次使用者阅读**

### 🧪 测试验收
- **[验收测试用例](./LLM_ORCHESTRATOR_TESTS.md)**
  - 10+ 完整测试用例
  - 性能验收标准
  - 故障排查指南
  - 测试报告模板
  - **推荐部署前完整执行**

### 📖 实施文档
- **[实施完成报告](../LLM_ORCHESTRATOR_IMPLEMENTATION.md)**
  - 完整技术实现细节
  - 文件清单和代码说明
  - 架构设计和数据流
  - 向后兼容性说明
  - **推荐开发者阅读**

---

## 🎯 核心功能概览

### 功能清单

- ✅ **需求理解**：8 种意图类型自动识别
- ✅ **模块化答案**：16 种标准模块，结构化渲染
- ✅ **详尽度控制**：精简/标准/详细三档切换
- ✅ **少追问策略**：先假设给答案，再提示澄清问题（≤3）
- ✅ **结构修复**：自动修复格式不规范的 LLM 输出
- ✅ **折叠渲染**：前端卡片式展示，可展开/折叠
- ✅ **向后兼容**：老字段继续返回，不破坏旧客户端

---

## 📂 代码结构

### 后端

```
backend/app/
├── schemas/
│   ├── orchestrator.py          # 数据模型（IntentType, RequirementJSON, ChatSection）
│   └── chat.py                  # ChatRequest/ChatResponse（增加编排器字段）
├── services/
│   └── orchestrator/
│       ├── __init__.py
│       ├── orchestrator_service.py  # 核心服务类
│       └── prompts.py           # Prompt 模板（Extractor, Modular, Repair）
└── routers/
    └── chat.py                  # /api/chat 和 /api/chat/stream（集成编排器）
```

### 前端

```
frontend/src/
├── types/
│   ├── index.ts                 # ChatSection, DetailLevel, ChatRequestPayload
│   └── orchestrator.ts          # 编排器专用类型
└── components/
    ├── ModularAnswer.tsx        # 折叠卡片组件（核心）
    ├── MessageList.tsx          # 集成 ModularAnswer
    └── ChatLayout.tsx           # 编排器开关和详尽度选择
```

---

## 🔧 快速导航

### 我想...

| 需求                          | 推荐文档                                      | 章节                     |
|-------------------------------|-----------------------------------------------|--------------------------|
| **快速体验编排器**            | [快速入门指南](./LLM_ORCHESTRATOR_QUICKSTART.md) | 第 1-3 节                |
| **测试各种场景**              | [验收测试用例](./LLM_ORCHESTRATOR_TESTS.md)   | 用例 1-10                |
| **了解技术实现**              | [实施完成报告](../LLM_ORCHESTRATOR_IMPLEMENTATION.md) | 实施内容总结             |
| **调优 Prompt**               | [实施完成报告](../LLM_ORCHESTRATOR_IMPLEMENTATION.md) | 技术细节 → Prompt 设计   |
| **自定义模块**                | [快速入门指南](./LLM_ORCHESTRATOR_QUICKSTART.md) | Q3: 可以自定义模块吗？   |
| **排查问题**                  | [验收测试用例](./LLM_ORCHESTRATOR_TESTS.md)   | 附录：常见问题           |
| **查看性能指标**              | [验收测试用例](./LLM_ORCHESTRATOR_TESTS.md)   | 性能验收标准             |
| **了解向后兼容性**            | [实施完成报告](../LLM_ORCHESTRATOR_IMPLEMENTATION.md) | 技术细节 → 向后兼容性保证 |

---

## 🌟 核心概念速查

### 意图类型（IntentType）

| 类型          | 说明                 | 典型模块                               |
|---------------|----------------------|----------------------------------------|
| information   | 获取信息/知识综述    | timeline, concepts, controversy        |
| howto         | 教程/操作指南        | prerequisites, steps, examples         |
| decision      | 选型/决策            | comparison, next_steps                 |
| troubleshoot  | 排障/调试            | checklist, steps, pitfalls             |
| writing       | 写作/生成文档        | outline, examples                      |
| compute       | 计算/推理            | steps, verification                    |
| research      | 研究/深度分析        | timeline, controversy, sources         |
| other         | 其他                 | core_answer, next_steps                |

### 模块类型（16 种）

**必需模块**：
- `align_summary` - 理解确认
- `core_answer` - 核心答案

**可选模块**：
- `timeline` - 时间线
- `concepts` - 核心概念
- `controversy` - 争议与口径
- `examples` - 示例与案例
- `comparison` - 对比矩阵
- `checklist` - 检查清单
- `steps` - 执行步骤
- `pitfalls` - 常见陷阱
- `next_steps` - 下一步建议
- `sources` - 参考来源
- `verification` - 核对路径
- `alternatives` - 替代方案
- `prerequisites` - 前置条件
- `outline` - 大纲结构

### 详尽度级别（DetailLevel）

- **brief** - 精简：2-3 段，3-4 模块，0-1 例子
- **normal** - 标准：3-5 段，4-6 模块，1-2 例子（默认）
- **detailed** - 详细：5-8 段，6-10 模块，3-4 例子

---

## 📊 流程图

### 完整流程

```
用户输入
   ↓
启用编排器？
   ├─ 否 → [原有流程] → 文本块渲染
   └─ 是
       ↓
   1️⃣ Extractor Call（非流式，1-2秒）
       ↓
   RequirementJSON
   (intent, detail_level, blueprint_modules, ...)
       ↓
   2️⃣ Modular Answer Call（流式，逐块推送）
       ↓
   完整答案（Markdown，包含 ## 标题）
       ↓
   3️⃣ Parse Sections（正则解析，<0.1秒）
       ↓
   sections 列表
       ↓
   Validate OK？
   ├─ 是 → 前端折叠渲染
   └─ 否 → 4️⃣ Repair Call（2-3秒）→ 前端折叠渲染
```

### 数据流

```
前端 ChatLayout
   ↓ {enable_orchestrator: true, detail_level: "normal", message: "..."}
后端 /api/chat/stream
   ↓ [Extractor]
   ↓ RequirementJSON
   ↓ [Modular Answer]
   ↓ event: delta (多次)
   ↓ event: result (最后)
   ↓ {answer: "...", sections: [...], followups: [...], orchestrator_meta: {...}}
前端 MessageList
   ↓ [ModularAnswer 组件]
   ↓ 折叠卡片渲染
```

---

## 🎓 学习路径

### 初学者路径

1. **阅读快速入门指南**（10 分钟）
   - 启动服务
   - 启用编排器
   - 测试 3 个基本示例

2. **执行核心测试用例**（30 分钟）
   - 用例 1：知识综述
   - 用例 2：排障
   - 用例 3：选型

3. **尝试自定义问题**（20 分钟）
   - 根据你的业务场景提问
   - 观察生成的模块是否符合预期

### 开发者路径

1. **阅读实施完成报告**（30 分钟）
   - 了解技术架构
   - 查看代码结构
   - 理解数据流

2. **阅读源码**（1-2 小时）
   - `orchestrator_service.py` - 核心逻辑
   - `prompts.py` - Prompt 设计
   - `ModularAnswer.tsx` - 前端渲染

3. **执行完整测试**（1 小时）
   - 执行全部 10+ 测试用例
   - 填写测试报告
   - 验证性能指标

4. **自定义扩展**（按需）
   - 增加自定义模块
   - 调优 Prompt
   - 优化性能

---

## 🔍 常见场景示例

### 场景 1：技术学习

**输入**：
```
详细介绍 Kubernetes 的架构和核心组件
```

**生成模块**：
- 理解确认
- 核心答案
- 核心概念（Pod, Node, Master 等）
- 架构图/对比矩阵（控制平面 vs 工作节点）
- 示例与案例
- 下一步建议

---

### 场景 2：故障排查

**输入**：
```
MySQL 慢查询应该如何定位和优化？
```

**生成模块**：
- 理解确认
- 核心答案
- 检查清单（开启慢查询日志、查看执行计划等）
- 执行步骤（1. 定位慢查询，2. 分析索引，3. 优化查询）
- 常见陷阱（索引失效场景、锁等待等）
- 下一步建议

---

### 场景 3：技术选型

**输入**：
```
在自托管场景下，选择 PostgreSQL 还是 MySQL？主要考虑性能和可扩展性。
```

**生成模块**：
- 理解确认
- 核心答案
- 对比矩阵（性能、功能、生态、运维成本等）
- 示例与案例（典型应用场景）
- 下一步建议（POC 测试建议）

---

### 场景 4：深度研究

**输入**：
```
分析区块链技术的发展历程和未来趋势
```

**生成模块**：
- 理解确认
- 核心答案
- 时间线（比特币 → 以太坊 → DeFi → NFT → ...）
- 核心概念（共识机制、智能合约等）
- 争议与口径（能耗问题、去中心化程度等）
- 参考来源
- 核对路径（如何验证信息真实性）

---

## 💡 提示与技巧

### 获得更好答案的技巧

1. **明确你的意图**
   - ❌ "告诉我关于 Docker"
   - ✅ "我想学习 Docker，请介绍核心概念和基本使用"

2. **利用关键词**
   - 想要简短答案：加 "简短说明"、"一句话概括"
   - 想要详细答案：加 "详细展开"、"多举些例子"

3. **提供上下文**
   - ❌ "如何部署？"
   - ✅ "在 Ubuntu 20.04 上如何部署 Docker 应用？"

4. **分步提问**
   - 第一轮：概念理解
   - 第二轮：深入某个细节
   - 编排器会利用历史上下文

---

### 调优建议

**调整模块数量**：
```python
# backend/app/schemas/orchestrator.py
INTENT_BLUEPRINTS = {
    IntentType.INFORMATION: [
        "align_summary",
        "core_answer",
        # "timeline",  # 注释掉减少模块
        "next_steps",
    ],
}
```

**调整详尽度参数**：
```python
# backend/app/services/orchestrator/prompts.py
DETAIL_LEVEL_PARAMS = {
    "brief": {
        "max_sections": 3,  # 调整最大模块数
        "core_answer_paragraphs": "2-3",  # 调整段落数
    },
}
```

**优化 Prompt**：
编辑 `backend/app/services/orchestrator/prompts.py` 中的三个 Prompt：
- `EXTRACTOR_PROMPT` - 调整需求理解的指令
- `MODULAR_SYSTEM_PROMPT` - 调整答案生成的格式要求
- `REPAIR_PROMPT` - 调整修复的策略

---

## 🆘 获取帮助

### 问题排查流程

1. **查看前端控制台**
   - 打开浏览器 F12 → Console
   - 查找错误信息

2. **查看网络请求**
   - F12 → Network → 找到 `/api/chat/stream`
   - 检查请求 body 和响应内容

3. **查看后端日志**
   - `tail -f /aidata/x-llmapp1/backend/logs/app.log`
   - 搜索 "Orchestrator" 相关日志

4. **参考常见问题**
   - [快速入门指南 - 常见问题](./LLM_ORCHESTRATOR_QUICKSTART.md#常见问题)
   - [测试用例 - 附录：常见问题](./LLM_ORCHESTRATOR_TESTS.md#附录常见问题)

---

## 📞 联系与支持

- **实施日期**：2025-12-17
- **代码仓库**：`/aidata/x-llmapp1`
- **文档位置**：
  - `docs/LLM_ORCHESTRATOR_INDEX.md`（本文档）
  - `docs/LLM_ORCHESTRATOR_QUICKSTART.md`
  - `docs/LLM_ORCHESTRATOR_TESTS.md`
  - `LLM_ORCHESTRATOR_IMPLEMENTATION.md`

---

## 🎉 开始使用

选择你的角色：

- **首次使用者** → [快速入门指南](./LLM_ORCHESTRATOR_QUICKSTART.md)
- **QA 测试** → [验收测试用例](./LLM_ORCHESTRATOR_TESTS.md)
- **开发者** → [实施完成报告](../LLM_ORCHESTRATOR_IMPLEMENTATION.md)

祝你使用愉快！🚀

