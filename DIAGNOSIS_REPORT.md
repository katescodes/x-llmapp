# 招投标项目基本信息提取不全 - 诊断报告

## 问题描述
用户反馈："测试"项目有三个原始文件，但基本信息提取不全（如预算金额、最高限价等字段为空）

## 诊断过程

### 1. 数据库检查

#### 1.1 项目信息
```
项目ID: tp_9160ce348db444e9b5a3fa4b66e8680a
项目名称: 测试
知识库ID: be9688a650134e19ac1e796ef9121baf
```

#### 1.2 已提取的基本信息（来自 tender_project_info 表）
```json
{
  "projectName": "成都市第六再生水厂二期项目智慧化及自控系统设备",
  "ownerName": "成都环境建设管理有限公司",
  "agencyName": "成都市公共资源电子交易云平台",
  "bidDeadline": "2024年12月12日10时30分",
  "schedule": "90个日历天",
  "bidBond": "50万元",
  "location": "高洪村成都市第六再生水厂南侧",
  "contact": "联系人：李女士，电话：028-61528024",
  
  // ❌ 以下字段为空
  "budget": "",
  "maxPrice": "",
  "bidOpeningTime": "",
  "quality": ""
}
```

#### 1.3 文档索引检查

**关键发现：**

1. **kb_chunks表**：0条记录
   ```sql
   SELECT COUNT(*) FROM kb_chunks WHERE kb_id = 'be9688a650134e19ac1e796ef9121baf'
   -- 结果：0
   ```

2. **tender_project_documents表**：0条记录
   ```sql
   SELECT COUNT(*) FROM tender_project_documents WHERE project_id = 'tp_9160ce348db444e9b5a3fa4b66e8680a'
   -- 结果：0
   ```

3. **documents表**：0条记录
   ```sql
   SELECT COUNT(*) FROM documents WHERE namespace = 'tp_9160ce348db444e9b5a3fa4b66e8680a'
   -- 结果：0
   ```

## 根本原因

**文档没有被索引到docstore（文档存储）！**

项目的三个原始文件上传后，并未触发文档分片和索引流程，导致：
1. 文档内容没有被切分成chunks（文档块）
2. chunks没有被向量化并存储到数据库
3. LLM提取信息时，检索不到任何文档内容
4. 因此只能提取到有限的几个字段（可能是从文件名或其他元数据中提取的）

## 解决方案

### 方案1：前端手动触发索引（推荐）

在前端项目详情页，应该有一个"索引文档"或"准备文档库"按钮：

1. 登录系统：`admin/admin123`
2. 进入"测试"项目
3. 点击**"索引文档"**或**"准备文档库"**按钮
4. 等待索引完成（通常需要几分钟，取决于文档大小）
5. 索引完成后，再点击**"提取基本信息"**

### 方案2：API手动触发索引

```bash
# 1. 获取token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')

# 2. 触发文档索引
curl -X POST "http://localhost:8000/api/apps/tender/projects/tp_9160ce348db444e9b5a3fa4b66e8680a/docstore/index" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# 3. 等待索引完成（查询状态）
curl -X GET "http://localhost:8000/api/apps/tender/projects/tp_9160ce348db444e9b5a3fa4b66e8680a/docstore/status" \
  -H "Authorization: Bearer $TOKEN"

# 4. 索引完成后，重新提取基本信息
curl -X POST "http://localhost:8000/api/apps/tender/projects/tp_9160ce348db444e9b5a3fa4b66e8680a/extract/project-info" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_id": null}'
```

### 方案3：检查自动索引流程（开发修复）

如果文档上传后应该自动索引但没有触发，需要检查：

1. **文档上传endpoint**（`/api/apps/tender/projects/{id}/documents`）
   - 是否正确调用了docstore索引接口
   - 检查后台任务是否正常执行

2. **Docstore服务**
   - 检查`DocstoreService`是否正常工作
   - 查看后端日志是否有错误

3. **后台任务队列**
   - 检查Redis连接
   - 检查worker进程是否运行

## 验证索引成功

索引完成后，应该能看到：

```sql
-- 1. kb_chunks表应该有记录
SELECT COUNT(*) FROM kb_chunks WHERE kb_id = 'be9688a650134e19ac1e796ef9121baf';
-- 应该返回 > 0

-- 2. 可以搜索到预算相关信息
SELECT 
    LEFT(content, 100) as preview
FROM kb_chunks
WHERE kb_id = 'be9688a650134e19ac1e796ef9121baf'
  AND (content ILIKE '%预算%' OR content ILIKE '%限价%' OR content ILIKE '%万元%')
LIMIT 5;
-- 应该能找到包含预算金额的chunks
```

## 后续改进建议

1. **自动化索引**
   - 文档上传后自动触发索引
   - 添加索引状态显示（进行中/完成/失败）

2. **索引状态提示**
   - 提取基本信息前，检查文档是否已索引
   - 如果未索引，给出明确提示并提供"立即索引"按钮

3. **索引失败通知**
   - 如果索引失败，给出清晰的错误信息
   - 提供重试机制

## 联系人
如需技术支持，请联系开发团队。

