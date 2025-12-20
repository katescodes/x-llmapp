# Step 5 完成报告：入库切到 PREFER_NEW（灰度到 smoke 项目）

## ✅ 验收状态

**所有验收项通过！**

---

## 📋 实现内容

### 1. 完善 PREFER_NEW 模式实现

**文件**: `backend/app/services/tender_service.py` (`import_assets` 方法)

#### 重构后的入库逻辑流程

```python
# 1. 判断 cutover 模式
if kind in ("tender", "bid", "custom_rule"):
    cutover = get_cutover_config()
    ingest_mode = cutover.get_mode("ingest", project_id)
    
    # 2. PREFER_NEW 或 NEW_ONLY: 先尝试新入库
    if ingest_mode in ("PREFER_NEW", "NEW_ONLY"):
        try:
            ingest_v2_result = await ingest_v2.ingest_asset_v2(...)
            v2_success = True
            
            # PREFER_NEW 成功后不跑旧入库
            if ingest_mode == "PREFER_NEW":
                need_legacy_ingest = False
                tpl_meta["ingest_v2_fallback_to_legacy"] = False
        except Exception as e:
            if ingest_mode == "NEW_ONLY":
                # NEW_ONLY 失败直接抛错
                raise ValueError(f"IngestV2 NEW_ONLY failed: {e}")
            else:
                # PREFER_NEW 失败回退旧入库
                logger.warning(f"IngestV2 PREFER_NEW failed, fallback to legacy")
                tpl_meta["ingest_v2_fallback_to_legacy"] = True
                need_legacy_ingest = True
    
    # 3. 执行旧入库（如果需要）
    if need_legacy_ingest:
        kb_doc_id = self._ingest_to_kb(...)
    
    # 4. SHADOW 模式：旧入库成功后，同步跑新入库
    if ingest_mode == "SHADOW" and not v2_success:
        try:
            ingest_v2_result = await ingest_v2.ingest_asset_v2(...)
        except Exception as e:
            # SHADOW 失败仅记录，不影响主流程
            logger.error(f"IngestV2 SHADOW failed: {e}")
```

#### 关键改进

1. **先判断模式**: 在任何入库操作前，先判断 cutover 模式
2. **条件执行旧入库**: 只有在需要时才执行旧入库
3. **正确的 PREFER_NEW**: 先跑新入库，成功则不跑旧；失败才回退旧
4. **Meta 记录完整**: 记录 `ingest_mode_used`, `ingest_v2_fallback_to_legacy`

### 2. 扩展 smoke 脚本

**文件**: `scripts/smoke/tender_e2e.py`

#### 打印项目 ID（方便灰度测试）

```python
def create_project(token: str) -> str:
    # ... 创建项目 ...
    project_id = project["id"]
    log_success(f"项目创建成功 (ID: {project_id})")
    
    # 新增：醒目打印项目 ID
    print()
    print(f"{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}  项目 ID: {GREEN}{project_id}{RESET}")
    print(f"{BLUE}  灰度测试用法: CUTOVER_PROJECT_IDS={project_id}{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    print()
    
    return project_id
```

**输出示例：**

```
✓ 项目创建成功 (ID: tp_155a5d0efdfa4ad2858073ec27d8b94f)

═══════════════════════════════════════════════════════════
  项目 ID: tp_155a5d0efdfa4ad2858073ec27d8b94f
  灰度测试用法: CUTOVER_PROJECT_IDS=tp_155a5d0efdfa4ad2858073ec27d8b94f
═══════════════════════════════════════════════════════════
```

### 3. 更新文档

**文件**: `docs/SMOKE.md`

#### 新增章节：Cutover 控制 & 灰度测试

- **灰度入库到指定项目**: 详细步骤说明
- **Cutover 模式说明**: 4 种模式的对比表格
- **Meta 记录**: 成功和 fallback 的示例
- **Debug 接口**: 完整的 curl 命令示例

---

## 🧪 验收测试结果

### 1. 默认配置（INGEST_MODE=OLD）

```bash
✅ Smoke 测试全绿
✅ 非灰度项目使用 OLD 模式
✅ meta_json: {"ingest_mode_used": "OLD"}
```

### 2. 灰度配置（PREFER_NEW）

**设置：**

```bash
CUTOVER_PROJECT_IDS=tp_155a5d0efdfa4ad2858073ec27d8b94f
INGEST_MODE=PREFER_NEW
```

**结果：**

```bash
✅ 灰度项目上传成功（asset_id: ta_361458dd0d13424cb86a0da397d0c703）
✅ 使用 v2 入库
✅ meta_json:
   {
     "doc_version_id": "dv_d11b9a3463ff43a88b759f06446df9f5",
     "ingest_mode_used": "PREFER_NEW",
     "ingest_v2_status": "success",
     "ingest_v2_segments": 36,
     "ingest_v2_fallback_to_legacy": false
   }
✅ 实际写入: 36 segments
```

### 3. 非灰度项目（OLD 模式）

**新项目：** `tp_58a074d9145649108fdae622f760c728`

```bash
✅ Smoke 测试全绿
✅ meta_json: {"ingest_mode_used": "OLD"}
✅ 未使用 v2 入库
```

### 4. 灰度隔离验证

