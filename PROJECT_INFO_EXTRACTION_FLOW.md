# 项目信息抽取完整流程

## 📋 流程图

```
前端请求
   ↓
[1] POST /api/apps/tender/projects/{project_id}/extract/project-info
   ├─ 创建 run 记录 (status=running, progress=0.01)
   ├─ 启动异步后台任务 job_async()
   └─ 立即返回 {run_id}
   
后台任务 job_async()
   ↓
[2] ExtractV2Service.extract_project_info_v2()
   ├─ Step 1: 检索招标文档上下文 (progress=0.05)
   ├─ Step 2: 初始化Checklist提取器
   ├─ Step 3: 执行6个stage
   │   ├─ 并行模式 (EXTRACT_PROJECT_INFO_PARALLEL=true)
   │   │   ├─ 所有6个stage同时执行
   │   │   ├─ 使用信号量控制并发 (max=6)
   │   │   ├─ 每个stage独立提取 (P0+P1)
   │   │   └─ progress=0.10 → 0.90
   │   │
   │   └─ 顺序模式 (EXTRACT_PROJECT_INFO_PARALLEL=false)
   │       ├─ Stage 1: 项目概览 (progress=0.05 → 0.20)
   │       ├─ Stage 2: 投标人资格 (progress=0.20 → 0.35)
   │       ├─ Stage 3: 评审与评分 (progress=0.35 → 0.50)
   │       ├─ Stage 4: 商务条款 (progress=0.50 → 0.65)
   │       ├─ Stage 5: 技术要求 (progress=0.65 → 0.80)
   │       ├─ Stage 6: 文件编制 (progress=0.80 → 0.95)
   │       └─ 每个stage完成后增量保存
   │
   ├─ Step 4: 最终保存（并行模式）
   ├─ Step 5: 验证提取结果
   ├─ Step 6: 构建最终结果
   ├─ Step 7: 最终确认保存
   ├─ Step 8: 更新run进度 (status=running, progress=0.98)
   └─ 返回结果
   
[3] 后台任务完成
   ├─ 更新 run 状态 (status=success, progress=1.0, message="项目信息提取完成")
   └─ 记录日志
```

## 🔄 详细步骤

### 1. 前端发起请求

```typescript
POST /api/apps/tender/projects/{project_id}/extract/project-info
Body: { model_id: "..." }
```

### 2. Router层 (async函数)

```python
# backend/app/routers/tender.py:354-420

@router.post("/projects/{project_id}/extract/project-info")
async def extract_project_info(...):
    # 1. 创建run记录
    run_id = dao.create_run(project_id, "extract_project_info")
    dao.update_run(run_id, "running", progress=0.01, message="初始化...")
    
    # 2. 定义异步后台任务
    async def job_async():
        try:
            # 调用ExtractV2Service
            result = await extract_v2.extract_project_info_v2(...)
            
            # 更新最终状态
            dao.update_run(run_id, "success", progress=1.0, message="项目信息提取完成")
        except Exception as e:
            dao.update_run(run_id, "failed", message=f"提取失败: {str(e)}")
    
    # 3. 启动后台任务
    asyncio.create_task(job_async())
    
    # 4. 立即返回
    return {"run_id": run_id}
```

### 3. ExtractV2Service层

