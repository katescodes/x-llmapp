# 审核功能恢复到 v0.3.7 版本总结

## 问题描述

用户报告：**审核任务失败，一个都没有比对上**

原因：在之前的清理过程中，删除了投标响应提取功能和相关的数据库表 `tender_bid_response_items`，导致审核功能完全失效，因为审核流程依赖预先提取的投标响应数据。

---

## 错误信息

```
psycopg.errors.UndefinedTable: relation "tender_bid_response_items" does not exist
LINE 5:                     FROM tender_bid_response_items
```

---

## 恢复步骤

### 1️⃣ 恢复数据库表 `tender_bid_response_items`

从 v0.3.7 的 DDL 中恢复表结构：

```sql
CREATE TABLE IF NOT EXISTS tender_bid_response_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  bidder_name TEXT NOT NULL,
  dimension TEXT NOT NULL,
  response_type TEXT NOT NULL,
  response_text TEXT NOT NULL,
  extracted_value_json JSONB,
  evidence_chunk_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- 036 migration 新增字段
  asset_id UUID NULL,
  run_id UUID NULL,
  submission_id UUID NULL,
  normalized_fields_json JSONB NULL,
  evidence_json JSONB NULL
);
```

### 2️⃣ 恢复 `bid_response_service.py`

从 v0.3.7 完整恢复文件：
```bash
git show v0.3.7:backend/app/works/tender/bid_response_service.py > backend/app/works/tender/bid_response_service.py
```

功能：
- 从投标文件中提取响应要素
- 支持两种提取模式：
  - `extract_bid_response`: 逐条提取（52 次 LLM 调用）
  - `extract_bid_response_framework`: 框架式批量提取（6 次 LLM 调用）
- 输出标准化字段 `normalized_fields_json`
- 输出证据片段 `evidence_segment_ids`

### 3️⃣ 恢复投标响应提取 API

在 `backend/app/routers/tender.py` 中恢复 3 个 API：

1. **`POST /projects/{project_id}/extract-bid-responses`**
   - 抽取投标响应要素（逐条模式）
   
2. **`POST /projects/{project_id}/extract-bid-responses-framework`**
   - 抽取投标响应要素（框架式批量模式）
   
3. **`GET /projects/{project_id}/bid-responses`**
   - 获取已提取的投标响应数据

### 4️⃣ 恢复 `ReviewPipelineV3._load_responses` 方法

从之前错误的"返回空列表"修改，恢复为从 `tender_bid_response_items` 表加载数据：

```python
def _load_responses(self, project_id: str, bidder_name: str) -> List[Dict[str, Any]]:
    """加载投标响应"""
    with self.pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT id, dimension, response_type, response_text,
                       extracted_value_json, evidence_chunk_ids,
                       normalized_fields_json, evidence_json
                FROM tender_bid_response_items
                WHERE project_id = %s AND bidder_name = %s
            """, (project_id, bidder_name))
            
            rows = cur.fetchall()
            return [dict(row) for row in rows]
```

### 5️⃣ 恢复前置检查

恢复审核流程对投标响应的强制要求：

```python
# ✅ 前置检查2：确保投标响应已提取
if not responses:
    error_msg = f"❌ 未找到投标响应，请先提取投标响应。项目ID: {project_id}, 投标人: {bidder_name}"
    logger.error(error_msg)
    raise ValueError(error_msg)
```

---

## 审核流程说明（v0.3.7 架构）

### 完整审核流程

```
1. 用户上传招标文件
   ↓
2. 提取招标要求
   API: POST /projects/{id}/extract/requirements
   存储到: tender_requirements 表
   ↓
3. 用户上传投标文件
   ↓
4. 提取投标响应 ⭐️ 必需步骤
   API: POST /projects/{id}/extract-bid-responses-framework
   存储到: tender_bid_response_items 表
   ↓
5. 执行审核
   API: POST /projects/{id}/audit/unified
   - 加载招标要求（从 tender_requirements）
   - 加载投标响应（从 tender_bid_response_items）
   - 使用 ReviewPipelineV3 进行审核
   - 保存审核结果（到 tender_review_items）
   ↓
6. 查看审核结果
   API: GET /projects/{id}/review?bidder_name=xxx
```

