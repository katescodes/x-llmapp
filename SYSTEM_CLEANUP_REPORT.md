# 系统清理报告

生成时间：2025-12-31
分析范围：招投标系统全栈代码和数据库

## 📊 系统架构概览

### 核心功能模块
1. **文档存储系统**
   - ✅ 新系统：`documents` + `document_versions` + `doc_segments` (6144条数据)
   - ⚠️ 旧系统：`kb_documents` (15条) + `kb_chunks` (0条) - **可清理**

2. **招标要求提取**
   - ✅ V2清单方式：`tender_requirements` (标准清单 + P1全文补充)
   - ❌ V1传统方式：已废弃 (2025-12-29)
   - ⚠️ 旧表：`tender_risks` (0条数据) - **可清理**

3. **项目抽取状态**
   - ✅ 已清除所有项目的抽取状态（46条运行记录 + 4个项目数据）

---

## 🗑️ 可清理内容分析

### 1. 废弃的数据表

#### 1.1 tender_risks 表
- **状态**：已废弃，被 `tender_requirements` 替代
- **数据量**：0 条
- **废弃时间**：2025-12-29
- **废弃原因**：V2标准清单方式提供更高质量的数据
- **代码引用**：
  - `backend/app/services/dao/tender_dao.py:442` - 注释标记已废弃
  - `backend/app/services/project_delete/cleaners.py:312` - 删除逻辑（兼容）
  - `backend/migrations/005_create_tender_app_tables.sql:47` - 表定义

**建议**：✅ 可以安全删除

#### 1.2 kb_chunks 表
- **状态**：旧文档存储系统，已被 `doc_segments` 替代
- **数据量**：0 条
- **新系统**：`doc_segments` (6144条数据)
- **保留原因**：兼容性（独立导入的文档）
- **代码引用**：
  - `backend/app/platform/retrieval/facade.py:236-254` - 策略2：兼容旧系统检索
  - `backend/app/platform/retrieval/providers/legacy/pg_lexical.py` - 旧检索器
  - `backend/app/services/dao/tender_dao.py:334-360` - 插入chunks方法

**建议**：⚠️ 暂时保留（作为兼容层），但可标记为 DEPRECATED

#### 1.3 kb_documents 表
- **状态**：旧文档元数据表
- **数据量**：15 条（仍在使用）
- **新系统**：`documents` + `document_versions` (155条)
- **代码引用**：
  - `backend/app/platform/retrieval/facade.py:304-310` - 从meta_json提取doc_version_id
  - `backend/app/services/kb_service.py` - 知识库服务
  - `backend/app/services/dao/kb_dao.py` - 数据访问层

**建议**：⚠️ 暂时保留（仍有15条数据在使用中）

---

### 2. 废弃的代码功能

#### 2.1 V1招标要求提取
- **文件**：`backend/app/works/tender/extract_v2_service.py:317-325`
- **状态**：已废弃，返回错误信息
- **废弃时间**：2025-12-29
- **路由**：`POST /api/apps/tender/projects/{project_id}/extract/risks?use_checklist=0`
- **代码位置**：
  ```python
  # backend/app/routers/tender.py:512-517
  # ❌ V1已废弃，不应进入此分支
  logger.error(f"❌ V1提取方式已废弃: project={project_id}")
  ```

**建议**：✅ 可以删除V1相关代码，强制使用V2

#### 2.2 规则集管理（已弃用）
- **文件**：`backend/app/services/dao/tender_dao.py:306-311`
- **状态**：已弃用，规则文件现在直接作为审核上下文叠加
- **注释**：
  ```python
  # ==================== 规则集管理（已弃用） ====================
  # 注意：以下方法已弃用，规则文件现在直接作为审核上下文叠加
  # 保留这些方法是为了向后兼容，避免线上代码调用时报错
  # 可在确认前端完全移除相关调用后删除
  ```

**建议**：⚠️ 需要确认前端是否还在调用，确认后可删除

#### 2.3 导出DOCX V2 (deprecated)
- **文件**：`backend/app/routers/export.py:119-129`
- **状态**：标记为 `deprecated=True`
- **说明**：已废弃，推荐使用 GET 版本

**建议**：✅ 可以删除POST版本

---

### 3. 未使用的迁移文件

#### 需要保留的迁移文件
所有迁移文件都需要保留，因为它们记录了数据库schema的演进历史。即使某些表已废弃，迁移文件也应保留以便：
1. 回滚到历史版本
2. 理解schema变更历史
3. 新环境初始化

**建议**：✅ 保留所有迁移文件

---

### 4. 测试和临时文件

#### 4.1 根目录测试文件
- `backend/test_pipeline_simple.py`
- `backend/test_review_v3.py`

**建议**：⚠️ 确认是否还需要，考虑移到 `tests/` 目录

#### 4.2 备份文件
- `backup_before_v2_migration_20251229_223640.sql` (13798行)

