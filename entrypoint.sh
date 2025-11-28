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

# 2. 启动 WebDAV 同步（如果配置了）
if [ -n "$WEBDAV_URL" ] && [ -n "$WEBDAV_USERNAME" ] && [ -n "$WEBDAV_PASSWORD" ]; then
    echo "Starting WebDAV sync service..."
    echo "WebDAV URL: $WEBDAV_URL"
    echo "WebDAV Username: $WEBDAV_USERNAME"
    echo "Local Sync Path: ${SYNC_LOCAL_PATH:-/app/output}"
    echo "Remote Sync Path: ${SYNC_REMOTE_PATH:-/}"
    echo "Sync Mode: ${SYNC_MODE:-download}"
    
    # 等待一下确保网络连接稳定
    sleep 5
    
    python3 /webdav_sync.py &
    WEBDAV_PID=$!
    echo "WebDAV sync started with PID: $WEBDAV_PID"
    
    # 等待几秒钟让 WebDAV 同步完成初始同步
    echo "Waiting for initial WebDAV sync to complete..."
    sleep 10
else
    echo "WebDAV credentials not set. Skipping WebDAV sync..."
    echo "Required variables: WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD"
    WEBDAV_PID=""
fi

# 3. 启动 nginx
echo "Starting nginx..."
nginx -g "daemon off;" &
NGINX_PID=$!

# 4. 启动原应用
echo "Starting application..."
uv run python -m backend.app &
APP_PID=$!

# 清理函数
cleanup() {
    echo "Shutting down services..."
    kill $NGINX_PID $APP_PID $WEBDAV_PID 2>/dev/null || true
    exit 0
}

# 捕获退出信号
trap cleanup SIGTERM SIGINT

# 等待任一进程退出
if [ -n "$WEBDAV_PID" ]; then
    wait -n $NGINX_PID $APP_PID $WEBDAV_PID
else
    wait -n $NGINX_PID $APP_PID
fi

# 如果任一进程退出，清理并退出
echo "One of the processes has exited. Cleaning up..."
cleanup
