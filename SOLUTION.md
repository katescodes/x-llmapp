# 招投标项目基本信息提取不全 - 完整解决方案

## 问题根源

**文档没有被索引！**

通过数据库检查发现：
- `kb_chunks`表：0条记录 ❌
- `tender_project_documents`表：0条记录 ❌  
- `documents`表：0条记录 ❌

**原因分析：**
1. 文档上传后，未触发自动索引流程
2. 或者索引过程中出现错误但未报告
3. 或者文档是在旧版本系统中上传的，未使用IngestV2

## 解决方案

### 方案1：前端界面操作（推荐，最简单）

1. **登录系统**
   ```
   用户名: admin
   密码: admin123
   ```

2. **进入项目**
   - 找到"测试"项目
   - 点击进入项目详情

3. **重新上传文档**（最彻底的方法）
   - 删除现有的三个文档（如果能看到的话）
   - 重新上传三个原始文件
   - 系统会自动触发索引

4. **等待索引完成**
   - 上传后会显示"处理中..."
   - 等待几分钟（取决于文档大小）
   - 索引完成后会显示"就绪"

5. **提取基本信息**
   - 点击"提取基本信息"按钮
   - 这次应该能提取到完整的信息（包括预算金额、最高限价等）

---

### 方案2：使用手动索引脚本

如果文档已经上传到服务器，可以使用我创建的脚本手动触发索引：

```bash
# 1. 进入容器
docker exec -it localgpt-backend bash

# 2. 运行索引脚本
cd /repo
python3 manual_index.py tp_9160ce348db444e9b5a3fa4b66e8680a

# 3. 查看输出，确认索引成功
# 应该看到类似：
#   ✅ 索引成功
#   - 文档版本ID: xxx
#   - 分片数量: 123
#   - Milvus数量: 123

# 4. 退出容器
exit
```

**注意**：如果脚本报告"项目文件目录不存在"，说明文档没有实际上传，需要使用方案1重新上传。

---

### 方案3：API触发索引（高级用户）

```bash
# 1. 获取token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')

# 2. 重新上传文档（如果有原始文件）
# 假设有三个文件：file1.pdf, file2.docx, file3.pdf
curl -X POST "http://localhost:8000/api/apps/tender/projects/tp_9160ce348db444e9b5a3fa4b66e8680a/assets/import" \
  -H "Authorization: Bearer $TOKEN" \
  -F "kind=tender" \
  -F "files=@file1.pdf" \
  -F "files=@file2.docx" \
  -F "files=@file3.pdf"

# 3. 等待几分钟让索引完成

# 4. 重新提取基本信息
curl -X POST "http://localhost:8000/api/apps/tender/projects/tp_9160ce348db444e9b5a3fa4b66e8680a/extract/project-info" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_id": null}'
```

---

## 验证索引成功

索引完成后，可以通过数据库验证：

```bash
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
-- 查询分片数量（应该 > 0）
SELECT COUNT(*) as chunk_count
FROM kb_chunks
WHERE kb_id = 'be9688a650134e19ac1e796ef9121baf';

-- 查询预算相关信息（应该能找到）
SELECT LEFT(content, 150) as preview
FROM kb_chunks
WHERE kb_id = 'be9688a650134e19ac1e796ef9121baf'
  AND (
    content ILIKE '%预算%' 
    OR content ILIKE '%限价%'
    OR content ILIKE '%万元%'
  )
LIMIT 3;
"
```

**预期结果：**
- chunk_count应该 > 0（通常几百到几千）
- 应该能找到包含预算、限价等信息的文本片段

---

## 为什么会出现这个问题？

### 代码分析

查看`backend/app/services/tender_service.py`的`import_assets`方法（line 590-598）：

```python
# 新入库逻辑 - 自动调用 IngestV2 进行索引
if kind in ("tender", "bid", "custom_rule"):
    ingest_v2_result = await ingest_v2.ingest_asset_v2(
        project_id=project_id,
        asset_id=temp_asset_id,
        file_bytes=b,
        filename=filename,
        doc_type=kind,
        owner_id=proj.get("owner_id"),
        storage_path=storage_path,
    )
```

**正常流程：**
1. ✅ 文档上传 → 调用`/api/apps/tender/projects/{id}/assets/import`
2. ✅ 后端调用`TenderService.import_assets`
3. ✅ 自动调用`IngestV2Service.ingest_asset_v2`进行索引
4. ✅ 文档被分片并存储到数据库
5. ✅ 提取基本信息时能检索到文档内容

**异常情况（导致测试项目问题）：**
1. ❌ 文档在旧版本系统中上传（没有IngestV2）
2. ❌ 索引过程出错但未报告
3. ❌ 环境变量配置错误（如`INGEST_MODE != NEW_ONLY`）
4. ❌ 后台任务队列未运行或失败

---

## 建议的长期改进

### 1. 添加索引状态显示
在前端显示文档的索引状态：
- 🔄 索引中...
- ✅ 已索引 (123个分片)
- ❌ 索引失败

### 2. 自动检测并提示
在"提取基本信息"按钮旁边显示：
```
⚠️ 文档未索引，无法提取信息
[立即索引]
```

### 3. 索引失败重试机制
如果索引失败，提供"重新索引"按钮

### 4. 后台任务监控
添加后台任务状态监控，及时发现索引失败

---

## 总结

**根本原因**：文档没有被索引到docstore

**最简单的解决方案**：重新上传文档（前端操作）

**快速修复方案**：运行`manual_index.py`脚本

**验证方法**：查询`kb_chunks`表，应该有记录

**后续改进**：添加索引状态显示和自动检测

如有问题，请联系开发团队！

