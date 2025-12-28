# Docker Compose 编译和部署指南

## 前提条件

1. 已安装 Docker 和 Docker Compose
2. 已创建 Docker 网络：`docker network create localgpt-net`
3. 项目根目录存在 `.env` 文件（包含环境变量配置）

## 编译步骤

### 1. 完整构建（不使用缓存）

```bash
cd /aidata/x-llmapp1
docker-compose build --no-cache
```

适用场景：
- 首次构建
- 依赖项有重大更新
- 需要确保完全重新构建

### 2. 快速构建（使用缓存）

```bash
cd /aidata/x-llmapp1
docker-compose build
```

适用场景：
- 代码变更后重新构建
- 日常开发迭代
- 仅部分文件更新

### 3. 构建特定服务

```bash
# 只构建后端
docker-compose build backend

# 只构建前端
docker-compose build frontend

# 只构建 worker
docker-compose build worker
```

## 启动服务

### 1. 启动所有服务

```bash
docker-compose up -d
```

参数说明：
- `-d`: 后台运行（detached mode）
- 不加 `-d`: 前台运行，可以看到实时日志

### 2. 启动特定服务

```bash
# 只启动后端和数据库
docker-compose up -d backend postgres redis

# 只启动前端
docker-compose up -d frontend
```

### 3. 查看服务状态

```bash
docker-compose ps
```

### 4. 查看服务日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 查看最近100行日志
docker-compose logs --tail=100 backend
```

## 停止和清理

### 1. 停止服务

```bash
# 停止所有服务
docker-compose stop

# 停止特定服务
docker-compose stop backend
```

### 2. 停止并删除容器

```bash
docker-compose down
```

### 3. 完全清理（包括数据卷）

```bash
# ⚠️ 警告：这会删除所有数据！
docker-compose down -v
```

## 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart backend
```

## 更新和重新部署

### 场景1：代码变更

```bash
# 1. 停止服务
docker-compose stop

# 2. 重新构建
docker-compose build

# 3. 启动服务
docker-compose up -d
```

### 场景2：依赖变更

```bash
# 1. 停止并删除容器
docker-compose down

# 2. 完全重新构建
docker-compose build --no-cache

# 3. 启动服务
docker-compose up -d
```

### 场景3：配置变更

```bash
# 1. 修改 .env 或 docker-compose.yml

# 2. 重新创建容器（不需要重新构建镜像）
docker-compose up -d --force-recreate
```

## 服务访问地址

构建完成并启动后，可以通过以下地址访问服务：

- **前端**: http://localhost:6173
- **后端API**: http://localhost:9001
- **PostgreSQL**: localhost:5432 (容器内: postgres:5432)
- **Redis**: localhost:6379 (容器内: redis:6379)

## 服务说明

### 1. Backend (后端服务)
- 镜像：`x-llm-backend:local`
- 端口：9001 → 8000
- 依赖：postgres, redis
- 挂载卷：
  - `./data` → `/app/data` (数据存储)
  - `./storage` → `/app/storage` (文件存储)
  - `./` → `/repo` (测试用)

### 2. Frontend (前端服务)
- 镜像：`x-llm-frontend:local`
- 端口：6173 → 5173
- 技术栈：React + Vite + Nginx
- 依赖：backend

### 3. Worker (异步任务处理)
- 镜像：`x-llm-backend:local`
- 依赖：postgres, redis
- 用途：处理后台异步任务

### 4. PostgreSQL (数据库)
- 镜像：postgres:15-alpine
- 用户：localgpt
- 密码：localgpt
- 数据库：localgpt
- 数据持久化：`./data/postgres`

### 5. Redis (缓存和队列)
- 镜像：redis:7-alpine
- 数据持久化：`./data/redis`

## 常见问题

### 1. 端口被占用

```bash
# 修改 docker-compose.yml 中的端口映射
ports:
  - "9002:8000"  # 后端改为9002
  - "6174:5173"  # 前端改为6174
```

### 2. 构建失败

```bash
# 查看详细构建日志
docker-compose build --no-cache --progress=plain

# 检查磁盘空间
df -h

# 清理 Docker 缓存
docker system prune -a
```

### 3. 服务无法启动

```bash
# 查看服务日志
docker-compose logs backend

# 检查网络
docker network ls | grep localgpt-net

# 重新创建网络
docker network rm localgpt-net
docker network create localgpt-net
```

### 4. 数据库连接失败

```bash
# 确认 PostgreSQL 已启动
docker-compose ps postgres

# 查看 PostgreSQL 日志
docker-compose logs postgres

# 进入容器检查
docker-compose exec postgres psql -U localgpt -d localgpt
```

### 5. 前端无法访问后端

```bash
# 检查后端是否正常运行
curl http://localhost:9001/

# 检查环境变量
docker-compose exec frontend env | grep VITE
```

## 开发模式

### 热重载开发

如果需要在开发时实时看到代码变更效果：

**后端**：
```bash
# 挂载代码目录（已在 docker-compose.yml 中配置）
# 修改代码后自动重启（需要配置 watchdog）
```

**前端**：
```bash
# 本地开发模式
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 监控和调试

### 1. 进入容器

```bash
# 进入后端容器
docker-compose exec backend bash

# 进入数据库容器
docker-compose exec postgres psql -U localgpt -d localgpt
```

### 2. 查看资源使用

```bash
# 查看所有容器的资源使用情况
docker stats

# 查看特定容器
docker stats localgpt-backend
```

### 3. 导出日志

```bash
# 导出所有日志到文件
docker-compose logs > compose_logs.txt

# 导出特定时间段的日志
docker-compose logs --since 1h backend > backend_logs.txt
```

## 备份和恢复

### 数据库备份

```bash
# 备份数据库
docker-compose exec postgres pg_dump -U localgpt -d localgpt > backup.sql

# 恢复数据库
docker-compose exec -T postgres psql -U localgpt -d localgpt < backup.sql
```

### 数据卷备份

```bash
# 备份 data 目录
tar -czf data_backup.tar.gz ./data

# 恢复
tar -xzf data_backup.tar.gz
```

## 最佳实践

1. **使用 .env 文件管理环境变量**
2. **定期备份数据**
3. **监控容器资源使用**
4. **及时清理无用的镜像和容器**
5. **使用 docker-compose logs 排查问题**
6. **生产环境移除 DEBUG=true**
7. **定期更新基础镜像**

## 故障排查流程

1. 查看服务状态：`docker-compose ps`
2. 查看服务日志：`docker-compose logs -f [service]`
3. 检查网络连接：`docker network inspect localgpt-net`
4. 检查容器资源：`docker stats`
5. 进入容器调试：`docker-compose exec [service] bash`
6. 重启服务：`docker-compose restart [service]`
7. 重新构建：`docker-compose build [service]`

## 总结

本次编译已成功完成，所有服务的 Docker 镜像已构建完成：
- ✅ x-llm-backend:local (后端和Worker)
- ✅ x-llm-frontend:local (前端)
- ✅ PostgreSQL (数据库)
- ✅ Redis (缓存)

可以使用 `docker-compose up -d` 启动所有服务。

