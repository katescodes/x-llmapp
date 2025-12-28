# 知识库无法加载问题解决方案

## 问题原因

从日志可以看到：
```
GET /api/kb HTTP/1.1" 403 Forbidden
GET /api/kb-categories HTTP/1.1" 403 Forbidden
```

这是因为：**用户未登录或认证token无效**

## 解决步骤

### 1. 检查登录状态

在浏览器中：
1. 打开开发者工具 (F12)
2. 切换到 **Console** 标签
3. 输入并执行：
```javascript
console.log('Token:', localStorage.getItem('token'));
console.log('User:', localStorage.getItem('user'));
```

### 2. 重新登录

如果token为空或无效：

1. **访问登录页面**：
   - 在浏览器地址栏输入：`http://192.168.2.17:6173`
   - 或者在页面上找到"登录"按钮

2. **使用管理员账号登录**：
   - 用户名：`admin`
   - 密码：（你设置的管理员密码）

3. **登录后刷新页面**

### 3. 验证权限

登录成功后，在开发者工具Console中执行：
```javascript
fetch('/api/kb', {
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(r => r.json())
.then(data => console.log('知识库列表:', data))
.catch(err => console.error('错误:', err));
```

应该能看到知识库列表。

### 4. 清除缓存并重新登录

如果还是不行，执行以下步骤：

1. **清除浏览器存储**：
```javascript
localStorage.clear();
sessionStorage.clear();
```

2. **清除浏览器缓存**：
   - 按 `Ctrl + Shift + Delete`
   - 选择"缓存的图片和文件"
   - 点击"清除数据"

3. **刷新页面并重新登录**：
   - 按 `Ctrl + Shift + R` 强制刷新
   - 重新登录

### 5. 检查后端日志

如果登录后仍然403，检查后端日志：
```bash
docker-compose logs backend --tail=50 | grep -E "auth|permission"
```

## 快速解决脚本

在浏览器Console中执行：
```javascript
// 1. 检查当前状态
console.log('=== 当前认证状态 ===');
console.log('Token:', localStorage.getItem('token') ? '已设置' : '未设置');

// 2. 测试API
fetch('/api/permissions/me/permissions')
  .then(r => {
    console.log('权限API状态:', r.status);
    return r.json();
  })
  .then(data => console.log('我的权限:', data))
  .catch(err => console.error('错误:', err));

// 3. 测试知识库API
fetch('/api/kb')
  .then(r => {
    console.log('知识库API状态:', r.status);
    return r.json();
  })
  .then(data => console.log('知识库:', data))
  .catch(err => console.error('错误:', err));
```

## 预期结果

登录成功后，应该看到：
- ✅ 知识库列表正常显示
- ✅ 可以创建知识库
- ✅ 可以上传文档
- ✅ 招投标按钮正常显示

## 管理员默认密码

如果忘记管理员密码，可以重置：

```bash
docker-compose exec backend python -c "
from app.services.db.postgres import _get_pool
from app.utils.auth import hash_password

pool = _get_pool()
new_password = 'Admin@123'  # 修改为你想要的密码
hashed = hash_password(new_password)

with pool.connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE users SET password_hash = %s WHERE username = %s',
            (hashed, 'admin')
        )
        conn.commit()
        print(f'管理员密码已重置为: {new_password}')
"
```

## 常见问题

### Q: 登录后还是403
**A**: 检查用户角色和权限配置，确保管理员有所有权限

### Q: 找不到登录入口
**A**: 直接访问：`http://192.168.2.17:6173/login`

### Q: 登录后自动退出
**A**: 检查token过期时间，可能需要延长过期时间

### Q: 知识库显示但无法操作
**A**: 检查具体权限，需要 `kb:read` 和 `kb:write` 权限

## 联系支持

如果以上方法都无法解决，请提供：
1. 浏览器Console的完整输出
2. 后端日志（`docker-compose logs backend --tail=100`）
3. 用户信息（不包括密码）

