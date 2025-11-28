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
        self.remote_path = remote_path.rstrip('/')
        self.syncing = set()  # 正在同步的文件

    def get_remote_path(self, local_file_path):
        """获取远程路径"""
        rel_path = Path(local_file_path).relative_to(self.local_path)
        return f"{self.remote_path}/{rel_path.as_posix()}"

    def upload_file(self, local_file_path):
        """上传文件到 WebDAV"""
        if local_file_path in self.syncing:
            return

        try:
            self.syncing.add(local_file_path)
            remote_file_path = self.get_remote_path(local_file_path)

            # 确保远程目录存在
            remote_dir = '/'.join(remote_file_path.split('/')[:-1])
            try:
                self.client.mkdir(remote_dir)
            except:
                pass  # 目录可能已存在

            # 上传文件
            logger.info(f"Uploading: {local_file_path} -> {remote_file_path}")
            self.client.upload_sync(
                remote_path=remote_file_path,
                local_path=local_file_path
            )
            logger.info(f"Successfully uploaded: {local_file_path}")

        except Exception as e:
            logger.error(f"Failed to upload {local_file_path}: {e}")
        finally:
            self.syncing.discard(local_file_path)

    def delete_file(self, local_file_path):
        """删除 WebDAV 上的文件"""
        try:
            remote_file_path = self.get_remote_path(local_file_path)
            logger.info(f"Deleting: {remote_file_path}")
            self.client.clean(remote_file_path)
            logger.info(f"Successfully deleted: {remote_file_path}")
        except Exception as e:
            logger.error(f"Failed to delete {remote_file_path}: {e}")

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


def initial_sync(client, local_path, remote_path):
    """初始同步 - 上传所有现有文件"""
    logger.info(f"Starting initial sync of {local_path}")
    local_path = Path(local_path)

    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            try:
                rel_path = file_path.relative_to(local_path)
                remote_file_path = f"{remote_path.rstrip('/')}/{rel_path.as_posix()}"

                # 确保远程目录存在
                remote_dir = '/'.join(remote_file_path.split('/')[:-1])
                try:
                    client.mkdir(remote_dir)
                except:
                    pass

                # 上传文件
                logger.info(f"Initial sync: {file_path} -> {remote_file_path}")
                client.upload_sync(
                    remote_path=remote_file_path,
                    local_path=str(file_path)
                )

            except Exception as e:
                logger.error(f"Failed to sync {file_path}: {e}")

    logger.info("Initial sync completed")


def main():
    """主函数"""
    # 从环境变量获取配置
    webdav_url = os.getenv('WEBDAV_URL')
    webdav_username = os.getenv('WEBDAV_USERNAME')
    webdav_password = os.getenv('WEBDAV_PASSWORD')
    local_path = os.getenv('SYNC_LOCAL_PATH', '/app/output')
    remote_path = os.getenv('SYNC_REMOTE_PATH', '/')

    if not all([webdav_url, webdav_username, webdav_password]):
        logger.error("WebDAV credentials not set. Required: WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD")
        sys.exit(1)

    # 配置 WebDAV 客户端
    options = {
        'webdav_hostname': webdav_url,
        'webdav_login': webdav_username,
        'webdav_password': webdav_password,
        'webdav_timeout': 30
    }

    try:
        client = Client(options)

        # 测试连接
        logger.info("Testing WebDAV connection...")
        client.list()
        logger.info("WebDAV connection successful")

    except Exception as e:
        logger.error(f"Failed to connect to WebDAV: {e}")
        logger.error(f"URL: {webdav_url}, Username: {webdav_username}")
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

    logger.info(f"Watching directory: {local_path}")
    logger.info(f"Remote path: {remote_path}")
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Stopping WebDAV sync...")

    observer.join()


if __name__ == '__main__':
    main()
