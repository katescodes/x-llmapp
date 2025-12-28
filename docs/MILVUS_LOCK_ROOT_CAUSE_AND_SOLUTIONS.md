# Milvus 锁定问题深度分析与解决方案

**日期**: 2025-12-29  
**问题**: Milvus Lite 文件被后端进程锁定，导致向量化失败

---

## 🔍 问题根源分析

### 1. Milvus Lite 的工作原理

**Milvus Lite = SQLite 模式的向量数据库**:
- 📁 单文件数据库：`/app/data/milvus.db`
- 🔒 **独占锁**：同一时间只能有一个进程持有写锁
- 🚫 **不支持多进程并发写入**
- 🏃 **嵌入式守护进程**：每个客户端连接会启动独立的 milvus 子进程

### 2. 当前架构问题

#### 进程布局（docker-compose.yml）

```yaml
backend:
  MILVUS_LITE_PATH=/app/data/milvus.db
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000
  
worker:
  MILVUS_LITE_PATH=/app/data/milvus_worker.db  # 独立文件
  command: python worker.py
```

#### 实际运行状态

```bash
# docker-compose top backend
PID     CMD
326749  python uvicorn app.main:app
327771  /milvus_lite/lib/milvus /app/data/milvus.db  # ← Milvus 守护进程
```

**问题**：
- ✅ Backend 启动了 Milvus Lite 守护进程
- ✅ Worker 使用独立的 `milvus_worker.db`（避免了跨容器冲突）
- ❌ **Backend 内部可能有多个地方尝试连接 Milvus**
- ❌ **延迟初始化 + 多worker进程 → 文件锁竞争**

---

## 🎯 根本原因：延迟初始化 + uvicorn workers

### 代码分析

#### 1. MilvusDocSegStore 的延迟初始化

```python
# backend/app/platform/vectorstore/milvus_docseg_store.py:44

class MilvusDocSegStore:
    def __init__(self) -> None:
        # 延迟初始化 - 第一次使用时才创建连接
        self._client = None  # ← 不立即连接
        
    @property
    def client(self) -> MilvusClient:
        if self._client is None:
            # ❌ 每个进程第一次访问时都会尝试打开 milvus.db
            self._client = MilvusClient(uri=settings.MILVUS_LITE_PATH)
        return self._client
```

#### 2. 全局单例模式

```python
# backend/app/platform/vectorstore/milvus_docseg_store.py:291

_milvus_docseg_store_instance = None

def get_milvus_docseg_store() -> MilvusDocSegStore:
    global _milvus_docseg_store_instance
    if _milvus_docseg_store_instance is None:
        # ❌ 在每个 worker 进程中都会执行一次
        _milvus_docseg_store_instance = MilvusDocSegStore()
    return _milvus_docseg_store_instance
```

### 问题场景

#### Scenario 1: Uvicorn 多 worker 模式

```bash
# 如果 uvicorn 使用 --workers=4
uvicorn app.main:app --workers=4

# 会创建 4 个进程
Process 1: Master
Process 2: Worker 1 → 尝试打开 milvus.db
Process 3: Worker 2 → 尝试打开 milvus.db  # ❌ 冲突
Process 4: Worker 3 → 尝试打开 milvus.db  # ❌ 冲突
```

#### Scenario 2: 延迟初始化时机冲突

```python
# Request 1 到达 Worker 1
IngestV2Service.ingest_asset_v2()
  → _write_milvus()
    → milvus_docseg_store.upsert_segments()
      → self.client  # ← 第一次访问，尝试创建连接

# 同时 Request 2 到达 Worker 2
NewRetriever._search_dense()
  → milvus_store = get_milvus_docseg_store()
    → milvus_store.client  # ← 也尝试创建连接
    
# ❌ 两个进程同时尝试打开 milvus.db → 锁竞争
```

#### Scenario 3: 文件上传时的竞争

