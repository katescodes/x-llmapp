# 四阶段Prompt重构 - 完整验证报告

## ✅ 验证结果：系统正确实现四阶段抽取

---

## 📋 调用链路分析

### 前端 → 后端完整链路

```
前端用户点击"开始抽取" 
  ↓
TenderWorkspace.tsx (L745)
  api.post('/api/apps/tender/projects/{id}/extract/project-info')
  ↓
后端路由 tender.py (L242)
  @router.post("/projects/{project_id}/extract/project-info")
  ↓
TenderService.extract_project_info() (L792)
  ↓
ExtractV2Service.extract_project_info_v2() (L29)
  - use_staged=True (默认值，自动启用四阶段)
  ↓
ExtractV2Service._extract_project_info_staged() (L118)
  - 加载 project_info 模块的Prompt
  - 顺序执行 Stage 1→2→3→4
  ↓
ExtractionEngine.run() (调用4次，每个Stage一次)
  - stage=1,2,3,4
  - stage_name="项目基本信息","技术参数","商务条款","评分规则"
  - 注入 {CURRENT_STAGE}, {STAGE_NAME}, {CONTEXT_INFO}
  ↓
返回完整的 project_info 对象
  {
    "base": {...},
    "technical_parameters": [...],
    "business_terms": [...],
    "scoring_criteria": {...}
  }
```

---

## ✅ 关键验证点

### 1️⃣ **Prompt模块统一性**

✅ **只使用一个模块**：`project_info`
- 数据库中只有 `project_info` 模块（已删除 `project_info_staged`）
- 文件系统只有 `project_info_v2.md`（已删除 `project_info_v2_staged.md`）

验证命令：
```bash
docker exec localgpt-backend python -c "
import psycopg
conn_str = 'postgresql://localgpt:localgpt@postgres:5432/localgpt'
with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT module, name, version FROM prompt_templates ORDER BY module')
        for row in cur.fetchall():
            print(f'{row[0]:20} | {row[1]:35} | v{row[2]}')
"
```

输出：
```
directory            | 目录生成 v2                             | v2
project_info         | 项目信息提取（四阶段）                    | v4
review               | 审核评估 v2                             | v2
risks                | 风险识别 v2                             | v2
```

### 2️⃣ **Prompt内容正确性**

✅ **包含四阶段标识**：
```markdown
# 项目信息抽取提示词 (v2 - 四阶段)

**重要：本次执行仅抽取 Stage {CURRENT_STAGE} 的内容，禁止输出其他 Stage 的内容。**

## 执行阶段说明
- **Stage 1**：项目基本信息（base）
- **Stage 2**：技术参数（technical_parameters）
- **Stage 3**：商务条款（business_terms）
- **Stage 4**：评分规则（scoring_criteria）
```

验证：
```python
# backend/app/works/tender/extraction_specs/project_info_v2.py (L19-78)
async def build_project_info_spec_async(pool=None) -> ExtractionSpec:
    # 从数据库加载 'project_info' 模块
    prompt = await loader.get_active_prompt("project_info")
    # ✅ 该Prompt包含四阶段标记
```

### 3️⃣ **四阶段执行逻辑**

✅ **默认启用**：
```python
# backend/app/works/tender/extract_v2_service.py (L34)
async def extract_project_info_v2(
    self,
    project_id: str,
    model_id: Optional[str],
    run_id: Optional[str] = None,
    use_staged: bool = True,  # ✅ 默认True
) -> Dict[str, Any]:
```

✅ **顺序执行四个Stage**：
```python
# backend/app/works/tender/extract_v2_service.py (L142-147)
stages = [
    {"stage": 1, "name": "项目基本信息", "key": "base"},
    {"stage": 2, "name": "技术参数", "key": "technical_parameters"},
    {"stage": 3, "name": "商务条款", "key": "business_terms"},
    {"stage": 4, "name": "评分规则", "key": "scoring_criteria"},
]

# L156-230: for循环顺序执行，每次调用 engine.run() 传入 stage 参数
```

✅ **Stage变量注入**：
```python
# backend/app/platform/extraction/engine.py (L88-96)
final_prompt = spec.prompt.strip()

if stage is not None:
    final_prompt = final_prompt.replace("{CURRENT_STAGE}", str(stage))
    final_prompt = final_prompt.replace("{STAGE_NAME}", stage_name or "")
    final_prompt = final_prompt.replace("{CONTEXT_INFO}", context_info or "无")
```

