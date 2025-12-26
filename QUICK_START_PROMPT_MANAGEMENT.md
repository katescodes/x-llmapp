# 快速开始指南

## 🚀 Prompt 管理系统更新 - 快速使用

### 1️⃣ 初始化新的 Prompt 模板（一次性操作）

```bash
cd /aidata/x-llmapp1
python scripts/init_v3_prompts.py
```

**期望输出**:
```
✓ 成功插入模块 'project_info_v3' (长度: 15234 字符)
✓ 成功插入模块 'requirements_v1' (长度: 8756 字符)
✓ 成功插入模块 'bid_response_v1' (长度: 4189 字符)
✓ 已标记 2 个旧版 prompt 为 deprecated

✅ V3 Prompt 模板初始化完成！
```

### 2️⃣ 验证 API

```bash
# 获取所有模块（包括新增的 V3 模块）
curl http://localhost:8000/api/apps/tender/prompts/modules | jq '.modules[] | {id, name, version, category}'
```

**期望输出**:
```json
{
  "id": "project_info_v3",
  "name": "招标信息提取 (V3)",
  "version": "v3",
  "category": "extraction"
}
{
  "id": "requirements_v1",
  "name": "招标要求抽取",
  "version": "v1",
  "category": "extraction"
}
{
  "id": "bid_response_v1",
  "name": "投标响应要素抽取",
  "version": "v1",
  "category": "extraction"
}
```

### 3️⃣ 测试 Prompt 加载

```python
# test_prompt_loading.py
import asyncio
from app.services.db.postgres import _get_pool
from app.services.prompt_loader import PromptLoaderService

async def test():
    pool = _get_pool()
    loader = PromptLoaderService(pool)
    
    for module in ["project_info_v3", "requirements_v1", "bid_response_v1"]:
        prompt = await loader.get_active_prompt(module)
        if prompt:
            print(f"✓ {module}: {len(prompt)} 字符")
        else:
            print(f"✗ {module}: 未找到")

asyncio.run(test())
```

### 4️⃣ 前端集成示例

```typescript
// PromptModules.tsx
import React, { useEffect, useState } from 'react';
import axios from 'axios';

interface PromptModule {
  id: string;
  name: string;
  description: string;
  icon: string;
  version?: string;
  category?: string;
  deprecated?: boolean;
}

export const PromptModules: React.FC = () => {
  const [modules, setModules] = useState<PromptModule[]>([]);

  useEffect(() => {
    axios.get('/api/apps/tender/prompts/modules')
      .then(res => setModules(res.data.modules));
  }, []);

  // 按分类分组
  const grouped = modules.reduce((acc, mod) => {
    const cat = mod.category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(mod);
    return acc;
  }, {} as Record<string, PromptModule[]>);

  return (
    <div>
      {Object.entries(grouped).map(([category, mods]) => (
        <div key={category}>
          <h3>{category}</h3>
          {mods.map(mod => (
            <div key={mod.id} className={mod.deprecated ? 'deprecated' : ''}>
              <span>{mod.icon} {mod.name}</span>
              {mod.version && <span className="badge">{mod.version}</span>}
              {mod.deprecated && <span className="badge-warning">已弃用</span>}
              <p>{mod.description}</p>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};
```

### 5️⃣ 在线编辑 Prompt（管理员功能）

```typescript
// EditPrompt.tsx
const updatePrompt = async (promptId: string, content: string) => {
  await axios.put(`/api/apps/tender/prompts/${promptId}`, {
    content,
    name: "招标信息提取 V3 (已更新)",
    description: "优化后的版本"
  });
};
```

---

## 📋 常见任务

### 查看当前激活的 Prompt
```sql
SELECT module, name, version, length(content), is_active
FROM prompt_templates
WHERE is_active = TRUE
ORDER BY module;
```

### 切换到新版本
```sql
-- 停用旧版本
UPDATE prompt_templates SET is_active = FALSE WHERE module = 'project_info_v3' AND version = 1;

-- 激活新版本
UPDATE prompt_templates SET is_active = TRUE WHERE module = 'project_info_v3' AND version = 2;
```

### 导出 Prompt 备份
```bash
pg_dump -U your_user -d your_database -t prompt_templates > prompt_templates_backup.sql
```

---

## 🔍 故障排查

### 问题：初始化脚本失败
```bash
# 检查数据库连接
export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"

# 检查 prompt 文件是否存在
ls -la backend/app/works/tender/prompts/
```

### 问题：API 返回旧模块列表
```bash
# 重启后端服务
# 或检查代码是否已更新
git log -1 backend/app/routers/prompts.py
```

---

## 📚 参考文档

- **详细文档**: `PROMPT_MANAGEMENT_UPDATE.md`
- **重构报告**: `REFACTORING_COMPLETION_REPORT.md`
- **前端迁移**: `frontend/TENDER_INFO_V3_MIGRATION.md`

---

**快速支持**: 遇到问题？查看上述文档或联系开发团队。

