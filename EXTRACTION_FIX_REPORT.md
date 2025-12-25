# 招投标项目基本信息提取不全 - 问题分析与解决方案

## 问题现象

"测试"项目提取的基本信息**部分缺失**：

### ✅ 已提取的字段
- `projectName`: "成都市第六再生水厂二期项目智慧化及自控系统设备"
- `ownerName`: "成都环境建设管理有限公司"
- `agencyName`: "成都市公共资源电子交易云平台"
- `bidDeadline`: "2024年12月12日10时30分"
- `contact`: "联系人：李女士，电话：028-61528024"
- `location`: "高洪村成都市第六再生水厂南侧"
- `schedule`: "90个日历天"
- `bidBond`: "50万元"

### ❌ 缺失的字段
- `budget`: "" (预算金额)
- `maxPrice`: "" (最高限价/招标控制价)
- `bidOpeningTime`: "" (开标时间)
- `quality`: "" (质量要求)

---

## 深度调查过程

### 第一步：检查文档是否被索引

**初步假设**：文档没有被索引，所以提取不到信息

**检查结果**：
```sql
-- 旧版kb_chunks表：0条记录
SELECT COUNT(*) FROM kb_chunks WHERE kb_id = 'be9688a650134e19ac1e796ef9121baf';
-- 结果：0

-- 新版documents表：0条记录（项目专属）
SELECT COUNT(*) FROM documents WHERE namespace = 'tp_9160ce348db444e9b5a3fa4b66e8680a';
-- 结果：0
```

**结论**：❌ 假设错误！因为已经提取到了部分信息，说明文档是被索引了的。

---

### 第二步：追踪证据来源

查看提取结果中的`evidence_chunk_ids`：
```json
["seg_4a74143ab0db45e986611ac856c82065", "seg_23", "seg_88", "seg_87"]
```

**关键发现**：这些是`seg_`开头的ID，说明使用的是**新版doc_segments系统**！

---

### 第三步：定位文档存储位置

查询`doc_segments`表，发现文档存储在**通用的`tender` namespace**下，而不是项目ID下：

```sql
SELECT d.namespace, dv.filename, COUNT(ds.id) as segment_count
FROM documents d
JOIN document_versions dv ON dv.document_id = d.id
LEFT JOIN doc_segments ds ON ds.doc_version_id = dv.id
WHERE dv.filename LIKE '%成都市第六再生水厂%'
GROUP BY d.namespace, dv.filename;
```

**结果**：
| namespace | filename | segment_count |
|-----------|----------|---------------|
| tender | 成都市第六再生水厂二期项目智慧化及自控系统设备采购-招标文件.pdf | 155 |
| tender | 技术标准和要求.pdf | 305 |
| tender | 成都市第六再生水厂二期项目智慧化及自控系统设备采购-招标附件.docx | 8 |

**结论**：✅ 文档已被正确索引！共**468个分片**。

---

### 第四步：在文档中搜索缺失信息

在这些文档中搜索"预算"、"限价"等关键词：

```sql
SELECT LEFT(ds.content_text, 300) as content
FROM doc_segments ds
JOIN document_versions dv ON dv.id = ds.doc_version_id
WHERE dv.filename LIKE '%成都市第六再生水厂%'
  AND (ds.content_text ILIKE '%预算%' OR ds.content_text ILIKE '%限价%')
LIMIT 1;
```

**发现**：
```
★招标控制价招标控制价为40199936.16元
```

**关键结论**：
1. ✅ 信息**确实存在于文档**中
2. ❌ 但是**没有被提取出来**

---

## 根本原因分析

### 问题1：查询关键词不匹配

查看提取规格（`project_info_v2.py`）：

```python
queries = {
    "base": "招标公告 项目名称 项目编号 预算金额 采购人 代理机构 投标截止 开标 时间 地点 联系人 电话",
    ...
}
```

**问题**：
- 查询中使用的是"**预算金额**"
- 但文档中使用的是"**招标控制价**"、"**最高限价**"

**结果**：向量检索时，相关分片没有被召回到top-K中，导致LLM看不到这些信息！

### 问题2：字段映射不明确

查看prompt模板（`project_info_v2.md`）：

```json
"budget": "预算金额",
"maxPrice": "最高限价",
```

**问题**：prompt没有告诉LLM：
- "招标控制价" = "最高限价"
- 这两个词是同义词

