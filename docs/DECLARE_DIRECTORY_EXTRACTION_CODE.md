# 📋 申报书目录抽取代码位置清单

## 🎯 概述

申报书应用的"目录抽取"功能，用于从申报通知文档中自动提取申报书的目录结构（章节、层级、必填项等）。

---

## 📂 核心文件清单

### 1. **API 路由层** 🔌

#### `/backend/app/routers/declare.py`

**关键接口：**

**1.1 生成目录**
```python
@router.post("/projects/{project_id}/directory/generate", response_model=RunOut)
def generate_directory(
    project_id: str,
    bg: BackgroundTasks,
    req: Request,
    sync: int = 0,
    model_id: Optional[str] = None,
    user=Depends(get_current_user_sync),
):
    """生成申报书目录"""
```

- **URL**: `POST /api/apps/declare/projects/{project_id}/directory/generate`
- **功能**: 触发目录生成任务（支持同步/异步）
- **参数**:
  - `project_id`: 项目ID
  - `sync`: 0=异步, 1=同步
  - `model_id`: 可选的LLM模型ID
- **调用**: `service.generate_directory()`

**1.2 获取目录节点**
```python
@router.get("/projects/{project_id}/directory/nodes")
def get_directory_nodes(project_id: str, user=Depends(get_current_user_sync)):
    """获取目录节点"""
    dao = _get_dao()
    nodes = dao.get_active_directory_nodes(project_id)
    return {"nodes": nodes}
```

- **URL**: `GET /api/apps/declare/projects/{project_id}/directory/nodes`
- **功能**: 获取当前项目的目录节点列表
- **返回**: `{"nodes": [...]}`

---

### 2. **服务层** 🔧

#### `/backend/app/services/declare_service.py`

**关键方法：**

```python
def generate_directory(
    self,
    project_id: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
):
    """生成申报书目录（同步入口）"""
    from app.services.db.postgres import _get_pool
    
    pool = _get_pool()
    extract_v2 = DeclareExtractV2Service(pool, self.llm)
    
    try:
        result = run_async(extract_v2.generate_directory(
            project_id=project_id,
            model_id=model_id,
            run_id=run_id,
        ))
        
        # 提取 nodes
        nodes = result.get("data", {}).get("nodes", [])
        if not nodes:
            raise ValueError("Directory nodes empty")
        
        # 后处理：排序 + 构建树
        nodes_sorted = sorted(nodes, key=lambda n: (n.get("level", 99), n.get("order_no", 0)))
        nodes_with_tree = self._build_directory_tree(nodes_sorted)
        
        # 保存（版本化）
        version_id = self.dao.create_directory_version(project_id, source="notice", run_id=run_id)
        self.dao.upsert_directory_nodes(version_id, project_id, nodes_with_tree)
        
        # 更新 run 状态
        if run_id:
            self.dao.update_run(run_id, status="completed", result={"nodes_count": len(nodes_with_tree)})
        
        return {"nodes": nodes_with_tree, "version_id": version_id}
    
    except Exception as e:
        logger.error(f"generate_directory failed: {e}", exc_info=True)
        if run_id:
            self.dao.update_run(run_id, status="failed", error=str(e))
        raise
```

**职责：**
1. 调用 V2 抽取服务
2. 对返回的节点排序
3. 构建树形结构（`_build_directory_tree`）
4. 保存到数据库（版本化）
5. 更新 run 状态

---

### 3. **Work 层（V2 抽取服务）** 🏗️

#### `/backend/app/works/declare/extract_v2_service.py`

**核心类：`DeclareExtractV2Service`**

