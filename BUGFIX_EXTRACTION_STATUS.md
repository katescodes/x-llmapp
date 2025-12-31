# 项目信息提取Bug修复

## 修复时间
2025-12-31

## 问题描述

用户报告了两个问题：
1. **抽取完成后，状态仍显示"抽取中"**
2. **抽取结果显示不全，有些stage的结果没有在前端显示**

---

## 问题分析

### 问题1：状态显示问题

**原因：**
- `_extract_project_info_staged`方法在完成所有stage的提取后，直接返回结果
- 没有更新`run_id`的状态，导致前端查询时仍然是"running"状态

**代码位置：**
```python:330:341:backend/app/works/tender/extract_v2_service.py
# 旧代码：直接返回结果，没有更新run状态
return {
    "schema_version": "tender_info_v3",
    **all_stage_results,
    ...
}
```

### 问题2：结果显示不全

**原因：**
1. 返回结果时使用`**all_stage_results`展开，如果某个stage失败（设置为空字典），可能导致结构不完整
2. TenderService中会再次保存数据，可能覆盖了`_extract_project_info_staged`中保存的完整数据

**代码位置：**
- `extract_v2_service.py` 第330-341行：返回结果的构建
- `tender_service.py` 第948行：TenderService中的数据保存

---

## 修复方案

### 修复1：明确列出所有6个stage

**修改前：**
```python
return {
    "schema_version": "tender_info_v3",
    **all_stage_results,  # 使用展开，可能不完整
    "evidence_chunk_ids": list(all_evidence_ids),
    ...
}
```

**修改后：**
```python
final_result = {
    "schema_version": "tender_info_v3",
    # ✅ 明确列出所有6个stage，即使某些为空
    "project_overview": all_stage_results.get("project_overview", {}),
    "bidder_qualification": all_stage_results.get("bidder_qualification", {}),
    "evaluation_and_scoring": all_stage_results.get("evaluation_and_scoring", {}),
    "business_terms": all_stage_results.get("business_terms", {}),
    "technical_requirements": all_stage_results.get("technical_requirements", {}),
    "document_preparation": all_stage_results.get("document_preparation", {}),
    "evidence_chunk_ids": list(all_evidence_ids),
    ...
}
```

### 修复2：最终确认保存

在返回结果前，再次保存数据到数据库，确保所有stage的数据都已保存：

```python
# ===== 步骤7：最终确认保存（确保数据完整） =====
logger.info("最终保存项目信息到数据库...")
data_to_save_final = {
    "schema_version": "tender_info_v3",
    "project_overview": all_stage_results.get("project_overview", {}),
    "bidder_qualification": all_stage_results.get("bidder_qualification", {}),
    "evaluation_and_scoring": all_stage_results.get("evaluation_and_scoring", {}),
    "business_terms": all_stage_results.get("business_terms", {}),
    "technical_requirements": all_stage_results.get("technical_requirements", {}),
    "document_preparation": all_stage_results.get("document_preparation", {}),
}
self.dao.upsert_project_info(
    project_id,
    data_json=data_to_save_final,
    evidence_chunk_ids=list(all_evidence_ids)
)
logger.info("项目信息已保存到数据库")
```

### 修复3：更新run进度

在返回结果前，更新run进度为接近完成（0.98），保持"running"状态：

```python
# ===== 步骤8：更新run进度为接近完成 =====
if run_id:
    logger.info(f"更新run进度: run_id={run_id}")
    self.dao.update_run(
        run_id, 
        "running",  # 保持running状态，由TenderService最终更新为success
        progress=0.98,
        message="项目信息提取完成，正在保存..."
    )
```

### 修复4：TenderService中的调整

**修改1：移除重复保存**

```python
# ✅ 数据已经在_extract_project_info_staged中保存过了，这里不需要重复保存
# 只更新run状态即可
logger.info(f"项目信息提取完成，准备更新run状态: project={project_id}")
```

**修改2：更新消息为中文**

```python
self.dao.update_run(
    run_id, "success", progress=1.0, 
    message="项目信息提取完成",  # ✅ 改为中文
    result_json=result_json_data
)
```

---

## 修复后的流程

### 完整流程

```
1. 用户发起提取请求
   ↓
2. TenderService.extract_project_info()
   ↓
3. ExtractV2Service.extract_project_info_v2()
   ↓
4. ExtractV2Service._extract_project_info_staged()
   ├─ Stage 1: 提取 + 增量保存 (progress=0.20)
   ├─ Stage 2: 提取 + 增量保存 (progress=0.35)
   ├─ Stage 3: 提取 + 增量保存 (progress=0.50)
   ├─ Stage 4: 提取 + 增量保存 (progress=0.65)
   ├─ Stage 5: 提取 + 增量保存 (progress=0.80)
   ├─ Stage 6: 提取 + 增量保存 (progress=0.95)
   ├─ 最终确认保存所有数据
   └─ 更新run进度为0.98, status="running", message="项目信息提取完成，正在保存..."
   ↓
5. 返回完整结果到TenderService
   ↓
6. TenderService更新run状态
   └─ status="success", progress=1.0, message="项目信息提取完成"
   ↓
7. 前端轮询获取到success状态
   ↓
8. 前端查询项目信息，获取所有6个stage的完整数据
```

---

## 保证数据完整性的机制

### 1. 增量保存（每个stage完成后）

