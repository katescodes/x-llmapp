# LLM 配置调用链完整分析

## 调用链路

1. **ExtractionEngine** (`backend/app/platform/extraction/engine.py`)
   ```python
   out_text = await call_llm(messages, llm, model_id, temperature=spec.temperature, max_tokens=4096)
   ```

2. **LLM Adapter** (`backend/app/platform/extraction/llm_adapter.py`)
   ```python
   async def call_llm(messages, llm_orchestrator, model_id, temperature, **kwargs) -> str:
       res = llm_orchestrator.chat(messages=messages, model_id=model_id, temperature=temperature, **kwargs)
   ```

3. **SimpleLLMOrchestrator** (`backend/app/main.py`)
   ```python
   class SimpleLLMOrchestrator:
       def chat(self, messages: list, model_id: str = None, **kwargs) -> dict:
           # 1. 检查 MOCK_LLM
           if os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes"):
               return mock_response  # 返回模拟数据
           
           # 2. 获取模型配置
           if model_id:
               model = get_llm_model_by_id(model_id)
           else:
               model = get_default_llm_model()  # ← 获取默认模型
           
           # 3. 调用真实 LLM 服务
           response = httpx.Client().post(endpoint, json=payload, headers=headers)
   ```

4. **LLM Model Store** (`backend/app/services/llm_model_store.py`)
   ```python
   def get_default_llm_model() -> Optional[LLMModelStored]:
       store = get_llm_store()
       return store.get_default_model()
   
   # 从 /app/data/llm_models.json 加载配置
   ```

## 当前配置

### 配置文件: `/app/data/llm_models.json`

```json
{
  "models": [
    {
      "name": "本地默认模型",
      "base_url": "http://host.docker.internal:8001",  ← 问题所在！
      "endpoint_path": "/v1/chat/completions",
      "model": "local-llm",
      "temperature": 0.3,
      "max_tokens": 16000,
      "timeout_ms": 30000,
      "is_default": true
    }
  ],
  "default_model_id": "5a947c1f-1e37-4c24-815d-c6a468ef09c4"
}
```

## 问题分析

### ❌ 当前问题

**错误**: `httpcore.ConnectError: [Errno -2] Name or service not known`

**根因**: `http://host.docker.internal:8001` 无法解析

### 为什么会这样？

1. **`host.docker.internal` 只在 Docker Desktop 可用**
   - ✅ Windows/Mac Docker Desktop: 自动配置
   - ❌ Linux Docker: 默认不存在，需手动添加

2. **Linux Docker 解决方案**:
   - 方案 A: 使用 `--add-host=host.docker.internal:host-gateway` (docker-compose)
   - 方案 B: 使用宿主机 IP (如 `http://192.168.x.x:8001`)
   - 方案 C: 使用 Docker 网络内部服务名

3. **当前环境**: Linux (`5.4.0-216-generic`)
   - `host.docker.internal` 未配置
   - LLM 服务可能运行在宿主机或其他容器

## 环境变量

```bash
MOCK_LLM=false                              # ✓ 正确（已关闭）
LLM_STORE_PATH=/app/data/llm_models.json   # ✓ 正确
```

## 结论

### ✅ 配置加载流程正确
1. LLMModelStore 成功加载 `llm_models.json`
2. 找到默认模型（ID: 5a947c1f-1e37-4c24-815d-c6a468ef09c4）
3. SimpleLLMOrchestrator.chat() 正确获取模型配置
4. 尝试调用 `http://host.docker.internal:8001/v1/chat/completions`

### ❌ LLM 服务地址不可达
- `host.docker.internal` 在 Linux Docker 中无法解析
- 需要配置正确的 LLM 服务地址

## 解决方案

### 方案 1: 添加 host.docker.internal (推荐)

修改 `docker-compose.yml`:
```yaml
services:
  backend:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### 方案 2: 修改 LLM 配置地址

修改 `/app/data/llm_models.json`:
```json
{
  "base_url": "http://192.168.x.x:8001"  // 使用宿主机实际IP
}
```

### 方案 3: 暂时使用 MOCK 模式完成测试

设置 `MOCK_LLM=true` 以继续完成 A3-2 验证

## 下一步

请告知：
1. LLM 服务实际运行在哪里？（宿主机端口？另一个容器？）
2. 希望如何配置 LLM 地址？
3. 或者暂时使用 MOCK 模式完成 A3-2 测试？

