# 招投标审核完整流程问题诊断报告

## 1. 数据完整性检查 ✅

测试2项目 (tp_259c05d1979e402db656a58a930467e2)：

| 数据项 | 状态 | 数量 |
|--------|------|------|
| 项目信息 | ✓ | 1个 |
| 招标文件 | ✓ | 1个 |
| 投标文件 | ✓ | 1个 |
| 招标要求 | ✓ | 69条 |
| 投标响应 | ✓ | 12条 |

**结论**：数据完整，不是数据缺失的问题。

## 2. 规则系统问题 ⚠️

### 问题1：缺少系统规则包

```sql
SELECT pack_type, COUNT(*) FROM tender_rule_packs GROUP BY pack_type;
```

结果：
- custom: 6个
- **system: 0个** ❌

**影响**：
- `ReviewV3Service.run_review_v3()` 默认调用 `build_effective_ruleset(include_system_defaults=True)`
- 但数据库中没有 `pack_type='system'` 的规则包
- 导致返回 0 条规则

### 问题2：字段不匹配

**tender_rules 表实际字段**：
- ✓ id, rule_pack_id, rule_key, rule_name
- ✓ dimension, evaluator, condition_json
- ✓ severity, is_hard, created_at

**代码期望的字段**：
- ❌ name → 实际是 `rule_name`
- ❌ description → 不存在
- ❌ priority → 不存在
- ❌ rule_type → 实际是 `evaluator`
- ❌ action_json → 不存在
- ❌ is_active → 不存在

**tender_rule_packs 表实际字段**：
- ✓ id, pack_name, pack_type, project_id
- ✓ priority, is_active, created_at, updated_at

**代码期望的字段**：
- ❌ name → 实际是 `pack_name`
- ❌ is_system_default → 不存在，应该用 `pack_type = 'system'`

## 3. 审核流程分析

### 当前流程（有问题）

```python
# ReviewV3Service.run_review_v3()

# 1. 读取招标要求 ✓
requirements = self._get_requirements(project_id)  # 返回69条

# 2. 读取投标响应 ✓
responses = self._get_responses(project_id, bidder_name)  # 返回12条

# 3. 构建规则集 ❌
effective_rules = self.ruleset_builder.build_effective_ruleset(
    project_id, 
    custom_rule_pack_ids=None  # ← 问题：没有传自定义规则包ID
)
# 查询：WHERE pack_type = 'system'  → 0条（数据库中没有system规则）
# 查询：WHERE project_id = xxx     → 0条（自定义规则包的project_id都是NULL）
# 结果：0条规则 ❌

# 4. 分离规则类型 ❌
deterministic_rules = [r for r in effective_rules if r.get("evaluator") == "deterministic"]
semantic_rules = [r for r in effective_rules if r.get("evaluator") == "semantic_llm"]
# 因为effective_rules=[], 所以都是空 ❌

# 5-6. 执行规则引擎 ❌
# 0条规则 → 0条结果

# 7. 返回 ❌
# {total_review_items: 0, pass_count: 0, fail_count: 0, ...}
```

### 正确流程（应该是）

```python
# 前端：用户在审核Tab选择自定义规则包
selectedRulePackIds = ['4ff8f82c-d188-4ac1-aaff-a7cf9090da28', ...]

# API调用
POST /api/apps/tender/projects/{project_id}/review/run
{
  "bidder_name": "123",
  "custom_rule_pack_ids": selectedRulePackIds  # ← 必须传！
}

# 后端：ReviewV3Service.run_review_v3()
effective_rules = self.ruleset_builder.build_effective_ruleset(
    project_id, 
    custom_rule_pack_ids=custom_rule_pack_ids  # ← 传入自定义规则包ID
)
# 查询：WHERE rp.id IN (custom_rule_pack_ids) → 返回规则 ✓
```

## 4. 核心问题总结

### 问题1：ReviewV3必须有规则才能审核

**现状**：
- 数据库没有系统规则包 (`pack_type='system'`)
- 自定义规则包的 `project_id=NULL`（共享规则包）
- 如果不传 `custom_rule_pack_ids`，审核会找不到任何规则

**解决方案A**：前端必须选择规则包（当前设计）
- 用户在审核Tab选择自定义规则包
- 传递 `custom_rule_pack_ids` 参数
- ✅ 符合当前数据模型

**解决方案B**：创建系统默认规则包
- 在数据库中插入 `pack_type='system'` 的规则包
- 添加一些默认规则
- 审核时自动加载系统规则
- ❌ 需要数据迁移和规则设计

### 问题2：字段名称不匹配已修复

已修复的SQL查询：
- ✓ `r.rule_name` 而不是 `r.name`
- ✓ `rp.pack_name` 而不是 `rp.name`
- ✓ `rp.pack_type = 'system'` 而不是 `rp.is_system_default`
- ✓ `r.evaluator` 而不是 `r.rule_type`

### 问题3：priority字段不存在已修复

修改前：
```python
effective_rules.sort(key=lambda r: r["priority"])  # ❌ KeyError
```

