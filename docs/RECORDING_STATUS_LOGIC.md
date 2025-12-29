# 录音状态逻辑说明

## 状态定义

录音的 `import_status` 字段用于表示录音的整体状态，包括转写和导入知识库两个阶段。

### 状态枚举

| 状态 | 前端显示 | 含义 | 触发场景 |
|------|---------|------|---------|
| `pending` | ⚠️ 未入库 | 录音已创建，转写成功（或待转写），等待导入知识库 | 1. 录音刚创建<br>2. 转写成功<br>3. 重新转写成功 |
| `importing` | ⏳ 导入中 | 正在导入知识库 | 用户点击"导入"按钮 |
| `imported` | ✅ 已入库 | 已成功导入知识库 | 导入知识库成功 |
| `failed` | ❌ 失败 | 转写失败或导入失败 | 1. 转写失败<br>2. 导入知识库失败 |

## 状态流转图

```
┌─────────────┐
│  创建录音    │
└──────┬──────┘
       │
       ▼
  ┌─────────┐
  │ pending │ ◄──────────┐
  └────┬────┘            │
       │                 │
   [自动/手动转写]    [重新转写成功]
       │                 │
       ├─[成功]──────────┘
       │
       └─[失败]─────────┐
                        │
                        ▼
                   ┌────────┐
                   │ failed │
                   └────────┘
                        │
                   [重新转写]
                        │
       ┌────────────────┘
       │
  ┌────┴────┐
  │ pending │
  └────┬────┘
       │
   [导入知识库]
       │
       ├─[开始]─────► ┌───────────┐
       │              │ importing │
       │              └─────┬─────┘
       │                    │
       │              [成功] │ [失败]
       │                    │     │
       ▼                    ▼     ▼
  ┌──────────┐        ┌──────────┐
  │ imported │        │  failed  │
  └──────────┘        └──────────┘
```

## 代码实现

### 1. 录音创建（上传音频文件）

**文件**: `backend/app/routers/recordings.py` - `upload_audio_file()`

```python
# 初始状态为 pending
import_status = "pending"
```

### 2. WebSocket录音后台转写

**文件**: `backend/app/routers/asr_ws.py` - `background_transcribe()`

```python
# 转写成功：不修改状态，保持 pending
UPDATE voice_recordings 
SET transcript = %s, word_count = %s, updated_at = CURRENT_TIMESTAMP
WHERE id = %s

# 转写失败：设置为 failed
UPDATE voice_recordings 
SET import_status = 'failed', updated_at = CURRENT_TIMESTAMP
WHERE id = %s
```

### 3. 手动转写录音

**文件**: `backend/app/routers/recordings.py` - `transcribe_recording()`

```python
# 转写成功：
# - 如果之前状态是 failed，恢复为 pending
# - 如果是其他状态，保持不变
UPDATE voice_recordings
SET transcript = %s, 
    word_count = %s,
    duration = %s,
    import_status = CASE 
        WHEN import_status = 'failed' THEN 'pending'
        ELSE import_status
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE id = %s

# 转写失败：设置为 failed
UPDATE voice_recordings
SET import_status = 'failed',
    updated_at = CURRENT_TIMESTAMP
WHERE id = %s
```

### 4. 导入知识库

**文件**: `backend/app/services/recording_service.py` - `import_recording_to_kb()`

```python
# 开始导入：设置为 importing
UPDATE voice_recordings
SET import_status = 'importing'
WHERE id = %s

# 导入成功：设置为 imported
UPDATE voice_recordings
SET 
    kb_id = %s,
    doc_id = %s,
    import_status = 'imported',
    imported_at = CURRENT_TIMESTAMP,
    ...
WHERE id = %s

# 导入失败：设置为 failed
UPDATE voice_recordings
SET import_status = 'failed'
WHERE id = %s
```

## 前端状态显示

**文件**: `frontend/src/components/RecordingsList.tsx` - `getStatusBadge()`

```typescript
const config = {
  pending: { icon: '⚠️', label: '未入库', color: '#f59e0b' },
  importing: { icon: '⏳', label: '导入中', color: '#3b82f6' },
  imported: { icon: '✅', label: '已入库', color: '#22c55e' },
  failed: { icon: '❌', label: '失败', color: '#ef4444' },
};
```

## 常见场景

### 场景1: 新建录音 → 转写成功 → 导入成功

```
pending (创建) 
  → pending (转写成功，保持pending等待导入)
  → importing (开始导入)
  → imported (导入成功)
```

### 场景2: 新建录音 → 转写失败 → 重新转写成功 → 导入成功

```
pending (创建)
  → failed (转写失败)
  → pending (重新转写成功)
  → importing (开始导入)
  → imported (导入成功)
```

### 场景3: 新建录音 → 转写成功 → 导入失败 → 不重新转写 → 重新导入成功

```
pending (创建)
  → pending (转写成功)
  → importing (开始导入)
  → failed (导入失败)
  → importing (重新导入)
  → imported (导入成功)
```

### 场景4: 上传音频文件 → 手动转写 → 导入

```
pending (上传文件，待转写)
  → pending (手动转写成功)
  → importing (导入)
  → imported (导入成功)
```

## 重要注意事项

1. **转写成功不改变状态**：转写成功后状态保持为 `pending`，因为用户可能还想修改标题、标签等再导入。

2. **失败后重新转写**：如果录音状态为 `failed`（转写失败），重新转写成功后会自动恢复为 `pending`。

3. **`failed` 状态的两种含义**：
   - 转写失败：调用ASR服务失败
   - 导入失败：导入知识库过程失败

4. **区分转写和导入**：
   - 转写：将音频转换为文字（`transcript` 字段）
   - 导入：将转写文本导入知识库（`kb_id`、`doc_id` 字段）

## 修复历史

### 2025-12-29: 修复手动转写时状态未更新的问题

**问题**：
- 手动转写失败时，`import_status` 没有更新为 `failed`
- 导致前端显示错误的状态（仍显示为 `pending` 或其他状态）

**修复**：
1. 在 `transcribe_recording()` 的异常处理中添加状态更新逻辑
2. 转写成功时，如果之前状态是 `failed`，自动恢复为 `pending`

**相关文件**：
- `backend/app/routers/recordings.py`

