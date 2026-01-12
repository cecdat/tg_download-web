#!/bin/bash

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# --- 配置 ---
DEPLOY_DIR="$SCRIPT_DIR"
ZIP_FILE="tg_downloader_production.zip"
# -------------

# 错误处理
set -e

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then 
  echo "❌ 请使用 root 权限运行此脚本 (例如: sudo ./deploy.sh)"
  exit 1
fi

cd "$DEPLOY_DIR"

# 检查安装包是否存在
if [ -f "$ZIP_FILE" ]; then
    echo "📦 发现安装包 $ZIP_FILE，准备更新..."
    HAS_ZIP=true
elif [ -f "docker-compose.yml" ]; then
    echo "⚠️ 未找到 $ZIP_FILE，检测到 docker-compose.yml，将仅执行重启/构建..."
    HAS_ZIP=false
else
    echo "❌ 错误：当前目录下既未找到 $ZIP_FILE (用于更新)，也未找到 docker-compose.yml (用于启动)"
    exit 1
fi

echo "🚀 开始在当前目录执行..."

# 1. 检查并安装必要工具
if [ "$HAS_ZIP" = true ] && ! command -v unzip &> /dev/null; then
    echo "📦 安装 unzip..."
    apt-get update && apt-get install -y unzip
fi

# 2. 停止旧服务
if [ -f "docker-compose.yml" ]; then
    echo "🛑 停止现有服务..."
    # 尝试多种命令停止
    docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
fi

# 3. 更新代码 (仅当有压缩包时)
if [ "$HAS_ZIP" = true ]; then
    echo "📦 解压更新代码..."
    # 解压并覆盖代码文件
    unzip -o "$ZIP_FILE"
    
    # 备份或删除压缩包 (这里选择保留备份，避免重复执行时报错，或者重命名)
    mv "$ZIP_FILE" "${ZIP_FILE}.bak"
    echo "✅ 已将安装包重命名为 ${ZIP_FILE}.bak"
fi

# 4. 权限修正
echo "🔒 修正目录权限..."
mkdir -p data downloads logs
chmod -R 777 data downloads logs

# 5. 启动服务
echo "🔥 构建并启动容器..."
if docker compose version &>/dev/null; then
    docker compose up -d --build --remove-orphans
elif docker-compose version &>/dev/null; then
    docker-compose up -d --build --remove-orphans
else
    echo "❌ 未检测到 docker compose 或 docker-compose，请先安装 Docker！"
    exit 1
fi

# 6. 部署完成
echo "✅ 部署完成！"
echo "-----------------------------------"
echo "服务状态："
if docker compose version &>/dev/null; then
    docker compose ps
else
    docker-compose ps
fi
echo "-----------------------------------"
echo "🌐 Web 访问: https://bot.237890.xyz"
echo "📂 下载目录: $DEPLOY_DIR/downloads"
