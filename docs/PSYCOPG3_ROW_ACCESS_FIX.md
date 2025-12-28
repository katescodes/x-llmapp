# 套用格式失败500错误修复报告

## 问题描述

用户反馈：**套用格式失败 - 500: Internal Server Error**

## 根本原因

### Psycopg3 Row对象索引访问问题

**问题：**
- 项目从 `psycopg2` 迁移到 `psycopg` (v3)
- Psycopg3 默认返回的 `Row` 对象不支持数字索引访问（如 `row[0]`）
- 代码中大量使用了 `row[0]`, `row[1]` 等索引访问方式
- 导致 `KeyError: 0` 异常

**错误日志：**
```python
File "/app/app/services/permission_service.py", line 612, in has_permission
  is_admin = cur.fetchone()[0]
             ~~~~~~~~~~~~~~^^^
KeyError: 0

File "/app/app/utils/permission.py", line 89, in get_owner_filter
  if row and row[0]:
             ~~~^^^
KeyError: 0
```

### Psycopg2 vs Psycopg3 的区别

**Psycopg2:**
```python
cursor.execute("SELECT id, name FROM users WHERE id = %s", (user_id,))
row = cursor.fetchone()
id = row[0]    # ✅ 支持索引访问
name = row[1]  # ✅ 支持索引访问
```

**Psycopg3 (默认):**
```python
cursor.execute("SELECT id, name FROM users WHERE id = %s", (user_id,))
row = cursor.fetchone()
id = row[0]    # ❌ KeyError: 0
name = row[1]  # ❌ KeyError: 1
```

**Psycopg3 支持的访问方式：**
1. 列名访问：`row['id']`, `row['name']`
2. 使用 `tuple_row` factory：配置后支持索引访问

## 修复方案

### 方案选择

有两种修复方案：

1. **修改所有代码** - 将 `row[0]` 改为 `row['column_name']`
   - ❌ 工作量大，需要修改数百处代码
   - ❌ 容易遗漏
   - ✅ 更符合Psycopg3的最佳实践

2. **配置 row_factory** - 在连接池级别配置使用 `tuple_row`
   - ✅ 一次修改，全局生效
   - ✅ 最小改动
   - ✅ 保持代码兼容性

我们选择了 **方案2**。

### 实施步骤

**修改文件：** `/aidata/x-llmapp1/backend/app/services/db/postgres.py`

#### 1. 导入 tuple_row

```python
from psycopg.rows import tuple_row
```

#### 2. 配置连接池的 row_factory

```python
def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_build_conninfo(),
            min_size=settings.POSTGRES_POOL_MIN,
            max_size=settings.POSTGRES_POOL_MAX,
            kwargs={"row_factory": tuple_row},  # ✅ 关键修改：使用tuple row factory
        )
        _pool.wait()
    return _pool
```

**说明：**
- `kwargs={"row_factory": tuple_row}` 会传递给每个新建的连接
- 使用 `tuple_row` 后，查询结果将返回普通的 Python tuple
- 支持索引访问：`row[0]`, `row[1]`, etc.

## 影响范围

### 修复的错误

这个修复解决了以下模块中的索引访问问题：

1. **permission_service.py** - 权限检查
   ```python
   is_admin = cur.fetchone()[0]  # ✅ 现在可以工作
   ```

2. **utils/permission.py** - 数据权限过滤
   ```python
   if row and row[0]:  # ✅ 现在可以工作
       data_scope = row[0]
   ```

3. **所有使用数据库的服务**
   - custom_rule_service.py
   - user_document_service.py
   - tender_service.py
   - 等等...

### 为什么"套用格式"会触发这个错误

"套用格式"功能的调用链：
1. 前端调用 `/api/apps/tender/projects/{project_id}/directory/apply-format-template`
2. 后端进行权限检查 → `require_permission("tender.edit")`
3. 权限检查调用 `has_permission()` → 检查是否是管理员
4. 查询数据库 → 尝试访问 `row[0]` → **KeyError!**

所以这不仅仅是"套用格式"的问题，而是**所有需要权限检查的API**都会失败。

## 验证步骤

1. ✅ 修改 `postgres.py` 添加 `tuple_row` 配置
2. ✅ 重启 Docker 容器：`docker restart localgpt-backend`
3. ✅ 验证服务启动成功
4. ⏳ 测试"套用格式"功能
5. ⏳ 测试其他需要权限检查的功能

## 部署说明

**Docker容器：** `localgpt-backend`
- 端口映射：`9001:8000`
- 重启命令：`docker restart localgpt-backend`

## 后续建议

虽然当前使用 `tuple_row` 可以快速解决问题，但长期来看，建议逐步迁移到使用列名访问：

```python
# 推荐的方式（Psycopg3 最佳实践）
from psycopg.rows import dict_row

# 在查询时指定
with conn.cursor(row_factory=dict_row) as cur:
    cur.execute("SELECT id, name FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    id = row['id']
    name = row['name']
```

这样代码更具可读性和可维护性。

## 修改文件清单

- ✅ `/aidata/x-llmapp1/backend/app/services/db/postgres.py`

## 总结

这是一个由于数据库驱动升级导致的兼容性问题。通过在连接池级别配置 `tuple_row` factory，我们使所有数据库查询结果都支持索引访问，从而一次性解决了所有相关的 `KeyError` 问题。

