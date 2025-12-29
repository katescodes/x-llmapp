# ASR 并发控制架构修复说明

## 🔴 问题根源

之前的实现有**嵌套并发控制**问题：

```python
# ❌ 错误的架构（嵌套控制）
async def background_transcribe():
    await execute_asr_with_concurrency_control(  # 外层控制
        do_transcription
    )
    
async def do_transcription():
    await transcribe_audio()  # 没控制
    
async def transcribe_audio():
    await call_remote_asr_api()  # 又控制一次？

# 结果：并发控制失效！
```

### 为什么会失效？

1. **外层控制了 `do_transcription`**，但它只是个包装函数
2. **真正调用 Whisper 的 `call_remote_asr_api`** 没有受到控制
3. 多个请求可以**同时进入 `call_remote_asr_api`**
4. 导致**多个请求同时发给 Whisper 服务** → OOM

## ✅ 修复后的架构

### 正确的设计

```python
# ✅ 正确的架构（单层控制，在最底层）
async def background_transcribe():
    await transcribe_audio()  # 无控制
    
async def transcribe_audio():
    await call_remote_asr_api()  # 核心控制点
    
async def call_remote_asr_api():
    if use_concurrency_control:  # 默认 True
        await execute_asr_with_concurrency_control(  # 唯一控制点
            _call_asr_api_internal  # 实际API调用
        )
```

### 关键改进

1. **并发控制在 `call_remote_asr_api` 内部**
   - 所有转录请求都必须经过这里
   - 统一的并发控制入口
   
2. **移除外层的重复包装**
   - `background_transcribe` 直接调用 `transcribe_audio`
   - `transcribe_audio` 直接调用 `call_remote_asr_api`
   
3. **真正的单例并发控制**
   - 全局只有一个 `Semaphore`
   - 所有转录请求共享这个信号量

## 📊 调用链路对比

### 修复前（错误）

```
[Request 1] background_transcribe()
    └─> execute_asr_with_concurrency_control()  ← 控制点1（无效）
        └─> do_transcription()
            └─> transcribe_audio()
                └─> call_remote_asr_api()  ← 实际API调用（无控制）
                    └─> Whisper 服务

[Request 2] background_transcribe()
    └─> execute_asr_with_concurrency_control()  ← 控制点2（无效）
        └─> do_transcription()
            └─> transcribe_audio()
                └─> call_remote_asr_api()  ← 实际API调用（无控制）
                    └─> Whisper 服务

结果：Request 1 和 2 同时到达 Whisper！
```

### 修复后（正确）

```
[Request 1] background_transcribe()
    └─> transcribe_audio()
        └─> call_remote_asr_api()
            └─> execute_asr_with_concurrency_control()  ← 唯一控制点
                └─> _call_asr_api_internal()
                    └─> Whisper 服务  ✓ 正在处理

[Request 2] background_transcribe()
    └─> transcribe_audio()
        └─> call_remote_asr_api()
            └─> execute_asr_with_concurrency_control()  ← 唯一控制点
                └─> 等待 Semaphore...  ⏳ 排队中

结果：Request 2 在排队，不会同时到达 Whisper！
```

## 🔧 修改的文件

### 1. `asr_api_service.py`

**修改**：在 API 调用层实现并发控制

```python
async def call_remote_asr_api(..., use_concurrency_control=True):
    """调用远程ASR API（内置并发控制）"""
    if use_concurrency_control:
        # 通过并发管理器调用
        return await execute_asr_with_concurrency_control(_call_asr_api_internal, task_id)
    else:
        # 直接调用（测试用）
        return await _call_asr_api_internal(...)
```

### 2. `asr_ws.py`

**修改**：移除外层的重复并发控制

```python
# 修复前
async def background_transcribe():
    await execute_asr_with_concurrency_control(do_transcription, ...)  # 删除

# 修复后
async def background_transcribe():
    await transcribe_audio(...)  # 直接调用
```

### 3. `recordings.py`

**修改**：移除外层的重复并发控制

```python
# 修复前
async def transcribe_recording():
    await execute_asr_with_concurrency_control(do_transcription, ...)  # 删除

# 修复后
async def transcribe_recording():
    transcript, duration = await transcribe_audio(...)  # 直接调用
```

## 🎯 验证方法

### 1. 查看日志

正确的日志应该是：

