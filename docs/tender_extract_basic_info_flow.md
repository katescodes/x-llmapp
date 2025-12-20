# 招投标应用 - 提取基本信息详细流程

## 概述

本文档详细描述招投标应用中提取项目基本信息的完整流程，包括数据流、核心组件、技术实现和可用性评估。

**流程版本**: V2 (NEW_ONLY 模式)
**生成日期**: 2025-12-20

---

## 一、整体流程架构

```
用户请求
   ↓
TenderService.extract_project_info()
   ↓
ExtractV2Service.extract_project_info_v2()
   ↓
ExtractionEngine.run()
   ├─→ RetrievalFacade.retrieve()  [检索相关文档块]
   │    └─→ NewRetriever.retrieve()
   │         └─→ 数据库查询 (doc_segments/kb_chunks)
   │         └─→ 向量相似度检索 (pgvector)
   ├─→ build_marked_context()      [构建标记的上下文]
   ├─→ call_llm()                  [调用大模型]
   └─→ extract_json()              [解析JSON结果]
   ↓
保存到数据库 (project_info表)
   ↓
返回结构化结果
```

---

## 二、详细流程说明

### 2.1 入口层 - TenderService

**文件**: `backend/app/services/tender_service.py`

**方法**: `extract_project_info(project_id, model_id, run_id, owner_id)`

**功能**:
1. 检查 cutover 模式（必须是 NEW_ONLY）
2. 创建 platform job（可选，用于任务追踪）
3. 调用 V2 抽取服务
4. 保存结果到旧表（保证前端兼容）
5. 更新运行状态

**关键代码**:
```python:792:848:backend/app/services/tender_service.py
def extract_project_info(
    self,
    project_id: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
    owner_id: Optional[str] = None,
):
    """抽取项目信息"""
    
    # 1. 检查模式
    cutover = get_cutover_config()
    extract_mode = cutover.get_mode("extract", project_id)
    if extract_mode.value != "NEW_ONLY":
        raise RuntimeError("Legacy extraction deleted. Set EXTRACT_MODE=NEW_ONLY")
    
    # 2. 创建 job（可选）
    job_id = self.jobs_service.create_job(...) if enabled
    
    # 3. 调用 v2 抽取
    from app.works.tender.extract_v2_service import ExtractV2Service
    pool = _get_pool()
    extract_v2 = ExtractV2Service(pool, self.llm)
    
    v2_result = asyncio.run(extract_v2.extract_project_info_v2(
        project_id=project_id,
        model_id=model_id,
        run_id=run_id
    ))
    
    # 4. 保存到旧表
    self.dao.upsert_project_info(project_id, data_json=data, evidence_chunk_ids=eids)
    
    # 5. 更新状态
    if run_id:
        self.dao.update_run(run_id, "success", ...)
```

---

### 2.2 V2抽取服务层 - ExtractV2Service

**文件**: `backend/app/works/tender/extract_v2_service.py`

**方法**: `extract_project_info_v2(project_id, model_id, run_id)`

**功能**:
1. 获取 embedding provider
2. 构建抽取规格（ExtractionSpec）
3. 调用通用抽取引擎
4. 返回结构化结果

**关键代码**:
```python:28:89:backend/app/works/tender/extract_v2_service.py
async def extract_project_info_v2(
    self,
    project_id: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    抽取项目信息 (v2) - 使用平台 ExtractionEngine
    
    Returns:
        {
            "data": {...},
            "evidence_chunk_ids": [...],
            "evidence_spans": [...],
            "retrieval_trace": {...}
        }
    """
    
    # 1. 获取 embedding provider
    embedding_provider = get_embedding_store().get_default()
    
    # 2. 构建 spec
    spec = build_project_info_spec()
    
    # 3. 调用引擎
    result = await self.engine.run(
        spec=spec,
        retriever=self.retriever,
        llm=self.llm,
        project_id=project_id,
        model_id=model_id,
        run_id=run_id,
        embedding_provider=embedding_provider,
    )
    
    # 4. 返回结果
    return {
        "data": result.data,
        "evidence_chunk_ids": result.evidence_chunk_ids,
        "evidence_spans": result.evidence_spans,
        "retrieval_trace": result.retrieval_trace.__dict__
    }
```

