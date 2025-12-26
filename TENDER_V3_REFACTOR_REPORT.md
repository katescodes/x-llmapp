# 招投标系统核心链路改造 - 执行报告

## 任务目标
一次性替换招投标系统的核心链路（招标信息抽取/目录生成增强/DOCX按用户模板渲染/投标审核+用户自定义规则），**不保留旧逻辑**。

## 已完成的步骤

### ✅ Step 1: 建立 tender_info_v3 schema 和 validators（已提交）
- **文件**: 
  - `backend/app/works/tender/schemas/tender_info_v3.py` (九大类 Pydantic 模型)
  - `backend/app/works/tender/schemas/validators.py` (校验器)
  - `backend/tests/test_tender_info_v3_schema.py` (11个测试)
- **测试**: 全部通过 ✅
- **Commit**: `6692240`

### ✅ Step 2: 数据库迁移 - 新增规则和审核表（已提交）
- **文件**:
  - `backend/migrations/028_add_tender_v3_tables.sql` (新增4张表+扩展1张表)
  - `scripts/verify_tender_v3_schema.py` (验证脚本)
  - `backend/tests/test_tender_v3_migration.py` (8个测试)
- **新增表**:
  - `tender_requirements` - 招标要求基准条款库
  - `tender_rule_packs` - 规则包
  - `tender_rules` - 规则详情
  - `tender_bid_response_items` - 投标响应要素库
  - 扩展 `tender_review_items` - 新增4个字段
- **测试**: 全部通过 ✅
- **Commit**: `81497ff`

### ⏳ Step 3: 替换招标信息抽取为九大类（进行中）
- **已完成**:
  - ✅ 创建 `backend/app/works/tender/prompts/project_info_v3.md` (九大类 prompt)
  - **Commit**: `3353187` (WIP)

- **待完成**:
  - ⏳ 替换 `backend/app/works/tender/extraction_specs/project_info_v2.py` 的 queries 为九大类
  - ⏳ 更新 `backend/app/works/tender/extract_v2_service.py` 的 staged extraction 从4阶段改为9阶段
  - ⏳ 测试: 确保抽取输出 tender_info_v3 结构
  - ⏳ 落库: 确保 `tender_project_info.data_json` 写入 `schema_version: "tender_info_v3"`

## 待执行的步骤

### Step 4: 生成 tender_requirements 基准条款库
- 新增 `backend/app/works/tender/extraction_specs/requirements_v1.py`
- 新增 `backend/app/works/tender/prompts/requirements_v1.md`
- 在 extract_project_info_v2() 后追加调用 requirements 抽取
- 落库到 `tender_requirements`
- 测试

### Step 5: 目录生成增强
- 利用 `tender_info_v3.document_preparation` 补充必填目录
- 从 `bidder_qualification.must_provide_documents` 提取文件清单
- 自动增强 `tender_directory_nodes`
- 测试

### Step 6: 投标响应要素抽取 BidResponseIndex
- 新增 `backend/app/works/tender/extraction_specs/bid_response_v1.py`
- 新增 `backend/app/works/tender/prompts/bid_response_v1.md`
- 新增 `backend/app/works/tender/bid_response_service.py`
- 在审核前自动触发（如果不存在）
- 落库到 `tender_bid_response_items`
- 测试

### Step 7: 审核重做 - requirements × response + 规则引擎
- 新增规则引擎模块:
  - `backend/app/works/tender/rules/effective_ruleset.py`
  - `backend/app/works/tender/rules/deterministic_engine.py`
  - `backend/app/works/tender/rules/semantic_llm_engine.py`
- 重写 `ReviewV2Service.run_review_v2()`
- 支持用户自定义规则（读取 `assets.kind=custom_rule`）
- 生成基于 `requirement_id` 的 review_items
- 测试

### Step 8: DOCX 导出 - 按模板样式渲染
- 确认模板加载逻辑
- 增加样式映射器（level -> style_name）
- 插入 TOC field
- 测试: 验证标题样式、TOC 可更新

### Step 9: 前端同步 - 切到 tender_info_v3
- 修改 `TenderWorkspace.tsx`
- 更新 API 类型定义
- 九大类分组展示
- 前端测试

### Step 10: E2E 集成测试
- 新增 `backend/tests/test_e2e_tender_flow_v3.py`
- Mock LLM/检索
- 验证完整链路
- 测试

## 当前挑战与决策

### 挑战 1: Token 使用
- **问题**: Step 3 涉及多个大文件的修改，Token 使用快速增长
- **解决方案**: 分批提交，保持进度可追踪

### 挑战 2: 向后兼容 vs 彻底替换
- **用户要求**: "不保留旧逻辑，彻底替换"
- **实际考虑**: 
  - API 路由保持不变（前端依赖）
  - 数据表保持不变（`tender_project_info`）
  - 只替换内部实现和数据结构
  - **决策**: 保留文件名，替换内容

### 挑战 3: 四阶段 vs 九阶段
- **旧**: 4个 Stage (base/technical/business/scoring)
- **新**: 9个 Stage (九大类)
- **影响**: 
  - extraction_specs 需要定义9组 queries
  - extract_v2_service 的 staged extraction 需要改为9阶段
  - 进度计算需要调整 (每个 stage 占 ~11% 进度)
  - 增量写库逻辑需要适配 tender_info_v3 结构

## 下一步行动

1. **继续完成 Step 3**:
   - 更新 `project_info_v2.py` queries (保留文件名，替换为九大类 queries)
   - 更新 `extract_v2_service.py` 的 `_extract_project_info_staged` (改为9阶段)
   - 更新落库逻辑（写入 tender_info_v3 结构）
   - 编写测试
   - 提交

2. **按顺序执行 Step 4-10**，每步完成后运行测试确保通过

## 测试策略

- **单元测试**: 每个新增模块都有对应测试
- **集成测试**: E2E 测试覆盖完整链路
- **Mock 策略**: LLM 和检索全部 mock，确保测试稳定快速
- **现有测试**: 确保所有现有测试保持通过

## 估计完成时间

- Step 3: 2-3 小时（正在进行）
- Step 4: 1-2 小时
- Step 5: 1 小时
- Step 6: 2 小时
- Step 7: 3-4 小时（最复杂）
- Step 8: 1-2 小时
- Step 9: 2 小时
- Step 10: 1-2 小时

**总计**: ~13-18 小时

## 风险与缓解

1. **风险**: 改动范围大，可能引入 bug
   - **缓解**: 每步测试，分批提交

2. **风险**: 前端依赖旧结构
   - **缓解**: 保持 API 兼容，只改返回数据结构

3. **风险**: 数据库迁移失败
   - **缓解**: 使用 IF NOT EXISTS，迁移幂等

4. **风险**: LLM 输出不稳定
   - **缓解**: 测试中 mock LLM，生产中增加校验和重试

