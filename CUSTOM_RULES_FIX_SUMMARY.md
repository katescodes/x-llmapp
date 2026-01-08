# 自定义规则创建失败问题 - 修复总结

## 🔍 问题描述
用户反馈："**招投标-自定义规则-创建规则包失败：[object Object]**"

## 🐛 根本原因分析

经过系统性排查，发现了**3个关键问题**：

### 1. **后端 Schema 验证错误（422）**
- **问题**：`CustomRulePackCreateReq` 中 `project_id` 被定义为必填字段
- **影响**：前端传 `null`（共享规则包）时被 FastAPI 拒绝，返回 `422 Unprocessable Entity`
- **修复**：改为 `Optional[str]`，允许 `null` 值

### 2. **LLM 调用失败 - SOCKS 代理依赖缺失**
- **问题**：系统环境配置了 `ALL_PROXY=socks5://127.0.0.1:1080`，但缺少 `socksio` 依赖包
- **影响**：`httpx.Client` 尝试使用 SOCKS 代理时报错
- **修复**：对内网地址（192.168.x.x）设置 `trust_env=False`，禁用环境变量代理

### 3. **LLM 调用失败 - SSL 证书验证失败**
- **问题**：LLM 服务器（192.168.2.17）使用自签名证书，IP 地址不匹配
- **影响**：SSL 验证失败，无法调用 LLM
- **修复**：对内网地址设置 `verify=False`，跳过 SSL 验证

### 4. **前端错误展示问题**
- **问题**：直接使用 `err.response?.data?.detail` 时，如果 `detail` 是对象会显示 `[object Object]`
- **影响**：用户看不到具体错误信息
- **修复**：添加 `extractErrorMessage()` 函数，正确处理各种错误格式

## 🛠️ 修复内容

### 后端修改

#### 1. `backend/app/schemas/custom_rules.py`
```python
# 修复前
project_id: str = Field(..., description="项目ID")

# 修复后
project_id: Optional[str] = Field(None, description="项目ID（可选，不传则创建共享规则包）")
```

#### 2. `backend/app/services/llm_client.py`
```python
# 新增：对内网地址禁用代理和SSL验证
from urllib.parse import urlparse
parsed_url = urlparse(profile.base_url)
hostname = parsed_url.hostname or ""

is_internal = (
    hostname.startswith("192.168.") or
    hostname.startswith("10.") or
    hostname.startswith("172.") or
    hostname == "localhost" or
    hostname == "127.0.0.1"
)

trust_env = not is_internal  # 内网地址不使用环境变量代理
verify_ssl = not is_internal  # 内网地址跳过SSL验证

with httpx.Client(timeout=300.0, trust_env=trust_env, verify=verify_ssl) as client:
    # ... LLM调用逻辑
```

#### 3. `backend/app/services/custom_rule_service.py`
```python
# 新增：正确处理 HTTPException
except HTTPException as e:
    logger.error(f"AI 分析规则失败（LLM调用失败）: {e.detail}", exc_info=True)
    raise ValueError(f"AI 分析规则失败: {e.detail}")
```

#### 4. `backend/app/routers/custom_rules.py`
```python
# 新增：路由层异常处理
try:
    service = _get_service(request)
    rule_pack = service.create_rule_pack(...)
    return rule_pack
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    raise HTTPException(status_code=500, detail=f"创建规则包失败：{str(e)}")
```

### 前端修改

#### `frontend/src/components/CustomRulesPage.tsx`
```typescript
// 新增：通用错误提取函数
const extractErrorMessage = (err: any): string => {
  if (err.response?.data) {
    const detail = err.response.data.detail;
    if (typeof detail === 'string') {
      return detail;
    } else if (detail && typeof detail === 'object') {
      // 处理结构化错误（如Pydantic验证错误）
      if (Array.isArray(detail)) {
        return detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ');
      } else {
        return JSON.stringify(detail, null, 2);
      }
    } else if (err.response.data.message) {
      return err.response.data.message;
    }
  }
  if (err.message) {
    return err.message;
  }
  return '未知错误';
};

// 统一更新所有错误处理
const errorMsg = extractErrorMessage(err);
alert(`创建规则包失败：\n${errorMsg}`);
```

## ✅ 测试验证

### 1. LLM 接口测试
```bash
$ python3 /tmp/test_llm_json.py
✅ 成功！
返回类型: <class 'dict'>
返回内容: {'rules': [{'rule_key': 'test_rule', ...}]}
```

### 2. 创建规则包测试
```bash
$ docker exec localgpt-backend python3 -c "..."
✅ 创建成功！
规则包ID: 32136b12-f5cd-4c52-9f26-f6c19df45d5b
规则包名称: 测试规则包_1767841677
规则数量: 2
```

## 📊 修复效果

| 问题 | 修复前 | 修复后 |
|------|--------|--------|
| Schema 验证 | ❌ 422 错误 | ✅ 正常通过 |
| LLM 调用 | ❌ SOCKS/SSL 错误 | ✅ 正常调用 |
| 错误展示 | ❌ [object Object] | ✅ 清晰错误信息 |
| 规则包创建 | ❌ 失败 | ✅ 成功（生成2条规则）|

## 🚀 使用说明

现在可以正常使用"自定义规则"功能：

1. **访问路径**：招投标工作台 → 自定义规则
2. **创建规则包**：
   - 输入规则包名称
   - 输入规则要求（自然语言）
   - 点击"创建规则包"
   - AI 自动分析并生成结构化规则

3. **错误处理**：
   - 如果失败，会显示详细的错误信息
   - 常见错误：LLM 服务不可用、规则解析失败、数据库错误

## 🔧 已部署

- ✅ 后端代码已更新并重新构建镜像
- ✅ Backend 容器已重启
- ✅ 功能测试通过

---

**修复完成时间**：2026-01-08  
**测试状态**：✅ 通过  
**部署状态**：✅ 已部署