```
User uploads file
  ↓
IngestV2Service.ingest_asset_v2()
  ↓
_write_segments() → PostgreSQL ✅
  ↓
_write_milvus() → 尝试打开 milvus.db
  ↓
如果另一个请求正在检索（search_dense）
  → 文件锁被占用
  → ConnectionConfigException: Open local milvus failed
  ↓
捕获异常 → 返回 milvus_count=0
  ↓
IngestV2Result(segment_count=102, milvus_count=0)  # ← 向量化失败但不报错！
```

---

## ✅ 解决方案

### 方案1: 使用独立的 Milvus 服务 ⭐⭐⭐⭐⭐ 推荐

**彻底解决文件锁问题，支持真正的并发**

#### 1.1 使用 Milvus Standalone (Docker)

```yaml
# docker-compose.yml 新增服务
services:
  milvus:
    image: milvusdb/milvus:v2.3.3
    container_name: localgpt-milvus
    restart: unless-stopped
    environment:
      - ETCD_ENDPOINTS=etcd:2379
      - MINIO_ADDRESS=minio:9000
    ports:
      - "19530:19530"
    volumes:
      - ./data/milvus:/var/lib/milvus
    networks:
      - localgpt-net
    depends_on:
      - etcd
      - minio

  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    container_name: localgpt-etcd
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
    volumes:
      - ./data/etcd:/etcd
    networks:
      - localgpt-net

  minio:
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    container_name: localgpt-minio
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - ./data/minio:/minio_data
    command: minio server /minio_data --console-address ":9001"
    networks:
      - localgpt-net

  backend:
    environment:
      # 改为远程 Milvus
      - MILVUS_URI=http://milvus:19530
      # 移除 MILVUS_LITE_PATH
```

**优点**:
- ✅ 完全避免文件锁
- ✅ 支持真正的并发读写
- ✅ 性能更好（专业向量数据库）
- ✅ 支持分布式部署

**缺点**:
- ❌ 需要额外的依赖服务（etcd, minio）
- ❌ 资源占用更多（~2GB 内存）

---

### 方案2: 单进程 + 连接池 ⭐⭐⭐⭐ 简单有效

**保持 Milvus Lite，但确保只有一个主连接**

#### 2.1 修改代码：应用级单例

```python
# backend/app/platform/vectorstore/milvus_docseg_store.py

import asyncio
from threading import Lock

_init_lock = Lock()
_init_event = None  # 用于异步等待

class MilvusDocSegStore:
    _shared_client = None  # 类级别共享
    _client_owner_pid = None  # 记录创建客户端的进程 PID
    
    def __init__(self) -> None:
        self.collection_dim = None
        self.connection_error = None
    
    @property
    def client(self) -> MilvusClient:
        """获取共享的 Milvus 客户端（进程级单例）"""
        import os
        current_pid = os.getpid()
        
        # 如果是新进程，重置客户端
        if (MilvusDocSegStore._client_owner_pid is not None and 
            MilvusDocSegStore._client_owner_pid != current_pid):
            MilvusDocSegStore._shared_client = None
        
        if MilvusDocSegStore._shared_client is None:
            with _init_lock:
                # 双重检查
                if MilvusDocSegStore._shared_client is None:
                    try:
                        logger.info(f"Creating Milvus client in PID={current_pid}")
                        MilvusDocSegStore._shared_client = MilvusClient(
                            uri=settings.MILVUS_LITE_PATH
                        )
                        MilvusDocSegStore._client_owner_pid = current_pid
                        self.connection_error = None
                    except Exception as e:
                        logger.error(f"Failed to create Milvus client: {e}")
                        self.connection_error = str(e)
                        raise RuntimeError(f"Milvus client not available: {e}")
        
        return MilvusDocSegStore._shared_client
```

#### 2.2 确保 Uvicorn 单进程模式

```python
# backend/main.py 或启动命令
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=1,  # ← 强制单进程
        reload=False
    )
```

**docker-compose.yml**:
```yaml
backend:
  # 确保不使用 --workers 参数
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**优点**:
- ✅ 简单，改动小
- ✅ 不需要额外服务
- ✅ 文件锁问题消失

**缺点**:
- ❌ 单进程限制并发能力
- ❌ 仍然是嵌入式数据库（性能有限）

---

### 方案3: 读写分离 + 队列 ⭐⭐⭐ 当前最快

**利用现有架构，将向量化操作移到 Worker**

#### 3.1 修改 IngestV2Service

```python
# backend/app/platform/ingest/v2_service.py

