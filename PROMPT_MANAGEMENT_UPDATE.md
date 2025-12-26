# Prompt 管理系统更新说明

## 概述

本次更新为招投标系统 V3 重构新增了三个 prompt 模板的管理功能。

## 新增的 Prompt 模块

### 1. `project_info_v3` - 招标信息提取 V3
- **文件**: `backend/app/works/tender/prompts/project_info_v3.md`
- **描述**: 从招标文件中提取九大类结构化信息
- **九大类**:
  1. 项目概况 (project_overview)
  2. 范围与标段 (scope_and_lots)
  3. 进度与提交 (schedule_and_submission)
  4. 投标人资格 (bidder_qualification)
  5. 评审与评分 (evaluation_and_scoring)
  6. 商务条款 (business_terms)
  7. 技术要求 (technical_requirements)
  8. 文件编制 (document_preparation)
  9. 投标保证金 (bid_security)

### 2. `requirements_v1` - 招标要求抽取 V1
- **文件**: `backend/app/works/tender/prompts/requirements_v1.md`
- **描述**: 从招标文件中抽取结构化的招标要求（基准条款库）
- **7个维度**:
  1. qualification - 资格要求
  2. technical - 技术要求
  3. business - 商务要求
  4. price - 价格要求
  5. doc_structure - 文档结构
  6. schedule_quality - 进度质量
  7. other - 其他要求

### 3. `bid_response_v1` - 投标响应要素抽取 V1
- **文件**: `backend/app/works/tender/prompts/bid_response_v1.md`
- **描述**: 从投标文件中抽取结构化的响应要素
- **7个维度**:
  1. qualification - 资格响应
  2. technical - 技术响应
  3. business - 商务响应
  4. price - 价格响应
  5. doc_structure - 文档结构响应
  6. schedule_quality - 进度质量响应
  7. other - 其他响应

## API 更新

### 获取模块列表
```http
GET /api/apps/tender/prompts/modules
```

**响应示例**:
```json
{
  "ok": true,
  "modules": [
    {
      "id": "project_info_v3",
      "name": "招标信息提取 (V3)",
      "description": "提取招标文件的九大类信息...",
      "icon": "📋",
      "version": "v3",
      "category": "extraction"
    },
    {
      "id": "requirements_v1",
      "name": "招标要求抽取",
      "description": "从招标文件中抽取结构化的招标要求...",
      "icon": "📝",
      "version": "v1",
      "category": "extraction"
    },
    {
      "id": "bid_response_v1",
      "name": "投标响应要素抽取",
      "description": "从投标文件中抽取结构化的响应要素...",
      "icon": "📄",
      "version": "v1",
      "category": "extraction"
    },
    // ... 其他模块
  ]
}
```

### 新增字段说明
- `version`: 版本标识 (v1, v3)
- `category`: 分类 (extraction, analysis, generation, review)
- `deprecated`: 是否已弃用 (true/false)

## 初始化步骤

### 方法 1: 使用 Python 脚本（推荐）

```bash
cd /aidata/x-llmapp1
python scripts/init_v3_prompts.py
```

**输出示例**:
```
✓ 成功插入模块 'project_info_v3' (长度: 15234 字符)
✓ 成功插入模块 'requirements_v1' (长度: 8756 字符)
✓ 成功插入模块 'bid_response_v1' (长度: 4189 字符)
✓ 已标记 2 个旧版 prompt 为 deprecated

验证结果：
--------------------------------------------------------------------------------
模块: project_info_v3            | 名称: 招标信息提取 V3        | 版本: 1 | 激活: True | 内容长度: 15234 | 创建时间: 2025-12-26...
模块: requirements_v1            | 名称: 招标要求抽取 V1        | 版本: 1 | 激活: True | 内容长度:  8756 | 创建时间: 2025-12-26...
模块: bid_response_v1            | 名称: 投标响应要素抽取 V1    | 版本: 1 | 激活: True | 内容长度:  4189 | 创建时间: 2025-12-26...
--------------------------------------------------------------------------------

✅ V3 Prompt 模板初始化完成！
```

### 方法 2: 使用 SQL 脚本

```bash
# 需要先手动编辑 SQL 文件中的文件路径
psql -U your_user -d your_database -f backend/migrations/029_init_v3_prompt_templates.sql
```

## 前端集成

### 获取模块列表
```typescript
import axios from 'axios';

const response = await axios.get('/api/apps/tender/prompts/modules');
const modules = response.data.modules;

// 按分类分组
const modulesByCategory = modules.reduce((acc, module) => {
  const category = module.category || 'other';
  if (!acc[category]) acc[category] = [];
  acc[category].push(module);
  return acc;
}, {});
```

