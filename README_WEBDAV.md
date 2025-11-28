# WebDAV 同步功能说明

## 功能概述
这个项目包含一个 WebDAV 同步服务，可以自动监控本地目录并将文件同步到 WebDAV 服务器。

## 环境变量配置

### 必需的环境变量
- `WEBDAV_URL`: WebDAV 服务器地址（例如：https://dav.example.com/remote.php/dav/files/username/）
- `WEBDAV_USERNAME`: WebDAV 用户名
- `WEBDAV_PASSWORD`: WebDAV 密码

### 可选的环境变量
- `SYNC_LOCAL_PATH`: 本地同步目录（默认：/app/output）
- `SYNC_REMOTE_PATH`: 远程同步路径（默认：/）
- `SYNC_MODE`: 同步模式（默认：download）
  - `download`: 仅从 WebDAV 下载文件到本地
  - `upload`: 仅上传本地文件到 WebDAV
  - `bidirectional`: 双向同步（先下载后上传）

## 启动流程
1. 容器启动时，entrypoint.sh 会检查 WebDAV 配置
2. 如果配置正确，会启动 WebDAV 同步服务
3. 同步服务会执行初始同步（根据 SYNC_MODE）
4. 然后开始监控本地文件变化

## 调试步骤

### 1. 检查环境变量
```bash
docker exec <container_id> env | grep WEBDAV
```

### 2. 查看同步日志
```bash
docker exec <container_id> tail -f /var/log/webdav_sync.log
# 或者查看容器日志
docker logs <container_id>
```

### 3. 运行测试脚本
```bash
docker exec <container_id> /test_sync.sh
```

### 4. 手动测试同步
```bash
# 进入容器
docker exec -it <container_id> bash

# 创建测试文件
echo "test content" > /app/output/manual_test.txt

# 查看同步日志
tail -f /var/log/webdav_sync.log
```

## 常见问题

### 问题1：启动时没有下载文件
**可能原因：**
- 环境变量未正确设置
- WebDAV 服务器上没有文件
- WebDAV 连接失败
- 远程路径配置错误

**解决方案：**
1. 检查环境变量是否正确
2. 确认 WebDAV 服务器上有文件需要下载
3. 验证远程路径是否正确
4. 查看 WebDAV 连接日志

### 问题2：文件上传失败
**可能原因：**
- WebDAV 权限不足
- 网络连接问题
- 文件路径问题

**解决方案：**
1. 检查 WebDAV 账户权限
2. 验证 WebDAV URL 格式
3. 查看详细错误日志

### 问题3：同步延迟
**可能原因：**
- 文件监控延迟
- 网络延迟

**解决方案：**
- 脚本中有 0.5 秒的延迟等待文件写入完成
- 可以根据需要调整延迟时间

## 日志级别
脚本使用 Python logging 模块，默认级别为 INFO。
可以通过修改脚本中的 logging.basicConfig 来调整日志级别。

## 文件监控
- 使用 watchdog 库监控文件系统变化
- 支持递归监控子目录
- 监控的事件：创建、修改、删除

## 权限测试
启动时会自动测试 WebDAV 权限：
- 写入权限：创建临时测试文件
- 读取权限：验证文件是否存在
- 删除权限：删除测试文件

只要写入权限正常，同步服务就会继续运行。