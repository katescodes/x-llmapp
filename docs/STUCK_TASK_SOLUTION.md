# 卡死任务问题解决方案

## 📋 问题描述

**现象**：
- 后台任务已经停止运行（进程退出）
- 但数据库中任务状态仍然是 `running`
- 前端轮询一直显示"提取中..."、"生成中..."等状态
- 用户无法进行后续操作，被阻塞

**原因**：
1. **异常退出**：任务执行过程中遇到未捕获的异常
2. **容器重启**：Docker容器重启导致运行中的任务中断
3. **资源不足**：OOM（内存不足）导致进程被杀
4. **超时未处理**：长时间运行的任务没有超时机制

## ✅ 已实施的解决方案

### 1. 立即修复（已完成）

已清理当前卡死的任务：

```bash
# 发现并修复了 1 个卡死任务
任务ID: tr_37813ef6eab04f4194dd6731667ad279
类型: extract_risks (招标要求提取)
运行时长: 12.1 分钟
状态: 已更新为 failed
```

### 2. 自动监控机制（已部署）

#### 后台监控服务

新增了 `TaskMonitor` 服务，会自动：
- **定期检测**：每60秒检查一次数据库
- **识别卡死任务**：超过10分钟仍为 `running` 状态的任务
- **自动清理**：更新为 `failed` 状态，并标注原因

**代码位置**：
- 服务实现：`/backend/app/services/task_monitor.py`
- 启动配置：`/backend/app/main.py` (startup event)

#### 手动清理API

提供了手动触发清理的接口：

```bash
POST /api/apps/tender/admin/cleanup-stuck-runs?timeout_minutes=10
```

**响应示例**：
```json
{
  "fixed_count": 1,
  "stuck_runs": [
    {
      "id": "tr_xxx",
      "project_id": "tp_xxx",
      "kind": "extract_risks",
      "started_at": "2026-01-15 02:01:51",
      "running_minutes": 12.1
    }
  ],
  "message": "成功修复 1 个卡死任务"
}
```

### 3. 独立修复脚本

提供了命令行工具用于诊断和修复：

```bash
# 在Docker容器内运行
docker exec localgpt-backend python3 /app/scripts/fix_stuck_runs.py

# 参数说明
--timeout 10           # 超时阈值（分钟），默认10
--dry-run              # 仅检测，不实际修复
--auto-fix             # 自动修复所有卡死任务
```

**脚本位置**：`/scripts/fix_stuck_runs.py`

## 🔧 使用指南

### 场景1：前端显示"提取中"但后台无响应

**步骤**：

1. **确认任务确实卡死**：
```bash
# 检查数据库中running状态的任务
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
  SELECT id, kind, started_at, 
         EXTRACT(EPOCH FROM (NOW() - started_at)) / 60 as minutes
  FROM tender_runs 
  WHERE status = 'running'
  ORDER BY started_at DESC;
"
```

2. **手动清理**（3种方式任选一种）：

**方式A：使用API**（推荐）
```bash
curl -X POST "http://localhost:8000/api/apps/tender/admin/cleanup-stuck-runs?timeout_minutes=10"
```

**方式B：使用Python脚本**
```bash
docker exec localgpt-backend python3 -c "
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    host='postgres', dbname='localgpt', 
    user='localgpt', password='localgpt',
    row_factory=dict_row
)

with conn.cursor() as cur:
    # 查找并修复
    cur.execute('''
        UPDATE tender_runs
        SET status = 'failed',
            finished_at = NOW(),
            error = '任务超时未完成',
            message = '任务异常终止：超时未完成'
        WHERE status = 'running'
          AND started_at < NOW() - INTERVAL '10 minutes'
        RETURNING id, kind
    ''')
    
    fixed = cur.fetchall()
    conn.commit()
    print(f'修复了 {len(fixed)} 个任务')
    for r in fixed:
        print(f\"  - {r['id']} ({r['kind']})\")

conn.close()
"
```

**方式C：使用修复脚本**
```bash
docker exec localgpt-backend python3 /app/scripts/fix_stuck_runs.py --auto-fix
```

3. **刷新前端页面**，任务状态应该更新为失败，用户可以重新操作

### 场景2：定期维护

建议设置定时任务（如cron job）：

```bash
# 每小时清理一次卡死超过10分钟的任务
0 * * * * curl -X POST "http://localhost:8000/api/apps/tender/admin/cleanup-stuck-runs?timeout_minutes=10"
```

### 场景3：批量检查所有项目

