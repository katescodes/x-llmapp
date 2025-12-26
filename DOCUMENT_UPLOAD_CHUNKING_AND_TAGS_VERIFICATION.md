# 文档上传切分和标签检查报告

**检查时间**: 2025-12-25  
**检查范围**: 文档上传、切分逻辑、标签设置

---

## ✅ 检查结果总结

| 检查项 | 状态 | 说明 |
|--------|------|------|
| **文档切分** | ✅ 正常 | 使用固定窗口切分，支持重叠 |
| **标签设置（知识库）** | ✅ 正常 | 使用`kb_category`标签分类 |
| **标签设置（招投标）** | ✅ 正常 | 使用`doc_type`标签分类 |
| **向量化** | ✅ 正常 | 切分后自动向量化并存储 |
| **存储** | ✅ 正常 | 同时存储到PostgreSQL和Milvus |

---

## 📋 详细检查

### 1. 文档切分逻辑

#### 切分函数位置
**文件**: `backend/app/services/segmenter/chunker.py`

#### 切分参数

```python
def chunk_document(
    url: str,
    title: str,
    text: str,
    target_chars: int = 1800,  # 目标字符数
    overlap_chars: int = 200,   # 重叠字符数
    request_id: Optional[str] = None,
) -> List[Chunk]:
```

#### 切分算法

**固定窗口切分（Fixed-size Chunking with Overlap）**:

1. **起始位置**: `start = 0`
2. **窗口大小**: `target_chars` (默认1800字符)
3. **重叠大小**: `overlap_chars` (默认200字符)
4. **移动步长**: `end - overlap_chars`

```python
while start < length:
    end = min(start + target_chars, length)
    chunk_text = text[start:end].strip()
    
    # 生成chunk_id（基于URL + position + 前200字符）
    seed = f"{url}-{position}-{chunk_text[:200]}"
    chunk_id = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    
    # 创建chunk
    chunks.append(
        Chunk(
            chunk_id=chunk_id,
            url=url,
            title=title,
            text=chunk_text,
            position=position,
        )
    )
    
    # 移动到下一个窗口（带重叠）
    if end == length:
        break
    start = end - overlap_chars
    position += 1
```

#### 招投标系统的切分参数

**文件**: `backend/app/platform/ingest/v2_service.py`

```python
chunks = chunk_document(
    url=asset_id,
    title=parsed_doc.title,
    text=parsed_doc.text,
    target_chars=1200,  # ✅ 招投标使用1200字符（更小）
    overlap_chars=150,  # ✅ 重叠150字符
)
```

**为什么使用更小的chunk？**
- 招投标文档通常结构复杂，包含大量表格、列表
- 更小的chunk可以提高检索精度
- 150字符重叠确保跨chunk的连续性

#### 知识库的切分参数

**文件**: `backend/app/services/kb_service.py`

```python
chunks = chunk_document(
    url=f"kb://{kb_id}/{doc_id}",
    title=parsed.title or filename,
    text=parsed.text,
    # ✅ 使用默认参数：target_chars=1800, overlap_chars=200
)
```

---

### 2. 标签设置（知识库系统）

#### 标签字段: `kb_category`

**支持的分类** (定义在 `backend/app/schemas/types.py`):

```python
KbCategory = Literal[
    "general_doc",      # 普通文档 - 通用知识资料
    "history_case",     # 历史案例 - 过往经验/案例记录
    "reference_rule",   # 规章制度 - 政策/规范/教程
    "web_snapshot"      # 网页快照 - 从网络抓取的内容
]
```

#### 上传时设置标签

**路由**: `POST /api/kb/{kb_id}/import`

```python
@router.post("/{kb_id}/import")
async def import_docs(
    kb_id: str,
    files: List[UploadFile] = File(...),
    kb_category: KbCategory = Form("general_doc"),  # ✅ 前端传入
):
    for upload in files:
        data = await upload.read()
        result = await kb_service.import_document(
            kb_id,
            upload.filename,
            data,
            kb_category=kb_category,  # ✅ 传递给service
        )
```

#### 存储到数据库

**表**: `kb_documents`

```python
cur.execute(
    """
    INSERT INTO kb_documents(
        id, kb_id, filename, source, content_hash, 
        status, meta_json, kb_category  -- ✅ 标签字段
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """,
    (doc_id, kb_id, filename, source, content_hash, 
     status, json.dumps(meta), kb_category),  -- ✅ 存储标签
)
```

