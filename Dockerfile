FROM python:3.11-slim

# 设置环境变量
ENV TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime

# 创建工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 安装Python依赖
RUN pip install --no-cache-dir -e .

# 默认命令
CMD ["python", "download_multi_streams_scheduled.py", "--schedule"]
