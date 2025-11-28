#!/bin/bash
set -e

echo "Starting initialization..."

# 1. 生成 nginx 基本认证密码文件
if [ -n "$AUTH_USERNAME" ] && [ -n "$AUTH_PASSWORD" ]; then
    echo "Setting up nginx basic authentication..."
    htpasswd -bc /etc/nginx/.htpasswd "$AUTH_USERNAME" "$AUTH_PASSWORD"
else
    echo "Warning: AUTH_USERNAME or AUTH_PASSWORD not set. Authentication will not work!"
fi

# 2. 配置和挂载 WebDAV
if [ -n "$WEBDAV_URL" ] && [ -n "$WEBDAV_USERNAME" ] && [ -n "$WEBDAV_PASSWORD" ]; then
    echo "Configuring WebDAV mount..."

    # 创建 davfs2 配置目录
    mkdir -p /root/.davfs2

    # 配置 davfs2 secrets
    echo "$WEBDAV_URL $WEBDAV_USERNAME $WEBDAV_PASSWORD" > /root/.davfs2/secrets
    chmod 600 /root/.davfs2/secrets

    # 创建挂载点
    mkdir -p /app/output

    # 挂载 WebDAV
    echo "Mounting WebDAV to /app/output..."
    mount -t davfs "$WEBDAV_URL" /app/output -o rw,uid=0,gid=0 || {
        echo "Warning: WebDAV mount failed. Continuing without mount..."
    }
else
    echo "Warning: WebDAV credentials not set (WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD). Skipping mount..."
fi

# 3. 启动 nginx
echo "Starting nginx..."
nginx -g "daemon off;" &
NGINX_PID=$!

# 4. 启动原应用
echo "Starting application..."
uv run python -m backend.app &
APP_PID=$!

# 等待任一进程退出
wait -n $NGINX_PID $APP_PID

# 如果任一进程退出，清理并退出
echo "One of the processes has exited. Cleaning up..."
kill $NGINX_PID $APP_PID 2>/dev/null || true
exit 1
