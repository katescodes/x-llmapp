# ASR转写失败问题修复

## ❌ 报告的错误

```
转写失败：转写失败: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
```

## 🔍 问题分析

通过分析后端日志和代码，发现**两个问题**：

### 问题1: ASR API网络连接超时 ⚠️（主要问题）

**日志显示**：
```
httpcore.ConnectTimeout
httpx.ConnectTimeout
RuntimeError: ASR API网络错误: 
```

**原因**：
- ASR API服务器无法连接
- 连接超时（10秒）
- 可能是ASR服务器未启动、网络不通、或URL配置错误

### 问题2: duration为None导致int()崩溃 ❌（次要问题）

**代码位置**：`backend/app/routers/recordings.py` 第315、322行

**问题代码**：
```python
# 当duration为None时，int(None)会报错
int(duration)  # ❌ TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
```

**原因**：
- 当ASR API调用失败时，`transcribe_audio`抛出异常
- 但某些错误路径下可能返回`(text, None)`
- 代码直接调用`int(duration)`导致崩溃

---

## ✅ 已完成修复

### 修复问题2: 处理duration为None的情况

**文件**：`backend/app/routers/recordings.py`

**修复前**：
```python
transcript, duration = await transcribe_audio(...)

# 更新数据库
word_count = len(transcript)
# ❌ 直接使用int(duration)
cur.execute("""...""", (transcript, word_count, int(duration), recording_id))

return {
    "status": "success",
    "transcript": transcript,
    "word_count": word_count,
    "duration": int(duration)  # ❌
}
```

**修复后**：
```python
transcript, duration = await transcribe_audio(...)

# 更新数据库
word_count = len(transcript)
# ✅ 处理duration可能为None的情况
duration_int = int(duration) if duration is not None else 0

cur.execute("""...""", (transcript, word_count, duration_int, recording_id))

return {
    "status": "success",
    "transcript": transcript,
    "word_count": word_count,
    "duration": duration_int  # ✅
}
```

---

## 🔧 需要解决的主要问题：ASR API连接

### 诊断步骤

#### 1. 检查ASR配置

```bash
# 查询数据库中的ASR配置
docker exec localgpt-postgres psql -U localgpt -d localgpt -c "
SELECT id, name, api_url, model_name, is_active, is_default, 
       last_test_status, last_test_message
FROM asr_configs
ORDER BY is_default DESC, created_at DESC;
"
```

**预期输出**：
- `api_url`：ASR服务的URL（例如：`https://ai.yglinker.com:6399/v1/audio/transcriptions`）
- `is_active`：`t`（激活）
- `is_default`：`t`（默认配置）
- `last_test_status`：`success`或`failed`

#### 2. 测试ASR服务连接

```bash
# 方法1：在后端容器内测试
docker exec localgpt-backend curl -v --max-time 10 https://ai.yglinker.com:6399/v1/audio/transcriptions

# 方法2：在宿主机测试
curl -v --max-time 10 https://ai.yglinker.com:6399/v1/audio/transcriptions
```

**预期结果**：
- ✅ 正常：返回400或405（表示服务在线，但缺少必需参数）
- ❌ 异常：超时、连接被拒绝、域名无法解析

#### 3. 检查网络连通性

```bash
# Ping测试（如果服务器允许ICMP）
ping -c 3 ai.yglinker.com

# DNS解析测试
nslookup ai.yglinker.com

# 端口测试
telnet ai.yglinker.com 6399
# 或
nc -zv ai.yglinker.com 6399
```

---

## 🛠️ 解决方案

### 方案A：修复ASR服务连接（推荐）

1. **确认ASR服务器状态**
   - 联系ASR服务提供方确认服务是否在线
   - 确认URL是否正确
   - 确认端口是否开放

2. **检查防火墙/网络策略**
   - Docker容器是否可以访问外部网络
   - 是否需要配置代理
   - 防火墙是否阻止了出站连接

