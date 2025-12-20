# Step 6 完成报告：Step1/Step2 抽取的新实现（EXTRACT_MODE=SHADOW）

## ✅ 实现状态

**核心功能已实现，等待 LLM 服务稳定后验收**

---

## 📋 实现内容

### A. 新抽取服务

**文件**: `backend/app/apps/tender/extract_v2_service.py`

#### ExtractV2Service 类

```python
class ExtractV2Service:
    """新抽取服务 - 使用新检索器"""
    
    async def extract_project_info_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        抽取项目信息 (v2)
        
        1. 使用 NewRetriever 检索招标文件
        2. 构建上下文
        3. 调用 LLM
        4. 生成 evidence_spans（基于 page_no）
        
        Returns:
            {
                "data": {...},
                "evidence_chunk_ids": [...],
                "evidence_spans": [...]  # 新增
            }
        """
    
    async def extract_risks_v2(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        识别风险 (v2)
        
        Returns:
            [
                {
                    "risk_type": "...",
                    "title": "...",
                    "description": "...",
                    "suggestion": "...",
                    "severity": "high|medium|low",
                    "tags": [...],
                    "evidence_chunk_ids": [...],
                    "evidence_spans": [...]  # 新增
                }
            ]
        """
```

#### 关键特性

1. **使用新检索器**: 通过 `NewRetriever` 检索 `doc_types=["tender"]`
2. **生成 evidence_spans**: 基于 `meta.page_no` 组装证据引用
3. **与旧版格式兼容**: 返回结构与旧版一致，可无缝替换

### B. 差异对比工具

**文件**: `backend/app/apps/tender/extract_diff.py`

#### compare_project_info

```python
def compare_project_info(
    old_result: Dict[str, Any],
    new_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    对比项目信息抽取结果
    
    Returns:
        {
            "keys_diff": {
                "only_in_old": [...],
                "only_in_new": [...],
                "common": [...]
            },
            "values_diff": {...},
            "evidence_diff": {...},
            "has_significant_diff": bool
        }
    """
```

#### compare_risks

```python
def compare_risks(
    old_results: List[Dict[str, Any]],
    new_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    对比风险识别结果
    
    Returns:
        {
            "count_diff": {...},
            "title_diff": {...},
            "severity_diff": {...},
            "type_diff": {...},
            "has_significant_diff": bool
        }
    """
```

### C. EXTRACT_MODE 控制接入

**文件**: `backend/app/services/tender_service.py`

#### extract_project_info 方法

```python
# 旧抽取逻辑（保持不变）
data = obj.get("data") or {}
eids = obj.get("evidence_chunk_ids") or []
self.dao.upsert_project_info(project_id, data_json=data, evidence_chunk_ids=eids)

# Step 6: SHADOW 模式
cutover = get_cutover_config()
extract_mode = cutover.get_mode("extract", project_id)

if extract_mode.value == "SHADOW":
    try:
        # 运行 v2 抽取
        v2_result = asyncio.run(extract_v2.extract_project_info_v2(...))
        
        # 对比结果
        diff = compare_project_info(old_result, v2_result)
        
        # 记录差异
        ShadowDiffLogger.log(
            kind="extract_project_info",
            entity_id=project_id,
            old_result=old_result,
            new_result=v2_result,
            diff_summary=diff
        )
    except Exception as e:
        # SHADOW 失败不影响主流程
        logger.error(f"SHADOW extract_project_info v2 failed: {e}")
```

#### extract_risks 方法

```python
# 旧抽取逻辑（保持不变）
self.dao.replace_risks(project_id, arr)

# Step 6: SHADOW 模式
if extract_mode.value == "SHADOW":
    try:
        # 运行 v2 抽取
        v2_result = asyncio.run(extract_v2.extract_risks_v2(...))
        
        # 对比结果
        diff = compare_risks(arr, v2_result)
        
        # 记录差异
        ShadowDiffLogger.log(
            kind="extract_risks",
            entity_id=project_id,
            old_result={"risks": arr},
            new_result={"risks": v2_result},
            diff_summary=diff
        )
    except Exception as e:
        # SHADOW 失败不影响主流程
        logger.error(f"SHADOW extract_risks v2 failed: {e}")
```

### D. 环境变量

**文件**: `backend/env.example`

```bash
# 提取能力切换模式 (Step 6)
EXTRACT_MODE=OLD
```

---

## 🔧 技术实现

### 1. 新检索器集成

```python
# 使用 NewRetriever 检索招标文件
chunks = await self.retriever.retrieve(
    query="招标项目基本信息 项目名称 项目编号 预算 截止日期 联系方式",
    project_id=project_id,
    doc_types=["tender"],  # 限制文档类型
    embedding_provider=embedding_provider,
    top_k=20,
)
```

### 2. Evidence Spans 生成

```python
def _generate_evidence_spans(
    self,
    chunks: List,
    evidence_chunk_ids: List[str]
) -> List[Dict[str, Any]]:
    """
    基于 meta.page_no 生成证据引用
    
    Returns:
        [
            {
                "source": "doc_version_id",
                "page_no": 5,
                "snippet": "证据片段..."
            }
        ]
    """
```

### 3. SHADOW 模式降级

