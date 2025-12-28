# Psycopg3 统一使用 dict_row 重构报告

## 问题背景

项目从 psycopg2 迁移到 psycopg3 后，代码中存在两种不同的行访问模式：

1. **索引访问**：`row[0]`, `row[1]` - 需要配置 `tuple_row`
2. **字典访问**：`row['column_name']` - 需要配置 `dict_row`

由于代码混用了这两种模式，导致：
- 使用 `tuple_row` 时，`dict(row)` 转换失败
- 使用 `dict_row` 时，`row[0]` 索引访问失败

## 重构目标

**统一使用 `dict_row` + 字典访问模式**，因为：
- ✅ 更语义化、可读性更好
- ✅ 符合 Psycopg3 的最佳实践
- ✅ 支持 `dict(row)` 直接转换
- ✅ 避免索引错位问题

## 修改文件清单

### 1. 核心数据库配置

**文件**: `backend/app/services/db/postgres.py`

```python
from psycopg.rows import dict_row  # 改用 dict_row

def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_build_conninfo(),
            min_size=settings.POSTGRES_POOL_MIN,
            max_size=settings.POSTGRES_POOL_MAX,
            kwargs={"row_factory": dict_row},  # ✅ 使用 dict_row
        )
        _pool.wait()
    return _pool
```

### 2. 权限服务 (706行)

**文件**: `backend/app/services/permission_service.py`

**修改内容**：
- 所有 `PermissionResponse` 构造：`row[0]` → `row['id']`
- 所有 `RoleResponse` 构造：`row[0]` → `row['id']`
- 所有 `UserRoleResponse` 构造：`row[0]` → `row['id']`
- 所有 `DataPermissionResponse` 构造：`row[0]` → `row['id']`
- 集合推导式：`{row[0] for row in ...}` → `{row['id'] for row in ...}`
- 条件判断：`if row[0]:` → `if row['is_system']:`

**示例**：
```python
# 修改前
PermissionResponse(
    id=row[0], code=row[1], name=row[2], description=row[3],
    module=row[4], parent_code=row[5], resource_type=row[6],
    display_order=row[7], is_active=row[8], created_at=row[9], updated_at=row[10]
)

# 修改后
PermissionResponse(
    id=row['id'], code=row['code'], name=row['name'], description=row['description'],
    module=row['module'], parent_code=row['parent_code'], resource_type=row['resource_type'],
    display_order=row['display_order'], is_active=row['is_active'], 
    created_at=row['created_at'], updated_at=row['updated_at']
)
```

### 3. 用户文档服务 (562行)

**文件**: `backend/app/services/user_document_service.py`

**修改内容**：
- `_row_to_category` 方法：所有 `row[0-7]` → `row['column_name']`
- `_row_to_document` 方法：所有 `row[0-18]` → `row['column_name']`
- 使用 `row.get()` 处理可选字段

**示例**：
```python
# 修改前
return {
    "id": row[0],
    "project_id": row[1],
    "category_name": row[2],
    "doc_count": row[7] if len(row) > 7 else 0,
}

# 修改后
return {
    "id": row['id'],
    "project_id": row['project_id'],
    "category_name": row['category_name'],
    "doc_count": row.get('doc_count', 0),
}
```

### 4. 自定义规则服务 (456行)

**文件**: `backend/app/services/custom_rule_service.py`

**修改内容**：
- `list_rule_packs`: 改回使用 `[dict(row) for row in rows]`
- `get_rule_pack`: 改回使用 `dict(row) if row else None`

**示例**：
```python
# 修改前（手动构建字典）
return [
    {
        "id": row[0],
        "pack_name": row[1],
        "pack_type": row[2],
        # ... 8个字段
    }
    for row in rows
]

# 修改后（直接转换）
return [dict(row) for row in rows]
```

### 5. 其他服务文件

批量修改了以下文件：

1. **`app/utils/permission.py`**
   - `row[0]` → `row.get('data_scope')`
   - `dp_row[0]` → `dp_row['data_scope']`
   - `dp_row[1]` → `dp_row['custom_scope_json']`

2. **`app/routers/chat.py`**
   - `[row[0] for row in rows]` → `[list(row.values())[0] for row in rows]`

3. **`app/services/kb_service.py`**
   - 字典构造：`row[0-5]` → `row['id'], row['name'], ...`

4. **`app/platform/retrieval/new_retriever.py`**
   - 列表推导式中的索引访问 → 字典访问