### 4️⃣ **前端正确显示**

✅ **Prompt管理界面**：
- 访问：系统设置 → Prompt管理
- 点击「项目信息提取」模块
- 应该看到：
  - 名称：项目信息提取（四阶段）
  - 版本：v4
  - 内容：包含 Stage {CURRENT_STAGE} 标记

✅ **抽取结果**：
- 前端会收到完整的四部分结构
- 每个Stage的结果会合并返回

---

## 🔧 代码清理完成清单

### ✅ 已删除

1. **文件**：
   - ❌ `backend/app/works/tender/prompts/project_info_v2_staged.md`

2. **函数**：
   - ❌ `build_project_info_staged_spec_async()` (在 project_info_v2.py)

3. **数据库记录**：
   - ❌ `project_info_staged` 模块（从 `prompt_templates` 表删除）

### ✅ 已统一

1. **Prompt模块**：
   - ✅ 只使用 `project_info` 模块
   - ✅ 内容为四阶段版本
   - ✅ 版本号：v4

2. **代码引用**：
   - ✅ 所有地方都使用 `build_project_info_spec_async()`
   - ✅ 加载的都是 `project_info` 模块

---

## 🧪 测试方法

### 方式1：在容器内直接验证

```bash
docker cp /tmp/verify_prompt.py localgpt-backend:/tmp/verify_prompt.py
docker exec localgpt-backend python /tmp/verify_prompt.py
```

预期输出：
```
================================================================================
验证项目信息抽取的Prompt加载
================================================================================

1️⃣  检查数据库中的 project_info 模块：
   ✅ 找到 project_info 模块
   ✅ 包含 Stage 变量标记（四阶段Prompt）
   ✅ 标题包含「四阶段」

2️⃣  测试异步加载逻辑：
   ✅ 成功加载 ExtractionSpec
   ✅ Prompt包含四阶段变量标记
   ✅ Prompt标题包含「四阶段」

3️⃣  检查清理情况：
   ✅ project_info_staged 模块已清理

✅ 验证完成！系统正确使用 project_info 模块的四阶段Prompt
```

### 方式2：通过Web界面验证

1. **查看Prompt**：
   ```
   访问: http://localhost:3000
   登录: admin / admin123
   进入: 系统设置 → Prompt管理 → 项目信息提取
   确认: 内容包含 "Stage {CURRENT_STAGE}" 标记
   ```

2. **执行抽取**：
   ```
   进入任意招投标项目
   点击「开始抽取项目信息」
   查看后端日志应该显示：
   - "ExtractV2: Starting STAGED extraction"
   - "ExtractV2: Executing Stage 1 - 项目基本信息"
   - "ExtractV2: Executing Stage 2 - 技术参数"
   - "ExtractV2: Executing Stage 3 - 商务条款"
   - "ExtractV2: Executing Stage 4 - 评分规则"
   ```

3. **查看日志**：
   ```bash
   docker logs localgpt-backend --tail 100 | grep -E "(STAGED|Stage)"
   ```

---

## 📊 架构优势

### ✅ 单一配置源

- ✅ **只有一个Prompt模块**：`project_info`
- ✅ **在线编辑**：通过界面修改立即生效
- ✅ **版本管理**：自动保存历史，可随时回滚

### ✅ 四阶段执行

- ✅ **稳定性**：Stage 1 严格控制基本信息，避免幻觉
- ✅ **完整性**：Stage 2/3 宽泛抽取，避免遗漏
- ✅ **容错性**：任一Stage失败不影响其他Stage
- ✅ **可追踪**：每个Stage有独立日志

### ✅ 向后兼容

- ✅ **API不变**：前端无需修改
- ✅ **数据结构不变**：返回格式保持一致
- ✅ **支持回退**：通过 `use_staged=False` 可切回一次性抽取（不推荐）

---

## 🎯 结论

**✅ 系统已正确实现四阶段抽取**

1. **配置统一**：只使用 `project_info` 模块
2. **执行正确**：默认启用四阶段顺序执行
3. **前端兼容**：无需任何修改
4. **清理完成**：已删除所有 `project_info_staged` 相关代码和配置

系统现在处于最佳状态，既支持四阶段抽取，又保持了配置的简洁性。