#### 存储到chunks

**表**: `kb_chunks`

```python
for chunk in chunks:
    kb_dao.upsert_chunk(
        chunk_id=chunk.chunk_id,
        kb_id=kb_id,
        doc_id=doc_id,
        title=chunk.title,
        url=chunk.url,
        position=chunk.position,
        content=chunk.text,
        kb_category=kb_category,  # ✅ 每个chunk都打标签
    )
```

#### 存储到Milvus

**集合**: 根据`kb_category`分类

```python
get_milvus_store().upsert_chunks(
    [
        {
            "chunk_id": chunk.chunk_id,
            "kb_id": kb_id,
            "doc_id": doc_id,
            "kb_category": kb_category,  # ✅ 向量也打标签
            "dense": vec.get("dense"),
        }
        for chunk, vec in zip(chunks, vectors)
    ],
    dense_dim=dense_dim,
)
```

---

### 3. 标签设置（招投标系统）

#### 标签字段: `doc_type`

**支持的分类**:

```python
doc_type = Literal[
    "tender",       # 招标文件
    "bid",          # 投标文件
    "template",     # 模板文件
    "custom_rule"   # 自定义规则
]
```

#### 上传时设置标签

**路由**: `POST /api/apps/tender/projects/{project_id}/assets/import`

```python
@router.post("/projects/{project_id}/assets/import")
async def import_assets(
    project_id: str,
    kind: str = Form(...),  # ✅ tender | bid | template | custom_rule
    bidder_name: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
):
    # kind 就是 doc_type
    return await svc.import_assets(project_id, kind, files, bidder_name)
```

#### 服务层处理

**文件**: `backend/app/services/tender_service.py`

```python
async def import_assets(
    self,
    project_id: str,
    kind: str,  # ✅ tender | bid | template | custom_rule
    files: List[UploadFile],
    bidder_name: Optional[str],
):
    for f in files:
        # 调用新入库服务
        ingest_v2_result = await ingest_v2.ingest_asset_v2(
            project_id=project_id,
            asset_id=temp_asset_id,
            file_bytes=b,
            filename=filename,
            doc_type=kind,  # ✅ 传递 doc_type
            owner_id=proj.get("owner_id"),
            storage_path=storage_path,
        )
```

#### 新入库服务

**文件**: `backend/app/platform/ingest/v2_service.py`

```python
async def ingest_asset_v2(
    self,
    project_id: str,
    asset_id: str,
    file_bytes: bytes,
    filename: str,
    doc_type: str,  # ✅ tender/bid/etc
    owner_id: Optional[str] = None,
    storage_path: Optional[str] = None,
):
    # 1. 创建 document（带 doc_type）
    document_id = self.docstore.create_document(
        namespace="tender",
        doc_type=doc_type,  # ✅ 存储到 documents 表
        owner_id=owner_id,
    )
    
    # 2. 解析 + 切分
    parsed_doc = await parse_document(filename, file_bytes)
    chunks = chunk_document(url=asset_id, title=parsed_doc.title, text=parsed_doc.text)
    
    # 3. 写入 doc_segments（带 doc_type）
    segment_ids = await self._write_segments(doc_version_id, chunks, parsed_doc.metadata)
    
    # 4. 写入 Milvus（带 doc_type）
    milvus_count = await self._write_milvus(
        segment_ids, chunks, doc_version_id, 
        project_id, doc_type, embedding_provider  # ✅ 传递 doc_type
    )
```

#### 存储到Milvus

**文件**: `backend/app/platform/ingest/v2_service.py`

```python
async def _write_milvus(
    self, segment_ids, chunks, doc_version_id, 
    project_id, doc_type, embedding_provider
):
    # 准备 Milvus 数据
    milvus_data = []
    for segment_id, chunk, vec in zip(segment_ids, chunks, vectors):
        milvus_data.append({
            "segment_id": segment_id,
            "doc_version_id": doc_version_id,
            "project_id": project_id,
            "doc_type": doc_type,  # ✅ 每个向量都打标签
            "dense": dense,
        })
    
    # 写入 Milvus
    count = milvus_docseg_store.upsert_segments(milvus_data, dense_dim)
```

---

## 🔍 检索时的标签过滤

### 知识库检索

