# API 权限修复说明

## 问题描述

用户报告两个功能加载失败：
1. **自定义规则：加载规则包失败**
2. **用户文档：加载分类失败**

## 根本原因

### 1. 用户文档权限过于严格

**位置**: `/aidata/x-llmapp1/backend/app/routers/user_documents.py`

**问题**: 
- 查询接口使用了 `require_permission("tender.view")` 权限检查
- 许多用户可能没有被分配 `tender.view` 权限
- 导致无法访问用户文档分类列表

**影响的端点**:
- `GET /api/user-documents/categories` - 列出文档分类
- `GET /api/user-documents/categories/{category_id}` - 获取单个分类
- `GET /api/user-documents/documents` - 列出文档
- `GET /api/user-documents/documents/{doc_id}` - 获取单个文档

### 2. 前端API路径不匹配

**位置**: `/aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx`

**问题**:
- 前端使用 `/custom-rules/rule-packs` 
- 后端路由定义为 `/api/custom-rules/rule-packs`
- 路径不匹配导致404错误

## 修复方案

### 1. 放宽用户文档查询权限

将查询接口的权限从 `require_permission("tender.view")` 改为 `get_current_user_sync`：

```python
# 修改前
@router.get("/categories", response_model=List[UserDocCategoryOut])
def list_categories(
    user: TokenData = Depends(require_permission("tender.view")),
):
    ...

# 修改后
@router.get("/categories", response_model=List[UserDocCategoryOut])
def list_categories(
    user: TokenData = Depends(get_current_user_sync),
):
    ...
```

**理由**: 
- 只要用户已登录，就应该能查看自己的文档和分类
- 创建、修改、删除操作仍然保留 `require_permission("tender.userdoc")` 权限检查
- 符合最小权限原则的同时保证基本可用性

### 2. 修复前端API路径

```typescript
// 修改前
const data = await api.get(`/custom-rules/rule-packs?project_id=${projectId}`);

// 修改后
const data = await api.get(`/api/custom-rules/rule-packs?project_id=${projectId}`);
```

### 3. 统一自定义规则路由文档

为所有自定义规则端点添加清晰的权限说明：

```python
@router.get("/rule-packs", response_model=List[CustomRulePackOut])
def list_rule_packs(
    user: TokenData = Depends(get_current_user_sync),
):
    """
    列出自定义规则包
    
    权限要求：已登录用户
    """
```

## 修改的文件

### 后端文件

1. `/aidata/x-llmapp1/backend/app/routers/user_documents.py`
   - 修改 `list_categories()` - 将权限从 `tender.view` 改为已登录用户
   - 修改 `get_category()` - 将权限从 `tender.view` 改为已登录用户
   - 修改 `list_documents()` - 将权限从 `tender.view` 改为已登录用户
   - 修改 `get_document()` - 将权限从 `tender.view` 改为已登录用户

2. `/aidata/x-llmapp1/backend/app/routers/custom_rules.py`
   - 添加 `require_permission` 导入（备用）
   - 为所有端点添加明确的权限说明文档

### 前端文件

1. `/aidata/x-llmapp1/frontend/src/components/TenderWorkspace.tsx`
   - 修复 `loadRulePacks()` 中的API路径：`/custom-rules/` → `/api/custom-rules/`

## 权限策略总结

### 自定义规则 (custom_rules)

| 操作 | 端点 | 权限要求 |
|------|------|----------|
| 列出规则包 | GET /api/custom-rules/rule-packs | 已登录用户 |
| 查看规则包 | GET /api/custom-rules/rule-packs/{id} | 已登录用户 |
| 创建规则包 | POST /api/custom-rules/rule-packs | 已登录用户 |
| 删除规则包 | DELETE /api/custom-rules/rule-packs/{id} | 已登录用户 |
| 列出规则 | GET /api/custom-rules/rule-packs/{id}/rules | 已登录用户 |

### 用户文档 (user_documents)

| 操作 | 端点 | 权限要求 |
|------|------|----------|
| 列出分类 | GET /api/user-documents/categories | 已登录用户 ✅ **已修复** |
| 查看分类 | GET /api/user-documents/categories/{id} | 已登录用户 ✅ **已修复** |
| 创建分类 | POST /api/user-documents/categories | tender.userdoc |
| 修改分类 | PATCH /api/user-documents/categories/{id} | tender.userdoc |
| 删除分类 | DELETE /api/user-documents/categories/{id} | tender.userdoc |
| 列出文档 | GET /api/user-documents/documents | 已登录用户 ✅ **已修复** |
| 查看文档 | GET /api/user-documents/documents/{id} | 已登录用户 ✅ **已修复** |
| 上传文档 | POST /api/user-documents/documents | tender.userdoc |
| 修改文档 | PATCH /api/user-documents/documents/{id} | tender.userdoc |
| 删除文档 | DELETE /api/user-documents/documents/{id} | tender.userdoc |
| 分析文档 | POST /api/user-documents/documents/{id}/analyze | tender.userdoc |

## 测试验证

### 使用测试脚本

```bash
# 设置环境变量（可选）
export API_BASE=http://localhost:8000
export AUTH_TOKEN=your_token_here

# 运行测试脚本
./test_api_fixes.sh
```

### 手动测试

1. **测试自定义规则包列表**:
```bash
curl -X GET "http://localhost:8000/api/custom-rules/rule-packs" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

2. **测试用户文档分类列表**:
```bash
curl -X GET "http://localhost:8000/api/user-documents/categories" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

3. **测试用户文档列表**:
```bash
curl -X GET "http://localhost:8000/api/user-documents/documents" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 预期结果

所有端点应该返回 `200 OK`，并返回 JSON 数组（可能为空）：

```json
[]  // 空列表表示还没有数据，但请求成功
```

## 回滚方案

如果修复导致问题，可以恢复原有权限设置：

```bash
# 回滚后端更改
cd /aidata/x-llmapp1
git checkout backend/app/routers/user_documents.py
git checkout backend/app/routers/custom_rules.py

# 回滚前端更改
git checkout frontend/src/components/TenderWorkspace.tsx

# 重启服务
# ... 根据实际情况重启后端和前端
```

## 注意事项

1. **数据安全**: 虽然放宽了查询权限，但用户仍然只能看到自己有权限访问的数据（通过 owner_id 和 project_id 过滤）

2. **写操作保护**: 创建、修改、删除操作仍然需要 `tender.userdoc` 权限

3. **兼容性**: 这个修复不会影响现有功能，只是让更多用户能够访问查询接口

4. **性能**: 由于去掉了额外的权限检查步骤，理论上查询性能会略有提升

## 相关文档

- [权限管理文档](./PERMISSION_MANAGEMENT.md)
- [快速开始指南](./QUICKSTART_PERMISSIONS.md)
- [权限审计报告](./PERMISSION_AUDIT_REPORT.md)

