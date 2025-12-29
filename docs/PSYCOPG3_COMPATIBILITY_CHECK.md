# PSycopg3 兼容性问题排查报告

## 问题背景
PSycopg3 使用 `dict_row` factory，`fetchone()` 返回的是 `DictRow` 对象（类似字典），不能直接用 tuple 方式解包。

## 常见错误模式

### ❌ 错误写法
```python
# Pattern 1: 直接tuple解包
current_content, current_version = cur.fetchone()
# 错误：DictRow 不能直接解包

# Pattern 2: 直接访问索引
value = row[0]
# 可能错误：DictRow 不支持数字索引
```

### ✅ 正确写法
```python
# Pattern 1: 转换为dict再访问
row = cur.fetchone()
row_dict = dict(row)
current_content = row_dict["content"]
current_version = row_dict["version"]

# Pattern 2: 直接访问键
row = cur.fetchone()
value = row["column_name"]

# Pattern 3: 获取第一个值（单列查询）
row = cur.fetchone()
value = list(row.values())[0] if row else default_value
```

## 已发现并修复的问题

### 1. ✅ prompts.py (Line 290)
**文件**: `backend/app/routers/prompts.py`

**错误代码**:
```python
current = cur.fetchone()
current_content, current_version = current  # ❌ tuple解包
```

**修复后**:
```python
current = cur.fetchone()
current_dict = dict(current)
current_content = current_dict["content"]
current_version = current_dict["version"]
```

**状态**: ✅ 已修复并重启

## 其他可疑代码（需要验证）

### 2. ⚠️ project_delete/cleaners.py (Line 199)
**文件**: `backend/app/services/project_delete/cleaners.py`

**代码**:
```python
samples = [list(row.values())[1] or list(row.values())[0][:12] for row in docs[:5]]
```

**风险**: 多次调用 `list(row.values())`，效率低且可能有问题

**建议优化**:
```python
samples = []
for row in docs[:5]:
    values = list(row.values())
    sample = values[1] if len(values) > 1 and values[1] else values[0][:12]
    samples.append(sample)
```

### 3. ⚠️ tender_snippets.py (Line 295)
**文件**: `backend/app/routers/tender_snippets.py`

**代码**:
```python
meta_json = json.loads(list(row.values())[0]) if list(row.values())[0] else {}
```

**风险**: 多次调用 `list(row.values())[0]`

**建议优化**:
```python
meta_value = list(row.values())[0] if row else None
meta_json = json.loads(meta_value) if meta_value else {}
```

## 正确使用的代码（无需修改）

### ✅ recording_service.py
```python
# Line 90: COUNT(*) 单列查询
total = list(cur.fetchone().values())[0]  # ✅ 正确

# Line 117, 159: 获取单列值
rec_dict["kb_name"] = list(kb_row.values())[0] if kb_row else None  # ✅ 正确
```

### ✅ kb_dao.py
```python
# Line 415: COUNT(*) 查询
return int(list(row.values())[0] if row else 0)  # ✅ 正确
```

### ✅ permission_service.py
```python
# Line 614: 布尔值查询
is_admin = list(row.values())[0] if row else False  # ✅ 正确
```

## 全局搜索结果

### fetchone() 使用统计
- **总计**: 70+ 处使用
- **已确认有问题**: 1 处（prompts.py Line 290）✅ 已修复
- **可能需要优化**: 2 处（cleaners.py, tender_snippets.py）
- **正确使用**: 67+ 处

## 检查清单

| 文件 | 行号 | 模式 | 状态 | 说明 |
|------|------|------|------|------|
| prompts.py | 290 | tuple解包 | ✅ 已修复 | 直接解包DictRow |
| cleaners.py | 199 | 多次values()调用 | ⚠️ 可优化 | 效率问题 |
| tender_snippets.py | 295 | 多次values()调用 | ⚠️ 可优化 | 效率问题 |
| recording_service.py | 90,117,159 | list(values())[0] | ✅ 正确 | 单列查询 |
| kb_dao.py | 415 | list(values())[0] | ✅ 正确 | COUNT查询 |
| permission_service.py | 614 | list(values())[0] | ✅ 正确 | 布尔查询 |

## 建议的最佳实践

### 1. 单列查询
```python
# COUNT(*), MAX(), MIN() 等聚合函数
cur.execute("SELECT COUNT(*) FROM table")
count = list(cur.fetchone().values())[0]
```

### 2. 多列查询
```python
# 已知列名
cur.execute("SELECT id, name FROM table WHERE ...")
row = cur.fetchone()
if row:
    row_dict = dict(row)
    id = row_dict["id"]
    name = row_dict["name"]
```

### 3. 动态列查询
```python
# 列名不固定
row = cur.fetchone()
if row:
    for key, value in dict(row).items():
        print(f"{key}: {value}")
```

### 4. 避免的写法
```python
# ❌ 不要直接解包
id, name = cur.fetchone()

# ❌ 不要数字索引
value = row[0]

# ❌ 不要多次调用values()
x = list(row.values())[0] or list(row.values())[1]  # 调用了2次！
```

## 测试建议

### 1. 单元测试
```python
def test_fetchone_dict_access():
    row = cur.fetchone()
    assert isinstance(row, dict) or hasattr(row, 'keys')
    assert 'column_name' in dict(row)
```

### 2. 集成测试
- 测试所有使用 `fetchone()` 的API端点
- 特别关注更新/创建操作
- 验证返回数据的完整性

### 3. 回归测试重点
- ✅ Prompt管理（保存/更新）
- ⚠️ 项目删除流程
- ⚠️ 目录节点应用范本
- ✅ 录音管理
- ✅ 权限检查

## 修复优先级

### P0 - 紧急（功能阻断）
- ✅ prompts.py Line 290 - **已修复**

### P1 - 高优先级（性能或潜在bug）
- ⚠️ cleaners.py Line 199 - 多次调用values()
- ⚠️ tender_snippets.py Line 295 - 多次调用values()

### P2 - 低优先级（代码优化）
- 添加类型注解
- 统一错误处理模式

## 监控建议

1. **日志监控**: 关注 `psycopg.errors.*` 相关错误
2. **性能监控**: 关注数据库查询响应时间
3. **错误追踪**: 设置 Sentry 或类似工具捕获运行时错误

## 总结

### 当前状态
- ✅ **核心问题已修复**: prompts.py 的tuple解包错误
- ✅ **大部分代码正确**: 67+处使用正确的访问模式
- ⚠️ **2处可优化**: 性能优化建议（非阻断性）

### 建议行动
1. ✅ 立即重启服务（已完成）
2. ⏳ 测试Prompt保存功能
3. 📝 记录此次问题到技术债务清单
4. 🔄 后续优化cleaners.py和tender_snippets.py

---

**检查人员**: AI Assistant (Claude Sonnet 4.5)  
**检查时间**: 2025-12-29  
**检查范围**: 全部backend Python代码  
**检查方法**: grep + 人工审查