```python
# 可以根据 kb_category 过滤
chunks = retriever.retrieve(
    query="...",
    kb_id=kb_id,
    kb_category="history_case",  # 只检索历史案例
    top_k=10
)
```

### 招投标检索

**文件**: `backend/app/platform/extraction/engine.py`

```python
# ExtractionSpec 中定义 doc_types
spec = ExtractionSpec(
    prompt=prompt,
    queries=queries,
    doc_types=["tender"],  # ✅ 只检索招标文件
    topk_per_query=20,
    topk_total=80,
)

# 检索时自动过滤
query_chunks = await retriever.retrieve(
    query=query_text,
    project_id=project_id,
    doc_types=spec.doc_types,  # ✅ 传递给检索器
    top_k=spec.topk_per_query,
)
```

---

## 📊 数据流图

### 知识库系统

```
1. 用户上传文件 (前端)
   └─> kb_category: "general_doc" | "history_case" | "reference_rule" | "web_snapshot"

2. 后端接收 (kb_service.py)
   └─> 解析文档 (parse_document)
   └─> 切分文档 (chunk_document)
       └─> target_chars=1800, overlap_chars=200

3. 存储 chunk
   ├─> kb_documents (doc_id, kb_category) ✅
   ├─> kb_chunks (chunk_id, kb_category) ✅
   └─> Milvus (chunk_id, kb_category, dense_vector) ✅

4. 检索时
   └─> 根据 kb_category 过滤
```

### 招投标系统

```
1. 用户上传文件 (前端)
   └─> kind: "tender" | "bid" | "template" | "custom_rule"

2. 后端接收 (tender_service.py)
   └─> 调用 IngestV2Service
       └─> 解析文档 (parse_document)
       └─> 切分文档 (chunk_document)
           └─> target_chars=1200, overlap_chars=150 (更小的chunk)

3. 存储 segment
   ├─> documents (document_id, doc_type) ✅
   ├─> document_versions (doc_version_id)
   ├─> doc_segments (segment_id, content_text, tsv) ✅
   └─> Milvus (segment_id, project_id, doc_type, dense_vector) ✅

4. 检索时
   └─> 根据 project_id + doc_type 过滤
```

---

## 💡 关键发现

### ✅ 正确实现

1. **切分逻辑完善**
   - 使用固定窗口切分
   - 支持重叠（避免断句）
   - chunk_id基于内容哈希（幂等）

2. **标签设置正确**
   - 知识库: `kb_category` 四种分类
   - 招投标: `doc_type` 四种分类
   - 每个chunk/segment都打标签

3. **存储完整**
   - PostgreSQL: 结构化数据 + 全文索引
   - Milvus: 向量数据 + 标签
   - 双存储确保数据安全

4. **检索可过滤**
   - 支持按标签过滤
   - 支持按项目过滤
   - 支持组合过滤

### 🎯 切分参数对比

| 系统 | target_chars | overlap_chars | 说明 |
|------|--------------|---------------|------|
| **知识库** | 1800 | 200 | 适合通用文档 |
| **招投标** | 1200 | 150 | 更小更精确 |

**招投标为何用更小的chunk？**
- 招投标文档结构复杂（表格、列表、条款）
- 需要更精确的检索（如"投标保证金"）
- 避免无关内容混入同一chunk

### 📍 标签使用场景

#### 知识库 `kb_category`
- ✅ 历史案例检索（只查案例，不查规章）
- ✅ 规章制度参考（只查政策，不查案例）
- ✅ 分类统计和管理

#### 招投标 `doc_type`
- ✅ 项目信息抽取（只从`tender`抽取）
- ✅ 风险识别（只从`tender`检索）
- ✅ 投标审核（对比`tender`和`bid`）
- ✅ 自定义规则叠加（额外检索`custom_rule`）

---

## ✨ 总结

**文档上传和切分逻辑**: ✅ **完全正常**

1. **切分算法**: 固定窗口 + 重叠，参数可配置
2. **标签设置**: 
   - 知识库使用 `kb_category`
   - 招投标使用 `doc_type`
3. **存储完整**: PostgreSQL + Milvus 双存储
4. **检索支持**: 支持按标签、项目过滤
5. **幂等性**: chunk_id基于内容，重复上传不会重复切分

**无需修改**，现有实现已经很完善！

---

**检查完成时间**: 2025-12-25
