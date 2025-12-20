# 录音转写超时问题修复报告

## 问题描述
用户反馈录音转写失败，显示超时。系统设置中的语音转文本测试功能正常。

## 问题分析

经过代码审查，发现了多个可能导致超时的问题：

### 1. 后端 API 超时配置过短
- **位置**: `backend/app/services/asr_api_service.py`
- **问题**: 默认超时时间仅为 120 秒（2分钟），对于较长的录音文件不够
- **影响**: 当录音文件较大或 ASR API 响应较慢时会超时

### 2. 流式转写超时配置过短
- **位置**: `backend/app/services/asr_service.py` 的 `transcribe_audio_streaming` 函数
- **问题**: 超时时间设置为 60 秒（1分钟）
- **影响**: WebSocket 实时录音转写可能在音频较长时超时

### 3. FFmpeg 转换超时不足
- **位置**: `backend/app/routers/asr_ws.py` 的 `background_transcribe` 函数
- **问题**: FFmpeg 音频格式转换超时仅 30 秒
- **影响**: 对于大文件的格式转换可能超时

### 4. 前端请求无超时保护
- **位置**: `frontend/src/components/RecordingsList.tsx` 的 `handleTranscribe` 函数
- **问题**: 前端 fetch 请求没有设置超时，可能被浏览器默认超时限制
- **影响**: 即使后端处理正常，前端也可能因为浏览器限制而超时

### 5. HTTP 客户端超时配置不够细致
- **位置**: `backend/app/services/asr_api_service.py`
- **问题**: 没有分别设置连接超时和读取超时
- **影响**: 可能在网络慢时连接就超时，或在 API 处理慢时读取超时

## 修复方案

### 1. 增加远程 ASR API 默认超时（120秒 → 300秒）
```python
# backend/app/services/asr_api_service.py
async def call_remote_asr_api(
    ...
    timeout: int = 300  # 从 120 改为 300（5分钟）
) -> Tuple[str, float]:
```

### 2. 优化 HTTP 客户端超时配置
```python
# backend/app/services/asr_api_service.py
timeout_config = httpx.Timeout(
    timeout=timeout,      # 总超时
    connect=10.0,         # 连接超时10秒
    read=timeout,         # 读取超时使用传入的timeout值
    write=30.0            # 写入超时30秒
)
```

### 3. 增加流式转写超时（60秒 → 180秒）
```python
# backend/app/services/asr_service.py
text, duration = await call_remote_asr_api(
    ...
    timeout=180  # 从 60 改为 180（3分钟）
)
```

### 4. 增加 FFmpeg 转换超时（30秒 → 60秒）
```python
# backend/app/routers/asr_ws.py
subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
              check=True, timeout=60)  # 从 30 改为 60
```

### 5. 增强后台转写错误处理
- 添加详细的日志记录
- 捕获 FFmpeg 超时异常
- 更新数据库记录状态为失败
- 包含完整的异常堆栈信息

### 6. 前端添加超时保护（5分钟）
```typescript
// frontend/src/components/RecordingsList.tsx
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000);

const response = await authFetch(`${apiBaseUrl}/api/recordings/${recordingId}/transcribe`, {
  method: 'POST',
  signal: controller.signal,
});
```

## 修改的文件清单

1. `backend/app/services/asr_api_service.py`
   - 增加默认超时时间
   - 优化 HTTP 客户端超时配置
   - 添加详细的超时日志

2. `backend/app/services/asr_service.py`
   - 增加流式转写的超时时间

3. `backend/app/routers/asr_ws.py`
   - 增加 FFmpeg 转换超时
   - 增强后台转写任务的错误处理
   - 添加详细的日志记录
   - 失败时更新数据库状态

4. `frontend/src/components/RecordingsList.tsx`
   - 添加请求超时控制（5分钟）
   - 改进超时错误提示

## 测试建议

1. **测试短录音（< 30秒）**
   - 验证基本转写功能正常

2. **测试中等长度录音（1-3分钟）**
   - 验证超时配置是否足够

3. **测试长录音（> 5分钟）**
   - 验证是否能正常完成或给出合理的错误提示

4. **测试网络慢的情况**
   - 模拟慢速网络，验证超时配置是否合理

5. **检查日志**
   - 查看后端日志确认转写过程的各个阶段
   - 确认超时发生在哪个环节

## 预期效果

修复后，系统应该能够：
- 处理更长的录音文件（最多5分钟内能完成的转写）
- 提供更清晰的超时错误信息
- 在转写失败时正确更新数据库状态
- 通过日志快速定位问题

## 后续优化建议

如果录音文件特别长（> 10分钟），可以考虑：
1. 实施分段转写策略
2. 添加转写进度显示
3. 使用更长的超时时间或异步任务队列
4. 考虑使用 Celery 等任务队列系统

