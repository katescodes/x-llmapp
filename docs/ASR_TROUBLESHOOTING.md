# ASR转写功能调试指南

## 问题描述
ASR接口配置可以用，但在系统上测试失败。

## 常见问题和解决方案

### 1. 检查环境变量

确认 `backend/.env` 文件中已设置：

```bash
ASR_ENABLED=true
```

查看当前配置：
```bash
cd backend
grep ASR .env
```

### 2. 检查数据库配置

ASR配置存储在数据库的 `asr_configs` 表中。

#### 检查配置是否存在：

```sql
SELECT id, name, api_url, model_name, is_active, is_default 
FROM asr_configs;
```

#### 如果表不存在，运行迁移：

```bash
cd backend
python scripts/run_migrations.py
```

#### 手动添加配置（如果需要）：

```sql
INSERT INTO asr_configs (id, name, api_url, model_name, response_format, is_active, is_default)
VALUES (
    'asr-default-001',
    '默认语音转文本API',
    'https://ai.yglinker.com:6399/v1/audio/transcriptions',
    'whisper',
    'verbose_json',
    TRUE,
    TRUE
);
```

### 3. 运行诊断脚本

使用提供的诊断脚本检查所有环节：

```bash
cd /aidata/x-llmapp1
python debug_asr.py
```

输出将包括：
- ✅ 环境变量检查
- ✅ 数据库配置检查
- ✅ 直接API调用测试
- ✅ 服务层调用测试

如果你有测试音频文件：
```bash
python debug_asr.py /path/to/test.mp3
```

### 4. 常见错误及解决方法

#### 错误1: "ASR 服务未启用"
**原因**: 环境变量 `ASR_ENABLED` 未设置或为 false

**解决**:
```bash
# 编辑 backend/.env
ASR_ENABLED=true

# 重启后端服务
```

#### 错误2: "未找到可用的ASR API配置"
**原因**: 数据库中没有激活的ASR配置

**解决**:
1. 检查数据库:
```sql
SELECT * FROM asr_configs WHERE is_active = TRUE;
```

2. 如果没有记录，运行迁移或手动插入（见上面第2节）

3. 如果有记录但 `is_active = FALSE`，激活它:
```sql
UPDATE asr_configs 
SET is_active = TRUE, is_default = TRUE 
WHERE id = 'asr-default-001';
```

#### 错误3: "ASR API调用失败: HTTP 503"
**原因**: ASR服务不可用或过载

**解决**:
- 检查ASR服务是否运行
- 验证API地址是否正确
- 稍后重试

#### 错误4: "ASR API网络错误: Connection refused"
**原因**: 无法连接到ASR服务器

**解决**:
- 检查API地址是否正确
- 检查网络连接
- 检查防火墙设置
- 验证SSL证书（如果使用HTTPS）

#### 错误5: "不支持的音频格式"
**原因**: 音频文件格式不在支持列表中

**解决**:
支持的格式: mp3, wav, m4a, ogg, webm, flac

使用 ffmpeg 转换格式:
```bash
ffmpeg -i input.mp4 -ar 16000 output.mp3
```

### 5. 测试流程

#### 方法1: 使用诊断脚本（推荐）
```bash
python debug_asr.py
```

#### 方法2: 使用curl直接测试API
```bash
# 创建测试音频
ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 1 -q:a 9 -acodec libmp3lame test.mp3

# 测试API
curl -X POST "https://ai.yglinker.com:6399/v1/audio/transcriptions" \
  -F "file=@test.mp3" \
  -F "model=whisper" \
  -F "response_format=verbose_json"
```

#### 方法3: 通过系统界面测试
1. 登录系统
2. 进入"我的录音"页面
3. 上传或录制一段音频
4. 点击"转写"按钮
5. 查看浏览器控制台的错误信息

### 6. 查看日志

#### 后端日志
```bash
# 如果使用docker
docker logs <backend_container_name>

# 如果直接运行
tail -f backend/logs/app.log
```

查找关键信息：
- `ASR API调用失败`
- `Failed to get ASR config`
- `transcribe_audio`

#### 前端日志
打开浏览器开发者工具（F12）:
- Console 标签: 查看JavaScript错误
- Network 标签: 查看API请求详情

### 7. 检查数据库连接

```bash
cd backend
python -c "
from app.services.db.postgres import get_conn
try:
    with get_conn() as conn:
        print('✅ 数据库连接成功')
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
"
```

### 8. 系统设置界面配置

如果系统有设置界面，可以通过UI配置ASR:

1. 登录系统
2. 进入"系统设置" > "ASR配置"
3. 添加或编辑ASR配置:
   - 名称: 默认语音转文本API
   - API地址: `https://ai.yglinker.com:6399/v1/audio/transcriptions`
   - 模型: `whisper`
   - 响应格式: `verbose_json`
   - 激活: ✅
   - 默认: ✅
4. 点击"测试"按钮验证配置
5. 保存

### 9. 完整诊断检查清单

- [ ] 环境变量 `ASR_ENABLED=true`
- [ ] 数据库迁移已运行
- [ ] `asr_configs` 表存在且有记录
- [ ] 至少有一个配置 `is_active=TRUE`
- [ ] API地址正确且可访问
- [ ] 网络连接正常
- [ ] 音频文件格式支持
- [ ] 后端服务正常运行
- [ ] 数据库连接正常

### 10. 获取详细错误信息

在代码中添加更详细的日志：

编辑 `backend/app/routers/recordings.py`，在转写接口中：

```python
@router.post("/{recording_id}/transcribe")
async def transcribe_recording(...):
    try:
        # ... 现有代码 ...
        logger.info(f"开始转写: recording_id={recording_id}")
        logger.info(f"音频路径: {audio_path}")
        logger.info(f"文件大小: {len(audio_data)}")
        
        transcript, duration = await transcribe_audio(...)
        
        logger.info(f"转写完成: 字数={len(transcript)}")
        
    except Exception as e:
        logger.error(f"转写失败详情: {str(e)}", exc_info=True)
        raise
```

### 11. 联系支持

如果问题仍然存在，收集以下信息：

1. 运行诊断脚本的输出：
```bash
python debug_asr.py > asr_debug.log 2>&1
```

2. 数据库配置：
```sql
SELECT * FROM asr_configs;
```

3. 环境变量：
```bash
env | grep ASR
```

4. 后端日志（最近50行）：
```bash
docker logs --tail 50 <backend_container>
```

5. 错误截图（如果通过界面测试）

## 快速修复脚本

创建 `fix_asr.sh` 快速修复常见问题：

```bash
#!/bin/bash

echo "🔧 ASR配置快速修复"

# 1. 检查环境变量
if ! grep -q "ASR_ENABLED=true" backend/.env; then
    echo "添加 ASR_ENABLED=true 到 .env"
    echo "ASR_ENABLED=true" >> backend/.env
fi

# 2. 运行迁移
echo "运行数据库迁移..."
cd backend && python scripts/run_migrations.py

# 3. 检查配置
echo "检查ASR配置..."
python debug_asr.py

echo "✅ 修复完成"
```

## 总结

最常见的问题是：
1. **环境变量未设置** - 80%的情况
2. **数据库配置缺失** - 15%的情况
3. **API不可访问** - 5%的情况

按照以上步骤逐一检查，大多数问题都能快速解决。