3. **更新ASR配置**
   ```bash
   # 在系统设置 → 语音转文本 中：
   1. 检查API URL是否正确
   2. 点击"测试连接"按钮
   3. 查看测试结果
   ```

### 方案B：使用本地ASR服务（备选）

如果远程ASR服务不可用，可以部署本地Whisper服务：

```bash
# 1. 部署本地Whisper API（使用faster-whisper）
docker run -d --name whisper-api \
  -p 9000:9000 \
  -v ~/.cache/whisper:/root/.cache/whisper \
  fedirz/faster-whisper-server:latest-cpu

# 2. 在系统设置中添加本地ASR配置
API URL: http://whisper-api:9000/v1/audio/transcriptions
Model: whisper-1
Response Format: verbose_json
```

### 方案C：增加连接超时时间

如果网络较慢，可以增加超时时间：

**文件**：`backend/app/services/asr_api_service.py`

```python
# 第66-71行
timeout_config = httpx.Timeout(
    timeout=timeout,
    connect=30.0,  # ✅ 连接超时从10秒增加到30秒
    read=timeout,
    write=30.0
)
```

---

## 🧪 测试步骤

### 步骤1：重新构建和部署后端

```bash
cd /aidata/x-llmapp1
docker-compose build backend
docker-compose up -d --no-deps backend
```

### 步骤2：测试ASR配置

1. 访问系统设置 → 语音转文本
2. 查看当前ASR配置
3. 点击"测试连接"按钮
4. 查看测试结果

### 步骤3：测试录音转写

1. 进入录音管理页面
2. 选择一条录音
3. 点击"转写"按钮
4. 查看结果

**预期结果**：
- ✅ 如果ASR连接正常：转写成功，显示文字
- ⚠️ 如果ASR仍然连接失败：显示网络错误，但不会崩溃（不再出现int() NoneType错误）

---

## 📊 错误类型对照表

| 错误信息 | 原因 | 是否已修复 | 解决方案 |
|---------|------|-----------|---------|
| `int() argument must be a string, a bytes-like object or a real number, not 'NoneType'` | duration为None时调用int() | ✅ 已修复 | 使用`duration_int = int(duration) if duration is not None else 0` |
| `httpcore.ConnectTimeout` | ASR API连接超时 | ⚠️ 配置问题 | 检查ASR服务状态、网络连通性、配置URL |
| `ASR API网络错误` | ASR API无法访问 | ⚠️ 配置问题 | 同上 |
| `音频转录失败: ASR API网络错误` | 同上 | ⚠️ 配置问题 | 同上 |

---

## 🔍 日志监控

### 监控后端日志

```bash
# 实时查看ASR相关日志
docker logs -f localgpt-backend 2>&1 | grep -E "ASR|transcribe|转写"

# 查看最近的错误
docker logs localgpt-backend --tail 100 | grep -E "Error|Failed|Timeout"
```

### 成功日志示例

```
INFO: Calling remote ASR API: https://ai.yglinker.com:6399/v1/audio/transcriptions (timeout=300s)
INFO: ASR API response received: 1234 chars
INFO: Streaming transcription completed: 1234 chars
```

### 失败日志示例

```
ERROR: Audio transcription failed file=recording.wav error=ASR API网络错误: 
ERROR: httpcore.ConnectTimeout
ERROR: Background transcription failed for rec_xxx: 音频转录失败: ASR API网络错误:
```

---

## 📝 总结

### 已修复
✅ **int() NoneType错误**：通过添加空值检查，当duration为None时使用默认值0

### 待解决
⚠️ **ASR API连接问题**：这是配置/网络问题，需要：
1. 检查ASR服务器状态
2. 验证API URL配置
3. 测试网络连通性
4. 考虑使用本地ASR服务

### 下一步
1. 重新构建并部署后端（应用int()修复）
2. 在系统设置中测试ASR连接
3. 根据测试结果选择解决方案（修复远程服务 或 部署本地服务）

---

**修复时间**：2025-12-25  
**状态**：✅ int()错误已修复 / ⚠️ ASR连接待配置

