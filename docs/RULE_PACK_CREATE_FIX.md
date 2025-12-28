# 规则包创建失败修复

## 问题描述
用户报告：创建规则包失败

## 错误信息
```
ValueError: dictionary update sequence element #0 has length 36; 2 is required
```

错误发生在：
```
File "/app/app/services/custom_rule_service.py", line 331, in get_rule_pack
    return dict(row) if row else None
           ^^^^^^^^^
```

## 根本原因

### 问题分析
在使用 `psycopg3` 的 `tuple_row` 作为 row factory 时，查询结果返回的是元组（tuple），而不是字典。代码中尝试使用 `dict(row)` 直接转换元组为字典，但这种转换要求元组中的每个元素都是长度为2的序列（键值对），而实际上查询结果是单层元组，导致转换失败。

### 具体场景
- `list_rule_packs` 方法：使用 `SELECT rp.*, COUNT(r.id) as rule_count`
- `get_rule_pack` 方法：使用 `SELECT rp.*, COUNT(r.id) as rule_count`

这两个查询都使用了 `SELECT *` 和聚合函数，返回的是元组格式的数据，无法直接用 `dict(row)` 转换。

## 解决方案

### 修改方法
明确列出所有列名，并手动构建字典对象。

### 1. 修改 `list_rule_packs` 方法

**文件**: `backend/app/services/custom_rule_service.py`

**修改前**:
```python
sql = """
SELECT 
    rp.*,
    COUNT(r.id) as rule_count
FROM tender_rule_packs rp
LEFT JOIN tender_rules r ON r.rule_pack_id = rp.id
WHERE rp.pack_type = 'custom'
"""
# ...
sql += " GROUP BY rp.id ORDER BY rp.created_at DESC"
# ...
return [dict(row) for row in rows]
```

**修改后**:
```python
sql = """
SELECT 
    rp.id,
    rp.pack_name,
    rp.pack_type,
    rp.project_id,
    rp.priority,
    rp.is_active,
    rp.created_at,
    rp.updated_at,
    COUNT(r.id) as rule_count
FROM tender_rule_packs rp
LEFT JOIN tender_rules r ON r.rule_pack_id = rp.id
WHERE rp.pack_type = 'custom'
"""
# ...
sql += " GROUP BY rp.id, rp.pack_name, rp.pack_type, rp.project_id, rp.priority, rp.is_active, rp.created_at, rp.updated_at ORDER BY rp.created_at DESC"
# ...
return [
    {
        "id": row[0],
        "pack_name": row[1],
        "pack_type": row[2],
        "project_id": row[3],
        "priority": row[4],
        "is_active": row[5],
        "created_at": row[6],
        "updated_at": row[7],
        "rule_count": row[8],
    }
    for row in rows
]
```

### 2. 修改 `get_rule_pack` 方法

**文件**: `backend/app/services/custom_rule_service.py`

**修改前**:
```python
cur.execute(
    """
    SELECT 
        rp.*,
        COUNT(r.id) as rule_count
    FROM tender_rule_packs rp
    LEFT JOIN tender_rules r ON r.rule_pack_id = rp.id
    WHERE rp.id = %s
    GROUP BY rp.id
    """,
    (pack_id,),
)
row = cur.fetchone()

return dict(row) if row else None
```

**修改后**:
```python
cur.execute(
    """
    SELECT 
        rp.id,
        rp.pack_name,
        rp.pack_type,
        rp.project_id,
        rp.priority,
        rp.is_active,
        rp.created_at,
        rp.updated_at,
        COUNT(r.id) as rule_count
    FROM tender_rule_packs rp
    LEFT JOIN tender_rules r ON r.rule_pack_id = rp.id
    WHERE rp.id = %s
    GROUP BY rp.id, rp.pack_name, rp.pack_type, rp.project_id, rp.priority, rp.is_active, rp.created_at, rp.updated_at
    """,
    (pack_id,),
)
row = cur.fetchone()

if not row:
    return None

return {
    "id": row[0],
    "pack_name": row[1],
    "pack_type": row[2],
    "project_id": row[3],
    "priority": row[4],
    "is_active": row[5],
    "created_at": row[6],
    "updated_at": row[7],
    "rule_count": row[8],
}
```

## 关键变更

1. **明确列名**: 将 `SELECT rp.*` 改为明确列出所有需要的列
2. **GROUP BY子句**: 在使用聚合函数时，需要在 GROUP BY 中列出所有非聚合列
3. **手动构建字典**: 使用索引访问元组元素，手动构建字典对象
4. **空值处理**: 在 `get_rule_pack` 中明确处理空结果的情况

## 技术说明

### Psycopg3 Row Factory
- `tuple_row`: 返回元组，支持索引访问 `row[0]`，但不支持 `dict(row)` 转换
- `dict_row`: 返回字典，支持字典访问 `row['column']`，但不支持索引访问
- 由于项目中很多代码使用索引访问（如 `permission_service.py`），所以继续使用 `tuple_row`

### 最佳实践
对于使用 `tuple_row` 的查询：
1. 避免使用 `SELECT *`，明确列出所有列名
2. 使用索引访问构建字典：`{"key": row[0], ...}`
3. 在 GROUP BY 中列出所有非聚合列

## 部署说明
1. 修改后端代码
2. 重启后端服务: `docker restart localgpt-backend`
3. 测试规则包创建功能

## 验证步骤
1. 打开"自定义规则"页面
2. 点击"创建规则包"
3. 输入规则包名称和规则要求
4. 点击"开始生成"
5. 验证规则包创建成功且能正确显示

## 相关文件
- `backend/app/services/custom_rule_service.py`
- `backend/app/services/db/postgres.py`

## 相关问题
- 之前的修复: `PSYCOPG3_ROW_ACCESS_FIX.md` - 解决了 `KeyError: 0` 问题
- 本次修复: 解决了 `ValueError: dictionary update sequence element #0 has length 36` 问题
- 两者都是 `psycopg3` 行对象处理相关的问题