| 项目类型 | 项目 ID | 入库模式 | v2 入库 | 结果 |
|---------|---------|---------|---------|------|
| 灰度项目 | tp_155a...b94f | PREFER_NEW | ✅ 成功 | ✅ 通过 |
| 非灰度项目 | tp_58a0...c728 | OLD | ❌ 未使用 | ✅ 通过 |

---

## 📊 关键指标

| 指标 | 数值 |
|------|------|
| 灰度项目入库模式 | PREFER_NEW |
| v2 入库成功率 | 100% |
| 分片数量（bid_sample.docx） | 36 |
| Fallback 发生次数 | 0 |
| 非灰度项目影响 | 0 |

---

## 🔧 Meta JSON 记录

### 成功情况

```json
{
  "doc_version_id": "dv_d11b9a3463ff43a88b759f06446df9f5",
  "ingest_mode_used": "PREFER_NEW",
  "ingest_v2_status": "success",
  "ingest_v2_segments": 36,
  "ingest_v2_fallback_to_legacy": false
}
```

### Fallback 情况（模拟）

```json
{
  "ingest_mode_used": "PREFER_NEW",
  "ingest_v2_status": "failed_fallback",
  "ingest_v2_error": "...",
  "ingest_v2_fallback_to_legacy": true
}
```

### OLD 模式

```json
{
  "ingest_mode_used": "OLD"
}
```

---

## 📝 代码变更摘要

### 修改文件

```
backend/app/services/tender_service.py (import_assets 方法重构)
scripts/smoke/tender_e2e.py (打印项目 ID)
docs/SMOKE.md (新增 Cutover 章节)
docker-compose.yml (已恢复默认配置)
```

### 核心改动

1. **重构入库逻辑**: 条件执行旧入库，避免重复入库
2. **PREFER_NEW 实现**: 先跑新入库，成功则不跑旧；失败回退旧
3. **Meta 记录增强**: 新增 `ingest_mode_used`, `ingest_v2_fallback_to_legacy`
4. **Smoke 脚本增强**: 醒目打印项目 ID
5. **文档完善**: 详细的灰度测试指南

---

## 🎯 使用指南

### 快速开始

```bash
# 1. 运行 Smoke 测试，获取项目 ID
python scripts/smoke/tender_e2e.py

# 输出会显示：
# ═══════════════════════════════════════════════════════════
#   项目 ID: tp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#   灰度测试用法: CUTOVER_PROJECT_IDS=tp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# ═══════════════════════════════════════════════════════════

# 2. 编辑 docker-compose.yml
# 设置：
#   CUTOVER_PROJECT_IDS=tp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#   INGEST_MODE=PREFER_NEW

# 3. 重启服务
docker compose restart backend

# 4. 验证配置
TOKEN=$(curl -s -X POST http://localhost:9001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access_token')

curl "http://localhost:9001/api/_debug/cutover?project_id=tp_xxx" \
  -H "Authorization: Bearer $TOKEN" | jq

# 5. 上传文件到灰度项目
# ... 正常上传 ...

# 6. 验证入库结果
curl "http://localhost:9001/api/_debug/ingest/v2?asset_id=ta_xxx" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Debug 命令

```bash
# 查看 cutover 配置
curl "http://localhost:9001/api/_debug/cutover?project_id=tp_xxx" \
  -H "Authorization: Bearer $TOKEN" | jq

# 查看入库状态
curl "http://localhost:9001/api/_debug/ingest/v2?asset_id=ta_xxx" \
  -H "Authorization: Bearer $TOKEN" | jq

# 查看资产 meta_json
curl "http://localhost:9001/api/apps/tender/projects/tp_xxx/assets" \
  -H "Authorization: Bearer $TOKEN" | jq '.[0].meta_json'
```

---

## ✅ 验收清单

- [x] PREFER_NEW 模式正确实现（先新后旧）
- [x] Fallback 逻辑正确（新失败则回退旧）
- [x] Meta 记录完整（mode/status/fallback）
- [x] Smoke 脚本打印项目 ID
- [x] 文档更新（灰度测试指南）
- [x] 默认配置测试通过（INGEST_MODE=OLD）
- [x] 灰度配置测试通过（PREFER_NEW）
- [x] 非灰度项目不受影响（OLD 模式）
- [x] 灰度隔离验证通过

---

## 🎉 总结

**Step 5 完成！**

成功实现了灰度入库切换：
- ✅ PREFER_NEW 模式：优先新入库，失败自动回退
- ✅ 灰度控制：仅指定项目使用新入库
- ✅ 业务连续性：Fallback 确保流程不中断
- ✅ 完整记录：Meta JSON 记录所有关键信息
- ✅ 便捷调试：Smoke 脚本打印项目 ID

**默认配置 (INGEST_MODE=OLD, CUTOVER_PROJECT_IDS=) 不影响现有功能，可安全部署！**

---

## 📌 下一步建议

### Step 6: 新检索接入业务 (RETRIEVAL_MODE=SHADOW)

1. 修改 `retrieve()` facade 接入 cutover 控制
2. SHADOW 模式：同时跑新旧检索，对比结果
3. 记录 shadow diff 到日志
4. 验证新检索质量

### Step 7: 检索切到 PREFER_NEW

1. 灰度切换检索到 PREFER_NEW
2. 验证检索质量和性能
3. 逐步扩大灰度范围

### Step 8: 全面切换到新链路

1. 所有项目切换到 NEW_ONLY
2. 移除旧入库/检索代码
3. 清理技术债务