---

### 2.3 抽取规格 - ExtractionSpec

**文件**: `backend/app/works/tender/extraction_specs/project_info_v2.py`

**方法**: `build_project_info_spec()`

**功能**: 构建项目信息抽取的配置规格

**配置内容**:
```python:19:53:backend/app/works/tender/extraction_specs/project_info_v2.py
def build_project_info_spec() -> ExtractionSpec:
    """构建项目信息抽取规格"""
    
    # 加载 prompt 模板
    prompt = _load_prompt("project_info_v2.md")
    
    # 四个查询维度
    queries = {
        "base": "招标公告 项目名称 项目编号 预算金额 采购人 代理机构 投标截止 开标 时间 地点 联系人 电话",
        "technical": "技术要求 技术规范 技术参数 设备参数 性能指标 功能要求 规格 型号 参数表",
        "business": "商务条款 合同条款 付款方式 交付期 工期 质保 验收 违约责任 发票",
        "scoring": "评分标准 评标办法 评审办法 评分细则 分值 权重 加分项 否决项 资格审查",
    }
    
    # 检索参数
    top_k_per_query = 30  # 每个查询返回30个文档块
    top_k_total = 120     # 总计最多120个文档块
    
    return ExtractionSpec(
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["tender"],
        temperature=0.0,  # 保证可复现
    )
```

**Prompt模板** (`prompts/project_info_v2.md`):
- 定义了严格的 JSON 输出格式
- 包含四个主要板块:
  - `base`: 基本信息（项目名称、预算、联系人等）
  - `technical_parameters`: 技术参数（功能要求、性能指标等）
  - `business_terms`: 商务条款（付款、验收、质保等）
  - `scoring_criteria`: 评分标准（评标办法、评分细则等）

---

### 2.4 核心引擎层 - ExtractionEngine

**文件**: `backend/app/platform/extraction/engine.py`

**方法**: `run(spec, retriever, llm, project_id, ...)`

**执行步骤**:

#### 步骤1: 文档检索
```python:64:76:backend/app/platform/extraction/engine.py
# 1. 执行检索
retrieval_start = time.time()
all_chunks, query_trace = await self._retrieve_chunks(
    spec=spec,
    retriever=retriever,
    project_id=project_id,
    embedding_provider=embedding_provider,
    trace_enabled=trace_enabled,
    run_id=run_id,
    mode=mode,
)
retrieval_ms = int((time.time() - retrieval_start) * 1000)
logger.info(f"AFTER_RETRIEVAL count={len(all_chunks)} ms={retrieval_ms}")
```

**检索过程** (`_retrieve_chunks`):
- 对每个查询维度（base/technical/business/scoring）独立检索
- 使用向量相似度搜索 (pgvector)
- 去重合并结果
- 截断到总量限制 (top_k_total=120)

#### 步骤2: 构建上下文
```python:89:99:backend/app/platform/extraction/engine.py
# 2. 构建上下文
chunk_dicts = [
    {
        "chunk_id": c.chunk_id,
        "text": c.text,
        "meta": c.meta
    }
    for c in all_chunks
]
ctx = build_marked_context(chunk_dicts)
```

**上下文格式**:
```
<chunk id="chunk_abc123">
原文内容...
</chunk>

<chunk id="chunk_def456">
原文内容...
</chunk>
```