```python
# backend/app/works/tender/extract_v2_service.py:131-473

async def extract_project_info_v2(...):
    # Step 1: 检索上下文 (progress=0.05)
    context_data = await context_retriever.retrieve_tender_context(...)
    
    # Step 2: 创建提取器
    extractor = ProjectInfoExtractor(llm=self.llm)
    
    # Step 3: 执行6个stage
    if parallel:  # 并行模式
        # 创建信号量限制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # 定义stage提取任务
        async def extract_stage_with_semaphore(stage_meta):
            async with semaphore:
                stage_result = await extractor.extract_stage(...)
                return stage_key, stage_result
        
        # 并行执行所有stage
        tasks = [extract_stage_with_semaphore(meta) for meta in stages_meta]
        results = await asyncio.gather(*tasks)
        
        # 收集结果
        for stage_key, stage_result in results:
            all_stage_results[stage_key] = stage_result["data"]
    
    else:  # 顺序模式
        for stage_meta in stages_meta:
            # 顺序执行每个stage
            stage_result = await extractor.extract_stage(...)
            all_stage_results[stage_key] = stage_result["data"]
            
            # 增量保存
            self.dao.upsert_project_info(project_id, ...)
            
            # 更新进度
            dao.update_run(run_id, "running", progress=0.05 + stage_num * 0.15)
    
    # Step 4-7: 验证、构建结果、最终保存
    self.dao.upsert_project_info(project_id, data_json=final_data, ...)
    
    # Step 8: 更新进度（接近完成）
    dao.update_run(run_id, "running", progress=0.98, message="项目信息提取完成，正在保存...")
    
    return final_result
```

### 4. ProjectInfoExtractor层

```python
# backend/app/works/tender/project_info_extractor.py

async def extract_stage(stage, context_text, ...):
    # P0阶段：基于checklist的结构化提取
    p0_output = await self._extract_p0(...)
    
    # P1阶段：补充扫描遗漏信息
    p1_output = await self._extract_p1(...)
    
    # 合并结果
    merged_data = self._merge_p0_p1(p0_output, p1_output)
    
    # 验证
    validation = self._validate_stage(merged_data)
    
    return {
        "data": merged_data,
        "evidence_segment_ids": evidence_ids,
        "p1_supplements_count": len(p1_output)
    }
```

## ⚙️ 环境配置

```yaml
# docker-compose.yml
- EXTRACT_PROJECT_INFO_PARALLEL=true  # 启用并行模式
- EXTRACT_MAX_CONCURRENT=6            # 最大并发数
```

## ✅ 关键点检查清单

1. ✅ Router函数必须是 `async def`
2. ✅ 使用 `asyncio.create_task()` 在当前事件循环中创建任务
3. ✅ 后台任务必须是 `async def`
4. ✅ 直接 `await` 异步方法，不使用 `asyncio.run()`
5. ✅ 异常必须被捕获并更新run状态
6. ✅ 最终状态必须更新为 `success` 或 `failed`
7. ✅ 并行模式使用 `asyncio.gather()` 和信号量
8. ✅ 顺序模式支持增量保存和context传递
9. ✅ 详细的日志输出便于调试
10. ✅ 前端立即返回，不阻塞

## 🐛 常见问题

### 问题1: 任务卡在"抽取中"
**原因**: 后台任务崩溃，未更新最终状态
**解决**: 确保所有异常被捕获并更新run状态为failed

### 问题2: 没有日志输出
**原因**: asyncio.run()在已有事件循环中失败
**解决**: Router改为async函数，使用asyncio.create_task()

### 问题3: 并行不生效
**原因**: 环境变量未设置或为false
**解决**: 确认 EXTRACT_PROJECT_INFO_PARALLEL=true

### 问题4: 进度不更新
**原因**: 并行模式下进度跳跃式更新（0.10→0.90）
**解决**: 这是正常的，6个stage同时执行无法显示每个stage的进度

## 📊 性能对比

| 模式 | 耗时 | 优点 | 缺点 |
|------|------|------|------|
| 顺序 | 6-12分钟 | 支持context传递，进度细粒度 | 慢 |
| 并行 | 1-2分钟 | 快6倍 | 进度粗粒度，不支持context传递 |

## 🔍 监控方式

### 查看当前运行的任务
```sql
SELECT id, project_id, status, progress, message, started_at
FROM tender_runs
WHERE status = 'running'
ORDER BY started_at DESC;
```

### 查看后端日志
```bash
docker logs localgpt-backend --tail 100 -f | grep -E "后台任务|ExtractV2|Stage"
```

### 查看提取结果
```sql
SELECT project_id, 
       jsonb_object_keys(data_json) as keys,
       array_length(evidence_chunk_ids, 1) as evidence_count
FROM tender_project_info
WHERE project_id = 'tp_xxx';
```