```python
async def generate_directory(
    self,
    project_id: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    生成申报书目录
    
    Returns:
        {
            "data": {"nodes": [...]},
            "evidence_chunk_ids": [...],
            "evidence_spans": [...],
            "retrieval_trace": {...}
        }
    """
    logger.info(f"DeclareExtractV2: generate_directory start project_id={project_id}")
    
    embedding_provider = get_embedding_store().get_default()
    if not embedding_provider:
        raise ValueError("No embedding provider configured")
    
    spec = build_directory_spec()
    
    result = await self.engine.run(
        spec=spec,
        retriever=self.retriever,
        llm=self.llm,
        project_id=project_id,
        model_id=model_id,
        run_id=run_id,
        embedding_provider=embedding_provider,
    )
    
    logger.info(
        f"DeclareExtractV2: generate_directory done "
        f"nodes_count={len(result.data.get('nodes', [])) if isinstance(result.data, dict) else 0} "
        f"evidence={len(result.evidence_chunk_ids)}"
    )
    
    return {
        "data": result.data,
        "evidence_chunk_ids": result.evidence_chunk_ids,
        "evidence_spans": result.evidence_spans,
        "retrieval_trace": result.retrieval_trace.__dict__ if result.retrieval_trace else {}
    }
```

**职责：**
1. 获取 embedding provider
2. 构建抽取规格（`build_directory_spec()`）
3. 调用 `ExtractionEngine.run()` 执行抽取
4. 返回结构化结果（包含证据链）

**依赖：**
- `ExtractionEngine`: 平台级抽取引擎
- `RetrievalFacade`: 检索服务
- `build_directory_spec()`: 构建抽取规格

---

### 4. **抽取规格 (Spec)** 📋

#### `/backend/app/works/declare/extraction_specs/directory_v2.py`

**核心函数：`build_directory_spec()`**

```python
def build_directory_spec() -> ExtractionSpec:
    """构建目录抽取规格"""
    prompt = _load_prompt("directory_v2.md")
    
    queries: Dict[str, str] = {
        "structure": os.getenv("DECLARE_DIRECTORY_QUERY_STRUCTURE", "申报书目录 申报书格式 申报书组成 目录结构 章节"),
        "template": os.getenv("DECLARE_DIRECTORY_QUERY_TEMPLATE", "附件 模板 申报书模板 格式范本 一、二、三、四"),
        "requirements": os.getenv("DECLARE_DIRECTORY_QUERY_REQUIREMENTS", "必填 必须提交 需提供 材料要求"),
    }
    
    top_k_per_query = int(os.getenv("DECLARE_DIRECTORY_TOPK_PER_QUERY", "30"))
    top_k_total = int(os.getenv("DECLARE_DIRECTORY_TOPK_TOTAL", "120"))
    
    return ExtractionSpec(
        task_type="directory",
        prompt=prompt,
        queries=queries,
        topk_per_query=top_k_per_query,
        topk_total=top_k_total,
        doc_types=["declare_notice"],  # 仅检索申报通知文档
        temperature=0.0,
        schema_model=DirectoryResultV2
    )
```

**配置项（环境变量）：**

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DECLARE_DIRECTORY_QUERY_STRUCTURE` | "申报书目录 申报书格式 申报书组成 目录结构 章节" | 结构查询关键词 |
| `DECLARE_DIRECTORY_QUERY_TEMPLATE` | "附件 模板 申报书模板 格式范本 一、二、三、四" | 模板查询关键词 |
| `DECLARE_DIRECTORY_QUERY_REQUIREMENTS` | "必填 必须提交 需提供 材料要求" | 要求查询关键词 |
| `DECLARE_DIRECTORY_TOPK_PER_QUERY` | "30" | 每个查询返回的 Top-K |
| `DECLARE_DIRECTORY_TOPK_TOTAL` | "120" | 总共返回的 Top-K |

**职责：**
1. 加载 Prompt 模板
2. 定义检索查询（多个查询提高召回）
3. 设置检索参数（Top-K）
4. 限定文档类型（仅 `declare_notice`）
5. 绑定输出 Schema（`DirectoryResultV2`）

---

### 5. **Prompt 模板** 💬

#### `/backend/app/works/declare/prompts/directory_v2.md`

**内容摘要：**

```markdown
你是一个专业的申报文档分析专家，请根据提供的申报通知原文片段（包括通知正文和附件模板），严格抽取申报书应提交的目录结构。