```bash
# 查看所有项目的任务统计
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
  SELECT status, kind, COUNT(*) as count
  FROM tender_runs
  GROUP BY status, kind
  ORDER BY status, kind;
"
```

## 🔍 监控与告警

### 查看监控器运行状态

```bash
# 检查后端日志中监控器相关信息
docker logs localgpt-backend 2>&1 | grep "任务监控器"
```

**正常输出**：
```
✅ 任务监控器已启动（超时阈值：10分钟，检查间隔：60秒）
```

### 调整监控参数

编辑 `/backend/app/main.py` 中的启动配置：

```python
monitor = TaskMonitor(
    monitor_conn, 
    timeout_minutes=10,           # 超时阈值（分钟）
    check_interval_seconds=60     # 检查间隔（秒）
)
```

## 🚨 预防措施

### 1. 任务超时设置

确保长时间运行的任务有合理的超时限制：

```python
# 示例：在任务执行代码中添加超时
import asyncio

try:
    result = await asyncio.wait_for(
        long_running_task(), 
        timeout=600  # 10分钟
    )
except asyncio.TimeoutError:
    # 更新任务状态为failed
    dao.update_run(run_id, "failed", message="任务执行超时")
```

### 2. 异常处理

确保所有任务都有完善的异常处理：

```python
try:
    # 执行任务
    result = await extract_project_info(...)
    
    # 成功：更新状态
    dao.update_run(run_id, "success", ...)
    
except Exception as e:
    # 失败：更新状态
    logger.error(f"任务失败: {e}", exc_info=True)
    dao.update_run(run_id, "failed", message=str(e))
    raise
```

### 3. 资源监控

监控系统资源，防止OOM：

```bash
# 检查Docker容器内存使用
docker stats localgpt-backend --no-stream

# 检查后端日志中的OOM信息
docker logs localgpt-backend 2>&1 | grep -i "oom\|memory"
```

### 4. 前端超时提示

前端轮询时添加超时判断：

```typescript
const MAX_WAIT_TIME = 15 * 60 * 1000; // 15分钟

const check = async () => {
  const elapsed = Date.now() - startTime;
  
  if (elapsed > MAX_WAIT_TIME) {
    alert("任务执行时间过长，请刷新页面或联系管理员");
    stopPolling();
    return;
  }
  
  // 正常轮询逻辑
  const run = await api.get(`/api/apps/tender/runs/${runId}`);
  // ...
};
```

## 📊 数据库维护

### 定期清理旧任务记录

```sql
-- 清理超过30天的失败任务记录
DELETE FROM tender_runs 
WHERE status = 'failed' 
  AND started_at < NOW() - INTERVAL '30 days';

-- 清理超过90天的成功任务记录
DELETE FROM tender_runs 
WHERE status = 'success' 
  AND started_at < NOW() - INTERVAL '90 days';
```

## 🔗 相关文件

| 文件 | 说明 |
|------|------|
| `/backend/app/services/task_monitor.py` | 任务监控服务实现 |
| `/backend/app/main.py` | 应用启动配置（集成监控器） |
| `/backend/app/routers/tender.py` | 手动清理API端点 |
| `/scripts/fix_stuck_runs.py` | 独立修复脚本 |
| `/docs/STUCK_TASK_SOLUTION.md` | 本文档 |

## 📞 故障排查

### 问题：监控器未启动

**检查**：
```bash
docker logs localgpt-backend 2>&1 | grep -A 5 "任务监控器"
```

**可能原因**：
1. 数据库连接失败
2. 启动脚本有错误
3. Python依赖缺失

**解决**：
- 检查环境变量：`POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- 查看完整错误日志：`docker logs localgpt-backend --tail 100`

### 问题：清理后前端仍显示"提取中"

**原因**：前端缓存了旧状态

**解决**：
1. 刷新浏览器页面（F5或Ctrl+R）
2. 清除浏览器缓存
3. 检查前端轮询逻辑是否正确

### 问题：任务频繁卡死

**排查方向**：
1. **资源不足**：增加Docker容器内存限制
2. **LLM超时**：检查LLM服务响应时间
3. **数据库连接池**：检查连接池配置
4. **代码BUG**：检查任务执行日志，找出异常点

## 📝 更新日志

- **2026-01-15**：初始版本，包含自动监控和手动清理功能
- **已修复任务**：1个 (extract_risks, 12.1分钟)

---

**维护建议**：
1. 每周检查一次卡死任务统计
2. 每月分析任务失败原因，优化代码
3. 定期更新监控阈值（根据实际情况调整10分钟的默认值）





