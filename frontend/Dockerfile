# 前端 Dockerfile
# 多阶段构建：构建阶段 + 运行阶段

# 构建阶段：使用官方 Bun 镜像，避免构建时再访问 npm Registry 安装 Bun。
FROM oven/bun:1-alpine AS builder

# 默认使用国内镜像，并允许在 Compose/CI 中按网络环境覆盖。
# 降低并发可避免代理在大量并行请求下返回不完整的包。
ARG BUN_REGISTRY=https://registry.npmmirror.com
ARG BUN_NETWORK_CONCURRENCY=16
ENV BUN_CONFIG_REGISTRY=${BUN_REGISTRY} \
    BUN_CONFIG_MAX_HTTP_REQUESTS=${BUN_NETWORK_CONCURRENCY}

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY package.json bun.lock ./

# 缓存依赖下载；遇到代理/CDN 返回损坏 tarball 时清理缓存并有限重试。
RUN --mount=type=cache,target=/root/.bun/install/cache \
    set -eu; \
    attempt=1; \
    until bun install --frozen-lockfile --network-concurrency "${BUN_NETWORK_CONCURRENCY}"; do \
        if [ "${attempt}" -ge 3 ]; then \
            echo "依赖安装连续失败 ${attempt} 次" >&2; \
            exit 1; \
        fi; \
        echo "依赖下载失败，清理缓存后重试（${attempt}/3）" >&2; \
        rm -rf node_modules /root/.bun/install/cache/*; \
        attempt=$((attempt + 1)); \
    done

# 复制源代码
COPY . .

# 构建生产版本
RUN bun run build

# 运行阶段
FROM nginx:alpine

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]
