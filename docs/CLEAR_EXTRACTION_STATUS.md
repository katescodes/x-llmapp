# 清除项目抽取状态脚本

## 问题
某些项目显示"已抽取"状态，但实际数据不正确，需要重新抽取。

## 解决方案
删除项目的 `tender_runs` 和 `tender_project_info` 记录，让前端显示"未抽取"状态。

## 使用方法

### 1. 查看所有项目
```bash
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "SELECT id, name FROM tender_projects ORDER BY created_at DESC LIMIT 10;"
```

### 2. 查看项目的抽取状态
```bash
PROJECT_ID="tp_xxxx"  # 替换为实际项目ID
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT 
    'tender_runs' as table_name,
    tr.id,
    tr.kind,
    tr.status,
    tr.finished_at
FROM tender_runs tr
WHERE tr.project_id = '$PROJECT_ID' AND tr.kind = 'extract_project_info'
UNION ALL
SELECT 
    'tender_project_info' as table_name,
    tpi.project_id as id,
    'N/A' as kind,
    'N/A' as status,
    tpi.updated_at as finished_at
FROM tender_project_info tpi
WHERE tpi.project_id = '$PROJECT_ID';
"
```

### 3. 清除项目的抽取状态（项目2和项目4）

**注意：请先确认项目ID！**

根据查询结果，假设：
- 项目2的ID是 `tp_259c05d1979e402db656a58a930467e2`
- 项目4的ID需要用户确认

```bash
# 清除项目2的抽取记录
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
BEGIN;
DELETE FROM tender_runs WHERE project_id = 'tp_259c05d1979e402db656a58a930467e2' AND kind = 'extract_project_info';
DELETE FROM tender_project_info WHERE project_id = 'tp_259c05d1979e402db656a58a930467e2';
COMMIT;
SELECT '✅ 已清除项目2的抽取状态' as result;
"

# 清除项目4的抽取记录（替换为实际ID）
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
BEGIN;
DELETE FROM tender_runs WHERE project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9' AND kind = 'extract_project_info';
DELETE FROM tender_project_info WHERE project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9';
COMMIT;
SELECT '✅ 已清除项目4的抽取状态' as result;
"
```

### 4. 验证结果
清除后，刷新前端页面，项目应该显示"未抽取"状态，可以重新点击"开始抽取"按钮。

## 一键清除脚本（清除项目2和4）
```bash
docker exec localgpt-postgres psql -U localgpt -d localgpt <<'EOF'
BEGIN;

-- 清除项目2
DELETE FROM tender_runs 
WHERE project_id = 'tp_259c05d1979e402db656a58a930467e2' 
  AND kind = 'extract_project_info';

DELETE FROM tender_project_info 
WHERE project_id = 'tp_259c05d1979e402db656a58a930467e2';

-- 清除项目4
DELETE FROM tender_runs 
WHERE project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9' 
  AND kind = 'extract_project_info';

DELETE FROM tender_project_info 
WHERE project_id = 'tp_3f49f66ead6d46e1bac3f0bd16a3efe9';

COMMIT;

SELECT '✅ 已清除项目2和项目4的抽取状态' as result;
EOF
```

## 注意事项
1. 此操作会删除项目的抽取记录和数据，不可恢复
2. 如果项目已有正确的数据，请勿执行
3. 清除后需要重新执行抽取操作

