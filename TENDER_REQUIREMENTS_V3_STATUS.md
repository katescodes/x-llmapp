# 📊 Tender Requirements V3 实现状态报告

## ✅ **实现概况**

`tender_requirements` 表和 `is_hard` 字段已完整实现，包括：
- ✅ 数据库表结构
- ✅ 数据抽取逻辑
- ✅ Prompt 模板
- ✅ 自动写入数据库

---

## 📋 **数据库表结构**

### **表名**: `tender_requirements`

```sql
CREATE TABLE IF NOT EXISTS tender_requirements (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES tender_projects(id) ON DELETE CASCADE,
  requirement_id TEXT NOT NULL,                      -- 要求ID（业务唯一标识，如 qual_001）
  dimension TEXT NOT NULL,                           -- 维度（qualification/technical/business/price/doc_structure/schedule_quality/other）
  req_type TEXT NOT NULL,                            -- 要求类型（threshold/must_provide/must_not_deviate/scoring/format/other）
  requirement_text TEXT NOT NULL,                    -- 要求内容（逐字复制原文）
  is_hard BOOLEAN NOT NULL DEFAULT false,            -- ✅ 是否硬性要求（不满足则废标/扣分）
  allow_deviation BOOLEAN NOT NULL DEFAULT false,    -- 是否允许偏离
  value_schema_json JSONB,                           -- 值约束（如 {min:50, max:100, unit:"万元"}）
  evidence_chunk_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],  -- 证据chunk IDs
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### **索引**:
```sql
CREATE INDEX idx_tender_requirements_project ON tender_requirements(project_id);
CREATE INDEX idx_tender_requirements_dimension ON tender_requirements(dimension);
CREATE INDEX idx_tender_requirements_req_id ON tender_requirements(requirement_id);
CREATE INDEX idx_tender_requirements_project_dimension ON tender_requirements(project_id, dimension);
```

---

## 🔧 **实现细节**

### **1. 迁移文件**
- **文件**: `backend/migrations/028_add_tender_v3_tables.sql`
- **状态**: ✅ 已创建
- **包含**: 
  - `tender_requirements` 表定义
  - `is_hard` 字段（BOOLEAN NOT NULL DEFAULT false）
  - 完整索引
  - 表和字段注释

### **2. 抽取规格**
- **文件**: `backend/app/works/tender/extraction_specs/requirements_v1.py`
- **功能**:
  - 定义 8 个维度的检索查询
  - 支持数据库/文件双重 Prompt 加载
  - 可配置 top_k 参数

**查询维度**:
```python
queries = {
    "qualification": "投标人资格 资格要求 资质要求...",
    "technical": "技术要求 技术规范 技术标准...",
    "business": "商务要求 合同条款 付款方式...",
    "price": "投标报价 报价要求 最高限价...",
    "doc_structure": "投标文件 文件编制 格式要求...",
    "schedule_quality": "工期要求 施工周期 交付期限...",
    "evaluation": "评分标准 评分细则 得分规则...",
    "other": "应当 必须 须 不得 禁止...",
}
```

### **3. Prompt 模板**
- **文件**: `backend/app/works/tender/prompts/requirements_v1.md`
- **长度**: 313 行
- **内容**:
  - 完整的 JSON 输出结构定义
  - 详细的字段说明（包括 `is_hard`）
  - 5 个完整示例
  - 抽取原则和判断标准

**is_hard 判断标准**（Prompt 第 96-98 行）:
```markdown
### is_hard（必填）
- `true` - 硬性要求（不满足则废标/扣分/不得分）
- `false` - 软性要求（可协商/可说明）
```

**判断准确性原则**（Prompt 第 140-143 行）:
```markdown
### 4. 判断准确性
- is_hard：看是否有"废标"、"不得分"、"扣分"等后果
- allow_deviation：看是否有"不得偏离"、"严格执行"等表述
- req_type：根据要求性质选择最匹配的类型
```

### **4. 抽取服务**
- **文件**: `backend/app/works/tender/extract_v2_service.py`
- **方法**: `extract_requirements_v1()`
- **位置**: 第 367-465 行

**核心逻辑**:
```python
async def extract_requirements_v1(self, project_id, model_id, run_id):
    # 1. 构建 spec（包含 8 维度查询）
    spec = await build_requirements_spec_async(self.pool)
    
    # 2. 调用 ExtractionEngine（检索 + LLM）
    result = await self.engine.run(spec, ...)
    
    # 3. 解析 LLM 返回的 JSON
    requirements = result.data.get("requirements", [])
    
    # 4. 写入数据库
    for req in requirements:
        cur.execute("""
            INSERT INTO tender_requirements (
                id, project_id, requirement_id, dimension, req_type,
                requirement_text, is_hard, allow_deviation, 
                value_schema_json, evidence_chunk_ids
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(uuid.uuid4()),
            project_id,
            req.get("requirement_id"),
            req.get("dimension"),
            req.get("req_type"),
            req.get("requirement_text"),
            req.get("is_hard", False),  # ✅ 从 LLM 返回中提取
            req.get("allow_deviation", False),
            req.get("value_schema_json"),
            req.get("evidence_chunk_ids", []),
        ))
```

### **5. 集成到主流程**
- **位置**: `extract_v2_service.py` 第 271-286 行
- **触发时机**: 项目信息抽取（V3）完成后自动执行
- **进度显示**: "正在生成招标要求基准条款库..."

```python
# ✅ Step 2.1: 追加调用 requirements 抽取（基准条款库）
try:
    logger.info(f"ExtractV2: Starting requirements extraction for project={project_id}")
    if run_id:
        self.dao.update_run(run_id, "running", progress=0.95, 
                          message="正在生成招标要求基准条款库...")
    
    requirements = await self.extract_requirements_v1(
        project_id=project_id,
        model_id=model_id,
        run_id=None,
    )
    
    logger.info(f"ExtractV2: Requirements extraction done - count={len(requirements)}")
except Exception as e:
    logger.error(f"ExtractV2: Requirements extraction failed: {e}", exc_info=True)
    # 不影响主流程，继续返回
```

---

## 📊 **数据结构示例**

### **示例 1: 资格要求（硬性）**
```json
{
  "requirement_id": "qual_001",
  "dimension": "qualification",
  "req_type": "must_provide",
  "requirement_text": "投标人须具有有效的营业执照、建筑工程施工总承包壹级及以上资质",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": null,
  "evidence_chunk_ids": ["CHUNK_123"]
}
```

### **示例 2: 技术要求（硬性 + 值约束）**
```json
{
  "requirement_id": "tech_001",
  "dimension": "technical",
  "req_type": "threshold",
  "requirement_text": "服务器CPU频率不低于2.5GHz",
  "is_hard": true,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "number",
    "min": 2.5,
    "unit": "GHz",
    "comparison": ">="
  },
  "evidence_chunk_ids": ["CHUNK_456"]
}
```

### **示例 3: 评分要求（软性）**
```json
{
  "requirement_id": "eval_001",
  "dimension": "qualification",
  "req_type": "scoring",
  "requirement_text": "企业资质评分：具有壹级资质得10分，贰级资质得6分",
  "is_hard": false,
  "allow_deviation": false,
  "value_schema_json": {
    "type": "enum",
    "enum": ["壹级资质:10分", "贰级资质:6分", "叁级资质:3分"]
  },
  "evidence_chunk_ids": ["CHUNK_789"]
}
```

---

## 🎯 **is_hard 字段的作用**

### **在审核流程中的用途**:

1. **确定性规则引擎**:
   - `is_hard=true` → 不满足则标记为 `fail` 或 `risk`
   - `is_hard=false` → 不满足则标记为 `warning`

2. **LLM 语义判断**:
   - 提示 LLM 关注硬性要求的严格性
   - 硬性要求的判断结果权重更高

3. **用户界面展示**:
   - 硬性要求用红色/高亮显示
   - 软性要求用黄色/次要样式

4. **报告生成**:
   - 硬性要求不满足 → 重点标注
   - 软性要求不满足 → 建议改进

---

## 🔍 **验证方法**

### **1. 检查数据库表**
```sql
-- 检查表是否存在
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_name = 'tender_requirements'
);

-- 检查字段
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'tender_requirements'
AND column_name IN ('is_hard', 'allow_deviation', 'value_schema_json');
```

### **2. 检查数据**
```sql
-- 统计数据
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN is_hard THEN 1 END) as hard_count,
    COUNT(CASE WHEN allow_deviation THEN 1 END) as allow_deviation_count,
    COUNT(CASE WHEN value_schema_json IS NOT NULL THEN 1 END) as with_schema_count
FROM tender_requirements;

-- 查看示例
SELECT 
    requirement_id, 
    dimension, 
    req_type, 
    LEFT(requirement_text, 50) as text_preview,
    is_hard,
    allow_deviation
FROM tender_requirements
LIMIT 10;
```

### **3. 测试抽取流程**
1. 创建新项目
2. 上传招标文件
3. 执行 "Step 1: 项目信息抽取"
4. 观察进度显示 "正在生成招标要求基准条款库..."
5. 检查数据库 `tender_requirements` 表是否有新数据

---

## ⚠️ **注意事项**

### **1. 数据库迁移**
- 需要执行 `028_add_tender_v3_tables.sql`
- 如果表已存在，检查是否有 `is_hard` 字段

### **2. Prompt 可用性**
- 优先从数据库加载 `requirements_v1` prompt
- 如果数据库中没有，fallback 到文件
- 确保 prompt 已通过 `scripts/init_v3_prompts.sql` 导入

### **3. LLM 输出质量**
- `is_hard` 判断依赖 LLM 理解
- 建议使用高质量模型（如 GPT-4）
- 可能需要人工审核和调整

### **4. 性能考虑**
- requirements 抽取在项目信息抽取之后
- 不影响主流程（即使失败也会继续）
- 大型招标文件可能产生 50-200 条 requirements

---

## 📈 **预期数据量**

根据 Prompt 设计：
- **小型项目**: 20-50 条 requirements
- **中型项目**: 50-100 条 requirements
- **大型项目**: 100-200 条 requirements

**is_hard 分布**（估算）:
- 硬性要求: 30-50%（资格、技术阈值、价格限制）
- 软性要求: 50-70%（评分标准、格式要求、可协商条款）

---

## ✅ **结论**

**V3 已完整实现 `tender_requirements` 表和 `is_hard` 字段**，包括：

1. ✅ 数据库表结构完整（包含 `is_hard` BOOLEAN 字段）
2. ✅ 抽取逻辑已实现（`extract_requirements_v1`）
3. ✅ Prompt 模板完整（313 行，包含 `is_hard` 判断标准）
4. ✅ 自动集成到项目信息抽取流程
5. ✅ 数据自动写入数据库（包含 `is_hard` 值）

**下一步**:
- 执行数据库迁移（如果尚未执行）
- 导入 V3 prompts 到数据库
- 测试完整抽取流程
- 验证 `is_hard` 字段的准确性

---

**文档生成时间**: 2025-12-26  
**相关文件**:
- `backend/migrations/028_add_tender_v3_tables.sql`
- `backend/app/works/tender/extract_v2_service.py`
- `backend/app/works/tender/extraction_specs/requirements_v1.py`
- `backend/app/works/tender/prompts/requirements_v1.md`

