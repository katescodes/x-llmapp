# "权限不足"错误排查指南

## 错误信息
```
项目信息开始抽取：抽取失败: Error: 权限不足
```

## 可能原因及解决方案

### 1. Token已过期 ⏰（最可能）

**现象**：
- 登录后一段时间（24小时）自动退出
- 操作时提示"权限不足"

**解决方案**：
```bash
# 方法1：刷新页面重新登录
1. 按 F5 刷新页面
2. 重新登录（admin/admin123）
3. 重试抽取操作

# 方法2：清除浏览器缓存
1. 按 F12 打开开发者工具
2. Application → Storage → Clear site data
3. 刷新页面重新登录
```

---

### 2. Token未正确存储 💾

**检查方法**：
```javascript
// 在浏览器控制台（F12）执行：
console.log('Token:', localStorage.getItem('auth_token'));

// 应该看到类似输出：
// Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**如果没有token**：
1. 退出登录
2. 清除浏览器缓存
3. 重新登录

---

### 3. 网络请求未携带Authorization头 🌐

**检查方法**：
```javascript
// 1. 打开开发者工具（F12）
// 2. 切换到 Network 标签
// 3. 点击"开始抽取"
// 4. 找到 POST /api/apps/tender/projects/.../extract/project-info
// 5. 查看 Request Headers

// 应该包含：
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**如果缺少Authorization头**：
- 这是前端代码bug，需要修复

---

### 4. 后端认证配置问题 🔧

**测试后端API**：
```bash
# 1. 获取token
curl -s http://localhost:9001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access_token'

# 2. 使用token测试API（替换YOUR_TOKEN）
curl -s http://localhost:9001/api/apps/tender/projects \
  -H "Authorization: Bearer YOUR_TOKEN"

# 如果返回项目列表 → 后端正常 ✅
# 如果返回401/403 → 后端认证有问题 ❌
```

---

## 快速修复步骤

### 步骤1：强制重新登录
```bash
1. 打开浏览器开发者工具（F12）
2. 在Console标签执行：
   localStorage.clear();
   location.reload();
3. 重新登录
4. 重试抽取操作
```

### 步骤2：检查token有效性
```bash
# 在浏览器Console执行：
const token = localStorage.getItem('auth_token');
if (!token) {
  console.error('❌ Token不存在，请重新登录');
} else {
  // 解析JWT token
  const payload = JSON.parse(atob(token.split('.')[1]));
  const exp = new Date(payload.exp * 1000);
  const now = new Date();
  console.log('Token过期时间:', exp.toLocaleString());
  console.log('当前时间:', now.toLocaleString());
  console.log('是否过期:', now > exp ? '❌ 是' : '✅ 否');
}
```

### 步骤3：测试API调用
```bash
# 在浏览器Console执行：
const token = localStorage.getItem('auth_token');
fetch('/api/apps/tender/projects', {
  headers: { 'Authorization': `Bearer ${token}` }
})
.then(r => r.json())
.then(d => console.log('✅ API调用成功:', d))
.catch(e => console.error('❌ API调用失败:', e));
```

---

## 代码层面的修复

### 前端：确保token正确发送

**文件**：`frontend/src/config/api.ts`

当前实现：
```typescript
function getToken(): string {
  return localStorage.getItem('auth_token') || 
         localStorage.getItem('access_token') || 
         localStorage.getItem('token') || 
         '';
}

async function request(path: string, options: RequestOptions = {}): Promise<any> {
  const token = getToken();
  const headers: Record<string, string> = { ...(options.headers as any) };
  
  // 自动添加 Authorization header
  if (token && !options.skipAuth) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  // ... rest of the code
}
```

**验证点**：
- ✅ `getToken()`能正确获取token
- ✅ Authorization头格式为`Bearer <token>`
- ✅ 所有API调用都使用`api.get/post/put/delete`

---

### 后端：确保认证依赖正确

**文件**：`backend/app/routers/tender.py`

当前实现：
```python
@router.post("/projects/{project_id}/extract/project-info")
def extract_project_info(
    project_id: str,
    req: ExtractReq,
    request: Request,
    bg: BackgroundTasks,
    sync: int = 0,
    user=Depends(get_current_user_sync),  # ✅ 已添加认证依赖
):
    # ...
```

**验证点**：
- ✅ 接口使用了`Depends(get_current_user_sync)`
- ✅ `get_current_user_sync`从`HTTPAuthorizationCredentials`获取token
- ✅ Token格式为`Bearer <jwt_token>`

---

## 常见问题FAQ

### Q1: 为什么会突然提示"权限不足"？
**A**: Token有24小时有效期，过期后需要重新登录。

### Q2: 刷新页面后还是提示"权限不足"？
**A**: 说明token已失效，需要清除localStorage并重新登录。

### Q3: 其他功能正常，只有"开始抽取"提示"权限不足"？
**A**: 可能是：
- 该接口特别敏感，需要更高权限
- 前端调用该接口时没有正确传递token
- 建议：检查Network标签，看该请求是否携带Authorization头

### Q4: 如何避免频繁重新登录？
**A**: 当前token有效期是24小时，如果需要延长：
```python
# backend/app/utils/auth.py
# 修改 ACCESS_TOKEN_EXPIRE_DAYS
ACCESS_TOKEN_EXPIRE_DAYS = 7  # 改为7天
```

---

## 监控和日志

### 前端日志
```javascript
// 在api.ts中添加日志
console.log('[API] Request:', path, {
  method: options.method,
  hasToken: !!token,
  headers: headers
});
```

### 后端日志
```python
# 在backend/app/utils/auth.py中添加
import logging
logger = logging.getLogger(__name__)

def decode_access_token(token: str) -> TokenData:
    logger.info(f"Decoding token: {token[:20]}...")
    # ...
```

---

## 总结

**最快解决方案**：
```bash
1. F12打开开发者工具
2. Console执行：localStorage.clear(); location.reload();
3. 重新登录（admin/admin123）
4. 重试操作
```

**如果还是不行**：
1. 检查后端日志：`docker logs localgpt-backend --tail 50`
2. 查看是否有认证相关错误
3. 提供错误日志以进一步诊断

---

**修复时间**：2025-12-25  
**状态**：排查指南已创建  
**建议**：先尝试重新登录