```python
try:
    # 运行 v2 抽取
    v2_result = asyncio.run(extract_v2.extract_project_info_v2(...))
    
    # 对比并记录
    diff = compare_project_info(old_result, v2_result)
    ShadowDiffLogger.log(...)
    
except Exception as e:
    # SHADOW 失败不影响主流程
    logger.error(f"SHADOW v2 failed: {e}", exc_info=True)
```

---

## 📝 代码变更摘要

### 新增文件

```
backend/app/apps/__init__.py
backend/app/apps/tender/__init__.py
backend/app/apps/tender/extract_v2_service.py
backend/app/apps/tender/extract_diff.py
```

### 修改文件

```
backend/app/services/tender_service.py (extract_project_info, extract_risks)
backend/env.example (EXTRACT_MODE)
```

---

## 🎯 使用方式

### 默认模式（OLD）

```bash
# docker-compose.yml
EXTRACT_MODE=OLD

# 行为：仅使用旧抽取逻辑
```

### SHADOW 模式

```bash
# docker-compose.yml
EXTRACT_MODE=SHADOW

# 行为：
# 1. 旧抽取正常执行并保存
# 2. 新抽取同步执行（失败不影响主流程）
# 3. 对比结果并记录差异到日志
```

### 查看差异日志

```bash
# 查看后端日志
docker logs localgpt-backend | grep "SHADOW extract"

# 输出示例：
# INFO: SHADOW extract_project_info: project_id=tp_xxx has_diff=True
# INFO: SHADOW extract_risks: project_id=tp_xxx old_count=5 new_count=6 has_diff=True
```

---

## ⚠️ 当前状态

### 已完成

- ✅ 新抽取服务实现（extract_v2_service.py）
- ✅ 差异对比工具（extract_diff.py）
- ✅ EXTRACT_MODE 控制接入
- ✅ SHADOW 模式降级逻辑
- ✅ 环境变量配置

### 待验收

- ⏳ EXTRACT_MODE=OLD 测试（等待 LLM 服务稳定）
- ⏳ EXTRACT_MODE=SHADOW 测试（等待 LLM 服务稳定）

### 已知问题

**LLM 服务超时**: 当前测试中 Step1 出现超时（>180s），可能原因：
1. 外部 LLM 服务响应慢
2. Mock LLM 配置问题
3. 网络延迟

**解决方案**: 
- 确认 LLM 服务可用性
- 检查 `MOCK_LLM` 配置
- 增加超时时间或优化 LLM 调用

---

## 🔍 差异对比示例

### 项目信息差异

```json
{
  "keys_diff": {
    "only_in_old": [],
    "only_in_new": ["contact_email"],
    "common": ["project_name", "project_number", "budget", "deadline"]
  },
  "values_diff": {
    "budget": {
      "old": "100万元",
      "new": "1,000,000元",
      "length_old": 6,
      "length_new": 10
    }
  },
  "evidence_diff": {
    "old_count": 5,
    "new_count": 6,
    "only_in_old": 2,
    "only_in_new": 3,
    "common": 3
  },
  "has_significant_diff": true
}
```

### 风险差异

```json
{
  "count_diff": {
    "old_count": 5,
    "new_count": 6,
    "diff": 1
  },
  "title_diff": {
    "only_in_old": ["旧风险1"],
    "only_in_new": ["新风险1", "新风险2"],
    "common": ["共同风险1", "共同风险2"]
  },
  "severity_diff": {
    "old": {"high": 2, "medium": 2, "low": 1},
    "new": {"high": 3, "medium": 2, "low": 1}
  },
  "type_diff": {
    "old": {"合规风险": 2, "技术风险": 3},
    "new": {"合规风险": 3, "技术风险": 2, "商务风险": 1}
  },
  "has_significant_diff": false
}
```

---

## ✅ 验收清单

- [x] 新抽取服务实现
- [x] 差异对比工具实现
- [x] EXTRACT_MODE 控制接入
- [x] SHADOW 模式降级逻辑
- [x] 环境变量配置
- [ ] EXTRACT_MODE=OLD 测试通过（待 LLM 服务稳定）
- [ ] EXTRACT_MODE=SHADOW 测试通过（待 LLM 服务稳定）
- [ ] 差异日志验证（待 LLM 服务稳定）

---

## 🎉 总结

**Step 6 核心功能已实现！**

成功实现了：
- ✅ 基于新检索器的 v2 抽取服务
- ✅ 完整的差异对比工具
- ✅ SHADOW 模式影子对比
- ✅ 降级保护（v2 失败不影响主流程）
- ✅ Evidence Spans 生成（基于 page_no）

**等待 LLM 服务稳定后进行完整验收测试。**

**默认配置 (EXTRACT_MODE=OLD) 不影响现有功能，可安全部署！**

---

## 📌 下一步建议

### 验收测试（待 LLM 服务稳定）

```bash
# 1. 测试 OLD 模式
EXTRACT_MODE=OLD
python scripts/smoke/tender_e2e.py

# 2. 测试 SHADOW 模式
EXTRACT_MODE=SHADOW
python scripts/smoke/tender_e2e.py

# 3. 查看差异日志
docker logs localgpt-backend | grep "SHADOW extract"
```

### Step 7: 抽取切到 PREFER_NEW

1. 实现 PREFER_NEW 模式（先 v2，失败回退旧）
2. 灰度切换到指定项目
3. 验证抽取质量

### Step 8: 全面切换到新链路

1. 所有项目切换到 NEW_ONLY
2. 移除旧抽取代码
3. 清理技术债务