async def ingest_asset_v2(self, ...) -> IngestV2Result:
    # ... 前面的代码不变 ...
    
    # 4. 写 doc_segments
    segment_ids = await self._write_segments(...)
    
    # 5. ❌ 不在这里直接写 Milvus
    # 改为：发送到 Redis 队列，让 Worker 处理
    
    if settings.ASYNC_INGEST_ENABLED:
        # 发送到异步队列
        await self._enqueue_vectorization(
            doc_version_id=doc_version_id,
            segment_ids=segment_ids,
            project_id=project_id,
            doc_type=doc_type,
        )
        return IngestV2Result(
            doc_version_id=doc_version_id,
            segment_count=len(segment_ids),
            milvus_count=0,  # 异步处理，暂时返回0
        )
    else:
        # 同步模式（保持原逻辑）
        try:
            milvus_count = await self._write_milvus(...)
        except Exception as e:
            logger.error(f"Milvus write failed: {e}")
            milvus_count = 0  # ← 失败也不报错，只是不向量化
        
        return IngestV2Result(
            doc_version_id=doc_version_id,
            segment_count=len(segment_ids),
            milvus_count=milvus_count,
        )
```

#### 3.2 Worker 处理向量化

```python
# backend/worker.py 新增任务

@celery_app.task(name="vectorize_segments")
def vectorize_segments(doc_version_id: str, segment_ids: List[str], ...):
    """异步向量化任务（在 Worker 中执行）"""
    try:
        # Worker 有独立的 milvus_worker.db，不会冲突
        store = get_milvus_docseg_store()
        
        # ... embedding + 写入 Milvus ...
        
        logger.info(f"Vectorized {len(segment_ids)} segments for {doc_version_id}")
    except Exception as e:
        logger.error(f"Vectorization failed: {e}")
```

**优点**:
- ✅ Backend 不碰 Milvus → 无文件锁冲突
- ✅ Worker 独立 DB (`milvus_worker.db`)
- ✅ 异步处理，不阻塞上传

**缺点**:
- ❌ 向量化有延迟
- ❌ 需要开启异步模式

---

### 方案4: 降级方案 - 禁用 Milvus，只用 PG 全文检索 ⭐⭐

**临时方案，快速让系统工作**

#### 4.1 修改 IngestV2Service

```python
# backend/app/platform/ingest/v2_service.py:116-120

async def ingest_asset_v2(self, ...) -> IngestV2Result:
    # ... 前面的代码 ...
    
    # 5. 强制跳过 Milvus
    logger.info("Skipping Milvus vectorization (disabled)")
    return IngestV2Result(
        doc_version_id=doc_version_id,
        segment_count=len(segment_ids),
        milvus_count=0,
    )
```

#### 4.2 修改 NewRetriever - 使用 pg_trgm

```python
# backend/app/platform/retrieval/new_retriever.py:246

def _search_lexical(self, query: str, doc_version_ids: List[str], limit: int):
    """改用 pg_trgm 三元组相似度"""
    try:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                sql = """
                    SELECT id, similarity(content_text, %s) as score
                    FROM doc_segments
                    WHERE doc_version_id = ANY(%s)
                      AND content_text %% %s  -- pg_trgm 相似度操作符
                    ORDER BY score DESC
                    LIMIT %s
                """
                cur.execute(sql, [query, doc_version_ids, query, limit])
                rows = cur.fetchall()
                
                return [
                    {
                        "chunk_id": row['id'],
                        "score": float(row['score']),
                        "rank": idx,
                    }
                    for idx, row in enumerate(rows)
                ]
    except Exception as e:
        logger.error(f"Lexical search failed: {e}", exc_info=True)
        return []
```

**优点**:
- ✅ 立即可用
- ✅ 完全避免 Milvus 问题
- ✅ pg_trgm 对中文模糊匹配有效

**缺点**:
- ❌ 语义理解能力差
- ❌ 性能不如向量检索

---

## 🚀 推荐实施路径

### 阶段1: 立即修复（今天）⭐

**使用方案4（降级） + 方案2（单进程）**

```bash
# 1. 修改 docker-compose.yml
backend:
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