5. **`app/services/asr_service.py`**
   - 字典构造：`row[0-4]` → `row['id'], row['name'], ...`

6. **`app/services/asr_config_service.py`**
   - 字典构造：`row[0-7]` → `row['id'], row['name'], ...`

7. **`app/routers/tender.py`**
   - 字典构造：`row[0-4]` → `row['id'], row['requirement_id'], ...`

## 修改统计

| 类别 | 文件数 | 修改行数（估计） |
|------|--------|------------------|
| 核心配置 | 1 | 3 |
| 权限服务 | 1 | ~200 |
| 文档服务 | 1 | ~40 |
| 规则服务 | 1 | ~60 |
| 其他服务 | 7 | ~80 |
| **总计** | **11** | **~383** |

## 测试验证

### 1. 后端启动测试
```bash
docker restart localgpt-backend
docker logs --tail 20 localgpt-backend
```

**结果**：✅ 启动成功，无报错

### 2. 功能测试

需要测试以下关键功能：

#### A. 权限系统
- [ ] 获取权限列表：`GET /api/permissions`
- [ ] 获取角色列表：`GET /api/permissions/roles`
- [ ] 获取用户权限：`GET /api/permissions/me/permissions`

#### B. 自定义规则
- [ ] 创建规则包：`POST /api/custom-rules/rule-packs`
- [ ] 获取规则包列表：`GET /api/custom-rules/rule-packs`
- [ ] 获取规则详情：`GET /api/custom-rules/rule-packs/{pack_id}`

#### C. 用户文档
- [ ] 创建分类：`POST /api/user-documents/categories`
- [ ] 获取分类列表：`GET /api/user-documents/categories`
- [ ] 上传文档：`POST /api/user-documents/upload`

#### D. 知识库
- [ ] 获取知识库列表：`GET /api/kb/list`
- [ ] 查询知识库：`POST /api/kb/query`

### 3. 性能测试

dict_row vs tuple_row 性能对比：
- **tuple_row**：内存占用更小，访问稍快（纳秒级差异）
- **dict_row**：内存占用略大，但可读性和维护性更好

对于业务应用来说，**可读性 > 微小性能差异**

## 优势总结

### 1. 代码可读性提升
```python
# 修改前 - 需要记住每列的位置
id = row[0]
name = row[1]
created_at = row[9]

# 修改后 - 语义清晰
id = row['id']
name = row['name']
created_at = row['created_at']
```

### 2. 减少错误风险
- ❌ 索引访问：修改 SQL 列顺序容易导致错误
- ✅ 字典访问：列顺序变化不影响代码

### 3. 简化字典转换
```python
# 修改前 - 需要手动映射
return {
    "id": row[0],
    "name": row[1],
    # ... 10+ 行
}

# 修改后 - 一行搞定
return dict(row)
```

### 4. 支持动态查询
```python
# dict_row 支持 .get() 方法
doc_count = row.get('doc_count', 0)

# 支持 .keys() 和 .values()
columns = list(row.keys())
```

## 注意事项

### 1. NULL 值处理
```python
# 使用 .get() 提供默认值
value = row.get('optional_field', default_value)

# 或使用短路运算
value = row.get('optional_field') or default_value
```

### 2. 日期格式化
```python
# 检查字段存在且不为 None
created_at = row['created_at'].isoformat() if row.get('created_at') else None
```

### 3. JSON 字段
```python
# JSON 字段可能为 None
meta = row.get('meta_json') or {}
tags = row.get('tags') or []
```

## 相关文档

- `PSYCOPG3_ROW_ACCESS_FIX.md` - 之前使用 tuple_row 的修复
- `RULE_PACK_CREATE_FIX.md` - tuple_row 导致的 dict() 转换问题
- Psycopg3 官方文档：https://www.psycopg.org/psycopg3/docs/

## 部署说明

1. ✅ 修改所有服务文件
2. ✅ 重启后端服务
3. ⏳ 全面功能测试（需要用户测试）
4. ⏳ 监控日志，确认无报错

## 总结

通过这次重构：
- 统一了代码风格，使用 `dict_row` + 字典访问
- 提升了代码可读性和维护性
- 减少了因索引错位导致的 bug 风险
- 符合 Psycopg3 的现代化最佳实践

**建议**：所有新代码都应该使用字典访问模式，避免使用数字索引。

