FROM python:3.11-slim-bookworm

WORKDIR /app

# 安装系统依赖（如果以后需要编译部分包可以加，这里主要为了保持镜像整洁）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 创建必要的目录
RUN mkdir -p data logs downloads

# 暴露 Web 端口
EXPOSE 5001

# 启动 Web 服务（它会负责启动机器人）
CMD ["python", "tg_download_web.py"]