#### 步骤3: 调用大模型
```python:102:114:backend/app/platform/extraction/engine.py
# 3. 调用 LLM
messages = [
    {"role": "system", "content": spec.prompt.strip()},
    {"role": "user", "content": f"招标文件原文片段：\n{ctx}"},
]

llm_start = time.time()
out_text = await call_llm(
    messages, 
    llm, 
    model_id, 
    temperature=spec.temperature, 
    max_tokens=4096
)
```

#### 步骤4: 解析JSON结果
```python:123:136:backend/app/platform/extraction/engine.py
# 4. 解析 JSON
try:
    obj = extract_json(out_text)
except Exception as e:
    # 尝试修复
    try:
        obj = repair_json(out_text)
    except Exception as e2:
        obj = {}
```

#### 步骤5: 提取数据和证据
```python:141:165:backend/app/platform/extraction/engine.py
# 5. 提取数据和证据
if isinstance(obj, dict):
    data = obj.get("data") or obj
    evidence_chunk_ids = obj.get("evidence_chunk_ids") or []

# 6. 生成 evidence_spans
evidence_spans = self._generate_evidence_spans(all_chunks, evidence_chunk_ids)

# 7. 构建追踪信息
trace = self._build_trace(query_trace, spec, len(all_chunks), trace_enabled)
```

#### 步骤6: 返回结果
```python:180:186:backend/app/platform/extraction/engine.py
return ExtractionResult(
    data=data,
    evidence_chunk_ids=evidence_chunk_ids,
    evidence_spans=evidence_spans,
    raw_model_output=out_text,
    retrieval_trace=trace
)
```

---

### 2.5 检索层 - RetrievalFacade & NewRetriever

**文件**: `backend/app/platform/retrieval/facade.py`

**RetrievalFacade** 负责根据 cutover 模式路由到合适的检索器。

**NEW_ONLY 模式流程**:
```python:81:95:backend/app/platform/retrieval/facade.py
if mode == CutoverMode.NEW_ONLY:
    try:
        results = await self.new_retriever.retrieve(
            query=query,
            project_id=project_id,
            doc_types=doc_types,
            embedding_provider=embedding_provider,
            top_k=top_k,
            **kwargs
        )
        return results
    except Exception as e:
        raise ValueError(f"NEW_ONLY failed: {e}")
```

**NewRetriever** 检索流程:
1. 从数据库获取文档块 (doc_segments 或 kb_chunks)
2. 使用 pgvector 进行向量相似度检索
3. 根据 doc_types 过滤（例如只检索 "tender" 类型）
4. 返回 top_k 个最相关的文档块

---

## 三、数据结构

### 3.1 输入数据

**项目ID** (`project_id`): 
- 唯一标识一个招标项目

**文档来源**:
- 表: `doc_segments` (新表) 或 `kb_chunks` (旧表)
- 类型: `doc_type = 'tender'`
- 字段: `segment_id`, `content`, `position`, `embedding`

### 3.2 输出数据结构

```json
{
  "data": {
    "base": {
      "projectName": "项目名称",
      "ownerName": "招标人/业主",
      "agencyName": "代理机构",
      "bidDeadline": "投标截止时间",
      "bidOpeningTime": "开标时间",
      "budget": "预算金额",
      "maxPrice": "最高限价",
      "bidBond": "投标保证金",
      "schedule": "工期要求",
      "quality": "质量要求",
      "location": "项目地点/交付地点",
      "contact": "联系人与电话"
    },
    "technical_parameters": [
      {
        "category": "分类",
        "item": "条目标题",
        "requirement": "要求描述",
        "parameters": [
          {
            "name": "参数名",
            "value": "参数值",
            "unit": "单位",
            "remark": "备注"
          }
        ],
        "evidence_chunk_ids": ["chunk_xxx"]
      }
    ],
    "business_terms": [
      {
        "term": "条款名称",
        "requirement": "条款内容",
        "evidence_chunk_ids": ["chunk_xxx"]
      }
    ],
    "scoring_criteria": {
      "evaluationMethod": "评标办法",
      "items": [
        {
          "category": "评分大项",
          "item": "评分细则",
          "score": "分值",
          "rule": "得分规则",
          "evidence_chunk_ids": ["chunk_xxx"]
        }
      ]
    }
  },
  "evidence_chunk_ids": ["chunk_xxx", "chunk_yyy"],
  "evidence_spans": [
    {
      "source": "doc_version_id",
      "page_no": 5,
      "snippet": "证据片段..."
    }
  ],
  "retrieval_trace": {
    "retrieval_provider": "new",
    "retrieval_strategy": "multi_query",
    "queries": {
      "base": {"retrieved_count": 30, "top_ids": [...]},
      "technical": {"retrieved_count": 30, ...},
      "business": {"retrieved_count": 30, ...},
      "scoring": {"retrieved_count": 30, ...}
    },
    "top_k_per_query": 30,
    "top_k_total": 120,
    "retrieved_count_total": 120,
    "doc_types": ["tender"]
  }
}
```

