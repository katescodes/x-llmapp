# 系统架构与招投标应用流程详解

**基于代码分析** | 生成时间: 2025-12-20

---

## 目录

1. [系统整体架构](#1-系统整体架构)
2. [技术栈](#2-技术栈)
3. [目录结构](#3-目录结构)
4. [核心模块详解](#4-核心模块详解)
5. [招投标应用完整流程](#5-招投标应用完整流程)
6. [数据流转](#6-数据流转)
7. [平台化架构](#7-平台化架构)

---

## 1. 系统整体架构

### 1.1 微服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Compose                        │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   Frontend   │   Backend    │    Worker    │  Postgres      │
│  (Vue.js)    │  (FastAPI)   │  (Celery)    │  (Database)    │
│  Port: 6173  │  Port: 9001  │              │  Port: 5432    │
└──────────────┴──────────────┴──────────────┴────────────────┘
                      │                              │
                      ├──────────────────────────────┤
                      │         Redis (Queue)        │
                      └──────────────────────────────┘
                      
外部服务:
  - LLM API: https://xai.yglinker.com:50443
  - Embedding API: http://192.168.2.16:9996
  - SearXNG (可选): localhost:8080
```

### 1.2 核心架构层次

```
┌─────────────────────────────────────────────────────────┐
│                    Router Layer (API)                    │
│  /api/apps/tender/*  /api/auth/*  /api/_debug/*        │
├─────────────────────────────────────────────────────────┤
│                   Service Layer (业务)                   │
│  TenderService, ExtractionEngine, TemplateAnalyzer      │
├─────────────────────────────────────────────────────────┤
│                Platform Layer (平台能力)                 │
│  ┌──────────┬──────────┬──────────┬──────────┐         │
│  │ DocStore │ Ingest   │Retrieval │Extraction│         │
│  │  (入库)  │  (切分)  │  (检索)  │  (抽取)  │         │
│  └──────────┴──────────┴──────────┴──────────┘         │
├─────────────────────────────────────────────────────────┤
│                   DAO Layer (数据访问)                   │
│  TenderDAO, Connection Pool                             │
├─────────────────────────────────────────────────────────┤
│               Storage Layer (存储)                       │
│  ┌──────────┬──────────┬──────────┬──────────┐         │
│  │Postgres  │MilvusLite│  Redis   │  Disk    │         │
│  │(结构化)  │ (向量)   │  (队列)  │ (文件)   │         │
│  └──────────┴──────────┴──────────┴──────────┘         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 技术栈

### 2.1 后端技术

| 组件 | 技术 | 版本/说明 |
|------|------|-----------|
| **Web框架** | FastAPI | Python 3.11 + Uvicorn |
| **数据库** | PostgreSQL | 15-alpine |
| **向量数据库** | Milvus Lite | 单机嵌入式 |
| **缓存/队列** | Redis | 7-alpine |
| **ORM/连接池** | psycopg3 | Connection Pool |
| **文档解析** | python-docx, pypdf, LibreOffice | 支持 PDF/DOCX/TXT |
| **LLM调用** | httpx | OpenAI兼容API |
| **Embedding** | httpx | 远程HTTP调用 |
| **语音识别** | faster-whisper | 本地ASR（CPU） |

### 2.2 前端技术

- **框架**: Vue.js 3 + Vite
- **UI库**: Element Plus
- **HTTP**: Axios
- **状态管理**: Pinia
- **路由**: Vue Router

### 2.3 基础设施

- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx（生产）
- **CI/CD**: 自定义脚本（scripts/ci/）
- **监控**: 自定义日志 + Debug端点

---

## 3. 目录结构

```
/aidata/x-llmapp1/
├── backend/
│   ├── app/
│   │   ├── routers/          # API路由
│   │   │   ├── tender.py     # 招投标核心API
│   │   │   ├── auth.py       # 认证
│   │   │   ├── debug.py      # 调试端点
│   │   │   ├── chat.py       # 聊天/RAG
│   │   │   └── ...
│   │   ├── services/         # 业务逻辑
│   │   │   ├── tender_service.py   # 招投标主服务（4400行）
│   │   │   ├── dao/                # 数据访问
│   │   │   ├── template/           # 模板解析
│   │   │   ├── retrieval/          # 检索（OLD）
│   │   │   ├── vectorstore/        # 向量存储（OLD）
│   │   │   └── ...
│   │   ├── platform/         # 平台化能力（NEW）
│   │   │   ├── docstore/     # 文档存储
│   │   │   ├── ingest/       # 入库切分
│   │   │   ├── retrieval/    # 检索（NEW）
│   │   │   ├── extraction/   # 抽取引擎
│   │   │   ├── rules/        # 规则引擎
│   │   │   └── vectorstore/  # Milvus管理
│   │   ├── core/             # 核心模块
│   │   │   ├── cutover.py    # 灰度切换
│   │   │   └── ...
│   │   ├── schemas/          # Pydantic模型
│   │   ├── utils/            # 工具函数
│   │   ├── config.py         # 配置
│   │   └── main.py           # 应用入口
│   ├── migrations/           # 数据库迁移
│   ├── scripts/              # 脚本
│   ├── testdata/             # 测试数据
│   └── worker.py             # 异步Worker
├── frontend/                 # Vue前端
├── data/                     # 持久化数据
│   ├── llm_models.json       # LLM配置
│   ├── milvus.db             # 向量数据库
│   ├── postgres/             # PG数据
│   └── ...
├── storage/                  # 文件存储
├── scripts/                  # CI/工具脚本
│   ├── ci/                   # 验收脚本
│   ├── eval/                 # 评估脚本
│   └── smoke/                # 烟雾测试
├── reports/                  # 验收报告
└── docker-compose.yml        # 容器编排
```

---

## 4. 核心模块详解

### 4.1 Router Layer (`backend/app/routers/tender.py`)

**职责**: HTTP请求处理，参数验证，权限控制

**核心端点**:

```python
# 项目管理
POST   /api/apps/tender/projects                 # 创建项目
GET    /api/apps/tender/projects                 # 列表
GET    /api/apps/tender/projects/{id}            # 详情
DELETE /api/apps/tender/projects/{id}            # 删除（级联）

# 文件管理
POST   /api/apps/tender/projects/{id}/assets/import    # 上传文件
GET    /api/apps/tender/projects/{id}/assets           # 文件列表
DELETE /api/apps/tender/assets/{asset_id}              # 删除文件

# 信息抽取（核心功能）
POST   /api/apps/tender/projects/{id}/extract/project-info   # 抽取项目信息
GET    /api/apps/tender/projects/{id}/project-info          # 获取抽取结果
POST   /api/apps/tender/projects/{id}/extract/risks         # 抽取风险
GET    /api/apps/tender/projects/{id}/risks                 # 获取风险

# 目录管理
POST   /api/apps/tender/projects/{id}/directory/parse      # 解析目录
GET    /api/apps/tender/projects/{id}/directory            # 获取目录
POST   /api/apps/tender/projects/{id}/directory/save       # 保存目录

# 审核对比
POST   /api/apps/tender/projects/{id}/review/run           # 运行审核
GET    /api/apps/tender/projects/{id}/review               # 获取审核结果

# 调试端点
GET    /api/_debug/llm/ping                     # LLM健康检查
GET    /api/_debug/docstore/ready               # 入库状态
GET    /api/_debug/retrieval/test               # 检索测试
```

**依赖注入模式**:

```python
def _get_pool(req: Request) -> ConnectionPool:
    """获取数据库连接池"""
    from app.services.db.postgres import _get_pool as get_sync_pool
    return get_sync_pool()

def _get_llm(req: Request):
    """获取LLM orchestrator"""
    return req.app.state.llm_orchestrator

def _svc(req: Request) -> TenderService:
    """创建TenderService实例"""
    dao = TenderDAO(_get_pool(req))
    jobs_service = JobsService(_get_pool(req)) if flags.PLATFORM_JOBS_ENABLED else None
    return TenderService(dao=dao, llm_orchestrator=_get_llm(req), jobs_service=jobs_service)
```

### 4.2 Service Layer (`backend/app/services/tender_service.py`)

**职责**: 业务逻辑编排，LLM调用，规则执行

**核心类**: `TenderService` (4400+ 行)

**主要方法**:

```python
class TenderService:
    def __init__(self, dao, llm_orchestrator, jobs_service=None):
        self.dao = dao                    # 数据访问
        self.llm = llm_orchestrator       # LLM调用
        self.jobs_service = jobs_service  # 平台任务（双写）
    
    # === 项目管理 ===
    def get_project(self, project_id) -> Dict
    def list_projects(self, offset, limit) -> List[Dict]
    def delete_project(self, project_id) -> ProjectDeletePlanResponse
    
    # === 文件管理 ===
    def upload_tender_file(self, project_id, file) -> Dict
    def list_assets(self, project_id) -> List[Dict]
    
    # === 信息抽取（核心） ===
    def extract_project_info(self, project_id, model_id, run_id, owner_id) -> str
        """
        抽取项目信息（四板块）
        流程：
        1. 决定模式（OLD/NEW_ONLY/SHADOW）
        2. 检索相关chunks
        3. 构建prompt
        4. 调用LLM
        5. 解析JSON
        6. 存储结果
        """
    
    def extract_risks(self, project_id, model_id, run_id, owner_id) -> str
        """抽取风险清单"""
    
    # === 目录管理 ===
    def parse_directory(self, project_id, asset_id) -> List[Dict]
        """
        解析招标文件目录
        流程：
        1. 读取DOCX文件
        2. 识别目录结构（样式+缩进）
        3. 提取编号、标题、层级
        4. 返回树形结构
        """
    
    def save_directory(self, project_id, nodes, base_policy) -> List[Dict]
        """保存目录节点"""
    
    # === 审核对比 ===
    def run_review(self, project_id, run_id, owner_id) -> str
        """
        运行审核对比
        流程：
        1. 对比招标文件目录 vs 响应文件目录
        2. 找出缺失/多余的节点
        3. 应用规则评分
        4. 生成审核报告
        """
    
    # === 内部方法 ===
    def _llm_text(self, call: LLMCall) -> str
        """调用LLM获取文本响应（带重试）"""
    
    def _retrieve_chunks(self, project_id, queries, top_k) -> List[Dict]
        """检索相关文档块（支持OLD/NEW切换）"""
```

**灰度切换机制**:

```python
from app.core.cutover import get_cutover_config

config = get_cutover_config()
mode = config.get_mode("extract", project_id)  # OLD/SHADOW/PREFER_NEW/NEW_ONLY

if mode == CutoverMode.OLD:
    # 走老路径
    result = self._extract_old(...)
elif mode == CutoverMode.NEW_ONLY:
    # 走新路径
    result = self._extract_new(...)
elif mode == CutoverMode.SHADOW:
    # 双跑对比
    old_result = self._extract_old(...)
    new_result = self._extract_new(...)
    self._compare_and_log(old_result, new_result)
    return old_result  # 返回老结果
```

### 4.3 Platform Layer (平台化能力)

#### 4.3.1 DocStore (`backend/app/platform/docstore/`)

**职责**: 文档统一存储，版本管理

```python
class DocStoreService:
    """
    文档存储服务
    
    表结构:
    - documents: 文档元数据（doc_id, doc_type, project_id）
    - document_versions: 版本管理（version_id, doc_id, content_hash）
    - doc_segments: 文档分片（segment_id, version_id, content_text, meta_json）
    """
    
    def create_document(self, doc_type, project_id, filename, content_hash) -> str:
        """创建文档记录"""
    
    def create_version(self, doc_id, content_hash, segment_count) -> str:
        """创建新版本"""
    
    def create_segments(self, version_id, segments: List[Dict]) -> int:
        """批量创建分片"""
    
    def get_segments_by_version(self, version_id) -> List[Dict]:
        """获取某版本的所有分片"""
```

**数据模型**:

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,              -- doc_xxx
    doc_type TEXT NOT NULL,           -- tender/bid/template
    project_id TEXT,
    filename TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE document_versions (
    id TEXT PRIMARY KEY,              -- dv_xxx
    doc_id TEXT REFERENCES documents(id),
    content_hash TEXT,
    segment_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE doc_segments (
    id TEXT PRIMARY KEY,              -- ds_xxx
    doc_version_id TEXT REFERENCES document_versions(id),
    position INTEGER,
    content_text TEXT,
    meta_json JSONB,
    tsv TSVECTOR,                     -- 全文索引
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_doc_segments_tsv ON doc_segments USING GIN(tsv);
```

#### 4.3.2 Ingest (`backend/app/platform/ingest/`)

**职责**: 文档解析切分，向量化

```python
class IngestV2Service:
    """
    入库服务 V2
    
    流程:
    1. 解析文档（PDF/DOCX）
    2. 切分段落（基于样式/语义）
    3. 生成向量（调用Embedding API）
    4. 写入DocStore（PG + Milvus）
    """
    
    async def ingest_document(
        self, 
        doc_type: str,
        project_id: str,
        filename: str,
        content_bytes: bytes
    ) -> Dict:
        """
        完整入库流程
        
        Returns:
            {
                "doc_id": "doc_xxx",
                "version_id": "dv_xxx",
                "segments": 120,
                "vectors": 120,
                "elapsed_ms": 5000
            }
        """
        # 1. 解析文档
        parser = self._get_parser(filename)
        elements = parser.parse(content_bytes)
        
        # 2. 切分段落
        segments = self._chunk_elements(elements)
        
        # 3. 生成向量
        vectors = await self._embed_segments(segments)
        
        # 4. 写入DocStore
        doc_id = docstore.create_document(...)
        version_id = docstore.create_version(...)
        docstore.create_segments(version_id, segments)
        
        # 5. 写入Milvus
        milvus_docseg_store.upsert_segments(vectors)
        
        return {"doc_id": doc_id, ...}
```

**文档解析器**:

```python
# PDF解析（基于pypdf）
class PDFParser:
    def parse(self, content_bytes) -> List[Element]:
        reader = PdfReader(io.BytesIO(content_bytes))
        elements = []
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            elements.append({
                "type": "paragraph",
                "text": text,
                "page": page_num + 1
            })
        return elements

# DOCX解析（基于python-docx）
class DOCXParser:
    def parse(self, content_bytes) -> List[Element]:
        doc = Document(io.BytesIO(content_bytes))
        elements = []
        for para in doc.paragraphs:
            elements.append({
                "type": "paragraph",
                "text": para.text,
                "style": para.style.name,
                "level": self._get_outline_level(para)
            })
        return elements
```

#### 4.3.3 Retrieval (`backend/app/platform/retrieval/`)

**职责**: 混合检索（Dense + Lexical）

```python
class NewRetriever:
    """
    新检索器
    
    混合检索策略:
    - Dense: Milvus向量检索（语义相似）
    - Lexical: PG全文检索（关键词匹配）
    - Fusion: RRF融合排序
    """
    
    async def retrieve(
        self,
        query: str,
        project_id: str,
        doc_types: List[str],
        embedding_provider: EmbeddingProviderStored,
        top_k: int = 12,
        dense_limit: int = 40,
        lexical_limit: int = 40
    ) -> List[RetrievedChunk]:
        """
        混合检索流程:
        
        1. 获取项目下的doc_version_ids
        2. Dense检索（Milvus）
           - 将query转为向量
           - 在Milvus中搜索top-N
           - 失败时降级到lexical-only ✅ (Step3修复)
        3. Lexical检索（PG tsvector）
           - 使用to_tsquery()全文搜索
           - 返回ts_rank排序结果
        4. RRF融合
           - 对dense和lexical结果融合排序
           - k=60, top_k=12
        5. 加载完整文本
        """
        
        # 1. 获取doc_version_ids
        doc_version_ids = self._get_project_doc_versions(project_id, doc_types)
        
        # 2. Dense检索（带降级）
        dense_hits, dense_error = await self._search_dense(query, doc_version_ids, ...)
        if dense_error:
            logger.warning(f"DENSE_FAILED, fallback to lexical only")
            dense_hits = []
        
        # 3. Lexical检索
        lexical_hits = self._search_lexical(query, doc_version_ids, lexical_limit)
        
        # 4. RRF融合
        if dense_error:
            fused = lexical_hits[:top_k]  # 降级模式
        else:
            fused = rrf_fuse(dense_hits, lexical_hits, k=60, topn=top_k)
        
        # 5. 加载完整文本
        chunk_ids = [hit["chunk_id"] for hit in fused]
        return self._load_chunks(chunk_ids)
```

**RRF融合算法**:

```python
def rrf_fuse(dense_hits, lexical_hits, k=60, topn=10):
    """
    Reciprocal Rank Fusion
    
    score(doc) = sum( 1 / (k + rank_in_list_i) )
    """
    scores = {}
    
    for rank, hit in enumerate(dense_hits):
        doc_id = hit["chunk_id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    
    for rank, hit in enumerate(lexical_hits):
        doc_id = hit["chunk_id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    
    sorted_docs = sorted(scores.items(), key=lambda x: -x[1])
    return sorted_docs[:topn]
```

#### 4.3.4 Extraction (`backend/app/platform/extraction/`)

**职责**: 统一抽取引擎

```python
class ExtractionEngine:
    """
    抽取引擎
    
    支持多种抽取任务:
    - project-info: 项目信息（四板块）
    - risks: 风险清单
    - custom: 自定义抽取
    """
    
    async def extract(
        self,
        task_type: str,
        project_id: str,
        queries: List[str],
        prompt_template: str,
        llm_call: Callable,
        run_id: str
    ) -> Dict:
        """
        统一抽取流程:
        
        1. 检索相关chunks
        2. 构建prompt
        3. 调用LLM
        4. 解析JSON
        5. 生成证据链
        6. 返回结构化数据
        """
        import time
        
        # 1. 检索
        retrieval_start = time.time()
        all_chunks = await self._retrieve_chunks(project_id, queries)
        retrieval_ms = int((time.time() - retrieval_start) * 1000)
        logger.info(f"AFTER_RETRIEVAL chunks={len(all_chunks)} ms={retrieval_ms}")
        
        # 2. 构建prompt
        context = self._build_context(all_chunks)
        messages = [
            {"role": "system", "content": "你是招投标专家..."},
            {"role": "user", "content": prompt_template.format(context=context)}
        ]
        
        # 3. 调用LLM
        llm_start = time.time()
        logger.info(f"BEFORE_LLM run_id={run_id}")
        result = llm_call(messages)
        llm_ms = int((time.time() - llm_start) * 1000)
        logger.info(f"AFTER_LLM run_id={run_id} ms={llm_ms}")
        
        # 4. 解析JSON
        out_text = result["choices"][0]["message"]["content"]
        obj = extract_json(out_text)  # 支持```json包裹
        
        # 5. 提取数据和证据
        data = obj.get("data", {})
        evidence_chunk_ids = obj.get("evidence_chunk_ids", [])
        
        # 6. 生成追踪信息
        trace = {
            "retrieval_ms": retrieval_ms,
            "llm_ms": llm_ms,
            "chunks_retrieved": len(all_chunks),
            "evidence_count": len(evidence_chunk_ids)
        }
        
        return {
            "data": data,
            "evidence_chunk_ids": evidence_chunk_ids,
            "trace": trace
        }
```

### 4.4 DAO Layer (`backend/app/services/dao/tender_dao.py`)

**职责**: 数据库CRUD操作

```python
class TenderDAO:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
    
    # === 项目 ===
    def create_project(self, name, kb_id, owner_id) -> str
    def get_project(self, project_id) -> Dict
    def list_projects(self, offset, limit) -> List[Dict]
    def delete_project(self, project_id) -> None
    
    # === 资产 ===
    def create_asset(self, project_id, kind, filename, file_sha256, meta_json) -> str
    def get_asset_by_id(self, asset_id) -> Dict
    def list_assets(self, project_id) -> List[Dict]
    def delete_asset(self, asset_id) -> None
    
    # === 抽取结果 ===
    def upsert_project_info(self, project_id, data_json, evidence_chunk_ids) -> None
    def get_project_info(self, project_id) -> Dict
    
    def upsert_risks(self, project_id, risks_json, evidence_chunk_ids) -> None
    def get_risks(self, project_id) -> List[Dict]
    
    # === 目录 ===
    def save_directory_nodes(self, project_id, nodes) -> int
    def get_directory_nodes(self, project_id) -> List[Dict]
    
    # === 审核 ===
    def save_review_items(self, project_id, items) -> int
    def list_review_items(self, project_id) -> List[Dict]
    
    # === 运行记录 ===
    def create_run(self, project_id, task_type, status) -> str
    def update_run(self, run_id, status, progress, message) -> None
    def get_run(self, run_id) -> Dict
```

---

## 5. 招投标应用完整流程

### 5.1 项目创建流程

```
用户 -> Frontend -> Backend API -> TenderService -> TenderDAO -> Postgres

1. POST /api/apps/tender/projects
   Request: {"name": "XX项目"}

2. Backend处理:
   a. 先创建知识库（KB）
      kb_id = kb_service.create_kb(...)
   
   b. 创建项目记录
      project_id = dao.create_project(name, kb_id, owner_id)
   
   c. 返回项目信息
      Response: {
          "id": "tp_xxx",
          "name": "XX项目",
          "kb_id": "kb_xxx",
          "created_at": "2025-12-20T..."
      }

3. 数据库操作:
   INSERT INTO tender_projects (id, name, kb_id, owner_id, created_at)
   VALUES ('tp_xxx', 'XX项目', 'kb_xxx', 'user_xxx', NOW())
```

### 5.2 文件上传与入库流程

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ 前端上传 │────>│  Router  │────>│ Service  │────>│ IngestV2 │
│  (DOCX)  │     │  接收    │     │  存储    │     │  切分    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                          │
                                                          v
              ┌───────────────────────────────────────────────┐
              │                 并行处理                       │
              ├─────────────────┬─────────────────────────────┤
              │  DocStore (PG)  │    Milvus Lite (向量)       │
              │  - documents    │    - 生成向量                │
              │  - versions     │    - upsert_segments()      │
              │  - doc_segments │    - collection创建          │
              └─────────────────┴─────────────────────────────┘
```

**详细步骤**:

```python
# 1. 前端上传
POST /api/apps/tender/projects/{project_id}/assets/import
Content-Type: multipart/form-data
files: tender.docx
kind: tender

# 2. Router处理
@router.post("/projects/{project_id}/assets/import")
async def import_assets(
    project_id: str,
    files: List[UploadFile],
    kind: str = Form(...),
    svc: TenderService = Depends(_svc)
):
    results = []
    for file in files:
        content = await file.read()
        asset = await svc.upload_tender_file(project_id, file.filename, content, kind)
        results.append(asset)
    return results

# 3. Service处理
async def upload_tender_file(self, project_id, filename, content, kind):
    # 3.1 计算文件哈希
    file_sha256 = _sha256(content)
    
    # 3.2 保存到磁盘
    file_path = f"storage/{project_id}/{file_sha256[:8]}_{filename}"
    with open(file_path, 'wb') as f:
        f.write(content)
    
    # 3.3 创建资产记录
    meta_json = {"file_path": file_path}
    asset_id = self.dao.create_asset(project_id, kind, filename, file_sha256, meta_json)
    
    # 3.4 触发入库（根据模式）
    cutover = get_cutover_config()
    if cutover.get_mode("ingest", project_id) == CutoverMode.NEW_ONLY:
        # 调用IngestV2
        result = await ingest_v2_service.ingest_document(
            doc_type=kind,
            project_id=project_id,
            filename=filename,
            content_bytes=content
        )
        # 更新meta_json
        meta_json["doc_version_id"] = result["version_id"]
        meta_json["ingest_v2_status"] = "completed"
        meta_json["ingest_v2_segments"] = result["segments"]
        self.dao.update_asset_meta(asset_id, meta_json)
    
    return {"id": asset_id, "filename": filename, "status": "uploaded"}

# 4. IngestV2处理
async def ingest_document(self, doc_type, project_id, filename, content_bytes):
    # 4.1 解析文档
    if filename.endswith('.docx'):
        parser = DOCXParser()
    elif filename.endswith('.pdf'):
        parser = PDFParser()
    elements = parser.parse(content_bytes)
    
    # 4.2 切分段落
    segments = []
    for i, elem in enumerate(elements):
        segments.append({
            "position": i,
            "content_text": elem["text"],
            "meta_json": {"type": elem["type"], "page": elem.get("page")}
        })
    
    # 4.3 生成向量（批量调用Embedding API）
    texts = [s["content_text"] for s in segments]
    vectors = await embed_texts(texts, provider=embedding_provider)
    
    # 4.4 写入DocStore（PG）
    doc_id = docstore.create_document(doc_type, project_id, filename, file_hash)
    version_id = docstore.create_version(doc_id, file_hash, len(segments))
    
    for i, segment in enumerate(segments):
        segment["id"] = f"ds_{uuid.uuid4().hex[:16]}"
        segment["doc_version_id"] = version_id
    
    docstore.create_segments(version_id, segments)
    
    # 4.5 写入Milvus（向量）
    milvus_data = []
    for i, segment in enumerate(segments):
        milvus_data.append({
            "segment_id": segment["id"],
            "doc_version_id": version_id,
            "project_id": project_id,
            "doc_type": doc_type,
            "dense": vectors[i]["dense"]
        })
    
    milvus_docseg_store.upsert_segments(milvus_data, dense_dim=1024)
    
    return {
        "doc_id": doc_id,
        "version_id": version_id,
        "segments": len(segments),
        "vectors": len(milvus_data)
    }
```

### 5.3 信息抽取流程（核心）

```
┌──────────┐
│ 触发抽取 │ POST /api/apps/tender/projects/{id}/extract/project-info
└─────┬────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 1: 模式决策                            │
│  - 读取 EXTRACT_MODE, RETRIEVAL_MODE 环境变量           │
│  - 调用 get_cutover_config().get_mode(...)             │
│  - 返回: OLD / SHADOW / PREFER_NEW / NEW_ONLY          │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 2: 检索相关文档                        │
│  NEW_ONLY模式:                                          │
│    1. 等待DocStore入库完成                              │
│    2. 调用 NewRetriever.retrieve()                     │
│       - 构建查询列表 ["项目名称", "预算金额", ...]       │
│       - 执行混合检索 (Dense + Lexical)                  │
│       - RRF融合排序                                     │
│    3. 返回 top-120 个 chunks                           │
│                                                          │
│  OLD模式:                                               │
│    - 调用 LegacyRetriever (基于KB的检索)                │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 3: 构建Prompt                          │
│  context = """                                          │
│  [DOC doc_xxx CHUNK ds_001 POS 0]                      │
│  XX项目招标文件...                                       │
│                                                          │
│  [DOC doc_xxx CHUNK ds_002 POS 1]                      │
│  项目预算：1000万元...                                   │
│  ...                                                    │
│  """                                                    │
│                                                          │
│  prompt = f"""                                          │
│  请从以下招标文件中抽取项目信息：                         │
│  {context}                                              │
│                                                          │
│  输出JSON格式（四板块）：                                 │
│  {{                                                     │
│    "data": {{                                          │
│      "base": {{"projectName": "...", ...}},           │
│      "technical_parameters": [...],                    │
│      "business_terms": [...],                          │
│      "scoring_criteria": {{...}}                       │
│    }},                                                 │
│    "evidence_chunk_ids": ["ds_001", "ds_002"]         │
│  }}                                                    │
│  """                                                    │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 4: 调用LLM                             │
│  - LLM配置: https://xai.yglinker.com:50443             │
│  - 模型: gpt-oss-120b                                   │
│  - 参数: temperature=0.7, max_tokens=16000             │
│  - 超时: 30秒                                           │
│  - 重试: 3次（失败时）                                   │
│                                                          │
│  Response:                                              │
│  ```json                                                │
│  {                                                      │
│    "data": {                                           │
│      "base": {                                         │
│        "projectName": "含山县城乡供水改造工程",          │
│        "budget": "800万元",                            │
│        ...                                             │
│      },                                                │
│      "technical_parameters": [                         │
│        {                                               │
│          "category": "设备要求",                        │
│          "item": "加压泵站",                            │
│          "requirement": "流量≥50m³/h",                 │
│          "evidence_chunk_ids": ["ds_012"]             │
│        }                                               │
│      ],                                                │
│      ...                                               │
│    },                                                  │
│    "evidence_chunk_ids": ["ds_001", "ds_012", ...]    │
│  }                                                     │
│  ```                                                    │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 5: 解析JSON                            │
│  - 提取 ```json ... ``` 中的内容                        │
│  - 解析为Python dict                                    │
│  - 验证schema（可选）                                    │
│  - 提取 data 和 evidence_chunk_ids                      │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 6: 存储结果                            │
│  INSERT INTO tender_project_info (                      │
│    project_id,                                          │
│    data_json,                                           │
│    evidence_chunk_ids,                                  │
│    updated_at                                           │
│  ) VALUES (...)                                         │
│  ON CONFLICT (project_id) DO UPDATE ...                │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 7: 返回结果                            │
│  Response: {                                            │
│    "run_id": "tr_xxx",                                 │
│    "status": "ok",                                     │
│    "progress": 100,                                    │
│    "message": "抽取完成"                                │
│  }                                                      │
│                                                          │
│  前端可通过 GET /projects/{id}/project-info 获取结果     │
└─────────────────────────────────────────────────────────┘
```

### 5.4 审核对比流程

```
┌──────────┐
│ 触发审核 │ POST /api/apps/tender/projects/{id}/review/run
└─────┬────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 1: 获取目录                            │
│  - 招标文件目录: tender_directory_nodes                  │
│  - 响应文件目录: bid_directory_nodes                     │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 2: 对比目录                            │
│  算法:                                                   │
│  1. 构建招标目录的扁平化映射（numbering -> node）         │
│  2. 遍历响应目录，逐个匹配                                │
│  3. 检查：                                               │
│     - 必需节点是否缺失                                    │
│     - 是否存在多余节点                                    │
│     - 节点顺序是否正确                                    │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 3: 规则评分                            │
│  规则库（tender_rules表）:                               │
│  - 缺失必需节点: -10分                                   │
│  - 多余无关节点: -5分                                    │
│  - 节点顺序错误: -3分                                    │
│  - 内容不完整: -8分                                      │
│                                                          │
│  示例:                                                   │
│  {                                                      │
│    "rule_id": "RULE_001",                              │
│    "rule_name": "必需节点缺失",                          │
│    "matched": true,                                    │
│    "score_delta": -10,                                 │
│    "evidence": "缺失'技术参数'章节"                      │
│  }                                                      │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 4: 生成审核项                          │
│  tender_review_items 表:                                │
│  [{                                                     │
│    "id": "tr_xxx",                                     │
│    "project_id": "tp_xxx",                             │
│    "item_type": "missing_node",                        │
│    "severity": "error",                                │
│    "title": "缺失必需章节：技术参数",                    │
│    "description": "响应文件中未找到...",                │
│    "score_delta": -10,                                 │
│    "evidence_chunk_ids": ["ds_001"],                   │
│    "auto_decision": "reject",                          │
│    "created_at": "2025-12-20T..."                      │
│  }, ...]                                               │
└─────┬───────────────────────────────────────────────────┘
      │
      v
┌─────────────────────────────────────────────────────────┐
│              Step 5: 存储并返回                          │
│  - 批量插入 tender_review_items                         │
│  - 更新运行状态（runs表）                                │
│  - 返回审核摘要                                          │
│                                                          │
│  Response: {                                            │
│    "run_id": "rr_xxx",                                 │
│    "status": "completed",                              │
│    "total_issues": 5,                                  │
│    "errors": 2,                                        │
│    "warnings": 3,                                      │
│    "score": 75                                         │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 6. 数据流转

### 6.1 数据库Schema（核心表）

```sql
-- ========== 项目管理 ==========
CREATE TABLE tender_projects (
    id TEXT PRIMARY KEY,              -- tp_xxx
    name TEXT NOT NULL,
    kb_id TEXT NOT NULL,              -- 关联知识库
    owner_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ========== 文件资产 ==========
CREATE TABLE tender_project_assets (
    id TEXT PRIMARY KEY,              -- ta_xxx
    project_id TEXT REFERENCES tender_projects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,               -- tender/bid/template
    filename TEXT,
    file_sha256 TEXT,
    meta_json JSONB,                  -- {"doc_version_id": "dv_xxx", ...}
    created_at TIMESTAMP DEFAULT NOW()
);

-- ========== 抽取结果 ==========
CREATE TABLE tender_project_info (
    project_id TEXT PRIMARY KEY REFERENCES tender_projects(id) ON DELETE CASCADE,
    data_json JSONB NOT NULL,         -- 四板块数据
    evidence_chunk_ids TEXT[],
    evidence_spans JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tender_risks (
    id TEXT PRIMARY KEY,              -- tr_xxx
    project_id TEXT REFERENCES tender_projects(id) ON DELETE CASCADE,
    data_json JSONB NOT NULL,         -- 风险清单
    evidence_chunk_ids TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- ========== 目录结构 ==========
CREATE TABLE tender_directory_nodes (
    id TEXT PRIMARY KEY,              -- dn_xxx
    project_id TEXT REFERENCES tender_projects(id) ON DELETE CASCADE,
    parent_id TEXT,
    order_no INTEGER DEFAULT 0,
    numbering TEXT,                   -- "1.2.3"
    level INTEGER,
    title TEXT,
    is_required BOOLEAN DEFAULT FALSE,
    source TEXT DEFAULT 'tender',     -- tender/bid
    evidence_chunk_ids TEXT[],
    bodyMeta JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ========== 审核结果 ==========
CREATE TABLE tender_review_items (
    id TEXT PRIMARY KEY,              -- tri_xxx
    project_id TEXT REFERENCES tender_projects(id) ON DELETE CASCADE,
    item_type TEXT,                   -- missing_node/extra_node/content_incomplete
    severity TEXT,                    -- error/warning/info
    title TEXT,
    description TEXT,
    score_delta INTEGER,
    evidence_chunk_ids TEXT[],
    auto_decision TEXT,               -- reject/approve/manual
    manual_decision TEXT,
    manual_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ========== 运行记录 ==========
CREATE TABLE runs (
    id TEXT PRIMARY KEY,              -- tr_xxx/rr_xxx
    project_id TEXT,
    task_type TEXT,                   -- extract_project_info/review
    status TEXT,                      -- pending/running/ok/error
    progress INTEGER DEFAULT 0,
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ========== 平台表（DocStore）==========
CREATE TABLE documents (
    id TEXT PRIMARY KEY,              -- doc_xxx
    doc_type TEXT,
    project_id TEXT,
    filename TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE document_versions (
    id TEXT PRIMARY KEY,              -- dv_xxx
    doc_id TEXT REFERENCES documents(id),
    content_hash TEXT,
    segment_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE doc_segments (
    id TEXT PRIMARY KEY,              -- ds_xxx
    doc_version_id TEXT REFERENCES document_versions(id),
    position INTEGER,
    content_text TEXT,
    meta_json JSONB,
    tsv TSVECTOR,                     -- 全文索引
    created_at TIMESTAMP DEFAULT NOW()
);

-- 全文索引
CREATE INDEX idx_doc_segments_tsv ON doc_segments USING GIN(tsv);
CREATE INDEX idx_doc_segments_version ON doc_segments(doc_version_id);

-- ========== Milvus Collection（概念） ==========
-- Collection: doc_segments_v1
-- Schema:
--   - segment_id: VARCHAR (主键)
--   - doc_version_id: VARCHAR
--   - project_id: VARCHAR
--   - doc_type: VARCHAR
--   - dense: FLOAT_VECTOR(1024)
-- Indexes:
--   - IVF_FLAT on dense
```

### 6.2 数据流向图

```
┌─────────────────────────────────────────────────────────┐
│                    数据流转全景                          │
└─────────────────────────────────────────────────────────┘

用户上传文件
    │
    v
┌─────────────────┐
│ Storage (Disk)  │  文件系统存储
│ /storage/...    │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ tender_project_ │  资产元数据
│ assets (PG)     │  {meta_json: {doc_version_id: "dv_xxx"}}
└────────┬────────┘
         │
         ├────────> IngestV2 (解析切分)
         │                  │
         v                  v
┌─────────────────┐  ┌─────────────────┐
│ documents (PG)  │  │ document_       │
│ doc_versions    │  │ versions (PG)   │
└────────┬────────┘  └────────┬────────┘
         │                    │
         v                    v
┌─────────────────┐  ┌─────────────────┐
│ doc_segments    │  │ Milvus Lite     │
│ (PG + tsvector) │  │ (向量存储)       │
└────────┬────────┘  └────────┬────────┘
         │                    │
         └──────────┬─────────┘
                    │
                    v
         【检索层：NewRetriever】
          Dense + Lexical Fusion
                    │
                    v
         【抽取层：ExtractionEngine】
            LLM调用 + JSON解析
                    │
                    v
         ┌──────────┴──────────┐
         │                     │
         v                     v
┌─────────────────┐  ┌─────────────────┐
│tender_project_  │  │ tender_risks    │
│info (PG)        │  │ (PG)            │
└─────────────────┘  └─────────────────┘
         │
         v
    【前端展示】
```

---

## 7. 平台化架构（Cutover机制）

### 7.1 灰度切换策略

```python
# backend/app/core/cutover.py

class CutoverMode(Enum):
    OLD = "OLD"                    # 100% 老路径
    SHADOW = "SHADOW"              # 双跑对比（返回老结果）
    PREFER_NEW = "PREFER_NEW"      # 新路径优先（失败降级老）
    NEW_ONLY = "NEW_ONLY"          # 100% 新路径

class CutoverConfig:
    """
    灰度配置
    
    环境变量:
    - CUTOVER_SCOPE: global/project
    - CUTOVER_PROJECT_IDS: tp_001,tp_002
    - RETRIEVAL_MODE: OLD/SHADOW/PREFER_NEW/NEW_ONLY
    - INGEST_MODE: ...
    - EXTRACT_MODE: ...
    """
    
    def get_mode(self, stage: str, project_id: str) -> CutoverMode:
        """
        获取某个阶段的模式
        
        决策逻辑:
        1. 如果 CUTOVER_SCOPE=project，检查 project_id 是否在白名单
        2. 读取环境变量 {STAGE}_MODE
        3. 返回对应的模式
        """
        if self.scope == "project":
            if project_id not in self.project_ids:
                return CutoverMode.OLD
        
        return getattr(self, f"{stage}_mode")
```

### 7.2 各阶段切换点

| 阶段 | OLD路径 | NEW路径 | 切换点 |
|------|---------|---------|--------|
| **Ingest** | KB文件上传 | DocStore + IngestV2 | `upload_tender_file()` |
| **Retrieval** | LegacyRetriever | NewRetriever | `extract_project_info()` |
| **Extraction** | 直接LLM调用 | ExtractionEngine | `extract_project_info()` |
| **Review** | 简单对比 | RulesEngine | `run_review()` |

### 7.3 典型切换示例

```python
# TenderService.extract_project_info()

cutover = get_cutover_config()
mode = cutover.get_mode("extract", project_id)

if mode == CutoverMode.OLD:
    # 走老路径
    chunks = self._retrieve_old(project_id, queries)
    result = self._llm_extract_old(chunks, prompt)
    
elif mode == CutoverMode.NEW_ONLY:
    # 走新路径
    engine = ExtractionEngine(pool, embedding_provider)
    result = await engine.extract(
        task_type="project-info",
        project_id=project_id,
        queries=queries,
        prompt_template=PROMPT_TEMPLATE,
        llm_call=lambda msgs: self.llm.chat(messages=msgs)
    )
    
elif mode == CutoverMode.SHADOW:
    # 双跑对比
    old_result = self._extract_old(...)
    new_result = self._extract_new(...)
    
    # 对比并记录差异
    diff = self._compare_results(old_result, new_result)
    logger.info(f"SHADOW_DIFF: {diff}")
    
    # 返回老结果（保证不影响业务）
    result = old_result
```

---

## 总结

### 核心特点

1. **分层架构清晰**: Router → Service → Platform → DAO → Storage
2. **平台化能力**: DocStore, Ingest, Retrieval, Extraction 独立复用
3. **灰度切换安全**: OLD/SHADOW/PREFER_NEW/NEW_ONLY 四阶段切换
4. **混合检索优化**: Dense(Milvus) + Lexical(PG) + RRF融合
5. **降级容错机制**: Dense失败自动降级 Lexical-only
6. **LLM调用封装**: 统一orchestrator，支持重试和Mock
7. **证据链追溯**: 每个抽取结果附带 evidence_chunk_ids
8. **Docker一键部署**: 所有服务容器化，开发/生产一致

### 关键流程耗时（真实LLM）

- **文件上传**: ~1s
- **入库切分**: ~5s (120个segments)
- **检索**: ~50ms (lexical-only) | ~500ms (dense+lexical)
- **LLM抽取**: ~3-75s (取决于复杂度)
- **审核对比**: ~100ms

### 技术亮点

1. **PostgreSQL FTS**: 使用 tsvector + GIN索引实现高性能全文检索
2. **Milvus Lite**: 单机向量数据库，无需独立服务
3. **RRF融合**: Reciprocal Rank Fusion 算法融合多路检索结果
4. **连接池复用**: psycopg3 连接池，高并发下性能稳定
5. **异步处理**: FastAPI async + httpx 异步HTTP调用
6. **灰度切换**: 项目级/全局级灰度控制，风险可控

---

**文档版本**: v1.0  
**代码基准**: /aidata/x-llmapp1 (2025-12-20)  
**维护**: Cursor AI Assistant

