#!/bin/bash

# ECMWF-DL Docker 简化部署脚本
set -e

echo "🚀 启动 ECMWF-DL 部署..."

# 检查依赖
if ! command -v docker &> /dev/null || ! (command -v docker-compose &> /dev/null || docker compose version &> /dev/null); then
    echo "❌ 请先安装 Docker 和 Docker Compose"
    exit 1
fi

# 创建目录和配置
mkdir -p data ecmwf_data logs config
[ ! -f .env ] && cp .env.example .env

# 构建和启动
if [[ $(uname -m) == "arm64" ]]; then
    echo "🍎 检测到 Apple Silicon - 使用 x64 兼容模式"
    docker buildx build --platform linux/amd64 -t ecmwf-dl:latest --load .
    docker-compose up -d
else
    docker-compose build && docker-compose up -d
fi

echo "✅ 部署完成！"
echo "📊 服务状态："
docker-compose ps
echo "📋 查看日志: docker-compose logs -f"