修改后：
```python
# 去重逻辑，不再排序
seen_keys = set()
effective_rules = []
for rule in all_rules:
    if rule["rule_key"] not in seen_keys:
        effective_rules.append(rule)
        seen_keys.add(rule["rule_key"])
```

## 5. 测试验证方案

### 测试1：不传规则包（当前会失败）

```bash
# 预期：0条规则，0条审核结果
curl -X POST http://localhost:8000/api/apps/tender/projects/tp_259c05d1979e402db656a58a930467e2/review/run \
  -H "Content-Type: application/json" \
  -d '{"bidder_name": "123", "custom_rule_pack_ids": null}'
```

### 测试2：传入规则包（应该成功）

```bash
# 1. 获取规则包ID
rule_pack_id=$(psql -U localgpt -d localgpt -tAc "SELECT id FROM tender_rule_packs LIMIT 1")

# 2. 调用审核API
curl -X POST http://localhost:8000/api/apps/tender/projects/tp_259c05d1979e402db656a58a930467e2/review/run \
  -H "Content-Type: application/json" \
  -d "{\"bidder_name\": \"123\", \"custom_rule_pack_ids\": [\"$rule_pack_id\"]}"
```

## 6. 推荐解决方案

### 方案：在审核时默认使用第一个可用规则包

修改 `ReviewV3Service.run_review_v3()`:

```python
async def run_review_v3(
    self,
    project_id: str,
    bidder_name: str,
    model_id: Optional[str] = None,
    custom_rule_pack_ids: Optional[List[str]] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    # ...
    
    # 3. 构建有效规则集
    # 如果没有传规则包ID，尝试使用所有激活的共享规则包
    if not custom_rule_pack_ids:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM tender_rule_packs 
                    WHERE project_id IS NULL 
                      AND is_active = true 
                      AND pack_type = 'custom'
                    ORDER BY priority DESC, created_at DESC
                """)
                rows = cur.fetchall()
                custom_rule_pack_ids = [row['id'] for row in rows]
                logger.info(f"ReviewV3: Auto-selected {len(custom_rule_pack_ids)} custom rule packs")
    
    effective_rules = self.ruleset_builder.build_effective_ruleset(
        project_id, 
        custom_rule_pack_ids=custom_rule_pack_ids
    )
    # ...
```

**优点**：
- ✅ 用户不选规则包也能审核
- ✅ 自动使用所有共享规则包
- ✅ 不需要数据迁移

**缺点**：
- ⚠️ 可能使用不相关的规则包
- ⚠️ 用户无法精确控制使用哪些规则

## 7. 前端UI改进建议

### 当前UI问题

审核Tab的规则包选择是**可选**的：
```
label: "可选：选择自定义规则包（可多选）"
```

但实际上，如果不选规则包，审核结果会是空的。

### 建议改进

1. **提示用户必须选择规则包**
   ```
   label: "选择自定义规则包（必选，可多选）"
   ```

2. **默认全选所有规则包**
   ```typescript
   useEffect(() => {
     if (rulePacks.length > 0 && selectedRulePackIds.length === 0) {
       setSelectedRulePackIds(rulePacks.map(p => p.id));
     }
   }, [rulePacks]);
   ```

3. **如果没有规则包，禁用审核按钮**
   ```typescript
   <button 
     onClick={runReview}
     disabled={reviewRun?.status === 'running' || selectedRulePackIds.length === 0}
   >
     开始审核
   </button>
   
   {selectedRulePackIds.length === 0 && (
     <div className="kb-doc-meta" style={{color: '#ef4444'}}>
       ⚠️ 请先选择至少一个规则包，否则无法进行审核
     </div>
   )}
   ```

## 8. 总结

### 根本原因

**ReviewV3 需要规则才能工作，但当前数据库中：**
1. 没有 `pack_type='system'` 的系统规则包
2. 自定义规则包都是共享的 (`project_id=NULL`)
3. 如果不传 `custom_rule_pack_ids`，审核找不到任何规则

### 立即修复方案

**选项1：后端自动加载所有共享规则包（推荐）✅**
- 修改 `ReviewV3Service.run_review_v3()`
- 如果 `custom_rule_pack_ids=None`，自动加载所有共享规则包
- 用户不选也能审核

**选项2：前端默认全选规则包**
- 修改 `TenderWorkspace.tsx`
- `rulePacks` 加载后自动全选
- 用户可以取消勾选不需要的

**选项3：前端强制必选规则包**
- 修改UI提示为"必选"
- 没有选择时禁用"开始审核"按钮
- 显示警告信息

### 长期改进

1. **创建系统默认规则包**
   - 设计通用的招投标审核规则
   - 插入到数据库中，`pack_type='system'`
   - 所有项目自动应用

2. **改进规则引擎**
   - 支持规则优先级
   - 支持规则冲突检测
   - 支持规则依赖关系

3. **改进审核结果**
   - 显示每条规则的匹配情况
   - 支持规则解释
   - 支持审核报告导出

