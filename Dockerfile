FROM histonemax/redink

# 安装 nginx 和 Python WebDAV 客户端
RUN apt-get update && \
    apt-get install -y nginx apache2-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python WebDAV 客户端库
RUN pip install --no-cache-dir webdavclient3 watchdog

# 创建必要的目录
RUN mkdir -p /etc/nginx/conf.d /app/output /var/log/nginx

# 复制 nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制 WebDAV 同步脚本
COPY webdav_sync.py /webdav_sync.py

# 复制启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 复制测试脚本
COPY test_sync.sh /test_sync.sh
RUN chmod +x /test_sync.sh

# 暴露 8080 端口
EXPOSE 8080

# 使用自定义的启动脚本
ENTRYPOINT ["/entrypoint.sh"]
