# 404静态资源加载问题修复指南

## 📋 问题描述

通过域名外网访问时出现以下错误：
```
Failed to load resource: the server responded with a status of 404 (Not Found)
index-BfLXJDHc.css:1
```

## 🔍 根本原因

1. **浏览器缓存了旧版本的 `index.html`**
2. **旧的HTML文件引用了已经不存在的CSS/JS文件**
3. **Docker容器已经更新，但浏览器还在使用缓存**

当前容器内的正确资源文件：
- `/assets/index-BfLXJDHc.css` ✅
- `/assets/index-DC0P0fOc.js` ✅

## ✅ 解决方案

### 方案1：清除浏览器缓存（推荐）

#### Chrome/Edge浏览器：
1. 按 `F12` 打开开发者工具
2. 右键点击浏览器刷新按钮
3. 选择 **"清空缓存并硬性重新加载"**

或者：
1. 按 `Ctrl + Shift + Delete` (Windows) 或 `Cmd + Shift + Delete` (Mac)
2. 选择 **"缓存的图像和文件"**
3. 时间范围选择 **"过去1小时"** 或 **"全部"**
4. 点击 **"清除数据"**

#### Firefox浏览器：
1. 按 `Ctrl + Shift + Delete`
2. 选择 **"缓存"**
3. 点击 **"立即清除"**

#### Safari浏览器：
1. 按 `Cmd + Option + E` 清空缓存
2. 或在菜单栏：开发 → 清空缓存

### 方案2：使用无痕/隐私模式访问

直接使用浏览器的无痕模式访问您的域名，避免缓存问题。

### 方案3：添加版本号参数（临时）

在地址栏添加版本参数强制刷新：
```
https://your-domain.com/?v=20251228
```

### 方案4：Nginx层强制禁用HTML缓存（已配置）

当前 `frontend/nginx.conf` 已配置禁用 `index.html` 缓存：

```nginx
# 禁用 index.html 的缓存
location = /index.html {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header Pragma "no-cache";
    add_header Expires "0";
}
```

**但是**，如果浏览器已经缓存了旧版本，这个配置只在首次访问时生效。

## 🔧 预防措施

### 1. 确保Nginx配置正确

检查 `frontend/nginx.conf` 包含以下配置：

```nginx
# 禁用 index.html 的缓存
location = /index.html {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header Pragma "no-cache";
    add_header Expires "0";
}

# 缓存静态资源（但index.html除外）
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### 2. 如果使用外部反向代理

如果在前端容器外还有nginx反向代理（如 `nginx_proxy` 容器），需要确保：

```nginx
# 示例：外部nginx反向代理配置
location / {
    proxy_pass http://localgpt-frontend:5173;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # 禁用代理层的缓存
    proxy_buffering off;
    proxy_cache_bypass $http_pragma $http_authorization;
    proxy_no_cache $http_pragma $http_authorization;
    
    # 允许HTML不被缓存
    add_header Cache-Control "no-cache" always;
}

# 静态资源可以缓存
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    proxy_pass http://localgpt-frontend:5173;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### 3. 重新构建和部署

每次更新前端代码后：

```bash
# 1. 重新构建镜像（无缓存）
cd /aidata/x-llmapp1
docker-compose build --no-cache frontend

# 2. 重启容器
docker-compose restart frontend

# 3. 验证容器内文件
docker exec localgpt-frontend ls -la /usr/share/nginx/html/assets/
docker exec localgpt-frontend cat /usr/share/nginx/html/index.html
```

## 📊 验证步骤

### 1. 检查容器状态
```bash
docker ps | grep frontend
```

### 2. 检查容器内文件
```bash
docker exec localgpt-frontend cat /usr/share/nginx/html/index.html
docker exec localgpt-frontend ls -la /usr/share/nginx/html/assets/
```

### 3. 测试本地访问
```bash
curl -I http://localhost:6173/
curl -I http://localhost:6173/assets/index-BfLXJDHc.css
```

### 4. 检查响应头
使用浏览器开发者工具（F12）→ Network标签：
- 查看 `index.html` 的响应头，确认包含 `Cache-Control: no-cache`
- 查看CSS/JS文件的响应头，确认返回 `200 OK`

## 🚨 常见问题

### Q1: 清除缓存后仍然404
**A:** 检查是否有CDN或其他缓存层：
- 如果使用了CDN，需要清除CDN缓存
- 检查是否有反向代理缓存配置

### Q2: 本地访问正常，外网访问异常
**A:** 可能的原因：
1. 外部反向代理配置问题
2. 防火墙或安全组配置
3. DNS缓存问题

### Q3: 每次更新都要手动清缓存太麻烦
**A:** 可以使用以下方法：
1. 在Vite配置中启用文件hash（已启用）
2. 确保nginx不缓存HTML文件（已配置）
3. 使用Service Worker进行版本管理

## 📝 技术细节

### Vite构建输出
```
dist/index.html                   0.43 kB
dist/assets/index-BfLXJDHc.css   47.88 kB
dist/assets/index-DC0P0fOc.js   648.27 kB
```

文件名中的hash值（如 `BfLXJDHc`）会随内容变化而变化，确保浏览器加载最新版本。

### Docker构建流程
```dockerfile
# 构建阶段
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# 生产阶段
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
```

## 🎯 总结

**主要原因**：浏览器缓存了旧版本的HTML文件

**最快解决**：清除浏览器缓存并硬性刷新（Ctrl+Shift+R 或 Cmd+Shift+R）

**长期预防**：
1. ✅ 已配置nginx禁用HTML缓存
2. ✅ Vite自动生成带hash的资源文件名
3. 🔄 如有外部代理，确保正确配置缓存策略

---

**修复日期**: 2025-12-28  
**相关文件**: `frontend/nginx.conf`, `frontend/Dockerfile`, `vite.config.ts`

