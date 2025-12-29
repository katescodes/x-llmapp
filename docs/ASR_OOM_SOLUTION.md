# ASR "CUDA Out of Memory" 问题解决方案

## 问题描述

转写音频时报错：
```
CUDA out of memory. Tried to allocate 1.34 GiB. 
GPU 0 has a total capacity of 23.57 GiB of which 229.44 MiB is free.
```

但实际GPU还有大量空闲显存（20GB+）。

## 问题根本原因

**不是GPU资源分配问题，而是请求参数导致显存需求过大：**

1. **`response_format: "verbose_json"`**
   - 返回详细的segments、timestamps等信息
   - 需要在显存中缓存更多数据

2. **`timestamp_granularities[]: "word"`**
   - 计算每个词的精确时间戳
   - 大幅增加显存消耗

3. **大音频文件（15+ MB）**
   - 基础显存需求已经较高
   - 加上详细参数后需要额外 1.34GB

**组合效果**：`大文件` + `verbose_json` + `word时间戳` = **OOM**

## 为什么Postman测试成功？

Postman可能只发送了最简单的参数：
```bash
curl -X POST https://ai.yglinker.com:6399/v1/audio/transcriptions \
  -F "file=@audio.webm" \
  -F "model=whisper"
```

不包含 `response_format` 和 `timestamp_granularities`，显存需求低。

## 解决方案

### 1. 修改数据库中的ASR配置

```sql
UPDATE asr_configs 
SET response_format = 'json'  -- 改为简单的json格式
WHERE id = 'asr-default-001';
```

### 2. 代码已优化

移除了自动添加 `timestamp_granularities` 的逻辑：

```python
# ❌ 旧代码（会导致OOM）
if 'timestamp_granularities' not in data:
    data['timestamp_granularities[]'] = 'word'

# ✅ 新代码（注释掉，不自动添加）
# 如果需要word级别时间戳，请在extra_params中显式指定
```

**文件位置**：`backend/app/services/asr_api_service.py`

### 3. 验证修复

测试16MB音频文件：

```bash
# 容器内测试
docker-compose exec backend python3 << EOF
import asyncio
from app.services.asr_service import transcribe_audio

async def test():
    with open('/app/data/recordings/rec_xxx.webm', 'rb') as f:
        audio_data = f.read()
    
    text, duration = await transcribe_audio(
        audio_data=audio_data,
        filename='test.webm',
        language='zh'
    )
    print(f"✅ 成功! 文本长度: {len(text)}")

asyncio.run(test())
EOF
```

## 响应格式对比

| 格式 | 显存需求 | 返回内容 | 推荐场景 |
|------|---------|---------|---------|
| `text` | 最低 | 纯文本 | 简单转写 |
| `json` | 低 | 文本 + duration | **推荐用于大文件** |
| `verbose_json` | 中 | 包含segments | 需要段落信息时 |
| `verbose_json` + word时间戳 | **高** | 每个词的时间戳 | 仅小文件使用 |

## 关键理解

1. **GPU资源由ASR服务（Whisper）自己管理**
   - 我们的程序不需要关心GPU分配
   - 只需调用API接口

2. **显存消耗由请求参数决定**
   - 简单请求（text/json）：显存需求低
   - 复杂请求（verbose_json + word时间戳）：显存需求高

3. **根据文件大小选择合适的参数**
   - 小文件（<5MB）：可以使用详细参数
   - 大文件（>10MB）：使用简单的 `json` 格式

## 配置建议

在系统设置中的ASR配置：

```json
{
  "name": "默认语音转文本API",
  "api_url": "https://ai.yglinker.com:6399/v1/audio/transcriptions",
  "model_name": "whisper",
  "response_format": "json",  // ⚠️ 推荐使用 json 而非 verbose_json
  "extra_params": {}  // 不要添加 timestamp_granularities
}
```

## 总结

- ✅ 问题已解决：修改 `response_format` 为 `json`
- ✅ 16MB音频文件转写成功
- ✅ 代码层面优化：移除自动添加高显存参数的逻辑
- ✅ GPU资源由ASR服务自动管理，无需程序干预