```
[ASR并发] 开始转录 task_id=asr_xxx active=1/1 queued=0
[ASR API] Calling ASR API: url=xxx
[ASR API] ASR API success: text_length=100
[ASR并发] 转录成功 task_id=asr_xxx

# 第二个请求到达时：
[ASR并发] 开始转录 task_id=asr_yyy active=1/1 queued=1  ← 注意：queued=1
```

### 2. 并发测试

```bash
# 开两个终端，同时发起转录
# Terminal 1
curl -X POST http://localhost:8000/api/recordings/123/transcribe

# Terminal 2 (立即执行)
curl -X POST http://localhost:8000/api/recordings/456/transcribe

# 观察：第二个请求应该等待第一个完成
```

### 3. 监控 GPU

```bash
watch -n 1 nvidia-smi

# 观察：显存使用应该是稳定的，不会突增
# 如果 ASR_MAX_CONCURRENT=1，显存应该只有一个转录任务的使用量
```

## 📈 预期效果

### 配置：ASR_MAX_CONCURRENT=1

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 单个请求 | ✅ 成功 | ✅ 成功 |
| 2个并发请求 | ❌ OOM | ✅ 第1个成功，第2个排队 |
| 10个并发请求 | ❌ 全部OOM | ✅ 依次处理，全部成功 |
| GPU显存占用 | 不稳定，波动大 | 稳定，可预测 |

### 配置：ASR_MAX_CONCURRENT=2

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 2个并发请求 | ❌ 可能OOM | ✅ 同时处理 |
| 3个并发请求 | ❌ 全部OOM | ✅ 前2个处理，第3个排队 |
| 10个并发请求 | ❌ 全部OOM | ✅ 每次处理2个，依次完成 |

## 🚀 部署步骤

### 1. 更新代码

```bash
git pull  # 或手动更新修改的文件
```

### 2. 重启服务

```bash
docker-compose restart backend
```

### 3. 验证配置

```bash
# 确认配置正确
cat .env | grep ASR_MAX_CONCURRENT

# 应该看到：
# ASR_MAX_CONCURRENT=1  # 从1开始测试
```

### 4. 测试验证

```bash
# 单个转录测试
# 在前端录音，观察是否成功

# 并发测试
# 开两个浏览器窗口，同时录音
# 观察第二个是否等待第一个完成
```

### 5. 查看统计

```bash
curl -H "Authorization: Bearer TOKEN" \
  http://your-domain/api/recordings/stats/asr-concurrency

# 检查：
# - active_tasks: 应该 <= ASR_MAX_CONCURRENT
# - oom_errors: 应该 = 0（或很少）
```

## ⚠️ 注意事项

### 1. 实时转录

实时转录（`asr_realtime.py`）仍然直接调用 `transcribe_audio`，因为：
- 它的音频块很小
- 已经有自己的分块控制
- 会自动通过 `call_remote_asr_api` 的并发控制

### 2. 测试调用

如果需要绕过并发控制（仅测试用）：

```python
# 测试代码
text, duration = await call_remote_asr_api(
    ...,
    use_concurrency_control=False  # 关闭并发控制
)
```

### 3. 监控重要性

修复后，**监控更加重要**：

```bash
# 持续监控
watch -n 5 'curl -s -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/recordings/stats/asr-concurrency | jq'

# 关注指标：
# - queued_tasks: 排队任务数（>5需要关注）
# - oom_errors: OOM次数（应该接近0）
# - success_rate: 成功率（应该>95%）
```

## 🎓 总结

### 核心教训

1. **并发控制应该在资源访问层**
   - 不是在业务逻辑层
   - 不是在包装函数层
   - 而是在实际API调用层

2. **避免嵌套并发控制**
   - 外层控制 → 内层无控制 ❌
   - 只在最底层控制 ✅

3. **单一控制点原则**
   - 全局只有一个 Semaphore
   - 所有请求共享
   - 统一管理和监控

### 为什么之前没发现？

1. **低并发时**：问题不明显
2. **测试不充分**：没有并发压力测试
3. **架构理解偏差**：以为外层控制了就够了

### 这次修复保证了什么？

✅ **真正的并发控制**：只有 N 个请求能同时到达 Whisper
✅ **可预测的行为**：超出的请求会排队
✅ **统一的监控**：所有请求都被追踪
✅ **可靠的重试**：失败会自动重试

---

**现在请测试并观察效果！**

期望结果：
- 单个转录：✅ 成功
- 并发转录：✅ 排队处理
- OOM错误：✅ 几乎不再出现
- GPU显存：✅ 稳定可控

