# ASR 转写失败：GPU 显存不足（CUDA OOM）

## 错误信息

```
ASR API调用失败: HTTP 500
Model actor is out of memory, model id: whisper-0
CUDA out of memory. Tried to allocate 1.34 GiB. 
GPU 0 has a total capacity of 23.57 GiB of which 11.44 MiB is free.
Process 2886328 has 21.22 GiB memory in use.
```

## 问题原因

远程 ASR API 服务器（`https://ai.yglinker.com:6399`）的 GPU 显存已满：
- GPU 总容量：23.57 GiB
- 已使用：21.22 GiB
- 可用：仅 11.44 MiB
- Whisper 模型需要：1.34 GiB

## 当前配置

```sql
ASR API: https://ai.yglinker.com:6399/v1/audio/transcriptions
模型: whisper
状态: 已激活，默认配置
```

## 解决方案

### 方案 1：重启远程 ASR API 服务（推荐） ⭐

登录到运行 ASR API 的服务器（`ai.yglinker.com`），执行：

#### 步骤 1：查看 GPU 使用情况
```bash
nvidia-smi
```

#### 步骤 2：找到占用 GPU 的进程
```bash
# 查看进程 2886328 的详细信息
ps aux | grep 2886328
```

#### 步骤 3：重启 ASR API 服务
根据您的部署方式选择：

**如果使用 Docker：**
```bash
docker ps | grep whisper
docker restart <容器名称或ID>
```

**如果使用 Docker Compose：**
```bash
cd /path/to/whisper-api
docker-compose restart
```

**如果使用 Systemd：**
```bash
sudo systemctl restart whisper-api
# 或
sudo systemctl restart vllm-whisper
```

**如果是 Python 进程：**
```bash
# 找到进程
ps aux | grep whisper | grep python

# 杀掉进程（慎重！）
sudo kill -9 2886328

# 重新启动服务
# (根据您的启动脚本)
```

#### 步骤 4：验证服务已恢复
```bash
# 查看 GPU 显存是否已释放
nvidia-smi

# 测试 API 是否正常
curl -X POST https://ai.yglinker.com:6399/v1/audio/transcriptions \
  -F "file=@test.wav" \
  -F "model=whisper"
```

### 方案 2：清理 GPU 显存

如果无法重启服务，可以尝试：

```bash
# 1. 查看占用 GPU 的所有进程
nvidia-smi

# 2. 使用 fuser 杀掉占用 GPU 的进程
sudo fuser -k /dev/nvidia0

# 3. 或手动杀掉特定进程
sudo kill -9 2886328

# 4. 清理 GPU 缓存
nvidia-smi --gpu-reset
```

### 方案 3：配置多个 ASR API（负载均衡）

如果您有多个 ASR API 服务器，可以配置多个 API：

1. 打开系统设置页面
2. 导航到"语音转文本配置"
3. 添加新的 ASR API 配置
4. 当一个服务不可用时，系统会自动尝试其他配置

### 方案 4：使用较小的 Whisper 模型

修改 ASR API 配置，使用较小的模型：

**数据库更新：**
```sql
UPDATE asr_configs 
SET model_name = 'whisper-tiny'  -- 或 'whisper-base', 'whisper-small'
WHERE id = 'asr-default-001';
```

**模型大小对比：**
- `whisper-tiny`: ~39M 参数，~1GB 显存
- `whisper-base`: ~74M 参数，~1.5GB 显存
- `whisper-small`: ~244M 参数，~2GB 显存
- `whisper-medium`: ~769M 参数，~5GB 显存
- `whisper-large`: ~1550M 参数，~10GB 显存

## 临时解决方案：使用本地 ASR

如果远程服务长期不可用，可以配置本地 ASR 服务：

### 使用 OpenAI Compatible API

```bash
# 1. 在数据库中添加新配置
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
INSERT INTO asr_configs (id, name, api_url, model_name, is_active, is_default)
VALUES (
  'asr-local-001',
  '本地语音转文本',
  'http://host.docker.internal:8000/v1/audio/transcriptions',
  'whisper-small',
  true,
  true
);
"

# 2. 禁用原有配置
docker-compose exec -T postgres psql -U localgpt -d localgpt -c "
UPDATE asr_configs SET is_default = false WHERE id = 'asr-default-001';
"
```

### 使用 FunASR（国产开源）

FunASR 是阿里开源的语音识别系统，支持中文：

```bash
# 拉取 FunASR Docker 镜像
docker pull registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:latest

# 运行 FunASR 服务
docker run -d --name funasr \
  -p 10095:10095 \
  registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:latest
```

## 预防措施

### 1. 设置 GPU 显存限制

在 ASR API 服务的启动配置中：

```bash
# 限制 PyTorch 使用的 GPU 显存
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,max_split_size_mb:512
```

### 2. 启用显存回收

在 Python 代码中：

```python
import torch
torch.cuda.empty_cache()  # 定期清理显存
```

### 3. 使用批处理限制

限制并发转写请求数量，避免多个请求同时占用显存。

### 4. 监控 GPU 使用

设置监控告警：

```bash
# 安装 GPU 监控
pip install gpustat

# 每分钟检查一次
watch -n 60 gpustat
```

## 验证修复

重启服务后，在系统设置页面：

1. 进入"系统设置" → "语音转文本"
2. 点击"测试连接"按钮
3. 查看是否显示"测试成功"

或在录音列表中：
1. 选择一个待转写的录音
2. 点击"转写"按钮
3. 等待转写完成

## 联系支持

如果问题持续存在，请联系 ASR API 服务管理员或提供：
- GPU 使用情况截图（`nvidia-smi`）
- ASR API 服务日志
- 进程占用情况（`ps aux | grep 2886328`）

