FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/node:20-alpine AS builder

WORKDIR /app

# 设置 npm 使用阿里云镜像
RUN npm config set registry https://registry.npmmirror.com

COPY package.json package-lock.json ./
RUN npm install

COPY . .

# 修复可执行文件权限
RUN chmod -R +x node_modules/.bin

# 构建生产版本
RUN npm run build

# 生产阶段：使用nginx
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
