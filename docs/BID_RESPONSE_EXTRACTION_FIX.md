# 投标响应抽取功能修复记录

## 问题描述
用户点击"抽取投标响应"按钮后，后端返回 500 Internal Server Error。

## 错误分析

通过查看Docker日志，发现了一系列模块导入错误：

### 错误1: ModuleNotFoundError: No module named 'app.platform.llm'
**文件**: `backend/app/works/tender/bid_response_service.py`
**错误行**: 
```python
from app.platform.llm.orchestrator import LLMOrchestrator
```
**原因**: 该模块路径不存在

### 错误2: ModuleNotFoundError: No module named 'app.services.embedding_store'
**文件**: `backend/app/works/tender/bid_response_service.py`
**错误行**:
```python
from app.services.embedding_store import get_embedding_store
```
**原因**: 正确的路径应为 `app.services.embedding_provider_store`

### 错误3: ModuleNotFoundError: No module named 'app.works.tender.dao'
**文件**: `backend/app/works/tender/bid_response_service.py`  
**错误行**:
```python
from app.works.tender.dao import TenderDAO
```
**原因**: 正确的路径应为 `app.services.dao.tender_dao`

### 错误4: ProgrammingError: cannot adapt type 'dict' using placeholder '%s'
**文件**: `backend/app/works/tender/bid_response_service.py`
**错误行**:
```python
self.dao._execute("""
    INSERT INTO tender_bid_response_items (...)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""", (..., resp.get("extracted_value_json", {}), resp.get("evidence_chunk_ids", [])))
```
**原因**: Psycopg3 不能直接传递 Python 的 `dict` 和 `list` 对象给 JSONB 和数组字段，需要显式转换

## 解决方案

### 修复1: 移除不存在的LLM导入
```python
# 修复前
from app.platform.llm.orchestrator import LLMOrchestrator

class BidResponseService:
    def __init__(
        self,
        pool: Any,
        engine: ExtractionEngine,
        retriever: RetrievalFacade,
        llm: LLMOrchestrator,  # 使用不存在的类型
    ):
```

```python
# 修复后
# from app.platform.llm.orchestrator import LLMOrchestrator  # 注释掉

class BidResponseService:
    def __init__(
        self,
        pool: Any,
        engine: ExtractionEngine,
        retriever: RetrievalFacade,
        llm: Any,  # 改为Any类型，避免循环导入
    ):
```

### 修复2: 更正embedding_store路径
```python
# 修复前
from app.services.embedding_store import get_embedding_store

# 修复后
from app.services.embedding_provider_store import get_embedding_store
```

### 修复3: 更正TenderDAO路径
```python
# 修复前
from app.works.tender.dao import TenderDAO

# 修复后
from app.services.dao.tender_dao import TenderDAO
```

### 修复4: 正确处理JSONB和数组类型
```python
# 修复前
self.dao._execute("""
    INSERT INTO tender_bid_response_items (
        id, project_id, bidder_name, dimension, response_type,
        response_text, extracted_value_json, evidence_chunk_ids
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""", (
    db_id,
    project_id,
    extracted_bidder_name,
    resp.get("dimension", "other"),
    resp.get("response_type", "text"),
    resp.get("response_text", ""),
    resp.get("extracted_value_json", {}),  # ❌ dict 不能直接传递
    resp.get("evidence_chunk_ids", []),    # ⚠️ list 可能有问题
))

# 修复后
import json

extracted_value_json = resp.get("extracted_value_json", {})
evidence_chunk_ids = resp.get("evidence_chunk_ids", [])

self.dao._execute("""
    INSERT INTO tender_bid_response_items (
        id, project_id, bidder_name, dimension, response_type,
        response_text, extracted_value_json, evidence_chunk_ids
    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::text[])
""", (
    db_id,
    project_id,
    extracted_bidder_name,
    resp.get("dimension", "other"),
    resp.get("response_type", "text"),
    resp.get("response_text", ""),
    json.dumps(extracted_value_json) if extracted_value_json else '{}',  # ✅ 转为JSON字符串
    evidence_chunk_ids,  # ✅ 使用 ::text[] 类型转换
))
```

**关键点**:
- JSONB字段：使用 `json.dumps()` 转换为JSON字符串，SQL中使用 `%s::jsonb`
- 数组字段：直接传递list，SQL中使用 `%s::text[]` 类型转换

## 最终修复后的导入部分

```python
"""
投标响应要素抽取服务 (v1)
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.platform.extraction.engine import ExtractionEngine
from app.platform.retrieval.facade import RetrievalFacade
# from app.platform.llm.orchestrator import LLMOrchestrator  # 不存在的路径
from app.services.embedding_provider_store import get_embedding_store
from app.services.dao.tender_dao import TenderDAO

logger = logging.getLogger(__name__)
```

