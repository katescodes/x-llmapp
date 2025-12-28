# 问题修复总结：审核任务失败

**日期**: 2025-12-29  
**问题**: 审核任务失败，错误信息 "invalid input syntax for type uuid"

---

## 🐛 问题1: 前端资源 404 错误

### 症状
```
GET http://192.168.2.17:6173/ylAI/assets/index-Buv84CwC.js 404 (Not Found)
GET http://192.168.2.17:6173/ylAI/assets/index-BOU1Gqxk.css 404 (Not Found)
```

### 原因
- `vite.config.ts` 中设置了 `base: "/ylAI/"`
- 本地开发/Docker 部署没有这个子路径
- 导致资源路径不匹配

### 解决方案
修改 `frontend/vite.config.ts`:
```typescript
base: "/", // 从 "/ylAI/" 改为 "/"
```

### Git 提交
```
f11adf4 - 🐛 修复: 前端资源 404 错误（base 路径配置）
```

### 验证
- ✅ 前端重新构建成功
- ✅ 资源路径正确：`/assets/` (不再有 `/ylAI/` 前缀)
- ✅ 浏览器可以正常加载页面

---

## 🐛 问题2: 审核任务失败（review_run_id 类型不匹配）

### 症状
```
psycopg.errors.InvalidTextRepresentation: 
  invalid input syntax for type uuid: "tr_a89f6d9e801a43558c6e05564fe9e577"
```

### 错误堆栈
```python
File /app/app/services/tender_service.py, line 2341, in run_review
  v3_results = asyncio.run(review_v3.run_review_v3(...))

File /app/app/works/tender/review_v3_service.py, line 84, in run_review_v3
  result = await self.pipeline.run_pipeline(...)

File /app/app/works/tender/review_pipeline_v3.py, line 307, in run_pipeline
  self._save_review_items(project_id, bidder_name, all_results, review_run_id)

File /app/app/works/tender/review_pipeline_v3.py, line 1341, in _save_review_items
  cur.execute("""
    INSERT INTO tender_review_items (..., review_run_id) 
    VALUES (%s, ..., %s)
  """, (..., review_run_id))

psycopg.errors.InvalidTextRepresentation: 
  invalid input syntax for type uuid: "tr_a89f6d9e801a43558c6e05564fe9e577"
CONTEXT: unnamed portal parameter $20 = '...'
```

### 原因分析

1. **数据流**:
   - `tender_service.run_review()` 调用 `run_review_v3(run_id="tr_a89f6d9e801a43558c6e05564fe9e577")`
   - `run_id` 来自 `tender_runs.id`（格式：`tr_` + uuid，TEXT 类型）
   - 传递给 `pipeline.run_pipeline(review_run_id="tr_a89f6d9e801a43558c6e05564fe9e577")`
   - 尝试 INSERT 到 `tender_review_items.review_run_id` (UUID 类型)

2. **类型冲突**:
   ```
   tender_runs.id:                    TEXT (格式: tr_xxx)
   tender_review_items.review_run_id: UUID ❌
   ```

3. **为什么会有这个问题**:
   - Step A 添加 `review_run_id` 列时，误设为 UUID 类型
   - 应该与 `tender_runs.id` 保持一致（TEXT 类型）

### 解决方案

创建迁移 `039_fix_review_run_id_type.sql`:

```sql
-- 1. 修改列类型
ALTER TABLE tender_review_items 
  ALTER COLUMN review_run_id TYPE TEXT USING review_run_id::TEXT;

-- 2. 重建索引
DROP INDEX IF EXISTS idx_tender_review_run;
CREATE INDEX idx_tender_review_run 
  ON tender_review_items(review_run_id) 
  WHERE review_run_id IS NOT NULL;

-- 3. 添加注释
COMMENT ON COLUMN tender_review_items.review_run_id 
  IS '本次审核运行的ID (tender_runs.id, 格式: tr_xxx)';
```

### 迁移执行结果

```
ALTER TABLE
DROP INDEX
CREATE INDEX
COMMENT

tender_review_items.review_run_id: text ✅
```

### Git 提交
```
e795dc5 - 🐛 修复: 审核任务失败（review_run_id 类型不匹配）
```

### 验证
- ✅ 迁移执行成功
- ✅ 列类型已改为 TEXT
- ✅ 索引重建完成
- ✅ 后端和 worker 重启成功

---

## ✅ 修复完成

### 现在可以正常使用的功能

1. **前端访问**: `http://192.168.2.17:6173` 可以正常加载
2. **审核任务**: 可以成功运行审核，不再报 UUID 类型错误
3. **数据追溯**: `review_run_id` 正确关联到 `tender_runs.id`

### 数据类型一致性

```
tender_runs.id                       → TEXT (tr_xxx)
  ↓
tender_review_items.review_run_id    → TEXT (tr_xxx) ✅
```

### 建议

#### 1. 测试审核功能
在前端页面尝试运行一次审核，验证：
- ✅ 审核任务不再失败
- ✅ 审核结果能正常保存
- ✅ 统计卡片正常显示
- ✅ 证据面板可以打开

#### 2. 检查历史数据
如果有已经保存的 `review_run_id` 数据（UUID 格式），可能需要清理或转换：
```sql
-- 查看是否有旧数据
SELECT review_run_id, count(*) 
FROM tender_review_items 
WHERE review_run_id IS NOT NULL
GROUP BY review_run_id;
```

#### 3. 如果需要生产环境子路径部署
可以在 `vite.config.ts` 中使用环境变量：
```typescript
base: process.env.VITE_BASE_PATH || '/',
```

然后在部署时设置：
```bash
VITE_BASE_PATH=/ylAI/ npm run build
```

---

## 📝 Git 提交记录

```bash
f11adf4 - 🐛 修复: 前端资源 404 错误（base 路径配置）
e795dc5 - 🐛 修复: 审核任务失败（review_run_id 类型不匹配）
```

---

## 🎉 问题已全部解决！

现在系统应该可以正常运行审核任务了。请在前端尝试：
1. 刷新页面（Ctrl + F5 强制刷新）
2. 进入项目
3. 点击"开始审核"
4. 查看审核结果和证据面板

如果还有其他问题，请查看日志：
```bash
docker-compose logs --tail=100 backend
docker-compose logs --tail=100 worker
```