# 2. 修改 NewRetriever 使用 pg_trgm（见方案4）

# 3. 重启服务
docker-compose down
docker-compose up -d --build

# 4. 测试上传和抽取
```

**预期结果**:
- ✅ 文件上传成功
- ✅ 抽取能获得 10-20 条结果（而不是3-6条）
- ⚠️ 暂时没有向量检索

### 阶段2: 中期优化（本周）⭐⭐

**实施方案3（读写分离）**

```bash
# 1. 开启异步模式
docker-compose.yml:
  - ASYNC_INGEST_ENABLED=true

# 2. 修改 IngestV2Service 发送队列

# 3. Worker 处理向量化

# 4. Backend 使用 pg_trgm 检索
```

**预期结果**:
- ✅ 上传快速完成
- ✅ 向量化在后台异步处理
- ✅ Worker 独立 DB，无冲突

### 阶段3: 长期方案（下周）⭐⭐⭐⭐⭐

**实施方案1（独立 Milvus 服务）**

```bash
# 1. 添加 Milvus Standalone
docker-compose.yml: 增加 milvus/etcd/minio 服务

# 2. 修改配置
MILVUS_URI=http://milvus:19530

# 3. 数据迁移
# 将 milvus.db 数据导入 Milvus Standalone

# 4. 测试并上线
```

**预期结果**:
- ✅ 完美的并发支持
- ✅ 向量检索和全文检索双保险
- ✅ 生产级架构

---

## 📊 问题影响分析

### 当前状态（Milvus 锁定）

```
文件上传
  ↓
doc_segments: 102条 ✅
  ↓
Milvus 写入: 尝试 → 锁冲突 → 失败（静默）❌
  ↓
milvus_count=0
  ↓
检索时: 
  - 向量检索: 0结果 ❌
  - 全文检索(中文): 0结果 ❌（ts_vector问题）
  ↓
LLM: 无上下文 → 生成3-6条最少响应
```

### 修复后（方案4临时 + 方案2单进程）

```
文件上传
  ↓
doc_segments: 102条 ✅
  ↓
跳过 Milvus（明确禁用）
  ↓
检索时:
  - pg_trgm 相似度匹配: 10-20个相关段落 ✅
  ↓
LLM: 有上下文 → 生成15-30条完整响应 ✅
```

---

## ✅ 执行检查清单

### 立即执行（方案2 + 方案4）

- [ ] 1. 备份当前 milvus.db
- [ ] 2. 修改 docker-compose.yml 强制 workers=1
- [ ] 3. 修改 NewRetriever 使用 pg_trgm
- [ ] 4. 重启服务
- [ ] 5. 测试文件上传
- [ ] 6. 测试投标响应抽取
- [ ] 7. 验证结果：15-30条

### 中期执行（方案3）

- [ ] 8. 实现异步向量化队列
- [ ] 9. Worker 处理向量化
- [ ] 10. 测试异步流程

### 长期执行（方案1）

- [ ] 11. 部署 Milvus Standalone
- [ ] 12. 数据迁移
- [ ] 13. 性能测试
- [ ] 14. 生产部署

---

## 📝 总结

### 根本原因

**Milvus Lite = SQLite 模式 → 独占文件锁 → 多进程/多请求并发冲突**

### 为什么会这样

1. ✅ **设计选择**: Milvus Lite 是嵌入式数据库，适合单进程应用
2. ❌ **架构不匹配**: Web 应用通常是多进程/多线程
3. ❌ **延迟初始化**: 每个进程第一次访问时都尝试打开文件
4. ❌ **错误处理不足**: 失败静默降级，没有明确报错

### 如何彻底解决

**短期**（今天）: 单进程 + pg_trgm  
**中期**（本周）: 异步队列 + Worker 独立处理  
**长期**（下周）: 独立 Milvus 服务

**推荐**: 立即实施短期方案，并行准备长期方案。