要求：
1.  输出必须是严格的 JSON 格式，包含 `data` 和 `evidence_chunk_ids` 两个顶级字段。
2.  `data` 字段下必须包含一个 `nodes` 数组，每个元素代表一个目录章节。
3.  每个 `node` 必须包含以下字段：
    -   `title`: 章节标题 (string, 非空)
    -   `level`: 章节层级 (integer, 1-6)
    -   `order_no`: 章节序号 (integer, 必须是整数，用于排序)
    -   `parent_ref`: 可选的父节点标题或本地ID (string, 可为空，用于辅助构建树结构)
    -   `required`: 该章节是否为必须提交 (boolean, 无法确定时默认为 true)
    -   `notes`: 可选的说明或备注 (string, 可为空)
    -   `evidence_chunk_ids`: 引用原文中支持该章节内容的 `<chunk id="...">` 列表 (string array, 必须来自输入片段的 chunk id)
4.  `evidence_chunk_ids` 必须包含在输入原文片段中出现的 `<chunk id="...">`。
...
11. 重点关注申报通知中的"附件"、"申报书模板"、"申报书格式"等部分，这些通常包含目录结构信息。
12. 目录章节通常使用"一、""（一）""1."等编号，请准确识别层级关系。

申报通知原文片段：
{ctx}

请输出 JSON 格式的申报书目录：
```

**关键指令：**
- 重点关注"附件"、"模板"、"格式"部分
- 识别"一、（一）、1."等编号的层级
- 必须返回结构化的 `nodes` 数组
- 每个节点必须包含证据 `evidence_chunk_ids`

---

### 6. **数据模型 (Schema)** 📊

#### `/backend/app/works/declare/schemas/directory_v2.py`

**核心类：**

**6.1 `DirectoryNodeV2`**
```python
class DirectoryNodeV2(BaseModel):
    """单个目录节点"""
    title: str = Field(..., min_length=1, description="章节标题")
    level: int = Field(..., ge=1, le=6, description="章节层级")
    order_no: int = Field(..., description="章节序号")
    parent_ref: Optional[str] = Field(None, description="引用父节点标题或本地ID")
    required: bool = Field(True, description="该章节是否为必须提交")
    notes: Optional[str] = Field(None, description="说明或备注")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="证据片段ID列表")
```

**字段说明：**
- `title`: 章节标题（如"一、企业基本情况"）
- `level`: 层级（1-6）
  - 1: 一级标题（如"一、"）
  - 2: 二级标题（如"（一）"）
  - 3: 三级标题（如"1."）
- `order_no`: 排序序号（整数）
- `parent_ref`: 父节点引用（用于构建树）
- `required`: 是否必填
- `notes`: 备注说明
- `evidence_chunk_ids`: 支持该节点的证据片段ID列表

**6.2 `DirectoryDataV2`**
```python
class DirectoryDataV2(BaseModel):
    """目录数据"""
    nodes: List[DirectoryNodeV2] = Field(..., min_items=1, description="目录节点列表")
```

**6.3 `DirectoryResultV2`**
```python
class DirectoryResultV2(BaseModel):
    """目录生成结果"""
    data: DirectoryDataV2 = Field(..., description="结构化目录数据")
    evidence_chunk_ids: List[str] = Field(default_factory=list, description="所有引用的证据片段ID列表")
    
    @root_validator(pre=True)
    def collect_all_evidence_chunk_ids(cls, values):
        """自动收集所有节点的 evidence_chunk_ids 到顶层"""
        # 自动聚合所有节点的证据ID
        ...