### 为什么需要预提取投标响应？

1. **性能优化**：避免在审核时重复提取响应（审核可能多次运行）
2. **结果复用**：提取的响应可用于其他功能（如报价分析、合规性检查）
3. **流程解耦**：提取和审核分离，便于独立优化和调试
4. **缓存机制**：预提取的响应作为缓存，加速审核流程

---

## 修改的文件清单

### 数据库
- ✅ 恢复表：`tender_bid_response_items`（包含所有字段）

### 后端代码
- ✅ 恢复文件：`backend/app/works/tender/bid_response_service.py`（从 v0.3.7）
- ✅ 修改文件：`backend/app/routers/tender.py`（添加 3 个投标响应 API）
- ✅ 修改文件：`backend/app/works/tender/review_pipeline_v3.py`（恢复 `_load_responses` 方法和前置检查）
- ✅ 修改文件：`backend/app/works/tender/unified_audit_service.py`（使用 ReviewPipelineV3）

---

## 测试验证

### 1. 验证表已恢复
```bash
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "\d tender_bid_response_items"
```

### 2. 验证服务启动
```bash
docker logs localgpt-backend --tail 20 | grep "Application startup complete"
```

### 3. 完整测试流程

1. **提取招标要求**
   ```
   POST /api/apps/tender/projects/{project_id}/extract/requirements
   ```

2. **提取投标响应（框架式）**
   ```
   POST /api/apps/tender/projects/{project_id}/extract-bid-responses-framework
   Body: {
     "bidder_name": "测试投标人"
   }
   ```

3. **执行审核**
   ```
   POST /api/apps/tender/projects/{project_id}/audit/unified
   Body: {
     "bidder_name": "测试投标人"
   }
   ```

4. **查看审核结果**
   ```
   GET /api/apps/tender/projects/{project_id}/review?bidder_name=测试投标人
   ```

---

## 架构对比

### 之前的错误架构（已修复）

```
审核流程
  ├─ 加载招标要求 ✅
  ├─ 加载投标响应 ❌ 返回空列表
  ├─ 构建候选对 ❌ 无响应数据
  ├─ Hard Gate ❌ 无法匹配
  ├─ Semantic ❌ 无法判断
  └─ 结果：全部未匹配 ❌
```

### v0.3.7 正确架构（已恢复）

```
提取投标响应
  ├─ 从投标文件中提取 ✅
  ├─ LLM 解析结构化数据 ✅
  └─ 保存到 tender_bid_response_items ✅
      ↓
审核流程
  ├─ 加载招标要求 ✅
  ├─ 加载投标响应 ✅ 从数据库加载
  ├─ 构建候选对 ✅ requirement ↔ response
  ├─ Hard Gate ✅ 确定性判断
  ├─ Semantic ✅ LLM 语义判断
  └─ 结果：准确匹配和判断 ✅
```

---

## 重要提示

### ⚠️ 审核前必须先提取投标响应

**错误操作流程：**
```
1. 提取招标要求
2. 直接执行审核 ❌
   → 错误：未找到投标响应
```

**正确操作流程：**
```
1. 提取招标要求
2. 提取投标响应 ⭐️
3. 执行审核 ✅
```

### 📝 前端 UI 建议

建议在前端添加流程提示：
1. 审核按钮应在"提取投标响应"完成后才启用
2. 如果审核失败提示"未找到投标响应"，应引导用户先执行"提取投标响应"
3. 显示清晰的流程步骤：要求提取 → 响应提取 → 审核

---

## 总结

✅ **问题已完全解决**

- 恢复了 `tender_bid_response_items` 表
- 恢复了投标响应提取服务和 API
- 恢复了审核流程对预提取响应的依赖
- 系统回退到 v0.3.7 的稳定审核架构

现在审核功能应该可以正常匹配和判断了！🎉

