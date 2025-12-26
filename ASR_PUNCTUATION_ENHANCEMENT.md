# ASR语音转写 - 标点符号和段落优化方案

## 🎯 目标

优化语音转写结果，添加**完美的标点符号**和**合理的段落划分**。

---

## 📊 当前实现分析

### 现有流程

```
用户录音 → ASR API (Whisper) → 原始文本 → 前端展示
```

**问题**：
- ❌ Whisper默认输出的标点符号较少或不准确
- ❌ 没有段落划分，全部是连续文本
- ❌ 长篇转写阅读困难

### 现有代码位置

1. **ASR调用**：`backend/app/services/asr_api_service.py`
   - `call_remote_asr_api()`: 调用远程Whisper API
   - 返回：`(text, duration)`

2. **文本处理**：目前**无后处理**
   - 第94-97行：简单拼接segments
   ```python
   if 'segments' in result:
       segments = result['segments']
       text_parts = [seg.get('text', '').strip() for seg in segments]
       text = ' '.join(text_parts)
   ```

---

## 🚀 优化方案（4种方案对比）

### 方案A：LLM后处理（推荐⭐⭐⭐⭐⭐）

**原理**：使用LLM对ASR原始输出进行润色和段落划分

**优点**：
- ✅ 效果最好，标点符号准确
- ✅ 段落划分合理，符合语义
- ✅ 可以修正语病，提升可读性
- ✅ 支持自定义润色规则（如会议纪要格式、采访格式等）
- ✅ 易于维护和调整

**缺点**：
- ⚠️ 需要调用LLM，增加成本和延迟（1-5秒）
- ⚠️ 依赖LLM服务可用性

**实现难度**：⭐⭐（中等）

**适用场景**：
- 会议纪要
- 采访记录
- 演讲转写
- 对质量要求高的场景

---

### 方案B：规则引擎后处理

**原理**：基于语言规则（停顿时长、语调、关键词）添加标点符号

**优点**：
- ✅ 响应快，无额外延迟
- ✅ 成本低，无需调用外部服务
- ✅ 可离线使用

**缺点**：
- ❌ 效果一般，准确率60-70%
- ❌ 规则复杂，维护困难
- ❌ 难以处理复杂语境

**实现难度**：⭐⭐⭐⭐（较难）

**适用场景**：
- 对延迟敏感的场景
- 简单对话转写
- 预算受限

---

### 方案C：Whisper高级参数优化

**原理**：调整Whisper API参数，利用其内置的标点符号功能

**优点**：
- ✅ 无需额外处理
- ✅ 响应快
- ✅ 实现简单

**缺点**：
- ❌ 效果提升有限（标点符号仍不完美）
- ❌ 无段落划分
- ❌ 依赖ASR模型能力

**实现难度**：⭐（简单）

**参数调整**：
```python
extra_params = {
    "temperature": 0,  # 降低温度提高稳定性
    "language": "zh",  # 明确指定中文
    "task": "transcribe",  # 转写任务
    "word_timestamps": True,  # 获取单词级时间戳
    "timestamp_granularities[]": ["word", "segment"]  # 多粒度时间戳
}
```

**适用场景**：
- 快速原型
- 对质量要求不高的场景

---

### 方案D：混合方案（推荐⭐⭐⭐⭐）

**原理**：Whisper优化参数 + LLM轻量级后处理

**优点**：
- ✅ 效果好，兼顾速度和质量
- ✅ LLM只做轻量级调整（快速）
- ✅ 成本适中

**缺点**：
- ⚠️ 实现复杂度中等

**实现难度**：⭐⭐⭐（中等偏上）

**流程**：
```
用户录音 → Whisper(优化参数) → 初步文本 → LLM快速润色 → 最终文本
```

**适用场景**：
- 平衡质量和性能的场景
- 生产环境推荐

---

## 💡 推荐实施方案：方案A（LLM后处理）

### 架构设计

```
┌─────────────┐
│  用户录音    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  ASR转写        │
│  (Whisper API)  │
└──────┬──────────┘
       │ 原始文本（无标点/段落）
       ▼
┌─────────────────┐
│  LLM后处理      │  ◄── 新增模块
│  - 添加标点     │
│  - 段落划分     │
│  - 语病修正     │
└──────┬──────────┘
       │ 优化后文本
       ▼
┌─────────────────┐
│  前端展示       │
└─────────────────┘
```

### 实现步骤

#### 步骤1：创建LLM标点符号增强服务

**文件**：`backend/app/services/text_enhancement_service.py`（新建）

