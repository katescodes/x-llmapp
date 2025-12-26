# PDF范本提取问题诊断报告

**项目**: 测试1 (tp_3246be74991b44b1a75a93825501a101)  
**报告时间**: 2025-12-26  
**问题**: PDF中明确包含的8个范本未被提取

---

## 📋 问题描述

### 用户报告的招标文件内容

招标文件中应包含以下范本（带页码编号）：

```
一、开标一览表……………………………………………………（页码）
二、投标函…………………………………………………………（页码）
三、货物报价一览表………………………………………………（页码）
四、对商务要求及合同条款的响应………………………………（页码）
五、对技术要求的响应……………………………………………（页码）
六、货物服务技术方案……………………………………………（页码）
七、法定代表人身份证明及授权委托书…………………………（页码）
八、各类资质证书及其他重要资料………………………………（页码）
```

### 系统实际提取结果

```json
{
  "tender_filename": "含山县城乡统筹供水一体化升级改造工程项目-仙踪镇剩余供水支管网改造工程（加压泵站设备采购及安装项目）-招标文件正文.pdf",
  "tender_storage_path_ext": ".pdf",
  "body_items_count": 31,
  "fragments_detected_by_rules": 0,
  "tender_fragments_upserted": 0,
  "llm_used": false
}
```

**结论**: 
- ✅ PDF文件存在（31个body items）
- ❌ 未检测到任何范本（fragments_detected_by_rules: 0）
- ❌ LLM定位未使用（llm_used: false）

---

## 🔍 根本原因分析

### 1️⃣ PDF提取流程

根据代码分析（`fragment_extractor.py`），PDF范本提取流程：

```
1. extract_pdf_items() → 提取PDF的body items（段落、表格等）
   └─ 使用 pdf_layout_extractor.py
   
2. detect_pdf_fragments() → 检测范本片段
   └─ 使用 pdf_sample_detector.py
   ├─ locate_region() → 定位"投标文件格式"区域
   ├─ 标题候选识别 → 使用编号模式和关键词
   └─ 切片分段 → 生成fragments
   
3. upsert_fragments() → 保存到数据库
```

### 2️⃣ 可能的失败点

#### A. `extract_pdf_items()` 阶段

**问题**: PDF解析质量
- PDF可能是扫描件
- 文本提取不完整
- 布局信息丢失

**诊断方法**:
```python
items, pdf_diag = extract_pdf_items(pdf_path, max_pages=500)
# 检查:
# - len(items) > 0  ✅ (实际: 31)
# - pdf_diag['pages_processed'] > 0
# - pdf_diag['elements_found'] > 0
```

**当前状态**: ✅ 已提取31个items

---

#### B. `locate_region()` 阶段

**问题**: 未能定位"投标文件格式"区域

**关键词匹配**:
```python
REGION_KW = [
    "投标文件格式",
    "响应文件格式",
    "样表",
    "范本",
    "格式",
    "附件",
    "投标文件",
    "投标资料",
    "标书"
]
```

**分析**:
- 用户提供的目录是："一、开标一览表……"
- **缺失**: 没有明确的"投标文件格式"标题
- 系统无法定位范本区域的起始位置

**诊断方法**:
```bash
# 查看PDF中的文本内容
docker-compose exec backend python -c "
from app.services.fragment.pdf_layout_extractor import extract_pdf_items
items, diag = extract_pdf_items('招标文件路径')
for i, it in enumerate(items[:50]):
    if it.get('type') == 'paragraph':
        print(f'{i}: {it.get(\"text\", \"\")[:100]}')
"
```

---

#### C. 标题候选识别阶段

**问题**: 标题模式不匹配

**当前的编号模式**:
```python
H1 = re.compile(r"^\s*[一二三四五六七八九十]+[、.．。]\s*\S+")  # 中文编号
H2 = re.compile(r"^\s*\d+(?:\.\d+)*[、.．。]\s*\S+")            # 数字编号
H3 = re.compile(r"^\s*[（(]\s*\d+\s*[)）]\s*\S+")              # (1)格式
H4 = re.compile(r"^\s*[附表第][一二三四五六七八九十\d]+[、：:]\s*\S+")  # 附件
H5 = re.compile(r"^\s*[附录]?\s*[A-Z]\s*[、.．。:：]\s*\S+")    # 附录A
```

