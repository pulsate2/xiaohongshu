#!/bin/bash
# 测试 WebDAV 同步功能的脚本

echo "=== WebDAV Sync Test ==="

# 检查环境变量
echo "Checking environment variables..."
echo "WEBDAV_URL: ${WEBDAV_URL:-'not set'}"
echo "WEBDAV_USERNAME: ${WEBDAV_USERNAME:-'not set'}"
echo "WEBDAV_PASSWORD: ${WEBDAV_PASSWORD:+('set')}"
echo "SYNC_LOCAL_PATH: ${SYNC_LOCAL_PATH:-'/app/output'}"
echo "SYNC_REMOTE_PATH: ${SYNC_REMOTE_PATH:-'/'}"
echo "SYNC_MODE: ${SYNC_MODE:-'download'}"

TEST_DIR="${SYNC_LOCAL_PATH:-/app/output}"

echo ""
echo "=== Testing Download Mode ==="
echo "Local sync directory: $TEST_DIR"

# 检查本地目录状态
echo ""
echo "Local directory contents before sync:"
if [ -d "$TEST_DIR" ]; then
    find "$TEST_DIR" -type f -exec echo "  - {}" \; 2>/dev/null || echo "  (empty or no readable files)"
else
    echo "  (directory does not exist)"
fi

# 手动触发下载测试
echo ""
echo "=== Manual Download Test ==="
echo "You can manually test the download by running:"
echo "python3 -c \"
import os
from webdav3.client import Client

webdav_url = os.getenv('WEBDAV_URL')
webdav_username = os.getenv('WEBDAV_USERNAME') 
webdav_password = os.getenv('WEBDAV_PASSWORD')
remote_path = os.getenv('SYNC_REMOTE_PATH', '/')

if webdav_url and webdav_username and webdav_password:
    options = {
        'webdav_hostname': webdav_url,
        'webdav_login': webdav_username,
        'webdav_password': webdav_password,
        'webdav_timeout': 30
    }
    client = Client(options)
    try:
        items = client.list(remote_path)
        print(f'Remote files in {remote_path}: {items}')
    except Exception as e:
        print(f'Error listing remote files: {e}')
else:
    print('WebDAV credentials not set')
\""

echo ""
echo "=== Test completed ==="
echo "Check the WebDAV sync logs to see if files were downloaded."
echo "Use 'docker logs <container_id>' to view the sync logs."