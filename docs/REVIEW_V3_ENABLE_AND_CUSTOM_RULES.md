# ReviewV3 启用和自定义规则包支持

## 问题描述
用户反馈：在"测试2"项目进行投标文件审核时，选择了自定义规则包，但审核结果中没有出现自定义规则的比对信息。

## 根本原因
系统当前使用的是 **ReviewV2Service**（基于RAG检索的审核），它**不支持自定义规则包**。

ReviewV3Service 才支持规则引擎和自定义规则包，但因缺少 `tender_bid_response_items` 数据而未被启用。

## 解决方案
采用**方案B：启用ReviewV3（完整方案）**

### 1. 架构对比

| 特性 | ReviewV2 (旧) | ReviewV3 (新) |
|------|---------------|---------------|
| **审核方式** | RAG检索+LLM直接对比 | 结构化数据+规则引擎 |
| **数据源** | 文档片段 (chunks) | requirements + responses |
| **规则支持** | ❌ 不支持 | ✅ 完整支持 |
| **规则引擎** | 无 | 确定性引擎 + 语义LLM引擎 |
| **自定义规则包** | ❌ 不支持 | ✅ 完整支持 |
| **前置条件** | 仅需上传文档 | 需抽取 requirements + responses |

### 2. ReviewV3 工作流程

```
1. 读取招标要求 (tender_requirements)
2. 读取投标响应 (tender_bid_response_items)  
3. 构建有效规则集:
   - 系统内置规则 (is_system_default=true)
   - 项目自定义规则 (project_id匹配)
   - 用户选择的自定义规则包 (custom_rule_pack_ids)
4. 应用确定性规则引擎 (DeterministicRuleEngine)
5. 应用语义LLM规则引擎 (SemanticLLMRuleEngine)
6. 生成审核结果 (tender_review_items)
```

### 3. 实施的修改

#### 3.1 添加投标响应抽取 API
**文件**: `backend/app/routers/tender.py`

添加新的 API 端点用于抽取投标响应数据：

```python
@router.post("/projects/{project_id}/extract-bid-responses")
async def extract_bid_responses(
    project_id: str,
    bidder_name: str,
    request: Request,
    user=Depends(get_current_user_sync),
):
    """
    抽取投标响应要素 (for V3 review)
    
    Args:
        bidder_name: 投标人名称
    """
    # 使用 BidResponseService 抽取结构化响应数据
    service = BidResponseService(pool, engine, retriever, llm)
    result = await service.extract_bid_response_v1(...)
    return result
```

#### 3.2 修改 ReviewV3Service 支持自定义规则包
**文件**: `backend/app/works/tender/review_v3_service.py`

添加 `custom_rule_pack_ids` 参数：

```python
async def run_review_v3(
    self,
    project_id: str,
    bidder_name: str,
    model_id: Optional[str] = None,
    custom_rule_pack_ids: Optional[List[str]] = None,  # 新增
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    # 构建有效规则集时传递 custom_rule_pack_ids
    effective_rules = self.ruleset_builder.build_effective_ruleset(
        project_id, 
        custom_rule_pack_ids=custom_rule_pack_ids
    )
```

#### 3.3 修改 EffectiveRulesetBuilder 加载自定义规则包
**文件**: `backend/app/works/tender/rules/effective_ruleset.py`

扩展规则集构建逻辑：

```python
def build_effective_ruleset(
    self,
    project_id: str,
    include_system_defaults: bool = True,
    include_project_rules: bool = True,
    custom_rule_pack_ids: Optional[List[str]] = None,  # 新增
) -> List[Dict[str, Any]]:
    all_rules = []
    
    # 1. 加载系统内置规则
    if include_system_defaults:
        # 查询 is_system_default=true 的规则包
        ...
    
    # 2. 加载项目级自定义规则
    if include_project_rules:
        # 查询 project_id 匹配的规则包
        ...
    
    # 3. 加载用户选择的自定义规则包 (新增)
    if custom_rule_pack_ids:
        # 查询 rule_pack_id IN (custom_rule_pack_ids) 的规则
        placeholders = ','.join(['%s'] * len(custom_rule_pack_ids))
        cur.execute(f"""
            SELECT r.id, r.rule_key, r.name, ...
            FROM tender_rules r
            JOIN tender_rule_packs rp ON r.rule_pack_id = rp.id
            WHERE rp.id IN ({placeholders})
              AND r.is_active = true
        """, tuple(custom_rule_pack_ids))
        
        for row in custom_rules:
            all_rules.append({
                ...
                "source": "user_selected_custom"
            })
    
    # 4. 去重：优先级 user_selected_custom > project_custom > system_default
    effective_rules = self._deduplicate_by_rule_key(all_rules)
    
    return effective_rules
```

**去重策略**：
- 按 `rule_key` 去重
- 优先级：`user_selected_custom` (3) > `project_custom` (2) > `system_default` (1)
- 保留优先级最高的规则

#### 3.4 切换 TenderService 使用 ReviewV3
**文件**: `backend/app/services/tender_service.py`

```python
def run_review(
    self,
    project_id: str,
    model_id: Optional[str],
    custom_rule_asset_ids: List[str],
    bidder_name: Optional[str],
    bid_asset_ids: List[str],
    custom_rule_pack_ids: Optional[List[str]] = None,  # 新增
    run_id: Optional[str] = None,
    owner_id: Optional[str] = None,
):
    # 使用 ReviewV3Service (替换原来的 ReviewV2Service)
    from app.works.tender.review_v3_service import ReviewV3Service
    
    review_v3 = ReviewV3Service(pool, self.llm)
    v3_results = asyncio.run(review_v3.run_review_v3(
        project_id=project_id,
        bidder_name=bidder_name,
        model_id=model_id,
        custom_rule_pack_ids=custom_rule_pack_ids,  # 传递自定义规则包
        run_id=run_id
    ))
```