---

## 四、关键技术点

### 4.1 多查询检索策略

使用4个不同维度的查询关键词，确保覆盖完整信息：
- **base**: 基本信息相关（项目名称、预算、联系人等）
- **technical**: 技术参数相关（技术要求、性能指标等）
- **business**: 商务条款相关（付款、验收、质保等）
- **scoring**: 评分标准相关（评标办法、评分细则等）

### 4.2 向量检索 (pgvector)

- 使用 PostgreSQL 的 pgvector 扩展
- 基于文档块的 embedding 向量
- 计算查询向量与文档向量的余弦相似度
- 返回最相似的 top_k 个结果

### 4.3 上下文标记 (Marked Context)

为每个文档块添加 `<chunk id="...">` 标记：
- 便于 LLM 理解文档结构
- 便于追溯证据来源
- 便于后续验证和审计

### 4.4 JSON 解析与修复

- 使用 `extract_json()` 提取 LLM 输出中的 JSON
- 支持 ```json ... ``` 代码块格式
- 如果解析失败，使用 `repair_json()` 尝试修复
- 处理常见格式问题（缺少引号、逗号等）

### 4.5 证据追踪

- **evidence_chunk_ids**: 引用的文档块ID列表
- **evidence_spans**: 包含页码和文本片段的详细证据
- **retrieval_trace**: 检索过程的完整追踪信息

---

## 五、配置参数

### 5.1 环境变量

```bash
# Cutover 模式控制
EXTRACT_MODE=NEW_ONLY           # 抽取模式（必须）
RETRIEVAL_MODE=NEW_ONLY         # 检索模式（必须）

# 检索参数
V2_RETRIEVAL_TOPK_PER_QUERY=30  # 每个查询的 top-k
V2_RETRIEVAL_TOPK_TOTAL=120     # 总计 top-k

# 查询自定义（JSON格式）
V2_PROJECT_INFO_QUERIES_JSON='{"base": "...", "technical": "...", ...}'

# 追踪控制
EXTRACT_TRACE_ENABLED=true      # 是否启用追踪信息
```

### 5.2 数据库依赖

**必需的表**:
- `documents`: 文档基本信息
- `document_versions`: 文档版本
- `doc_segments`: 文档块（新表，推荐）
- `kb_chunks`: 文档块（旧表，向后兼容）
- `project_info`: 项目信息存储表

**必需的扩展**:
- `pgvector`: 向量相似度检索

---

## 六、可用性评估

### 6.1 功能完整性 ✅

| 功能模块 | 状态 | 说明 |
|---------|------|------|
| 基本信息抽取 | ✅ 可用 | 支持项目名称、预算、联系人等12个字段 |
| 技术参数抽取 | ✅ 可用 | 支持参数化结构（name/value/unit/remark） |
| 商务条款抽取 | ✅ 可用 | 支持付款、验收、质保等条款 |
| 评分标准抽取 | ✅ 可用 | 支持评分大项、细则、分值、规则 |
| 证据追溯 | ✅ 可用 | 支持 chunk_id 和 evidence_span |
| 检索追踪 | ✅ 可用 | 支持完整的检索过程追踪 |

