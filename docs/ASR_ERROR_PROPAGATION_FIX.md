# ASR 错误传播链路分析和修复

## 🔴 原问题：多层错误包装

### 用户看到的错误
```
转写失败：转写失败: 音频转录失败: ASR服务GPU显存不足，请稍后重试或联系管理员: Model actor is out of memory, model id: whisper-0, error: CUDA out of memory...
```

### 错误来源追踪

#### 层级1：Whisper服务（源头）
```json
{
  "detail": "Model actor is out of memory, model id: whisper-0, error: CUDA out of memory. Tried to allocate 1.34 GiB. GPU 0 has a total capacity of 23.57 GiB of which 229.44 MiB is free. Process 2802421 has 1.15"
}
```

#### 层级2：asr_api_service.py（第一次包装）
```python
# 文件：backend/app/services/asr_api_service.py
# 行数：第181行

if "cuda" in error_lower or "gpu" in error_lower:
    error_message = f"ASR服务GPU显存不足，请稍后重试或联系管理员: {error_detail[:200]}"

raise RuntimeError(error_message)
```

**生成错误**：
```
ASR服务GPU显存不足，请稍后重试或联系管理员: Model actor is out of memory...
```

#### 层级3：asr_service.py（第二次包装）❌
```python
# 文件：backend/app/services/asr_service.py
# 行数：第482行（修复前）

except Exception as exc:
    raise RuntimeError(f"音频转录失败: {exc}") from exc
```

**生成错误**：
```
音频转录失败: ASR服务GPU显存不足，请稍后重试或联系管理员: Model actor is out of memory...
```

#### 层级4：recordings.py（第三次包装）❌
```python
# 文件：backend/app/routers/recordings.py
# 行数：第564行（修复前）

except Exception as e:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"转写失败: {str(e)}"
    )
```

**最终错误**：
```
转写失败: 音频转录失败: ASR服务GPU显存不足，请稍后重试或联系管理员: Model actor is out of memory...
```

## ✅ 修复方案

### 原则：**异常应该直接传播，不要重复包装**

### 修复1：asr_service.py
```python
# 修复前 ❌
except Exception as exc:
    raise RuntimeError(f"音频转录失败: {exc}") from exc

# 修复后 ✅
except Exception as exc:
    logger.error("Audio transcription failed file=%s error=%s", filename, exc)
    raise  # 直接传播，不包装
```

### 修复2：recordings.py
```python
# 修复前 ❌
except Exception as e:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"转写失败: {str(e)}"
    )

# 修复后 ✅
except HTTPException:
    raise  # HTTPException 直接传播
except Exception as e:
    logger.error(f"Transcription failed: {e}", exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(e)  # 不添加前缀
    )
```

## 📊 修复前后对比

### 修复前（3层包装）
```
错误源：Model actor is out of memory...
    ↓ asr_api_service.py 包装
错误：ASR服务GPU显存不足，请稍后重试或联系管理员: Model actor is...
    ↓ asr_service.py 包装
错误：音频转录失败: ASR服务GPU显存不足，请稍后重试或联系管理员: Model actor is...
    ↓ recordings.py 包装
用户看到：转写失败: 音频转录失败: ASR服务GPU显存不足，请稍后重试或联系管理员: Model actor is...

❌ 冗长、重复、难以理解
```

### 修复后（1层包装）
```
错误源：Model actor is out of memory...
    ↓ asr_api_service.py 包装
错误：ASR服务报告显存不足，但可能是显存管理异常，建议联系管理员重启Whisper服务
    ↓ asr_service.py 直接传播
    ↓ recordings.py 直接传播
用户看到：ASR服务报告显存不足，但可能是显存管理异常，建议联系管理员重启Whisper服务

✅ 简洁、清晰、可操作
```

## 🎯 错误消息设计原则

### 1. 单一职责
- **每一层只负责自己的错误**
- 不要重复包装下层的错误

### 2. 信息完整
- **只在最接近错误源的地方包装**
- 包装时提供上下文和解决建议

### 3. 用户友好
- **避免技术术语堆叠**
- 提供明确的操作建议

### 4. 可调试性
- **保留原始错误信息**
- 使用日志记录详细堆栈

## 🔍 其他文件的错误处理

### asr_ws.py（后台任务）
```python
# 位置：backend/app/routers/asr_ws.py

except Exception as e:
    logger.error(f"Background transcription failed for {recording_id}: {e}", exc_info=True)
    # 更新数据库，但不向前端抛出（因为是后台任务）
```

✅ 正确：后台任务只记录日志，不传播给前端

### asr_realtime.py（实时转录）
```python
# 位置：backend/app/services/asr_realtime.py

except Exception as e:
    logger.error(f"[实时ASR] 转录失败: {e}")
    return ""  # 返回空字符串，不中断流程
```

✅ 正确：实时转录失败时优雅降级

## 📋 错误分类和处理策略

### 用户错误（400）
- 文件格式不支持
- 文件太大
- 参数错误

**处理**：直接返回清晰的错误消息

### 配置错误（500）
- ASR服务未配置
- 找不到可用配置

**处理**：提示管理员配置系统

### 服务错误（503/500）
- ASR服务不可用
- 网络错误
- 超时

**处理**：自动重试，提示稍后再试

### 资源错误（503）
- GPU显存不足
- 队列已满

**处理**：自动重试或排队，提示等待

## 🚀 测试验证

### 测试1：正常转录
```bash
# 预期：成功，无错误
curl -X POST http://localhost:8000/api/recordings/123/transcribe
```

### 测试2：模拟OOM
```bash
# 预期：清晰的错误提示，不重复
# "ASR服务报告显存不足，但可能是显存管理异常"
```

### 测试3：并发转录
```bash
# 预期：第二个请求排队，不会看到"转写失败: 转写失败:"
```

## 📝 总结

### 修复的问题
1. ❌ 错误消息重复嵌套
2. ❌ "转写失败: 转写失败: 音频转录失败:"
3. ❌ 冗长难懂

### 修复的效果
1. ✅ 错误消息简洁清晰
2. ✅ 直接指出问题和解决方案
3. ✅ 便于用户理解和操作

### 核心原则
> **异常应该在最接近错误源的地方包装一次，然后直接传播**

### 实施建议
1. 重启backend服务
2. 测试转录功能
3. 观察错误消息是否清晰
4. 检查日志记录是否完整