```python
"""
文本增强服务
用于对ASR转写结果进行后处理，添加标点符号和段落划分
"""
import logging
from typing import Optional, Dict, Any
from app.services.llm.llm_model_store import LLMModelStore

logger = logging.getLogger(__name__)


PUNCTUATION_PROMPT = """你是一个专业的文本编辑助手。你的任务是为语音转写的文本添加标点符号和段落划分，使其更易读。

要求：
1. **添加标点符号**：句号、逗号、问号、感叹号、冒号、分号、引号等
2. **段落划分**：根据语义和主题切换合理分段，每段不超过200字
3. **保持原意**：不要改变原文的意思，只添加标点和分段
4. **不要删减**：保留所有内容，包括口语化表达
5. **不要添加**：不要添加原文没有的内容

原始文本：
{original_text}

请输出优化后的文本（只输出文本本身，不要任何解释）：
"""


PUNCTUATION_PROMPT_FORMAL = """你是一个专业的文本编辑助手。你的任务是将语音转写的口语文本转换为正式的书面语。

要求：
1. **添加标点符号**：句号、逗号、问号、感叹号、冒号、分号、引号等
2. **段落划分**：根据语义和主题切换合理分段，每段不超过200字
3. **口语转书面语**：
   - 去除语气词（嗯、啊、呃、那个等）
   - 修正重复表达
   - 统一时态和人称
   - 修正语病
4. **保持原意**：不要改变核心意思
5. **适当精简**：可以合并重复内容，但不要删除关键信息

原始文本：
{original_text}

请输出优化后的文本（只输出文本本身，不要任何解释）：
"""


MEETING_MINUTES_PROMPT = """你是一个会议记录专家。请将语音转写的会议内容整理为规范的会议纪要格式。

要求：
1. **识别发言人**：如果有多人发言，尝试区分（如"发言人A"、"发言人B"）
2. **结构化**：
   - 会议主题/讨论要点
   - 关键决策
   - 行动项（如果有）
3. **添加标点符号和段落**
4. **精简冗余**：去除无意义的口语填充词
5. **保留关键信息**：决策、数据、时间节点等

原始文本：
{original_text}

请输出整理后的会议纪要：
"""


async def enhance_transcription(
    text: str,
    enhancement_type: str = "punctuation",
    model_id: Optional[str] = None
) -> str:
    """
    增强转写文本
    
    Args:
        text: 原始转写文本
        enhancement_type: 增强类型
            - "punctuation": 只添加标点和段落（保持口语风格）
            - "formal": 转换为正式书面语
            - "meeting": 整理为会议纪要格式
        model_id: LLM模型ID（如果不指定则使用默认模型）
    
    Returns:
        增强后的文本
    """
    if not text or len(text.strip()) < 10:
        return text
    
    # 选择prompt模板
    if enhancement_type == "formal":
        prompt = PUNCTUATION_PROMPT_FORMAL.format(original_text=text)
    elif enhancement_type == "meeting":
        prompt = MEETING_MINUTES_PROMPT.format(original_text=text)
    else:  # "punctuation"
        prompt = PUNCTUATION_PROMPT.format(original_text=text)
    
    try:
        # 获取LLM服务
        store = LLMModelStore()
        
        # 如果没有指定model_id，使用默认模型
        if not model_id:
            models = store.list_models()
            if not models:
                logger.warning("No LLM models available, skipping enhancement")
                return text
            model_id = models[0]["model_id"]
        
        llm = store.get_model(model_id)
        
        # 调用LLM
        logger.info(f"Enhancing transcription with LLM (type={enhancement_type}, length={len(text)})")
        
        # 使用流式输出并收集完整结果
        enhanced_text = ""
        async for chunk in llm.chat_stream(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # 较低温度保证稳定性
            max_tokens=4000
        ):
            if chunk.get("type") == "content":
                enhanced_text += chunk.get("content", "")
        
        # 清理输出
        enhanced_text = enhanced_text.strip()
        
        # 验证输出长度（防止LLM输出过短）
        if len(enhanced_text) < len(text) * 0.5:
            logger.warning(f"Enhanced text too short ({len(enhanced_text)} vs {len(text)}), using original")
            return text
        
        logger.info(f"Enhancement completed: {len(text)} → {len(enhanced_text)} chars")
        return enhanced_text
    
    except Exception as e:
        logger.error(f"Enhancement failed: {e}", exc_info=True)
        # 失败时返回原文
        return text


async def enhance_transcription_with_segments(
    segments: list,
    enhancement_type: str = "punctuation",
    model_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    增强转写文本（保留segment信息）
    
    Args:
        segments: Whisper返回的segments列表
        enhancement_type: 增强类型
        model_id: LLM模型ID
    
    Returns:
        {
            "enhanced_text": str,  # 增强后的完整文本
            "original_segments": list,  # 原始segments
            "enhanced_paragraphs": list  # 增强后的段落列表
        }
    """
    # 提取原始文本
    original_text = ' '.join([seg.get('text', '').strip() for seg in segments])
    
    # 调用LLM增强
    enhanced_text = await enhance_transcription(
        text=original_text,
        enhancement_type=enhancement_type,
        model_id=model_id
    )
    
    # 分段（按换行符）
    paragraphs = [p.strip() for p in enhanced_text.split('\n\n') if p.strip()]
    
    return {
        "enhanced_text": enhanced_text,
        "original_segments": segments,
        "enhanced_paragraphs": paragraphs
    }
```

