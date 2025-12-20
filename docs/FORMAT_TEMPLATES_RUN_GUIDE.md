# 格式模板功能运行指南

## 📋 概述

本指南说明如何在 Docker 环境中运行格式模板相关的数据库迁移和验证测试。

## 🚀 快速开始

### 前置条件

确保 Docker 容器正在运行：

```bash
cd /aidata/x-llmapp1
docker-compose ps
```

应该看到：
- `x-llmapp1-backend-1` (运行中)
- `x-llmapp1-postgres-1` (运行中)
- `x-llmapp1-frontend-1` (运行中)

### Step 1: 运行数据库迁移

```bash
# 方式1：使用迁移脚本（推荐）
docker exec -it x-llmapp1-backend-1 python /app/migrations/run_migrations.py

# 方式2：直接执行 SQL（如果方式1不可用）
docker exec -it x-llmapp1-postgres-1 psql -U postgres -d ylyw -f /app/migrations/026_enhance_format_templates.sql
```

**预期输出**：
```
NOTICE:  Added meta_json column to tender_directory_nodes
NOTICE:  Added asset_type constraint
NOTICE:  Added analysis_status constraint
NOTICE:  Added parse_status constraint
NOTICE:  =====================================
NOTICE:  Migration 026 completed successfully
NOTICE:  Format templates tables enhanced
NOTICE:  =====================================
```

### Step 2: 运行验证测试

```bash
docker exec -it x-llmapp1-backend-1 python /app/scripts/verify_format_templates_db.py
```

**预期输出**：
```
============================================================
格式模板数据库验证
============================================================

📝 测试 1: 创建格式模板
------------------------------------------------------------
✅ 创建成功: template_id=tpl_xxxxx
   名称: 测试模板_xxxxx
   所有者: test_user_001

📝 测试 2: 设置存储路径和 SHA256
------------------------------------------------------------
✅ 设置成功
   存储路径: /app/storage/templates/test_xxxxx.docx
   SHA256: sha256_xxxxx

📝 测试 3: 设置分析结果
------------------------------------------------------------
✅ 设置成功
   状态: SUCCESS
   confidence: 0.95

📝 测试 4: 设置解析结果
------------------------------------------------------------
✅ 设置成功
   状态: SUCCESS
   sections: 1
   预览DOCX: /app/storage/previews/test_xxxxx.docx
   预览PDF: /app/storage/previews/test_xxxxx.pdf

📝 测试 5: 创建模板资产
------------------------------------------------------------
✅ 资产创建成功: asset_id=fta_xxxxx
   类型: HEADER_IMG
   变体: A4_PORTRAIT

   资产列表: 1 个资产
   - HEADER_IMG (A4_PORTRAIT)

📝 测试 6: 列出格式模板
------------------------------------------------------------
✅ 列表查询成功
   总数: 1 个模板
   找到测试模板: tpl_xxxxx

📝 测试 7: 绑定格式模板到项目目录
------------------------------------------------------------
   创建测试项目: tprj_xxxxx
   创建根节点: tdn_xxxxx
✅ 绑定成功
   项目ID: tprj_xxxxx
   模板ID: tpl_xxxxx
   根节点ID: tdn_xxxxx

📝 测试 8: 更新模板元数据
------------------------------------------------------------
✅ 更新成功
   新名称: 更新后的模板名称
   新描述: 更新后的描述
   公开状态: True

📝 测试 9: 清理测试数据
------------------------------------------------------------
   删除测试项目: tprj_xxxxx
   删除模板资产: 1 个
✅ 清理完成
   删除模板: tpl_xxxxx

============================================================
✅ 所有测试通过！
============================================================

验证项目:
  ✅ 创建格式模板
  ✅ 设置存储路径和 SHA256
  ✅ 设置分析结果
  ✅ 设置解析结果
  ✅ 创建和列出模板资产
  ✅ 列出格式模板
  ✅ 绑定格式模板到项目目录
  ✅ 更新模板元数据
  ✅ 清理测试数据

============================================================
数据完整性约束验证
============================================================

📝 测试 1: 分析状态约束
------------------------------------------------------------
✅ 约束生效：拒绝了无效的 analysis_status

🎉 格式模板数据库验证完成！
```

## 🔍 验证数据库状态

### 查看表结构

```bash
# 连接到数据库
docker exec -it x-llmapp1-postgres-1 psql -U postgres -d ylyw

# 查看 format_templates 表结构
\d format_templates

# 查看 format_template_assets 表结构
\d format_template_assets

# 查看所有格式模板
SELECT id, name, owner_id, analysis_status, parse_status, created_at 
FROM format_templates;

# 查看统计视图
SELECT * FROM v_format_template_stats;

# 退出
\q
```