**用户的实际格式**:
```
一、开标一览表……………………………………………………（页码）
```

**分析**:
- ✅ 应该匹配H1模式：`一、开标一览表`
- ⚠️ 但标题后面有很多点号（`……`）和括号"（页码）"
- ⚠️ 这可能导致标题文本过长或被切断

**诊断方法**:
```python
import re
H1 = re.compile(r"^\s*[一二三四五六七八九十]+[、.．。]\s*\S+")
test_titles = [
    "一、开标一览表",
    "一、开标一览表……………………………………………………（页码）",
    "二、投标函…………………………………………………………（页码）",
]
for title in test_titles:
    if H1.match(title):
        print(f"✅ 匹配: {title}")
    else:
        print(f"❌ 不匹配: {title}")
```

---

#### D. 关键词匹配阶段

**问题**: 标题关键词不在预定义列表中

**当前的范本关键词**:
```python
SAMPLE_KW = [
    "投标函","响应函","报价","报价一览表","开标一览表","分项报价",
    "报价表","报价清单","授权委托书","授权书","法定代表人","身份证明",
    "委托书","偏离","商务响应","技术响应","承诺函","声明","资格审查",
    "资质","营业执照","样表","范本","格式","保证金","投标保证金",
    "履约保证","证书","证明","业绩","项目组织","设备清单","材料清单",
    "工程量清单","施工方案","技术方案","实施方案","组织架构","人员配备"
]
```

**用户的实际标题**:
```
✅ 开标一览表           → 包含"开标一览表"
✅ 投标函               → 包含"投标函"
✅ 货物报价一览表       → 包含"报价一览表"
❓ 对商务要求及合同条款的响应  → 仅包含"响应"（可能需要"商务响应"）
❓ 对技术要求的响应     → 仅包含"响应"（可能需要"技术响应"）
❓ 货物服务技术方案     → 包含"技术方案"
✅ 法定代表人身份证明及授权委托书 → 包含多个关键词
❓ 各类资质证书及其他重要资料 → 包含"资质"、"证书"
```

**分析**:
- 前3个应该能匹配
- 第4-8个可能需要部分匹配逻辑

---

#### E. 阈值设置

**代码中的分数阈值**:
```python
if sc < 4.0:  # ✅ 从6.5降低到4.0
    continue

if sc >= 6.0:
    # 高分直接通过
    heads.append((int(it["bodyIndex"]), title, ftype, sc))
elif (ftype or _has_kw(title, SAMPLE_KW)):
    # 中等分数+有类型/关键词
    heads.append((int(it["bodyIndex"]), title, ftype, sc))
```

**分析**:
- 分数计算基于：编号匹配、关键词、字体大小
- 如果标题分数 < 4.0，直接跳过
- 如果标题分数 ≥ 4.0 但 < 6.0，需要匹配类型或关键词

---

## 🎯 问题定位总结

### 最可能的原因（优先级排序）

1. **⭐⭐⭐⭐⭐ 区域定位失败**
   - PDF中没有"投标文件格式"等明确标题
   - `locate_region()` 返回了错误的范围或空范围
   - 导致后续的标题检测在错误的区域进行

2. **⭐⭐⭐⭐ PDF文本提取质量问题**
   - PDF是扫描件或图片格式
   - 标题文本中包含大量点号（`……`）影响匹配
   - 字体信息丢失导致分数过低

3. **⭐⭐⭐ 标题格式问题**
   - 标题后缀"……（页码）"影响正则匹配
   - 需要更宽松的匹配规则

4. **⭐⭐ 日志级别不足**
   - 无法看到详细的调试信息
   - 不知道到底在哪个阶段失败

---

## 🛠️ 解决方案

### 方案A: 立即可行（无需代码修改）