#### 步骤2：修改ASR服务集成增强功能

**文件**：`backend/app/services/asr_service.py`

在 `transcribe_audio` 函数末尾添加：

```python
async def transcribe_audio(
    audio_data: bytes,
    filename: str,
    language: Optional[str] = None,
    enhance: bool = False,  # 新增参数
    enhancement_type: str = "punctuation",  # 新增参数
    model_id: Optional[str] = None  # 新增参数
) -> Tuple[str, float]:
    """
    使用远程 API 转录音频文件
    
    Args:
        audio_data: 音频文件的二进制数据
        filename: 文件名（用于确定格式）
        language: 可选的语言代码（如 'zh', 'en'）
        enhance: 是否使用LLM增强标点符号和段落
        enhancement_type: 增强类型 ("punctuation", "formal", "meeting")
        model_id: LLM模型ID（可选）
        
    Returns:
        (转录后的文本, 音频时长)
    """
    # ... 现有代码 ...
    
    # 在返回前添加增强逻辑
    if enhance and text:
        from .text_enhancement_service import enhance_transcription
        try:
            text = await enhance_transcription(
                text=text,
                enhancement_type=enhancement_type,
                model_id=model_id
            )
        except Exception as e:
            logger.warning(f"Text enhancement failed, using original: {e}")
    
    return text, duration
```

#### 步骤3：更新API端点支持增强参数

**文件**：`backend/app/routers/recordings.py`

修改 `/recordings/{recording_id}/transcribe` 端点：

```python
from pydantic import BaseModel

class TranscribeRequest(BaseModel):
    enhance: bool = False  # 是否增强
    enhancement_type: str = "punctuation"  # 增强类型
    model_id: Optional[str] = None  # LLM模型ID


@router.post("/recordings/{recording_id}/transcribe")
async def transcribe_recording(
    recording_id: str,
    request: TranscribeRequest = TranscribeRequest(),  # 新增请求体
    current_user: TokenData = Depends(get_current_user_sync)
):
    """手动转写录音文件（支持LLM增强）"""
    # ... 现有代码 ...
    
    # 执行转写
    transcript, duration = await transcribe_audio(
        audio_data=audio_data,
        filename=filename,
        language="zh",
        enhance=request.enhance,  # 传递增强参数
        enhancement_type=request.enhancement_type,
        model_id=request.model_id
    )
    
    # ... 现有代码 ...
```

#### 步骤4：前端UI添加增强选项

**文件**：`frontend/src/components/RecordingsPage.tsx`（或相关页面）

添加增强选项UI：

```typescript
// 转写对话框
<Dialog open={transcribeDialogOpen}>
  <DialogTitle>转写设置</DialogTitle>
  <DialogContent>
    <FormControl>
      <FormLabel>增强模式</FormLabel>
      <RadioGroup
        value={enhancementType}
        onChange={(e) => setEnhancementType(e.target.value)}
      >
        <FormControlLabel 
          value="none" 
          control={<Radio />} 
          label="不增强（原始转写）" 
        />
        <FormControlLabel 
          value="punctuation" 
          control={<Radio />} 
          label="添加标点和段落（保持口语风格）" 
        />
        <FormControlLabel 
          value="formal" 
          control={<Radio />} 
          label="转换为正式书面语" 
        />
        <FormControlLabel 
          value="meeting" 
          control={<Radio />} 
          label="整理为会议纪要格式" 
        />
      </RadioGroup>
    </FormControl>
  </DialogContent>
  <DialogActions>
    <Button onClick={handleTranscribe}>开始转写</Button>
  </DialogActions>
</Dialog>

// API调用
const handleTranscribe = async () => {
  const response = await api.post(`/api/recordings/${recordingId}/transcribe`, {
    enhance: enhancementType !== 'none',
    enhancement_type: enhancementType,
    model_id: null  // 使用默认模型
  });
};
```

---

## 🎨 用户体验优化

### 展示对比（可选）

在前端显示"原始文本"和"增强后文本"的对比：

