#!/usr/bin/env python3
"""
WebDAV 同步脚本 - 监控本地目录并自动上传到 WebDAV
不需要 root 权限，使用应用层 WebDAV 客户端
"""
import os
import sys
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from webdav3.client import Client

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebDAVSyncHandler(FileSystemEventHandler):
    """文件系统事件处理器"""

    def __init__(self, client, local_path, remote_path):
        self.client = client
        self.local_path = Path(local_path)
        self.remote_path = remote_path.rstrip('/') if remote_path != '/' else ''
        self.syncing = set()  # 正在同步的文件

    def get_remote_path(self, local_file_path):
        """获取远程路径"""
        rel_path = Path(local_file_path).relative_to(self.local_path)
        rel_path_str = rel_path.as_posix()

        # 拼接路径，避免双斜杠
        if self.remote_path:
            return f"{self.remote_path}/{rel_path_str}"
        else:
            return f"/{rel_path_str}" if not rel_path_str.startswith('/') else rel_path_str

    def ensure_remote_dir(self, remote_file_path):
        """确保远程目录存在"""
        parts = remote_file_path.rstrip('/').split('/')
        if len(parts) <= 1:
            return

        # 逐级创建目录
        for i in range(1, len(parts)):
            dir_path = '/'.join(parts[:i+1])
            if dir_path and not dir_path.endswith(parts[-1]):  # 不是文件本身
                try:
                    if not self.client.check(dir_path):
                        logger.debug(f"Creating directory: {dir_path}")
                        self.client.mkdir(dir_path)
                except Exception as e:
                    logger.debug(f"Directory check/create for {dir_path}: {e}")

    def upload_file(self, local_file_path):
        """上传文件到 WebDAV"""
        if local_file_path in self.syncing:
            return

        try:
            self.syncing.add(local_file_path)
            remote_file_path = self.get_remote_path(local_file_path)

            logger.info(f"Uploading: {local_file_path}")
            logger.info(f"  -> Remote path: {remote_file_path}")

            # 确保远程目录存在
            self.ensure_remote_dir(remote_file_path)

            # 上传文件
            self.client.upload_sync(
                remote_path=remote_file_path,
                local_path=local_file_path
            )
            logger.info(f"✓ Successfully uploaded: {Path(local_file_path).name}")

        except Exception as e:
            logger.error(f"✗ Failed to upload {local_file_path}")
            logger.error(f"  Error: {e}")
            logger.error(f"  Remote path was: {remote_file_path}")
        finally:
            self.syncing.discard(local_file_path)

    def delete_file(self, local_file_path):
        """删除 WebDAV 上的文件"""
        try:
            remote_file_path = self.get_remote_path(local_file_path)
            logger.info(f"Deleting remote file: {remote_file_path}")
            self.client.clean(remote_file_path)
            logger.info(f"✓ Successfully deleted: {remote_file_path}")
        except Exception as e:
            logger.error(f"✗ Failed to delete {remote_file_path}: {e}")

    def on_created(self, event):
        """文件创建事件"""
        if not event.is_directory:
            time.sleep(0.5)  # 等待文件写入完成
            self.upload_file(event.src_path)

    def on_modified(self, event):
        """文件修改事件"""
        if not event.is_directory:
            time.sleep(0.5)  # 等待文件写入完成
            self.upload_file(event.src_path)

    def on_deleted(self, event):
        """文件删除事件"""
        if not event.is_directory:
            self.delete_file(event.src_path)


def test_webdav_permissions(client, remote_path):
    """测试 WebDAV 读写权限"""
    test_file = f"{remote_path.rstrip('/')}/.__webdav_test__.txt"

    try:
        # 测试写入
        logger.info("Testing WebDAV write permissions...")
        client.upload_sync(
            remote_path=test_file,
            local_path='/dev/null'  # 创建空文件
        )
        logger.info("✓ Write permission OK")

        # 测试读取
        logger.info("Testing WebDAV read permissions...")
        client.check(test_file)
        logger.info("✓ Read permission OK")

        # 清理测试文件
        client.clean(test_file)
        logger.info("✓ Delete permission OK")

        return True

    except Exception as e:
        logger.error(f"✗ WebDAV permission test failed: {e}")
        logger.error("Please check if your account has write permissions")
        return False


def initial_sync(client, local_path, remote_path):
    """初始同步 - 上传所有现有文件"""
    logger.info(f"Starting initial sync of {local_path}")
    local_path = Path(local_path)

    files = list(local_path.rglob('*'))
    file_count = len([f for f in files if f.is_file()])

    if file_count == 0:
        logger.info("No files to sync")
        return

    logger.info(f"Found {file_count} files to sync")

    handler = WebDAVSyncHandler(client, local_path, remote_path)

    for file_path in files:
        if file_path.is_file():
            handler.upload_file(str(file_path))

    logger.info("Initial sync completed")


def main():
    """主函数"""
    # 从环境变量获取配置
    webdav_url = os.getenv('WEBDAV_URL')
    webdav_username = os.getenv('WEBDAV_USERNAME')
    webdav_password = os.getenv('WEBDAV_PASSWORD')
    local_path = os.getenv('SYNC_LOCAL_PATH', '/app/output')
    remote_path = os.getenv('SYNC_REMOTE_PATH', '/')

    logger.info("=" * 60)
    logger.info("WebDAV Sync Service Starting")
    logger.info("=" * 60)
    logger.info(f"WebDAV URL: {webdav_url}")
    logger.info(f"Username: {webdav_username}")
    logger.info(f"Local path: {local_path}")
    logger.info(f"Remote path: {remote_path}")
    logger.info("=" * 60)

    if not all([webdav_url, webdav_username, webdav_password]):
        logger.error("WebDAV credentials not set. Required: WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD")
        sys.exit(1)

    # 配置 WebDAV 客户端
    options = {
        'webdav_hostname': webdav_url,
        'webdav_login': webdav_username,
        'webdav_password': webdav_password,
        'webdav_timeout': 30,
        'disable_check': False
    }

    try:
        client = Client(options)

        # 测试连接
        logger.info("Testing WebDAV connection...")
        root_list = client.list()
        logger.info(f"✓ Connection successful. Root has {len(root_list)} items")

        # 测试权限
        if not test_webdav_permissions(client, remote_path):
            logger.warning("Permission test failed, but continuing anyway...")
            logger.warning("If uploads fail, check your WebDAV account permissions")

    except Exception as e:
        logger.error(f"✗ Failed to connect to WebDAV: {e}")
        logger.error(f"URL: {webdav_url}")
        logger.error(f"Username: {webdav_username}")
        logger.error("Please check your WebDAV credentials and URL")
        sys.exit(1)

    # 创建本地目录
    Path(local_path).mkdir(parents=True, exist_ok=True)

    # 初始同步
    initial_sync(client, local_path, remote_path)

    # 启动文件监控
    event_handler = WebDAVSyncHandler(client, local_path, remote_path)
    observer = Observer()
    observer.schedule(event_handler, local_path, recursive=True)
    observer.start()

    logger.info("=" * 60)
    logger.info(f"📁 Watching directory: {local_path}")
    logger.info(f"☁️  Syncing to: {webdav_url}{remote_path}")
    logger.info("🔄 Real-time sync is active")
    logger.info("=" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Stopping WebDAV sync...")

    observer.join()


if __name__ == '__main__':
    main()
