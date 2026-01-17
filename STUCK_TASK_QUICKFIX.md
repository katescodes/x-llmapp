# 🔧 卡死任务快速修复指南

## 问题：前端一直显示"提取中"，但后台已停止

### 快速修复（3选1）

#### 方法1：使用API（最简单）
```bash
curl -X POST "http://localhost:8000/api/apps/tender/admin/cleanup-stuck-runs"
```

#### 方法2：Docker内执行Python
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
    cur.execute('''
        UPDATE tender_runs
        SET status = 'failed',
            finished_at = NOW(),
            error = '任务超时未完成',
            message = '任务异常终止'
        WHERE status = 'running'
          AND started_at < NOW() - INTERVAL '10 minutes'
        RETURNING id
    ''')
    
    fixed = cur.fetchall()
    conn.commit()
    print(f'✅ 修复了 {len(fixed)} 个卡死任务')

conn.close()
"
```

#### 方法3：使用修复脚本
```bash
docker exec localgpt-backend python3 /app/scripts/fix_stuck_runs.py --auto-fix
```

### 修复后

1. **刷新浏览器页面**（F5）
2. 任务状态应显示为"失败"
3. 可以重新发起操作

## 预防措施

### 已自动启用（无需手动操作）

✅ **后台监控器**：每60秒自动检查并清理卡死任务（超过10分钟）

### 建议配置

设置定时任务，每小时清理一次：

```bash
# 添加到crontab
0 * * * * curl -X POST "http://localhost:8000/api/apps/tender/admin/cleanup-stuck-runs"
```

## 检查任务状态

```bash
# 查看当前running的任务
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
  SELECT id, kind, 
         EXTRACT(EPOCH FROM (NOW() - started_at)) / 60 as minutes
  FROM tender_runs 
  WHERE status = 'running'
  ORDER BY started_at DESC;
"
```

## 详细文档

查看完整解决方案：`/docs/STUCK_TASK_SOLUTION.md`

---
**最后更新**：2026-01-15





