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

        remote_file_path = None
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
            # 某些 WebDAV 服务器会返回 403 但文件实际已上传成功
            # 尝试验证文件是否真的上传了
            try:
                if remote_file_path and self.client.check(remote_file_path):
                    logger.info(f"✓ Upload succeeded despite error (file verified): {Path(local_file_path).name}")
                    return
            except:
                pass

            # 如果确实失败了，记录错误
            logger.error(f"✗ Failed to upload {local_file_path}")
            logger.error(f"  Error: {e}")
            if remote_file_path:
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

    write_ok = False
    read_ok = False
    delete_ok = False

    # 测试写入
    try:
        logger.info("Testing WebDAV write permissions...")
        # 创建临时测试文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
            tmp.write('webdav test')
            tmp_path = tmp.name

        try:
            client.upload_sync(
                remote_path=test_file,
                local_path=tmp_path
            )
            write_ok = True
            logger.info("✓ Write permission OK")
        finally:
            import os
            os.unlink(tmp_path)

    except Exception as e:
        logger.warning(f"⚠ Write test threw exception: {e}")
        # 即使抛出异常，也检查文件是否真的被创建了
        try:
            if client.check(test_file):
                write_ok = True
                logger.info("✓ Write actually succeeded (file exists despite error)")
        except:
            logger.error("✗ Write permission FAILED")

    # 如果写入失败，不继续测试
    if not write_ok:
        logger.error("Cannot proceed without write permission")
        return False

    # 测试读取
    try:
        logger.info("Testing WebDAV read permissions...")
        exists = client.check(test_file)
        if exists:
            read_ok = True
            logger.info("✓ Read permission OK")
        else:
            logger.warning("⚠ Cannot verify read permission")
    except Exception as e:
        logger.warning(f"⚠ Read test failed: {e}")
        logger.info("→ Read permission might be limited, but not critical")

    # 测试删除
    try:
        logger.info("Testing WebDAV delete permissions...")
        client.clean(test_file)
        delete_ok = True
        logger.info("✓ Delete permission OK")
    except Exception as e:
        logger.warning(f"⚠ Delete test failed: {e}")
        logger.info("→ Delete permission might be limited, but not critical")

    # 只要能写入就认为测试通过
    if write_ok:
        logger.info("=" * 60)
        logger.info("✓ WebDAV is ready for syncing")
        logger.info("=" * 60)
        return True

    return False


def download_from_webdav(client, local_path, remote_path):
    """从 WebDAV 下载文件到本地"""
    logger.info("=" * 60)
    logger.info("Starting download from WebDAV...")
    logger.info("=" * 60)

    local_path = Path(local_path)
    local_path.mkdir(parents=True, exist_ok=True)

    try:
        # 获取远程文件列表
        logger.info(f"Listing files in {remote_path}")
        items = client.list(remote_path)
        logger.info(f"Found {len(items)} items: {items}")

        # 过滤出文件（跳过目录和特殊项）
        files_to_download = []
        for item in items:
            if item in ['.', '..']:
                continue
            if item.lower() in ['dav', 'webdav']:
                logger.info(f"Skipping special directory: {item}")
                continue
                
            full_path = f"{remote_path.rstrip('/')}/{item}".replace('//', '/')
            
            # 检查是否是文件
            try:
                if not client.is_dir(full_path):
                    files_to_download.append(full_path)
                    logger.info(f"Found file: {full_path}")
            except:
                # 如果无法判断，尝试作为文件处理
                files_to_download.append(full_path)
                logger.info(f"Treating as file: {full_path}")

        if not files_to_download:
            logger.info("No files to download")
            return

        logger.info(f"Downloading {len(files_to_download)} files")

        # 下载文件
        for remote_file in files_to_download:
            try:
                # 计算本地文件路径
                filename = remote_file.split('/')[-1]
                local_file = local_path / filename

                logger.info(f"Downloading {remote_file} -> {local_file}")

                # 下载文件
                client.download_sync(
                    remote_path=remote_file,
                    local_path=str(local_file)
                )
                logger.info(f"✓ Downloaded: {filename}")

            except Exception as e:
                logger.error(f"✗ Failed to download {remote_file}: {e}")

        logger.info("Download completed")

    except Exception as e:
        logger.error(f"Failed to list remote files: {e}")
        logger.warning("Continuing without download...")


def upload_to_webdav(client, local_path, remote_path):
    """上传本地文件到 WebDAV"""
    logger.info("=" * 60)
    logger.info("Starting upload to WebDAV...")
    logger.info("=" * 60)

    local_path = Path(local_path)
    
    # 检查本地目录是否存在
    if not local_path.exists():
        logger.warning(f"Local directory does not exist: {local_path}")
        return
    
    if not local_path.is_dir():
        logger.error(f"Local path is not a directory: {local_path}")
        return

    files = list(local_path.rglob('*'))
    file_count = len([f for f in files if f.is_file()])

    if file_count == 0:
        logger.info(f"No local files found in: {local_path}")
        # 列出目录内容用于调试
        try:
            contents = list(local_path.iterdir())
            logger.info(f"Directory contents: {[str(c) for c in contents]}")
        except Exception as e:
            logger.debug(f"Cannot list directory contents: {e}")
        return

    logger.info(f"Found {file_count} local files to upload from: {local_path}")
    
    # 列出所有要上传的文件
    for file_path in files:
        if file_path.is_file():
            logger.info(f"Queueing file for upload: {file_path}")

    handler = WebDAVSyncHandler(client, local_path, remote_path)

    uploaded_count = 0
    for file_path in files:
        if file_path.is_file():
            try:
                handler.upload_file(str(file_path))
                uploaded_count += 1
            except Exception as e:
                logger.error(f"Failed to upload {file_path}: {e}")

    logger.info(f"Upload completed: {uploaded_count}/{file_count} files uploaded")


def initial_sync(client, local_path, remote_path, sync_mode='bidirectional'):
    """
    初始同步
    sync_mode:
      - 'bidirectional': 双向同步（先下载后上传）
      - 'download': 仅下载
      - 'upload': 仅上传
    """
    logger.info("=" * 60)
    logger.info(f"🚀 Starting initial sync with mode: {sync_mode}")
    logger.info(f"📁 Local path: {local_path}")
    logger.info(f"☁️  Remote path: {remote_path}")
    logger.info("=" * 60)

    try:
        if sync_mode in ['bidirectional', 'download']:
            logger.info("📥 Starting download phase...")
            download_from_webdav(client, local_path, remote_path)

        if sync_mode in ['bidirectional', 'upload']:
            logger.info("📤 Starting upload phase...")
            upload_to_webdav(client, local_path, remote_path)

        logger.info("=" * 60)
        logger.info("✅ Initial sync completed successfully")
        logger.info("=" * 60)
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ Initial sync failed: {e}")
        logger.error("=" * 60)
        # 不退出程序，继续运行监控


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
    sync_mode = os.getenv('SYNC_MODE', 'download')  # 默认仅下载模式
    logger.info(f"Starting initial sync with mode: {sync_mode}")
    initial_sync(client, local_path, remote_path, sync_mode)

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
