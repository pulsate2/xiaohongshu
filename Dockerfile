FROM histonemax/redink

# 安装 nginx 和 davfs2 用于 webdav 挂载
RUN apt-get update && \
    apt-get install -y nginx apache2-utils davfs2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 创建必要的目录
RUN mkdir -p /etc/nginx/conf.d /app/output /var/log/nginx

# 复制 nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露 8080 端口
EXPOSE 8080

# 使用自定义的启动脚本
ENTRYPOINT ["/entrypoint.sh"]