**建议**：✅ 可以移到专门的备份目录或删除（如果已确认迁移成功）

---

## 📋 清理执行计划

### 阶段1：安全清理（低风险）

#### 1.1 删除 tender_risks 表
```sql
-- 检查是否有数据
SELECT COUNT(*) FROM tender_risks;

-- 如果确认为0，执行删除
BEGIN;
DROP TABLE IF EXISTS tender_risks CASCADE;
COMMIT;
```

#### 1.2 删除V1招标要求提取代码
文件需要修改：
- `backend/app/routers/tender.py:511-534` - 删除V1分支
- `backend/app/works/tender/extract_v2_service.py:317-325` - 删除废弃方法

#### 1.3 删除废弃的导出接口
- `backend/app/routers/export.py:119-129` - 删除POST版本

#### 1.4 清理根目录文件
```bash
# 移动测试文件到tests目录
mv backend/test_pipeline_simple.py backend/tests/
mv backend/test_review_v3.py backend/tests/

# 移动备份文件
mkdir -p backups/
mv backup_before_v2_migration_20251229_223640.sql backups/
```

---

### 阶段2：谨慎清理（中风险）

#### 2.1 标记 kb_chunks 和 kb_documents 为 DEPRECATED
在代码中添加警告日志，但暂不删除：
```python
# backend/app/platform/retrieval/facade.py
logger.warning("DEPRECATED: Using kb_chunks retrieval (legacy). Please migrate to doc_segments.")
```

#### 2.2 确认并删除规则集管理代码
需要先确认前端是否还在调用：
```bash
# 搜索前端代码
grep -r "custom_rule_set" frontend/src/
```

---

### 阶段3：数据迁移（高风险）

#### 3.1 迁移 kb_documents 到新系统
如果15条数据仍在使用，需要：
1. 分析这15条数据的用途
2. 编写迁移脚本
3. 迁移到 `documents` + `document_versions`
4. 验证功能正常
5. 删除旧表

---

## ⚠️ 注意事项

### 删除前必须检查
1. ✅ 数据量为0
2. ✅ 代码中无活跃引用
3. ✅ 前端无依赖
4. ✅ 有完整备份
5. ✅ 在测试环境验证

### 不要删除
1. ❌ 所有迁移文件（migrations/*.sql）
2. ❌ 有数据的表（即使已废弃）
3. ❌ 正在使用的兼容层代码

---

## 📈 预期收益

### 代码清理
- 删除约 **200-300行** 废弃代码
- 简化 **3个** 核心接口
- 移除 **1个** 废弃数据表

### 维护性提升
- 减少代码复杂度
- 消除混淆（V1/V2并存）
- 明确系统边界

### 性能优化
- 减少无用查询
- 简化检索逻辑

---

## 🎯 推荐执行顺序

1. **立即执行**（安全）
   - ✅ 删除 `tender_risks` 表
   - ✅ 删除 V1 招标要求提取代码
   - ✅ 删除废弃的导出接口
   - ✅ 整理根目录文件

2. **短期执行**（1周内）
   - ⚠️ 标记 `kb_chunks` 为 DEPRECATED
   - ⚠️ 确认并删除规则集管理代码

3. **中期执行**（1个月内）
   - ⚠️ 迁移 `kb_documents` 数据
   - ⚠️ 删除旧文档系统表

---

## 📝 执行记录

### 已完成 ✅
- ✅ 2025-12-31 14:00: 清除所有项目抽取状态（46条运行记录 + 4个项目数据）
- ✅ 2025-12-31 14:30: 生成系统清理报告
- ✅ 2025-12-31 14:35: **删除 tender_risks 表**（已确认0条数据）
- ✅ 2025-12-31 14:36: **移动备份文件** 到 backups/ 目录
- ✅ 2025-12-31 14:37: **移动测试文件** 到 tests/ 目录
- ✅ 2025-12-31 14:38: **删除废弃的导出接口** (POST /export/docx-v2)
- ✅ 2025-12-31 14:39: **简化V1废弃代码** (保留错误提示，简化逻辑)
- ✅ 2025-12-31 14:40: **更新代码注释** (标记已删除的功能)
- ✅ 2025-12-31 14:41: **清理项目删除逻辑** (移除tender_risks引用)

### 清理成果统计
- 🗑️ 删除数据表：1个 (tender_risks)
- 📝 删除代码行：约50行
- 📁 整理文件：3个 (2个测试文件 + 1个备份文件)
- 🔧 更新文件：4个 (tender.py, export.py, tender_dao.py, cleaners.py)

### 待执行（中长期）
- ⏳ 标记 kb_chunks 为 DEPRECATED（需要保留兼容层）
- ⏳ 迁移 kb_documents 数据到新系统（15条数据）
- ⏳ 删除旧文档系统表（需要先完成数据迁移）


