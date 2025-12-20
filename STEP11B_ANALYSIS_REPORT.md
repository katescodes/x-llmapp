# Step 11B: 删除旧实现代码 - 现状分析

## 执行时间
2025-12-20

## 分析结果

### 当前状态

经过扫描，发现以下旧代码仍然存在：

#### 1. `tender_service.py` - extract_risks 方法
**位置**: 行 895-1113

**包含的旧模式**:
- `PREFER_NEW` 模式（行 992-1025）：先尝试 v2，失败回退旧逻辑
- 旧逻辑实现（行 1028-1052）：`_load_context_by_assets` + LLM 调用
- `SHADOW` 模式（行 1055-1092）：旧逻辑 + v2 对比

**风险评估**: 🟡 中等
- `NEW_ONLY` 路径已正确实现（行 927-989）
- 但其他模式代码仍存在，占用约 120 行
- 当前环境变量设置为 `EXTRACT_MODE=NEW_ONLY`，旧代码不会被执行

#### 2. `tender_service.py` - extract_project_info 方法
**位置**: 行 792-893

**状态**: ✅ 已清理
- 只有 NEW_ONLY 路径
- 非 NEW_ONLY 模式会抛出明确错误（行 810-815）
- 可作为清理的参考模板

#### 3. `services/semantic_outline`
**位置**: `backend/app/services/semantic_outline/`

**检查状态**: 需要验证
- 代码已迁移到 `works/tender/outline/`
- 需要检查是否还有其他地方在使用
- 如果没有引用，可以删除

#### 4. kb_documents/kb_chunks 写入
**位置**: 多处可能存在

**检查状态**: 需要全面扫描
- NEW_ONLY 模式不应写入旧的 kb 表
- 需要检查所有写入路径
- 已有测试: `test_newonly_never_writes_kb.py`

### 风险分析

#### 高风险操作（需要慎重）
1. **直接删除大段代码**: 可能影响回滚能力
2. **删除未充分测试的分支**: 可能有隐藏依赖

#### 低风险操作（可以执行）
1. **添加强制模式检查**: 在方法开头检查模式，非 NEW_ONLY 抛错
2. **注释旧代码**: 保留代码但添加 DEPRECATED 标记
3. **删除明确不再使用的模块**: 如 semantic_outline（需要验证）

## 推荐方案

### 方案 A: 保守方案（推荐）

**Step 1**: 在 extract_risks 开头添加强制检查
```python
def extract_risks(...):
    """识别风险 - REMOVED: Only NEW_ONLY mode supported"""
    # 强制检查模式
    from app.core.cutover import get_cutover_config
    cutover = get_cutover_config()
    extract_mode = cutover.get_mode("extract", project_id)
    
    if extract_mode.value != "NEW_ONLY":
        raise RuntimeError(
            f"[REMOVED] Legacy tender extraction deleted. "
            f"EXTRACT_MODE={extract_mode.value} is no longer supported. "
            f"Set EXTRACT_MODE=NEW_ONLY. Method: extract_risks"
        )
    
    # 只保留 NEW_ONLY 分支代码...
```

**Step 2**: 将旧逻辑代码块移到文档或单独文件
- 创建 `backend/docs/removed_code/extract_risks_old.py.txt`
- 保存旧代码供紧急回滚使用

**Step 3**: 删除 PREFER_NEW、SHADOW、OLD 分支

**优点**:
- 可以回滚（代码已备份）
- 清晰的错误提示
- 代码库更清爽

**缺点**:
- 需要两次提交（备份 + 删除）

### 方案 B: 渐进方案

**Phase 1**: 注释旧代码，添加 DEPRECATED
```python
# DEPRECATED: PREFER_NEW mode removed, only NEW_ONLY supported
# elif extract_mode.value == "PREFER_NEW":
#     ... (保留注释的代码)
```

**Phase 2**: 监控生产环境 1-2 周

**Phase 3**: 确认无问题后永久删除

**优点**:
- 最安全
- 容易回滚

**缺点**:
- 需要更长时间
- 注释的代码影响可读性

### 方案 C: 激进方案（不推荐）

**直接删除所有旧代码**

**风险**:
- 如果发现问题，回滚困难
- 可能影响还在使用旧模式的环境

## 建议执行顺序

### 立即可执行
1. ✅ 在所有 extract 方法开头添加强制模式检查
2. ✅ 删除明显不再使用的代码分支
3. ✅ 更新文档标记哪些模式已废弃

### 需要验证后执行
1. 🔍 检查 `services/semantic_outline` 是否还有引用
2. 🔍 扫描所有 kb_documents/kb_chunks 写入点
3. 🔍 验证前端不再调用旧接口

### 谨慎执行
1. ⚠️ 删除大段旧实现代码
2. ⚠️ 删除整个旧模块目录

## 当前环境检查

### ✅ 已确认安全的操作
- `EXTRACT_MODE=NEW_ONLY` 已在 docker-compose.yml 设置
- `LEGACY_TENDER_APIS_ENABLED=false` 已设置
- Step 11A 验证通过（legacy endpoints 404）

### 🟡 需要进一步验证
- extract_risks 的其他分支是否真的不会被执行
- 是否有其他服务/脚本依赖旧逻辑
- 数据库中是否有残留的旧表数据

## 下一步建议

### 选项 1: 执行方案 A（保守删除）
```bash
# 1. 备份旧代码
mkdir -p backend/docs/removed_code
# 提取旧代码到备份文件

# 2. 修改 tender_service.py
# 3. 运行测试
make verify-docker
python scripts/smoke/tender_newonly_gate.py

# 4. 提交变更
git add backend/app/services/tender_service.py
git commit -m "refactor: remove OLD/PREFER_NEW/SHADOW modes from extract_risks"
```

### 选项 2: 先注释再删除（方案 B）
```bash
# 1. 注释旧代码
# 2. 添加 DEPRECATED 标记
# 3. 运行测试
# 4. 监控 1-2 周
# 5. 确认无问题后永久删除
```

### 选项 3: 保持现状（最保守）
```bash
# 不删除旧代码，只添加强制检查
# 保留旧代码作为"应急回滚"的备份
# 在所有 extract 方法开头添加模式检查
```

## 我的推荐

考虑到当前状态：
1. Step 11A 已经完成（legacy API 隔离）
2. 系统在 NEW_ONLY 模式下运行稳定
3. 但生产环境还没有长期验证

**推荐执行方案 A 的简化版**:

1. ✅ **立即执行**: 在 extract_risks 开头添加强制模式检查
2. ✅ **立即执行**: 注释（不删除）PREFER_NEW/SHADOW/OLD 分支
3. 📅 **1-2周后**: 如果生产稳定，永久删除注释的代码
4. 📅 **之后**: 检查并删除 services/semantic_outline

这样既保证了安全性（代码还在，只是注释了），又清晰地表明了这些代码已废弃。

## 需要用户决策

请选择以下之一：

**A. 保守方案**: 添加检查 + 注释旧代码（推荐）
**B. 激进方案**: 直接删除旧代码
**C. 保持现状**: 只添加文档说明，不修改代码

---

**报告日期**: 2025-12-20  
**分析人**: AI Assistant (Claude Sonnet 4.5)  
**建议**: 采用保守方案 A