### 查看索引

```bash
docker exec -it x-llmapp1-postgres-1 psql -U postgres -d ylyw -c "
SELECT 
    tablename, 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE tablename IN ('format_templates', 'format_template_assets', 'tender_directory_nodes')
ORDER BY tablename, indexname;
"
```

### 查看约束

```bash
docker exec -it x-llmapp1-postgres-1 psql -U postgres -d ylyw -c "
SELECT 
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'format_templates'::regclass
   OR conrelid = 'format_template_assets'::regclass;
"
```

## 🐛 故障排除

### 问题 1: 迁移失败 - 字段已存在

**错误信息**：
```
ERROR:  column "xxx" of relation "format_templates" already exists
```

**解决方案**：
这是正常的！迁移是幂等的，如果字段已存在会被跳过（使用 `ADD COLUMN IF NOT EXISTS`）。

### 问题 2: 验证脚本失败 - 无法连接数据库

**错误信息**：
```
psycopg.OperationalError: could not connect to server
```

**解决方案**：
```bash
# 检查数据库容器是否运行
docker-compose ps

# 重启数据库容器
docker-compose restart postgres

# 等待几秒后重试
sleep 5
docker exec -it x-llmapp1-backend-1 python /app/scripts/verify_format_templates_db.py
```

### 问题 3: 导入错误 - 模块未找到

**错误信息**：
```
ModuleNotFoundError: No module named 'psycopg_pool'
```

**解决方案**：
```bash
# 确保在 Docker 容器内运行
docker exec -it x-llmapp1-backend-1 python /app/scripts/verify_format_templates_db.py

# 不要在宿主机上直接运行 Python 脚本
```

### 问题 4: 权限错误

**错误信息**：
```
permission denied for table format_templates
```

**解决方案**：
```bash
# 以 postgres 用户运行
docker exec -it x-llmapp1-postgres-1 psql -U postgres -d ylyw -c "
GRANT ALL ON format_templates TO <your_user>;
GRANT ALL ON format_template_assets TO <your_user>;
"
```

## 📊 性能测试

### 测试插入性能

```bash
docker exec -it x-llmapp1-backend-1 python -c "
import sys
import time
sys.path.insert(0, '/app/backend')

from psycopg_pool import ConnectionPool
from app.services.dao.tender_dao import TenderDAO

pool = ConnectionPool('postgresql://postgres:postgres@postgres:5432/ylyw')
dao = TenderDAO(pool)

start = time.time()
for i in range(100):
    dao.create_format_template(
        name=f'Test_{i}',
        description=f'Test description {i}',
        style_config={},
        owner_id='perf_test',
        is_public=False
    )
elapsed = time.time() - start

print(f'Created 100 templates in {elapsed:.2f}s ({100/elapsed:.2f} TPS)')

# 清理
dao._execute('DELETE FROM format_templates WHERE owner_id=%s', ('perf_test',))
"
```

### 测试查询性能

```bash
docker exec -it x-llmapp1-postgres-1 psql -U postgres -d ylyw -c "
EXPLAIN ANALYZE
SELECT * FROM format_templates 
WHERE owner_id='test_user' OR is_public=true 
ORDER BY created_at DESC;
"
```

## 📚 相关文档

- [STEP1_FORMAT_TEMPLATES_WORK_SUMMARY.md](./STEP1_FORMAT_TEMPLATES_WORK_SUMMARY.md) - Work 层实现总结
- [STEP2_DATABASE_AND_DAO_SUMMARY.md](./STEP2_DATABASE_AND_DAO_SUMMARY.md) - 数据库和 DAO 总结
- [FORMAT_TEMPLATES_GAP.md](./FORMAT_TEMPLATES_GAP.md) - 前后端接口缺口分析
- [FORMAT_TEMPLATES_WORK_INTEGRATION.md](./FORMAT_TEMPLATES_WORK_INTEGRATION.md) - Work 集成指南

## ✅ 完成检查清单

在继续下一步之前，确保：

- [ ] 数据库迁移成功运行
- [ ] 验证脚本所有测试通过
- [ ] 可以在数据库中看到新的表和字段
- [ ] 索引和约束正确创建
- [ ] 统计视图可查询

## 🎯 下一步

完成 Step 2 后，可以继续：

1. **Step 3**: 更新 Router 层，使用 Work 层替代直接调用 Service
2. **Step 4**: 前端集成测试
3. **Step 5**: 性能优化和监控

## 💡 提示

- 所有脚本都设计为幂等的，可以安全地重复运行
- 验证脚本会自动清理测试数据，不会污染生产环境
- 如果遇到问题，可以查看容器日志：`docker logs x-llmapp1-backend-1`