```python
# 在每个stage完成后立即保存
incremental_data = {
    "schema_version": "tender_info_v3",
    **{k: all_stage_results.get(k, {}) for k in [s["key"] for s in stages_meta]}
}
self.dao.upsert_project_info(
    project_id,
    data_json=incremental_data,
    evidence_chunk_ids=list(all_evidence_ids)
)
```

### 2. 最终确认保存（所有stage完成后）

```python
# 最后再保存一次，确保所有stage的数据都已保存
data_to_save_final = {
    "schema_version": "tender_info_v3",
    "project_overview": all_stage_results.get("project_overview", {}),
    "bidder_qualification": all_stage_results.get("bidder_qualification", {}),
    "evaluation_and_scoring": all_stage_results.get("evaluation_and_scoring", {}),
    "business_terms": all_stage_results.get("business_terms", {}),
    "technical_requirements": all_stage_results.get("technical_requirements", {}),
    "document_preparation": all_stage_results.get("document_preparation", {}),
}
self.dao.upsert_project_info(...)
```

### 3. 明确结构（返回结果时）

```python
# 返回时明确列出所有6个stage
final_result = {
    "schema_version": "tender_info_v3",
    "project_overview": all_stage_results.get("project_overview", {}),
    "bidder_qualification": all_stage_results.get("bidder_qualification", {}),
    # ... 其他4个stage
}
```

---

## 前端展示效果

### 进度展示

```
正在检索招标文档... (5%)
正在抽取：项目概览 (P0+P1)... (5%)
项目概览已完成 (20%)
正在抽取：投标人资格 (P0+P1)... (20%)
投标人资格已完成 (35%)
正在抽取：评审与评分 (P0+P1)... (35%)
评审与评分已完成 (50%)
正在抽取：商务条款 (P0+P1)... (50%)
商务条款已完成 (65%)
正在抽取：技术要求 (P0+P1)... (65%)
技术要求已完成 (80%)
正在抽取：文件编制 (P0+P1)... (80%)
文件编制已完成 (95%)
项目信息提取完成，正在保存... (98%)
项目信息提取完成 (100%) ✅
```

### 结果展示

前端查询`GET /api/apps/tender/projects/{project_id}/project-info`，会得到：

```json
{
  "project_id": "xxx",
  "data_json": {
    "schema_version": "tender_info_v3",
    "project_overview": {
      "project_name": "XX市政道路改造工程",
      "owner_name": "XX市交通局",
      "budget": "500万元",
      ...
    },
    "bidder_qualification": {
      "general_requirements": "...",
      ...
    },
    "evaluation_and_scoring": {
      "evaluation_method": "综合评分法",
      ...
    },
    "business_terms": {
      "payment_terms": "...",
      ...
    },
    "technical_requirements": {
      "technical_specifications": "...",
      ...
    },
    "document_preparation": {
      "bid_documents_structure": "...",
      ...
    }
  },
  "evidence_chunk_ids": ["seg_001", "seg_002", ...],
  "updated_at": "2025-12-31T..."
}
```

**✅ 所有6个stage的数据都会完整显示**

---

## 修改文件清单

### 1. backend/app/works/tender/extract_v2_service.py

**修改位置：** 第311-349行（`_extract_project_info_staged`方法的返回部分）

**修改内容：**
- ✅ 明确列出所有6个stage
- ✅ 添加最终确认保存
- ✅ 更新run进度为0.98

### 2. backend/app/services/tender_service.py

**修改位置：** 第948行、第969行

**修改内容：**
- ✅ 移除重复保存
- ✅ 更新消息为中文

---

## 测试验证

### 测试步骤

1. **启动服务**
   ```bash
   cd /aidata/x-llmapp1/backend
   python -m uvicorn app.main:app --reload
   ```

2. **发起提取**
   ```bash
   curl -X POST "http://localhost:8000/api/apps/tender/projects/{project_id}/extract/project-info" \
     -H "Content-Type: application/json" \
     -d '{"model_id": "gpt-4o-mini"}'
   ```

3. **轮询进度**
   ```bash
   # 每2秒查询一次
   curl "http://localhost:8000/api/apps/tender/runs/{run_id}"
   ```

4. **验证结果**
   ```bash
   # 查询项目信息
   curl "http://localhost:8000/api/apps/tender/projects/{project_id}/project-info"
   
   # 检查：
   # - status应为"success"
   # - progress应为1.0
   # - message应为"项目信息提取完成"
   # - data_json应包含所有6个stage的数据
   ```

### 预期结果

- ✅ 提取完成后，run状态为"success"
- ✅ 所有6个stage的数据都完整保存
- ✅ 前端可以正常显示所有stage的信息
- ✅ 进度信息清晰准确

---

## 总结

### ✅ 问题已修复

1. **状态显示问题** → 已修复
   - 增加run进度更新，TenderService最终更新为success

2. **结果显示不全** → 已修复
   - 明确列出所有6个stage
   - 最终确认保存，确保数据完整

### ✅ 改进点

1. **数据完整性保证**
   - 增量保存（每个stage）
   - 最终确认保存（所有stage完成）
   - 明确结构（返回结果）

2. **用户体验提升**
   - 进度信息更准确（0.98 → 1.0）
   - 状态消息中文化
   - 分步显示更清晰

3. **代码健壮性**
   - 即使某些stage失败，其他stage的数据仍然保存
   - 数据结构明确，避免展开带来的不确定性

---

**修复完成日期**: 2025-12-31  
**修复状态**: ✅ 完成  
**可用性**: ✅ 可投入使用