#### A1. 检查PDF文件质量
```bash
# 查看PDF的文本内容
docker-compose exec -T backend python << 'EOF'
from app.services.fragment.pdf_layout_extractor import extract_pdf_items
project_id = "tp_3246be74991b44b1a75a93825501a101"
pdf_path = "data/tender_assets/tp_3246be74991b44b1a75a93825501a101/tender_2840f3b4287a44f89528ff3e7ca2fa60_含山县城乡统筹供水一体化升级改造工程项目-仙踪镇剩余供水支管网改造工程（加压泵站设备采购及安装项目）-招标文件正文.pdf"

items, diag = extract_pdf_items(pdf_path, max_pages=100)
print(f"总计提取: {len(items)} 个items")
print(f"诊断信息: {diag}")
print("\n前20个段落:")
for i, it in enumerate(items[:20]):
    if it.get("type") == "paragraph":
        text = it.get("text", "")[:150]
        print(f"{i}: {text}")
EOF
```

#### A2. 手动触发LLM定位
```python
# 修改代码，强制使用LLM span定位作为兜底
# 在 fragment_extractor.py 中：
if ext == ".pdf" and len(fragments) == 0:
    # 规则检测失败，尝试LLM定位
    logger.warning(f"[samples][pdf] Rule-based detection failed, trying LLM...")
    # 调用 TenderSampleSpanLocator
```

---

### 方案B: 代码优化（推荐）

#### B1. 增强区域定位逻辑

**目标**: 即使没有"投标文件格式"标题，也能识别范本区域

```python
def locate_region_v2(items: List[Dict[str, Any]], window_pages: int = 12) -> Tuple[int, int, Dict[str, Any]]:
    """
    增强版区域定位：
    1. 优先查找"投标文件格式"等关键词
    2. 如果找不到，查找"开标一览表"、"投标函"等已知范本标题
    3. 如果还找不到，使用全文档
    """
    # 原有逻辑...
    
    # 新增：查找已知范本标题
    if r_end - r_start < 3:  # 区域太小，重新定位
        for i, it in enumerate(items):
            if it.get("type") != "paragraph":
                continue
            text = (it.get("text") or "").strip()
            if any(kw in text for kw in ["开标一览表", "投标函", "报价一览表"]):
                r_start = max(0, i - 5)  # 向前扩展5个items
                r_end = min(len(items), i + 100)  # 向后100个items
                diag["fallback"] = "detected_by_known_titles"
                break
    
    # 最后兜底：使用全文档
    if r_end - r_start < 3:
        r_start = 0
        r_end = len(items)
        diag["fallback"] = "use_full_document"
    
    return r_start, r_end, diag
```

#### B2. 优化标题识别

**目标**: 处理带点号和括号的标题

```python
def _clean_title(text: str) -> str:
    """
    清理标题文本：
    - 去除尾部的点号（……）
    - 去除尾部的括号内容（页码）
    """
    # 去除尾部的"………………（页码）"
    text = re.sub(r'[…\.]+\s*[（\(][^）\)]*[）\)]\s*$', '', text)
    # 去除尾部的"………………"
    text = re.sub(r'[…\.]+\s*$', '', text)
    return text.strip()

# 在detect_pdf_fragments中使用：
for it in seg:
    txt = (it.get("text") or "").strip()
    if not txt:
        continue
    
    # 清理标题
    title_raw = txt.split("\n")[0].strip()
    title = _clean_title(title_raw)  # ✅ 新增
    
    norm = title_normalize_fn(title)
    ftype = title_to_type_fn(norm) if norm else None
    # ...
```

#### B3. 降低匹配阈值

**目标**: 提高识别率

```python
# 当前阈值
if sc < 4.0:  # 已从6.5降到4.0
    continue

# 建议进一步降低
if sc < 2.0:  # ✅ 再降低到2.0
    continue

# 或者完全移除阈值，只要有编号就识别
if H1.match(title) or H2.match(title) or H3.match(title):
    heads.append((int(it["bodyIndex"]), title, ftype, 10.0))  # 强制高分
```

#### B4. 增加关键词

**目标**: 覆盖更多标题变体

```python
SAMPLE_KW = [
    # ... 现有关键词 ...
    
    # ✅ 新增
    "商务要求",      # 对应"对商务要求及合同条款的响应"
    "技术要求",      # 对应"对技术要求的响应"
    "货物服务",      # 对应"货物服务技术方案"
    "其他重要资料",  # 对应"各类资质证书及其他重要资料"
    "合同条款",
]
```

---

### 方案C: 日志增强（调试必需）

#### C1. 添加详细日志