### 6.2 技术架构 ✅

| 组件 | 状态 | 说明 |
|------|------|------|
| ExtractionEngine | ✅ 可用 | 通用抽取引擎，架构清晰 |
| RetrievalFacade | ✅ 可用 | 支持 cutover 模式切换 |
| NewRetriever | ✅ 可用 | 基于 pgvector 的向量检索 |
| JSON 解析 | ✅ 可用 | 支持提取和修复 |
| 多查询策略 | ✅ 可用 | 4维度查询，覆盖全面 |

### 6.3 数据兼容性 ✅

| 数据源 | 状态 | 说明 |
|--------|------|------|
| doc_segments (新表) | ✅ 优先 | 推荐使用，结构更清晰 |
| kb_chunks (旧表) | ✅ 兼容 | 向后兼容，自动回退 |
| 旧表写入 | ✅ 可用 | 保证前端兼容性 |

### 6.4 运维监控 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| 日志追踪 | ✅ 可用 | 详细的结构化日志 |
| 时间统计 | ✅ 可用 | 各阶段耗时统计 |
| 错误处理 | ✅ 可用 | 分级错误处理和回退 |
| Job 追踪 | ✅ 可选 | 支持 platform job 追踪 |

---

## 七、已知限制

### 7.1 模式限制

- ❌ 仅支持 NEW_ONLY 模式，不支持旧版抽取
- ❌ 如果 `EXTRACT_MODE != NEW_ONLY`，会直接抛出异常

### 7.2 性能限制

- ⚠️ 每次抽取最多检索 120 个文档块 (top_k_total)
- ⚠️ LLM 调用有 max_tokens=4096 限制
- ⚠️ 大型招标文档可能需要多次迭代

### 7.3 数据质量依赖

- ⚠️ 依赖文档分块质量（chunk 切分合理性）
- ⚠️ 依赖 embedding 质量（向量表示准确性）
- ⚠️ 依赖 LLM 能力（理解和抽取能力）

---

## 八、使用示例

### 8.1 Python 调用示例

```python
from app.services.tender_service import TenderService

# 初始化服务
service = TenderService(pool=db_pool, llm=llm_orchestrator)

# 调用抽取
result = service.extract_project_info(
    project_id="proj_123",
    model_id="gpt-4",
    run_id="run_456",
    owner_id="user_789"
)

# 结果包含在 run 的 result_json 中
```

### 8.2 API 调用示例 (假设)

```bash
POST /api/v1/tender/projects/{project_id}/extract-info
Content-Type: application/json

{
  "model_id": "gpt-4",
  "run_id": "run_456"
}
```

---

## 九、故障排查

### 9.1 常见错误

#### 错误1: "Legacy extraction deleted"
```
RuntimeError: Legacy extraction deleted. Set EXTRACT_MODE=NEW_ONLY
```
**原因**: 环境变量 `EXTRACT_MODE` 不是 NEW_ONLY  
**解决**: 设置 `export EXTRACT_MODE=NEW_ONLY`

#### 错误2: "No embedding provider configured"
```
ValueError: No embedding provider configured
```
**原因**: embedding provider 未配置  
**解决**: 检查 embedding_provider_store 配置

#### 错误3: "No chunks found"
```
WARNING: No chunks found for project {project_id}
```
**原因**: 项目没有上传招标文档，或文档未分块  
**解决**: 检查 doc_segments 或 kb_chunks 表中是否有数据

#### 错误4: JSON 解析失败
```
ERROR: JSON解析失败: Expecting value: line 1 column 1
```
**原因**: LLM 输出格式不正确  
**解决**: 
- 检查 prompt 模板
- 尝试不同的 model_id
- 查看 raw_model_output 日志