```

**特性：**
- Pydantic 模型提供自动验证
- `root_validator` 自动聚合所有节点的证据ID到顶层

---

## 🔄 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│  前端: 点击"生成目录"按钮                                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  API Router: POST /api/apps/declare/projects/{id}/directory │
│              /generate                                       │
│  文件: backend/app/routers/declare.py                        │
│  函数: generate_directory()                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Service Layer: DeclareService.generate_directory()         │
│  文件: backend/app/services/declare_service.py               │
│  职责:                                                       │
│  1. 调用 V2 抽取服务                                         │
│  2. 节点排序 + 构建树                                        │
│  3. 保存到数据库                                             │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Work Layer: DeclareExtractV2Service.generate_directory()   │
│  文件: backend/app/works/declare/extract_v2_service.py       │
│  职责:                                                       │
│  1. 获取 embedding provider                                  │
│  2. 构建抽取规格                                             │
│  3. 调用 ExtractionEngine                                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Spec Builder: build_directory_spec()                       │
│  文件: backend/app/works/declare/extraction_specs/          │
│        directory_v2.py                                       │
│  职责:                                                       │
│  1. 加载 Prompt 模板                                         │
│  2. 定义检索查询（3个查询）                                  │
│  3. 设置 Top-K 参数                                          │
│  4. 绑定输出 Schema                                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
     ┌──────────┐   ┌──────────┐   ┌──────────┐
     │ Prompt   │   │ Queries  │   │ Schema   │
     │ 模板     │   │ 检索词   │   │ 验证     │
     └──────────┘   └──────────┘   └──────────┘
     directory_v2   structure      DirectoryResultV2
     .md           template
                   requirements
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  ExtractionEngine: 执行抽取                                  │
│  文件: backend/app/platform/extraction/engine.py             │
│  步骤:                                                       │
│  1. 检索相关文档片段（向量检索）                             │
│  2. 组装 Prompt + Context                                    │
│  3. 调用 LLM 生成结构化输出                                  │
│  4. Pydantic 验证 + 解析                                     │
│  5. 返回 nodes + evidence_chunk_ids                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  返回结果:                                                   │
│  {                                                           │
│    "data": {                                                 │
│      "nodes": [                                              │
│        {                                                     │
│          "title": "一、企业基本情况",                        │
│          "level": 1,                                         │
│          "order_no": 1,                                      │
│          "required": true,                                   │
│          "evidence_chunk_ids": ["chunk_123", ...]           │
│        },                                                    │
│        ...                                                   │
│      ]                                                       │
│    },                                                        │
│    "evidence_chunk_ids": ["chunk_123", "chunk_456", ...]    │
│  }                                                           │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  后处理 (DeclareService):                                    │
│  1. 节点排序 (按 level + order_no)                           │
│  2. 构建树形结构 (_build_directory_tree)                     │
│  3. 保存到数据库:                                            │
│     - create_directory_version()                             │
│     - upsert_directory_nodes()                               │
│  4. 更新 run 状态                                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  前端: 显示目录树                                            │
│  - 用户可编辑、删除、新增节点                                │
│  - 用户可查看证据来源 (evidence_chunk_ids)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 关键技术点

### 1. **多查询检索策略**

定义了3个不同角度的查询，提高召回率：
- `structure`: 关注整体结构
- `template`: 关注模板和格式
- `requirements`: 关注必填项和要求

### 2. **证据链追踪**

每个节点都保留 `evidence_chunk_ids`，可追溯到原文：
```python
{
  "title": "一、企业基本情况",
  "evidence_chunk_ids": ["chunk_123", "chunk_456"]
}
```

### 3. **树形结构自动构建**

`DeclareService._build_directory_tree()` 根据 `level` 和 `order_no` 自动构建父子关系。

### 4. **版本化管理**

每次生成目录都会创建新版本：
```python
version_id = dao.create_directory_version(project_id, source="notice", run_id=run_id)
dao.upsert_directory_nodes(version_id, project_id, nodes)
```

---

## 📝 数据流示例

### 输入（申报通知片段）
```
<chunk id="chunk_001">
附件1：申报书格式
一、企业基本情况（必填）
  （一）企业概况
  （二）股权结构
二、项目基本情况（必填）
  （一）项目概述
  （二）技术路线