#### 3.5 修改 API 路由传递参数
**文件**: `backend/app/routers/tender.py`

```python
@router.post("/projects/{project_id}/review/run")
def run_review(...):
    def job():
        svc.run_review(
            project_id,
            req.model_id,
            req.custom_rule_asset_ids,
            req.bidder_name,
            req.bid_asset_ids,
            custom_rule_pack_ids=req.custom_rule_pack_ids,  # 新增
            run_id=run_id,
            owner_id=owner_id,
        )
```

### 4. 使用前提条件

**⚠️ 重要**：在使用 ReviewV3 和自定义规则包之前，必须先抽取投标响应数据！

#### 方法1：通过 API 抽取（推荐）

```bash
curl -X POST "http://localhost:8000/api/apps/tender/projects/{project_id}/extract-bid-responses?bidder_name=投标人名称" \
  -H "Authorization: Bearer {token}"
```

#### 方法2：通过前端界面
后续可在前端添加"抽取投标响应"按钮，调用上述 API。

### 5. 数据表说明

#### tender_requirements (招标要求)
- 从招标文件抽取的结构化要求
- 字段：requirement_id, dimension, req_type, requirement_text, is_hard, etc.
- 示例：测试4项目有 69 条招标要求

#### tender_bid_response_items (投标响应)
- 从投标文件抽取的结构化响应
- 字段：bidder_name, dimension, response_type, response_text, extracted_value_json, etc.
- **当前状态**：测试4项目为空，需要先抽取

#### tender_rule_packs (规则包)
- 包类型：`builtin` (系统内置), `custom` (用户自定义)
- `project_id IS NULL` 表示共享规则包
- `is_system_default` 标识系统默认规则包

#### tender_rules (规则)
- 规则类型：`deterministic` (确定性), `semantic_llm` (语义LLM)
- `rule_key`: 规则键，用于去重和覆盖
- `condition_json`: 规则条件 (DSL)
- `action_json`: 规则动作

### 6. 测试流程

#### 步骤1：抽取投标响应数据
```bash
# 为测试4项目抽取投标响应（投标人：123）
curl -X POST "http://localhost:8000/api/apps/tender/projects/tp_3f49f66ead6d46e1bac3f0bd16a3efe9/extract-bid-responses?bidder_name=123" \
  -H "Authorization: Bearer {token}"
```

#### 步骤2：创建自定义规则包
在前端"自定义规则"页面创建规则包并添加规则。

#### 步骤3：运行审核
在审核界面：
1. 选择投标人：123
2. 勾选自定义规则包
3. 点击"开始审核"

#### 步骤4：查看审核结果
审核结果应包含：
- 系统内置规则的审核项
- 自定义规则包的审核项
- 每个审核项显示规则来源 (source: system_default / user_selected_custom)

### 7. 优势

#### ReviewV3 优势
1. **规则可追溯**：每个审核项关联具体规则 (`rule_id`)
2. **规则可配置**：支持确定性规则和语义LLM规则
3. **规则可覆盖**：用户选择 > 项目级 > 系统级
4. **结构化数据**：基于结构化的 requirements 和 responses
5. **支持自定义规则包**：用户可创建和共享规则包

#### 自定义规则包优势
1. **共享性**：`project_id IS NULL` 的规则包跨项目共享
2. **灵活性**：审核时动态选择需要的规则包
3. **可组合**：可同时选择多个规则包
4. **优先级**：用户选择的规则优先于系统默认规则

### 8. 注意事项

1. **数据依赖**：ReviewV3 需要 `tender_requirements` 和 `tender_bid_response_items` 数据
2. **抽取耗时**：投标响应抽取可能需要较长时间（取决于文档量和LLM速度）
3. **模型要求**：语义LLM规则需要LLM模型支持
4. **规则设计**：规则的 `condition_json` 和 `action_json` 需要遵循特定DSL格式

### 9. 后续优化建议

1. **前端集成**：
   - 添加"抽取投标响应"按钮
   - 显示抽取进度和状态
   - 展示已抽取的响应数据

2. **规则编辑器**：
   - 可视化规则编辑界面
   - 规则模板库
   - 规则测试工具

3. **性能优化**：
   - 批量抽取多个投标人
   - 缓存抽取结果
   - 异步抽取+通知

4. **规则库**：
   - 内置规则包（常见招投标规则）
   - 行业规则包（建筑、IT、政府采购等）
   - 规则分享和导入导出

## 修改文件清单

1. `backend/app/routers/tender.py`
   - 添加 `/projects/{project_id}/extract-bid-responses` API
   - 修改 `/projects/{project_id}/review/run` 传递 `custom_rule_pack_ids`

2. `backend/app/works/tender/review_v3_service.py`
   - `run_review_v3` 添加 `custom_rule_pack_ids` 参数

3. `backend/app/works/tender/rules/effective_ruleset.py`
   - `build_effective_ruleset` 添加 `custom_rule_pack_ids` 参数
   - 实现加载和合并自定义规则包逻辑
   - 更新去重策略支持三级优先级

4. `backend/app/services/tender_service.py`
   - `run_review` 添加 `custom_rule_pack_ids` 参数
   - 切换使用 `ReviewV3Service` 替代 `ReviewV2Service`

## 部署

```bash
# 重启后端服务
docker-compose restart backend

# 查看日志
docker logs -f localgpt-backend
```

## 日期
2025-12-28