### 显示模块（带版本和状态标识）
```tsx
<div>
  {modules.map(module => (
    <div key={module.id}>
      <span>{module.icon} {module.name}</span>
      {module.version && <span className="badge">{module.version}</span>}
      {module.deprecated && <span className="badge-warning">已弃用</span>}
      <p>{module.description}</p>
    </div>
  ))}
</div>
```

## 在线编辑

管理员可以通过 API 在线编辑 prompt 内容：

### 获取 Prompt 内容
```http
GET /api/apps/tender/prompts?module=project_info_v3
```

### 更新 Prompt 内容
```http
PUT /api/apps/tender/prompts/{prompt_id}
Content-Type: application/json

{
  "name": "招标信息提取 V3 (更新)",
  "content": "更新后的 prompt 内容..."
}
```

### 创建新版本
```http
POST /api/apps/tender/prompts
Content-Type: application/json

{
  "module": "project_info_v3",
  "name": "招标信息提取 V3 (v2)",
  "description": "优化后的版本",
  "content": "新版本的 prompt 内容..."
}
```

## 代码集成示例

### 在抽取服务中使用

```python
from app.services.prompt_loader import PromptLoaderService

async def extract_project_info_v3(pool, project_id):
    # 尝试从数据库加载 prompt
    loader = PromptLoaderService(pool)
    prompt = await loader.get_active_prompt("project_info_v3")
    
    if not prompt:
        # Fallback 到文件
        from pathlib import Path
        prompt_file = Path(__file__).parent / "prompts" / "project_info_v3.md"
        prompt = prompt_file.read_text(encoding="utf-8")
    
    # 使用 prompt 进行抽取
    # ...
```

## 注意事项

1. **向后兼容**: 旧版模块（`project_info`, `review`）仍然可用，但标记为 deprecated
2. **版本管理**: 同一模块可以有多个版本，系统会自动使用 `is_active=TRUE` 且 `version` 最高的版本
3. **Fallback 机制**: 如果数据库中没有找到 prompt，系统会自动使用文件版本
4. **权限控制**: Prompt 的在线编辑功能应该只对管理员开放

## 测试

### 测试 API
```bash
# 获取模块列表
curl http://localhost:8000/api/apps/tender/prompts/modules

# 获取特定模块的 prompt
curl http://localhost:8000/api/apps/tender/prompts?module=project_info_v3
```

### 测试 Prompt 加载
```python
import asyncio
from app.services.db.postgres import _get_pool
from app.services.prompt_loader import PromptLoaderService

async def test_prompt_loader():
    pool = _get_pool()
    loader = PromptLoaderService(pool)
    
    # 测试加载 V3 prompt
    prompt = await loader.get_active_prompt("project_info_v3")
    print(f"Loaded prompt length: {len(prompt)}")
    print(f"First 200 chars: {prompt[:200]}")

asyncio.run(test_prompt_loader())
```

## 故障排查

### 问题 1: 脚本执行失败
**症状**: `ModuleNotFoundError` 或 `ConnectionError`

**解决**:
```bash
# 确保在项目根目录执行
cd /aidata/x-llmapp1

# 确保数据库连接配置正确
export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"

# 再次执行
python scripts/init_v3_prompts.py
```

### 问题 2: Prompt 未生效
**症状**: 抽取服务仍然使用旧版 prompt

**检查**:
```sql
-- 检查数据库中的 prompt
SELECT module, name, is_active, version, length(content)
FROM prompt_templates
WHERE module IN ('project_info_v3', 'requirements_v1', 'bid_response_v1');

-- 确保 is_active = TRUE
```

### 问题 3: API 返回空列表
**症状**: `/api/apps/tender/prompts/modules` 返回空的 modules 数组

**解决**:
- 检查路由是否正确加载
- 检查 API 服务是否重启
- 查看服务器日志

## 维护建议

1. **定期备份**: 定期导出 `prompt_templates` 表的数据
2. **版本控制**: 重要的 prompt 更新应该创建新版本而不是直接修改
3. **审计日志**: 考虑添加 prompt 修改的审计日志
4. **A/B 测试**: 新版本 prompt 上线前应该进行 A/B 测试

---

**文档版本**: 1.0  
**最后更新**: 2025-12-26  
**相关文档**: 
- `REFACTORING_COMPLETION_REPORT.md` - 重构完成报告
- `frontend/TENDER_INFO_V3_MIGRATION.md` - 前端迁移指南

