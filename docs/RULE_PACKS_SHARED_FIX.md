# 规则包共享模式修复

## 问题描述
用户报告：创建规则包需要先选择项目，且规则包无法在不同项目间共享。

需求：
1. 创建规则包不需要先选择项目
2. 规则包对所有招投标项目共享
3. 在每个审核界面都可以看到并选择自定义规则

## 问题分析

### 1. 前端限制
- `CustomRulesPage.tsx`: 加载规则包时传递了`project_id`参数
- `TenderWorkspace.tsx`: 加载规则包时强制要求`projectId`，并按项目过滤

### 2. 后端逻辑
- `custom_rule_service.py`: `list_rule_packs`方法支持按`project_id`过滤，但没有明确处理共享规则包的逻辑

### 3. 数据库结构
- `tender_rule_packs`表的`project_id`字段已支持NULL（在028迁移中定义）
- 缺少针对共享规则包（project_id IS NULL）的索引优化

## 解决方案

### 1. 数据库迁移
**文件**: `backend/migrations/033_make_rule_packs_shared.sql`

```sql
-- 删除外键约束（如果存在）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'tender_rule_packs_project_id_fkey') THEN
        ALTER TABLE tender_rule_packs DROP CONSTRAINT tender_rule_packs_project_id_fkey;
    END IF;
END
$$;

-- 为共享规则包添加索引
CREATE INDEX IF NOT EXISTS idx_rule_packs_null_project
  ON tender_rule_packs(id) WHERE project_id IS NULL;

-- 添加注释
COMMENT ON COLUMN tender_rule_packs.project_id IS '所属项目ID（可选，NULL表示全局共享规则包）';
```

### 2. 后端修改
**文件**: `backend/app/services/custom_rule_service.py`

**修改点**: `list_rule_packs`方法

```python
def list_rule_packs(
    self,
    project_id: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    列出自定义规则包
    
    Args:
        project_id: 项目ID（可选，不传则返回所有共享规则包）
        owner_id: 所有者ID（可选）
        
    Returns:
        规则包列表
    """
    with self.pool.connection() as conn:
        with conn.cursor() as cur:
            sql = """
            SELECT 
                rp.*,
                COUNT(r.id) as rule_count
            FROM tender_rule_packs rp
            LEFT JOIN tender_rules r ON r.rule_pack_id = rp.id
            WHERE rp.pack_type = 'custom'
            """
            params = []
            
            if project_id:
                sql += " AND rp.project_id = %s"
                params.append(project_id)
            else:
                # 不传project_id时，只返回共享规则包（project_id IS NULL）
                sql += " AND rp.project_id IS NULL"
            
            sql += " GROUP BY rp.id ORDER BY rp.created_at DESC"
            
            cur.execute(sql, params)
            rows = cur.fetchall()
    
    return [dict(row) for row in rows]
```

**关键变更**:
- 当不传`project_id`参数时，添加`AND rp.project_id IS NULL`条件
- 只返回共享规则包（project_id为NULL的记录）

### 3. 前端修改

#### 3.1 TenderWorkspace.tsx

**修改点1**: 规则包状态定义
```typescript
// 自定义规则包列表（全局共享，所有项目都能看到）
const [rulePacks, setRulePacks] = useState<any[]>([]);
```

**修改点2**: `loadRulePacks`方法
```typescript
// 加载自定义规则包列表（全局共享，不限制项目）
const loadRulePacks = useCallback(async () => {
  try {
    // 不传project_id，加载所有共享规则包
    const data = await api.get(`/api/custom-rules/rule-packs`);
    setRulePacks(data || []);
  } catch (err) {
    console.error('Failed to load rule packs:', err);
    setRulePacks([]);
  }
}, []); // 不依赖currentProject
```

**修改点3**: 切换到审核Tab时加载规则包
```typescript
onClick={() => {
  setActiveTab(tab.id);
  // 切换到审核Tab时加载规则包列表（全局共享）
  if (tab.id === 5) {
    loadRulePacks();
  }
}}
```

#### 3.2 CustomRulesPage.tsx

**修改点1**: `loadRulePacks`方法
```typescript
// 加载规则包列表（加载所有共享规则包，不限制项目）
const loadRulePacks = async () => {
  setLoading(true);
  try {
    // 不传project_id，加载所有共享规则包
    const res = await axios.get(`${API_BASE}/api/custom-rules/rule-packs`, {
      headers: getAuthHeaders(),
    });
    setRulePacks(res.data || []);
  } catch (err: any) {
    console.error('加载规则包失败:', err);
    alert(err.response?.data?.detail || '加载规则包失败');
  } finally {
    setLoading(false);
  }
};
```

**修改点2**: 移除项目提示
移除了"当前未选择项目，显示所有规则包。创建规则包需要先选择项目。"的提示信息。

## 验证步骤

1. **创建共享规则包**
   - 打开"自定义规则"页面
   - 点击"创建规则包"
   - 输入规则包名称和规则要求
   - 点击"开始生成"
   - 验证规则包创建成功

2. **查看共享规则包**
   - 在不同项目的审核界面查看规则包列表
   - 验证所有项目都能看到同样的规则包列表

3. **使用共享规则包**
   - 在任意项目的审核界面
   - 勾选自定义规则包
   - 点击"开始审核"
   - 验证审核功能正常工作

## 技术细节

### 数据库层
- `project_id IS NULL`: 表示共享规则包
- 添加了部分索引 `WHERE project_id IS NULL` 以优化查询性能

### API层
- GET `/api/custom-rules/rule-packs`: 不传`project_id`参数时返回所有共享规则包
- POST `/api/custom-rules/rule-packs`: `project_id`字段为`null`时创建共享规则包

### 前端层
- 移除了项目依赖，规则包列表不再按项目隔离
- 所有项目共享同一份规则包列表

## 影响范围
- ✅ 自定义规则管理页面
- ✅ 招投标项目审核功能
- ✅ 规则包选择界面

## 部署说明
1. 执行数据库迁移: `033_make_rule_packs_shared.sql`
2. 重新构建前端: `npm run build`
3. 重启后端服务: `docker restart localgpt-backend`

## 相关文件
- `backend/migrations/033_make_rule_packs_shared.sql`
- `backend/app/services/custom_rule_service.py`
- `frontend/src/components/TenderWorkspace.tsx`
- `frontend/src/components/CustomRulesPage.tsx`