</chunk>
```

### 输出（结构化目录）
```json
{
  "data": {
    "nodes": [
      {
        "title": "一、企业基本情况",
        "level": 1,
        "order_no": 1,
        "required": true,
        "evidence_chunk_ids": ["chunk_001"]
      },
      {
        "title": "（一）企业概况",
        "level": 2,
        "order_no": 1,
        "parent_ref": "一、企业基本情况",
        "required": true,
        "evidence_chunk_ids": ["chunk_001"]
      },
      {
        "title": "（二）股权结构",
        "level": 2,
        "order_no": 2,
        "parent_ref": "一、企业基本情况",
        "required": true,
        "evidence_chunk_ids": ["chunk_001"]
      },
      {
        "title": "二、项目基本情况",
        "level": 1,
        "order_no": 2,
        "required": true,
        "evidence_chunk_ids": ["chunk_001"]
      },
      {
        "title": "（一）项目概述",
        "level": 2,
        "order_no": 1,
        "parent_ref": "二、项目基本情况",
        "required": true,
        "evidence_chunk_ids": ["chunk_001"]
      },
      {
        "title": "（二）技术路线",
        "level": 2,
        "order_no": 2,
        "parent_ref": "二、项目基本情况",
        "required": true,
        "evidence_chunk_ids": ["chunk_001"]
      }
    ]
  },
  "evidence_chunk_ids": ["chunk_001"]
}
```

---

## 🛠️ 调试与测试

### 查看日志
```bash
# 查看目录生成日志
docker-compose logs -f backend | grep "generate_directory"

# 查看抽取引擎日志
docker-compose logs -f backend | grep "DeclareExtractV2"
```

### 环境变量配置
在 `docker-compose.yml` 或 `.env` 中调整：
```yaml
environment:
  - DECLARE_DIRECTORY_QUERY_STRUCTURE=申报书目录 章节结构 目录清单
  - DECLARE_DIRECTORY_QUERY_TEMPLATE=附件 模板 格式范本
  - DECLARE_DIRECTORY_QUERY_REQUIREMENTS=必填项 必须提交 材料要求
  - DECLARE_DIRECTORY_TOPK_PER_QUERY=30
  - DECLARE_DIRECTORY_TOPK_TOTAL=120
```

### 测试 API
```bash
# 生成目录（异步）
curl -X POST http://localhost:9001/api/apps/declare/projects/{project_id}/directory/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# 生成目录（同步）
curl -X POST "http://localhost:9001/api/apps/declare/projects/{project_id}/directory/generate?sync=1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# 获取目录节点
curl -X GET http://localhost:9001/api/apps/declare/projects/{project_id}/directory/nodes \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📚 相关文档

- [平台抽取引擎](../backend/app/platform/extraction/README.md)
- [检索服务文档](../backend/app/platform/retrieval/README.md)
- [申报书 DAO 文档](../backend/app/services/dao/declare_dao.py)

---

## ✅ 总结

| 层级 | 文件 | 职责 |
|------|------|------|
| **API 路由** | `routers/declare.py` | 接收请求，触发任务 |
| **服务层** | `services/declare_service.py` | 编排业务逻辑，保存结果 |
| **Work 层** | `works/declare/extract_v2_service.py` | 调用抽取引擎 |
| **规格层** | `works/declare/extraction_specs/directory_v2.py` | 定义抽取规格 |
| **Prompt** | `works/declare/prompts/directory_v2.md` | LLM 指令模板 |
| **Schema** | `works/declare/schemas/directory_v2.py` | 数据模型验证 |

**核心流程：**
API → Service → ExtractV2 → Spec → Engine → LLM → 结构化输出 → 树形构建 → 数据库保存 → 前端展示

**关键文件：**
- Prompt: `/backend/app/works/declare/prompts/directory_v2.md`
- Schema: `/backend/app/works/declare/schemas/directory_v2.py`
- Spec: `/backend/app/works/declare/extraction_specs/directory_v2.py`
- Service: `/backend/app/works/declare/extract_v2_service.py`