**结果**：即使LLM偶然看到"招标控制价"，也可能不知道应该提取到`maxPrice`字段。

---

## 解决方案

### 修复1：扩展检索关键词

**修改文件**：`backend/app/works/tender/extraction_specs/project_info_v2.py`

**修改前**：
```python
"base": "招标公告 项目名称 项目编号 预算金额 采购人 代理机构 投标截止 开标 时间 地点 联系人 电话",
```

**修改后**：
```python
"base": "招标公告 项目名称 项目编号 预算金额 招标控制价 最高限价 控制价 采购人 招标人 业主 代理机构 投标截止 开标时间 开标地点 联系人 电话 工期 质量标准",
```

**新增的关键词**：
- ✅ `招标控制价`（最重要！）
- ✅ `最高限价`
- ✅ `控制价`
- ✅ `招标人`（ownerName的另一个说法）
- ✅ `业主`（ownerName的另一个说法）
- ✅ `开标时间`（显式分开）
- ✅ `开标地点`（显式分开）
- ✅ `质量标准`（quality字段）

### 修复2：明确字段映射

**修改文件**：`backend/app/works/tender/prompts/project_info_v2.md`

**修改前**：
```json
"budget": "预算金额",
"maxPrice": "最高限价",
```

**修改后**：
```json
"budget": "预算金额/项目预算",
"maxPrice": "最高限价/招标控制价/控制价（注意：招标控制价=最高限价）",
```

**效果**：明确告诉LLM，这些术语是同义词，都应该提取到同一个字段。

---

## 测试验证

### 步骤1：重新提取基本信息

```bash
# 通过前端操作
1. 登录：admin/admin123
2. 进入"测试"项目
3. 点击"提取基本信息"按钮
4. 等待提取完成
```

### 步骤2：验证结果

查看数据库：
```sql
SELECT 
    data_json->'base'->>'maxPrice' as max_price,
    data_json->'base'->>'budget' as budget,
    data_json->'base'->>'bidOpeningTime' as opening_time,
    data_json->'base'->>'quality' as quality
FROM tender_project_info
WHERE project_id = 'tp_9160ce348db444e9b5a3fa4b66e8680a';
```

**预期结果**：
- `maxPrice`: "40199936.16元" 或 "40199936.16" ✅
- `budget`: 如果文档中有单独的预算字段 ✅
- `bidOpeningTime`: 如果文档中有明确的开标时间 ✅
- `quality`: 如果文档中有质量要求描述 ✅

---

## 总结

### 问题分类

这是一个**典型的信息检索问题**，不是索引问题：

1. ✅ 文档已正确索引（468个分片）
2. ✅ 提取逻辑正常工作
3. ❌ **检索关键词与文档术语不匹配**
4. ❌ **字段映射规则不明确**

### 核心教训

**在招投标领域，术语的多样性很高：**
- "招标人" = "采购人" = "业主"
- "招标控制价" = "最高限价" = "控制价"
- "投标截止时间" ≠ "开标时间"（两个不同的时间点）

**解决方案：**
1. **检索阶段**：使用尽可能多的同义词和相关词汇
2. **提取阶段**：明确告诉LLM字段的所有可能表述方式
3. **验证阶段**：检查文档中的实际用词，持续优化关键词库

---

## 后续改进建议

### 1. 建立招投标术语词典

创建一个`tender_terms.json`文件：
```json
{
  "ownerName": ["招标人", "采购人", "业主", "甲方"],
  "maxPrice": ["最高限价", "招标控制价", "控制价", "最高投标限价"],
  "budget": ["预算金额", "项目预算", "总预算", "资金总额"],
  ...
}
```

### 2. 动态扩展查询

根据术语词典自动生成查询：
```python
def expand_query(base_query: str, term_dict: dict) -> str:
    # 自动将同义词加入查询
    pass
```

### 3. 提取结果验证

添加字段完整性检查：
```python
def validate_extraction(result: dict) -> List[str]:
    """返回缺失的重要字段列表"""
    required_fields = ["projectName", "ownerName", "maxPrice", "bidDeadline"]
    missing = [f for f in required_fields if not result.get(f)]
    return missing
```

如果缺失关键字段，自动触发二次提取或提示用户。

---

## 联系与支持

如有问题，请联系开发团队。

**文档版本**：v1.0
**更新日期**：2025-12-25