```python
import logging
logger = logging.getLogger(__name__)

def detect_pdf_fragments(...):
    # ... 原有代码 ...
    
    # ✅ 增加日志
    logger.info(f"[samples][pdf] 区域定位: start={r_start}, end={r_end}, diag={region_diag}")
    logger.info(f"[samples][pdf] 标题候选数: {len(heads)}")
    
    for idx, title, ftype, sc in heads:
        logger.debug(f"[samples][pdf] 标题: idx={idx}, score={sc:.2f}, type={ftype}, title={title[:50]}")
    
    logger.info(f"[samples][pdf] 最终fragments数: {len(fragments)}")
```

#### C2. 临时启用DEBUG日志

```bash
# 修改docker-compose.yml或环境变量
LOG_LEVEL=DEBUG

# 或在代码中临时设置
logging.getLogger("app.services.fragment").setLevel(logging.DEBUG)
```

---

## 🧪 测试计划

### Step 1: 诊断当前状态
```bash
# 1. 查看PDF提取的items
./diagnose_pdf_items.sh tp_3246be74991b44b1a75a93825501a101

# 2. 查看区域定位结果
./diagnose_region_location.sh tp_3246be74991b44b1a75a93825501a101

# 3. 查看标题候选
./diagnose_title_candidates.sh tp_3246be74991b44b1a75a93825501a101
```

### Step 2: 实施修复
```bash
# 1. 应用代码优化（方案B）
# 2. 重启后端
docker-compose restart backend

# 3. 重新触发提取
curl -X POST "http://localhost:9001/api/apps/tender/projects/tp_3246be74991b44b1a75a93825501a101/directory/auto-fill-samples"
```

### Step 3: 验证结果
```bash
# 1. 查看提取的fragments数量
./diagnose_fragments.sh tp_3246be74991b44b1a75a93825501a101

# 2. 查看前端显示
# 访问前端，查看目录是否已填充

# 3. 查看日志
docker-compose logs backend | grep -A 10 "samples.*pdf"
```

---

## 📊 预期结果

### 修复前
```json
{
  "fragments_detected_by_rules": 0,
  "tender_fragments_upserted": 0,
  "attached_sections_builtin": 4,
  "warnings": ["PDF 未能抽取到范本片段..."]
}
```

### 修复后
```json
{
  "fragments_detected_by_rules": 8,
  "tender_fragments_upserted": 8,
  "attached_sections_template_sample": 8,
  "attached_sections_builtin": 0,
  "warnings": []
}
```

### 预期匹配结果
| 招标文件标题 | 检测结果 | 匹配类型 | 填充目录节点 |
|-------------|---------|---------|------------|
| 一、开标一览表 | ✅ | BID_OPENING_FORM | 1. 开标一览表 |
| 二、投标函 | ✅ | BID_LETTER | 2. 投标函 |
| 三、货物报价一览表 | ✅ | PRICE_SCHEDULE | 3. 货物报价一览表 |
| 四、对商务要求及合同条款的响应 | ✅ | BUSINESS_RESPONSE | 4. 对商务要求... |
| 五、对技术要求的响应 | ✅ | TECHNICAL_RESPONSE | 5. 对技术要求... |
| 六、货物服务技术方案 | ✅ | TECHNICAL_PROPOSAL | 6. 货物服务... |
| 七、法定代表人身份证明及授权委托书 | ✅ | LEGAL_REP_AUTH | 7. 法定代表人... |
| 八、各类资质证书及其他重要资料 | ✅ | QUALIFICATIONS | 8. 各类资质... |

---

## 📝 下一步行动

### 立即行动（用户）
1. ✅ 查看本诊断报告
2. ⏸️ 等待代码优化实施
3. ⏸️ 重新测试提取功能

### 短期行动（开发）
1. ⏸️ 实施方案B1-B4（代码优化）
2. ⏸️ 实施方案C1-C2（日志增强）
3. ⏸️ 创建诊断脚本
4. ⏸️ 重新测试

### 中期改进
1. ⏸️ PDF OCR集成
2. ⏸️ 更智能的区域定位算法
3. ⏸️ LLM增强的标题识别
4. ⏸️ 用户反馈机制

---

**报告作者**: AI Assistant  
**报告版本**: v1.0  
**报告状态**: 问题已诊断，待实施修复  
**预计修复时间**: 1-2小时（代码优化）+ 30分钟（测试验证）

