# ASR 即录即转（实时转录）功能说明

## 功能概述

即录即转功能允许用户在录音的同时实时看到转录文本，无需等待录音完成。系统会自动将音频流分块处理，并实时显示转录结果。

## 核心特性

### 1. 智能分块转录
- **时间触发**：每3秒自动触发一次转录（可配置）
- **大小触发**：当累积音频达到50KB时立即转录（可配置）
- **自动合并**：小块音频自动累积，避免过于频繁调用API

### 2. 上下文感知 🆕
- **音频重叠**：相邻音频块重叠500ms，保证语境连贯
- **文本上下文**：保留最近3段转录作为上下文
- **重复去除**：自动检测并去除因音频重叠导致的重复内容
- **句子连接**：智能处理分块边界的句子连接

### 3. 并发控制
- 使用Semaphore限制并发转录数，避免GPU显存溢出
- 默认最大并发数：2（可通过环境变量`ASR_MAX_CONCURRENT`调整）
- 自动排队机制，超出并发限制的请求会等待

### 3. 错误重试
- 自动重试机制：失败后最多重试3次（可配置）
- 指数退避策略：第1次重试等5秒，第2次等10秒，第3次等20秒
- 智能错误识别：区分OOM错误和其他错误

### 4. 实时反馈
- WebSocket实时推送转录片段
- 前端即时显示新的转录文本
- 显示"实时转录中"状态标识

## 配置参数

### 环境变量配置（backend/env.example）

```bash
# ASR并发控制和重试配置
ASR_MAX_CONCURRENT=2      # 最大并发转录数（建议：12G显存=2，24G显存=3-4）
ASR_MAX_RETRIES=3         # 失败后最大重试次数
ASR_RETRY_DELAY=5         # 重试延迟（秒）
ASR_REQUEST_TIMEOUT=300   # 请求超时（秒）
```

### 前端配置（VoiceRecorder组件）

```typescript
const config = {
  realtime: true,                // 启用即录即转
  chunk_duration_ms: 3000,       // 分块时长：3秒
  min_chunk_size_bytes: 50000,   // 最小块大小：50KB
  overlap_duration_ms: 500,      // 音频重叠：500ms（上下文）
  context_window: 3,             // 保留最近3段转录作为上下文
  language: 'zh'                 // 语言
};
```

### 上下文参数说明

- **overlap_duration_ms**: 相邻音频块的重叠时长
  - 目的：保证句子在分块边界处不被截断
  - 建议值：300-1000ms
  - 注意：重叠部分会被自动检测和去除

- **context_window**: 保留多少段转录作为上下文
  - 目的：帮助理解当前转录的语境
  - 建议值：2-5段
  - 最大文本长度限制：200字符

## 使用方法

### 1. 前端使用

在录音前勾选"即录即转"选项：

```tsx
// 用户界面会显示：
// [ ✓ ] 即录即转（实时显示转录文本）
//   ✓ 启用后会在录音过程中实时显示转录结果，但可能消耗更多资源
```

### 2. WebSocket 消息格式

**客户端发送（开始录音）：**
```json
{
  "action": "start",
  "config": {
    "language": "zh",
    "realtime": true,
    "chunk_duration_ms": 3000,
    "min_chunk_size_bytes": 50000
  }
}
```

**服务端推送（实时转录片段）：**
```json
{
  "type": "transcript",
  "text": "这是转录的文本",
  "is_final": false,
  "chunk_id": 0,
  "timestamp": 1234567890.123
}
```

**服务端推送（最终结果）：**
```json
{
  "type": "final",
  "recording_id": "uuid",
  "full_transcript": "完整的转录文本",
  "duration": 60,
  "word_count": 100
}
```

## 工作流程

```
用户开始录音
    ↓
[音频流] → [缓冲区累积]
    ↓
满足条件？(时间≥3s OR 大小≥50KB)
    ↓ 是
[提取音频块] + [添加前500ms作为上下文]
    ↓
[ffmpeg转换WAV]
    ↓
[并发控制] → 等待信号量
    ↓
[调用ASR API] → 带重试机制
    ↓
[转录成功] → [上下文后处理]
    ├─ 检测重复内容（音频重叠导致）
    ├─ 去除重复部分
    └─ 优化句子连接
    ↓
[WebSocket推送] → 只推送新内容
    ↓
[前端显示] → 用户实时看到
    ↓
继续录音... (循环)
    ↓
用户停止录音
    ↓
处理剩余音频 → 保存数据库
```

## 性能优化建议

### 1. 根据GPU显存调整并发数

| GPU显存 | 建议并发数 | 配置值 |
|---------|-----------|--------|
| 8GB     | 1-2       | ASR_MAX_CONCURRENT=1 |
| 12GB    | 2-3       | ASR_MAX_CONCURRENT=2 |
| 24GB    | 3-4       | ASR_MAX_CONCURRENT=3 |
| 40GB+   | 4-6       | ASR_MAX_CONCURRENT=4 |

### 2. 调整分块参数

**快速响应（消耗更多资源）：**
```typescript
{
  chunk_duration_ms: 2000,     // 2秒触发
  min_chunk_size_bytes: 30000  // 30KB触发
}
```