```typescript
<Tabs>
  <Tab label="增强后文本" />
  <Tab label="原始文本" />
</Tabs>

<TabPanel value={0}>
  <Typography style={{ whiteSpace: 'pre-wrap' }}>
    {enhancedText}
  </Typography>
</TabPanel>

<TabPanel value={1}>
  <Typography style={{ whiteSpace: 'pre-wrap', color: 'gray' }}>
    {originalText}
  </Typography>
</TabPanel>
```

---

## 📊 效果示例

### 示例1：会议记录

**原始文本（无标点）**：
```
大家好今天我们开会讨论一下这个项目的进度嗯首先呢我们看一下技术部那边的情况小王你来说一下好的我们现在已经完成了百分之七十的开发工作预计下周可以提交测试那个还有一个问题就是数据库的性能需要优化一下好的这个问题我记下来了那市场部这边呢小李你说说市场部这边我们已经联系了五家客户有三家表示有兴趣下周会安排产品演示
```

**增强后文本（会议纪要格式）**：
```
## 会议纪要

**会议时间**：[根据录音时间]
**会议主题**：项目进度讨论

### 技术部进展（发言人：小王）

目前开发工作已完成70%，预计下周可提交测试。

**待解决问题**：
- 数据库性能需要优化

### 市场部进展（发言人：小李）

已联系5家客户，其中3家表示有兴趣。

**后续行动**：
- 下周安排产品演示
```

### 示例2：简单对话

**原始文本**：
```
今天天气真不错我们去公园走走吧好啊我也正想出去透透气顺便买点水果回来行那我们现在就出发吧等我一下我去拿个外套
```

**增强后文本**：
```
今天天气真不错，我们去公园走走吧。

好啊，我也正想出去透透气，顺便买点水果回来。

行，那我们现在就出发吧。

等我一下，我去拿个外套。
```

---

## 🔧 配置选项

### 数据库配置表（可选）

**表名**：`asr_enhancement_configs`

```sql
CREATE TABLE IF NOT EXISTS asr_enhancement_configs (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50),
    default_enhancement_type VARCHAR(20) DEFAULT 'punctuation',
    auto_enhance BOOLEAN DEFAULT FALSE,
    preferred_model_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 系统设置UI

在"系统设置 → 语音转文本"中添加：

```
┌─────────────────────────────────────┐
│ ASR增强设置                         │
├─────────────────────────────────────┤
│ □ 自动启用文本增强                  │
│                                     │
│ 默认增强模式：                       │
│   ○ 添加标点和段落                  │
│   ○ 转换为正式书面语                │
│   ○ 整理为会议纪要                  │
│                                     │
│ LLM模型选择：                       │
│   [下拉选择框]                       │
└─────────────────────────────────────┘
```

---

## 📈 性能和成本

### 延迟分析

| 操作 | 时间 |
|------|------|
| ASR转写（Whisper） | 1-10秒（取决于音频长度） |
| LLM增强（1000字） | 2-5秒 |
| **总计** | **3-15秒** |

### 成本分析（以1000字转写为例）

| 模型 | ASR成本 | LLM成本 | 总成本 |
|------|---------|---------|--------|
| Whisper + GPT-4 | $0.006 | $0.03 | $0.036 |
| Whisper + GPT-3.5 | $0.006 | $0.002 | $0.008 |
| 本地Whisper + 本地LLM | 免费 | 免费 | 免费 |

---

## 🚦 实施建议

### 阶段1：MVP（1-2天）
1. 实现基础LLM增强（只支持"添加标点"模式）
2. 修改API端点支持enhance参数
3. 前端添加简单的"启用增强"复选框

### 阶段2：功能完善（3-5天）
1. 支持多种增强模式（formal、meeting）
2. 优化prompt模板
3. 添加原文/增强对比展示
4. 添加用户配置

### 阶段3：优化迭代（1周+）
1. A/B测试不同prompt效果
2. 收集用户反馈优化
3. 支持自定义prompt模板
4. 添加缓存减少重复增强

---

## 📝 总结

### 推荐方案：方案A（LLM后处理）

**理由**：
1. ✅ 效果最好，用户体验佳
2. ✅ 实现相对简单，易于迭代
3. ✅ 成本可控（可选择便宜的LLM）
4. ✅ 灵活性高，支持多种场景

### 快速开始

```bash
# 1. 创建增强服务
touch backend/app/services/text_enhancement_service.py

# 2. 修改ASR服务
vim backend/app/services/asr_service.py

# 3. 更新API端点
vim backend/app/routers/recordings.py

# 4. 测试
curl -X POST http://localhost:9001/api/recordings/{id}/transcribe \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"enhance": true, "enhancement_type": "punctuation"}'
```

---

**创建时间**：2025-12-25  
**作者**：AI Assistant  
**状态**：方案设计完成，待实施