### 9.2 调试建议

1. **启用详细日志**:
   ```python
   import logging
   logging.getLogger("app.platform.extraction").setLevel(logging.DEBUG)
   ```

2. **启用追踪**:
   ```bash
   export EXTRACT_TRACE_ENABLED=true
   ```

3. **查看检索结果**:
   - 检查 `retrieval_trace` 中的 `retrieved_count`
   - 检查 `queries` 各维度的检索数量

4. **查看 LLM 输出**:
   - 检查 `raw_model_output` 字段
   - 查看是否包含有效的 JSON

---

## 十、总结

### ✅ 可用性结论

**招投标应用的提取基本信息功能是可用的**，具备以下特点：

1. **架构清晰**: 分层设计，职责明确
2. **功能完整**: 支持四大板块信息抽取
3. **证据可追溯**: 完整的证据链和追踪信息
4. **性能可控**: 分阶段执行，有时间统计
5. **错误处理完善**: 多级回退和错误处理
6. **向后兼容**: 支持新旧数据表

### ⚠️ 注意事项

1. 必须设置 `EXTRACT_MODE=NEW_ONLY`
2. 必须配置 embedding provider
3. 必须有招标文档数据（doc_segments 或 kb_chunks）
4. LLM 能力影响抽取质量

### 🚀 推荐配置

```bash
# 环境变量
export EXTRACT_MODE=NEW_ONLY
export RETRIEVAL_MODE=NEW_ONLY
export V2_RETRIEVAL_TOPK_PER_QUERY=30
export V2_RETRIEVAL_TOPK_TOTAL=120
export EXTRACT_TRACE_ENABLED=true

# LLM 模型
推荐使用: gpt-4, gpt-4-turbo, claude-3-opus 等高能力模型

# 数据库
确保安装: pgvector 扩展
确保有数据: doc_segments 或 kb_chunks 表
```

---

## 附录

### A. 相关文件清单

```
backend/app/
├── services/
│   ├── tender_service.py               # 入口服务
│   └── dao/
│       └── tender_dao.py                # 数据访问层
├── works/tender/
│   ├── extract_v2_service.py           # V2 抽取服务
│   ├── extraction_specs/
│   │   ├── project_info_v2.py          # 项目信息规格
│   │   └── __init__.py
│   └── prompts/
│       └── project_info_v2.md          # Prompt 模板
└── platform/
    ├── extraction/
    │   ├── engine.py                   # 核心引擎
    │   ├── types.py                    # 类型定义
    │   ├── context.py                  # 上下文构建
    │   ├── json_utils.py               # JSON 工具
    │   └── llm_adapter.py              # LLM 适配器
    └── retrieval/
        ├── facade.py                   # 检索门面
        └── new_retriever.py            # 新检索器
```

### B. 数据库表结构

```sql
-- 文档表
CREATE TABLE documents (
    document_id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL,
    doc_type VARCHAR NOT NULL,
    ...
);

-- 文档版本表
CREATE TABLE document_versions (
    doc_version_id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    ...
);

-- 文档块表（新）
CREATE TABLE doc_segments (
    segment_id VARCHAR PRIMARY KEY,
    doc_version_id VARCHAR NOT NULL,
    content TEXT NOT NULL,
    position INTEGER,
    embedding VECTOR(1536),
    ...
);

-- 项目信息表
CREATE TABLE project_info (
    project_id VARCHAR PRIMARY KEY,
    data_json JSONB,
    evidence_chunk_ids TEXT[],
    updated_at TIMESTAMP,
    ...
);
```

### C. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v2 | 2025-12 | 基于 ExtractionEngine 的新架构 |
| v1 | 2024-xx | 旧版抽取（已删除） |

---

**文档生成**: AI Assistant  
**最后更新**: 2025-12-20  
**状态**: 可用 ✅