**节省资源（响应稍慢）：**
```typescript
{
  chunk_duration_ms: 5000,     // 5秒触发
  min_chunk_size_bytes: 100000 // 100KB触发
}
```

### 3. 监控并发状态

访问API端点查看实时统计：
```bash
GET /api/recordings/stats/asr-concurrency
```

返回示例：
```json
{
  "status": "success",
  "stats": {
    "max_concurrent": 2,
    "active_tasks": 1,
    "total_tasks": 25,
    "failed_tasks": 2,
    "oom_errors": 1,
    "success_rate": "92.0%"
  }
}
```

## 常见问题

### 上下文处理相关

**Q: 为什么需要音频重叠？**

A: 音频分块转录时，句子可能在分块边界被截断。例如：
- 第1块："今天天气很"（句子未完成）
- 第2块："很好，适合出门"（缺少主语）

通过500ms音频重叠：
- 第1块："今天天气很"
- 第2块（含重叠）："天气很好，适合出门"
- 系统自动检测"天气很"重复，去除后得到："好，适合出门"
- 最终拼接："今天天气很好，适合出门" ✓

**Q: 上下文窗口的作用是什么？**

A: 保留最近几段转录文本作为上下文，帮助：
1. **检测重复**：与前文对比，识别重复内容
2. **理解语境**：（未来可用于LLM优化）
3. **统计分析**：了解转录历史

**Q: 如何调优上下文参数？**

根据使用场景调整：

**场景1：快速对话**
```typescript
{
  overlap_duration_ms: 300,  // 短重叠，快速响应
  context_window: 2          // 少量上下文
}
```

**场景2：正式演讲/讲座**
```typescript
{
  overlap_duration_ms: 800,  // 长重叠，保证完整性
  context_window: 5          // 更多上下文
}
```

**场景3：多人对话**
```typescript
{
  overlap_duration_ms: 500,  // 中等重叠
  context_window: 3          // 中等上下文
}
```

### Q1: 即录即转和普通录音有什么区别？

**即录即转：**
- ✅ 实时显示转录文本
- ✅ 边录边转，无需等待
- ⚠️ 消耗更多GPU资源
- ⚠️ 多人同时使用时可能排队

**普通录音：**
- ✅ 资源消耗少
- ✅ 录音完成后统一转录
- ⚠️ 需要等待转录完成
- ✅ 适合长时间录音

### Q2: 为什么有时显存充足还是报OOM错误？

可能原因：
1. **多个用户同时转录**：超出并发限制
2. **模型未正确释放显存**：ASR服务需要重启
3. **音频块太大**：调小`min_chunk_size_bytes`
4. **并发数设置过高**：降低`ASR_MAX_CONCURRENT`

解决方案：
```bash
# 1. 降低并发数
ASR_MAX_CONCURRENT=1

# 2. 增加重试次数和延迟
ASR_MAX_RETRIES=5
ASR_RETRY_DELAY=10

# 3. 重启ASR服务
docker-compose restart asr-service
```

### Q3: 如何禁用即录即转？

**方法1：前端禁用（推荐）**
- 用户取消勾选"即录即转"选项

**方法2：后端禁用**
```python
# 修改 asr_ws.py，强制禁用
config['realtime'] = False
```

### Q4: 即录即转的文本准确吗？

- **准确性**：与普通转录相同，使用同一个ASR模型
- **完整性**：所有音频块都会转录，不会丢失
- **顺序性**：按时间顺序拼接，保证正确顺序

### Q5: 可以中途暂停实时转录吗？

当前版本暂停录音时，实时转录也会暂停。恢复录音后继续转录。

## 技术架构

```
前端 (VoiceRecorder.tsx)
    ↓ WebSocket
后端 (asr_ws.py)
    ↓ 创建 ASRSession
实时处理器 (asr_realtime.py)
    ↓ RealtimeASRProcessor
    ├─ 音频缓冲管理
    ├─ 后台处理任务
    └─ 分块转录
    ↓
并发管理器 (asr_concurrency.py)
    ↓ ASRConcurrencyManager
    ├─ Semaphore限流
    ├─ 重试机制
    └─ 统计信息
    ↓
ASR服务 (asr_service.py)
    ↓ transcribe_audio
远程API (asr_api_service.py)
    ↓
Whisper ASR 模型
```

## 相关文件

- **后端核心**：
  - `backend/app/services/asr_realtime.py` - 实时转录处理器
  - `backend/app/services/asr_concurrency.py` - 并发控制管理器
  - `backend/app/routers/asr_ws.py` - WebSocket路由

- **前端核心**：
  - `frontend/src/components/VoiceRecorder.tsx` - 录音组件
  - `frontend/src/styles/voice-recorder.css` - 样式文件

- **配置文件**：
  - `backend/env.example` - 环境变量示例
  - `backend/app/config.py` - 配置定义

## 更新日志

### v1.0.0 (2025-01-XX)
- ✨ 新增即录即转功能
- ✨ 添加并发控制和重试机制
- ✨ 前端UI支持实时转录开关
- 🐛 修复显存不足误报问题
- 📚 完善文档和使用说明