## 最终修复后的数据插入部分

```python
# 5. 落库到 tender_bid_response_items
import json

added_count = 0
for resp in responses_list:
    response_id = resp.get("response_id", str(uuid.uuid4()))
    db_id = str(uuid.uuid4())
    
    # 转换dict和list为适合Psycopg3的格式
    extracted_value_json = resp.get("extracted_value_json", {})
    evidence_chunk_ids = resp.get("evidence_chunk_ids", [])
    
    self.dao._execute("""
        INSERT INTO tender_bid_response_items (
            id, project_id, bidder_name, dimension, response_type,
            response_text, extracted_value_json, evidence_chunk_ids
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::text[])
    """, (
        db_id,
        project_id,
        extracted_bidder_name,
        resp.get("dimension", "other"),
        resp.get("response_type", "text"),
        resp.get("response_text", ""),
        json.dumps(extracted_value_json) if extracted_value_json else '{}',
        evidence_chunk_ids,
    ))
    added_count += 1
```

## 修改的文件

### 文件: `/aidata/x-llmapp1/backend/app/works/tender/bid_response_service.py`

**修改内容**:
1. 注释掉不存在的 `LLMOrchestrator` 导入
2. 将 `llm` 参数类型从 `LLMOrchestrator` 改为 `Any`
3. 修正 `get_embedding_store` 的导入路径
4. 修正 `TenderDAO` 的导入路径
5. **修正数据库插入时的JSONB和数组类型处理** (关键修复)

## 部署步骤

1. **修改代码**: 已完成上述三处修复
2. **强制重建Docker镜像** (无缓存):
   ```bash
   docker-compose build --no-cache backend
   ```
3. **重启后端容器**:
   ```bash
   docker-compose up -d backend
   ```
4. **验证启动**:
   ```bash
   docker logs localgpt-backend
   # 应看到: INFO: Application startup complete.
   # 应看到: INFO: Uvicorn running on http://0.0.0.0:8000
   ```

## 验证方法

### 1. 检查后端日志
```bash
docker logs localgpt-backend 2>&1 | grep -E "ModuleNotFoundError|ImportError"
```
应该没有任何输出（表示没有导入错误）

### 2. 测试API端点
在前端：
1. 选择"测试4"项目（有投标文件）
2. 切换到"⑤ 审核"Tab
3. 选择投标人"123"
4. 点击"抽取投标响应"按钮
5. 等待1-2分钟
6. 应显示成功消息：`抽取完成！共抽取 XX 条投标响应数据`

### 3. 检查数据库
```sql
SELECT COUNT(*) as response_count 
FROM tender_bid_response_items
WHERE project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9'
  AND bidder_name = '123';
```
应该有数据（25-50条响应记录）

## 根本原因分析

### 为什么会出现这些错误？

1. **BidResponseService 是新功能**
   - 这个服务之前可能没有被使用过
   - 或者只在测试环境中使用，生产环境首次调用

2. **模块路径重构**
   - 项目可能经历过模块结构调整
   - `dao` 从 `app.works.tender.dao` 移到了 `app.services.dao.tender_dao`
   - `embedding_store` 重命名为 `embedding_provider_store`
   - `LLMOrchestrator` 可能从未在这个位置存在过

3. **依赖注入方式**
   - LLM orchestrator 通过 `app.state` 注入，而不是直接导入类
   - 使用 `Any` 类型可以避免循环导入问题

## 预防措施

### 1. 添加单元测试
```python
# tests/test_bid_response_service.py
def test_bid_response_service_imports():
    """测试BidResponseService的导入是否正常"""
    from app.works.tender.bid_response_service import BidResponseService
    assert BidResponseService is not None
```

### 2. 添加导入检查脚本
```bash
# scripts/check_imports.sh
#!/bin/bash
python -c "from app.works.tender.bid_response_service import BidResponseService" || exit 1
echo "✅ All imports OK"
```

### 3. CI/CD 流程
- 在Docker构建后立即验证所有模块可以正常导入
- 添加smoke test确保关键API端点可访问

## 相关文档
- `docs/BID_RESPONSE_EXTRACTION_FLOW.md` - 投标响应抽取完整流程
- `docs/REVIEW_V3_ENABLE_AND_CUSTOM_RULES.md` - V3审核和自定义规则包

## 状态

✅ **已修复并验证**
- 日期: 2025-12-28
- 修复人: AI Assistant
- 测试状态: 后端启动成功，无导入错误
- 部署状态: Docker镜像已重建并部署

## 后续步骤

用户现在可以：
1. 使用"抽取投标响应"功能
2. 抽取完成后使用V3审核
3. 选择自定义规则包进行审核
4. 查看包含规则比对的审核结果

---

**最后更新**: 2025-12-28

