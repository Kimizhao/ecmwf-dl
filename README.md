# ECMWF 气象数据下载工具

本项目用于下载和处理 ECMWF 公开气象预报数据，支持多种分辨率（0.25°、0.4°）和数据流类型。

## 部署方式

### 🐳 Docker 部署（推荐）

#### 快速部署

```bash
# 一键部署
./deploy.sh
```

#### 手动部署

```bash
# 1. 复制环境配置
cp .env.example .env

# 2. 创建必要目录
mkdir -p data ecmwf_data logs config

# 3. 构建并启动
docker-compose up -d
```

#### Apple Silicon (M1/M2/M3) Mac 说明

项目已针对 Apple Silicon 优化，会自动构建 x64 架构镜像以确保兼容性。详见 [Apple Silicon 说明文档](docs/APPLE_SILICON.md)。

### 📦 本地安装

### 1. 安装依赖

```bash
pip install -e .
```

或手动安装：

```bash
pip install ecmwf-opendata numpy netcdf4 pygrib tqdm xarray
```

### 2. 下载图片中提到的4种数据

运行以下命令一键下载：

```bash
python download_today.py
```

这将下载：

- `20250916000000-0h-oper-fc.grib2` (业务预报)
- `20250916000000-0h-enfo-ef.grib2` (集合预报)  
- `20250916000000-0h-wave-fc.grib2` (波浪预报)
- `20250916000000-0h-waef-ef.grib2` (波浪集合预报)

### 3. 自定义下载

使用功能更全的脚本：

```bash
# 下载多个时间步长
python download_multi_streams.py --multi-steps

# 指定日期和时间
python download_multi_streams.py --date 2025-09-17 --time 12

# 单个时间步长
python download_multi_streams.py --step 6 --target-dir ./my_data
```

## 数据类型说明

- **oper**: 高分辨率确定性预报（业务预报）
- **enfo**: 集合预报（多个成员的预报）
- **wave**: 海洋波浪预报
- **waef**: 波浪集合预报

## 交互式开发

推荐使用 `ECMWF.ipynb` 进行数据探索和可视化：

```bash
jupyter notebook ECMWF.ipynb
```

## 文件格式转换

项目包含 grib2 到 NetCDF 的转换功能，详见 notebook 中的 `grib2nc` 函数。

## 项目结构

```
ecmwf-dl/
├── main.py                    # 简单入口
├── ECMWF.ipynb               # 主要数据处理流程 
├── download_today.py         # 一键下载脚本
├── download_multi_streams.py # 全功能下载脚本
├── deploy.sh                 # Docker 部署脚本
├── docker-compose.yml        # Docker 编排配置
├── Dockerfile               # Docker 镜像构建
├── .env.example             # 环境变量模板
├── pyproject.toml           # 项目配置
├── docs/
│   └── APPLE_SILICON.md     # Apple Silicon 说明
└── .github/
    └── copilot-instructions.md  # AI 协作指南
```

## Docker 管理命令

```bash
# 查看服务状态
docker-compose ps

# 查看实时日志
docker-compose logs -f ecmwf-dl

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 进入容器
docker exec -it ecmwf-dl-app bash

# 清理资源
docker-compose down -v --rmi all

# 直接运行容器
docker run -d \
  --name ecmwf-dl-app \
  --restart unless-stopped \
  -e TZ=Asia/Shanghai \
  -v /mnt/78qxsj/temps/ECMWF:/app/ecmwf_data \
  -v $(pwd)/logs:/app/logs \
  --memory=2g \
  --cpus=1.0 \
  ecmwf-dl:latest
```

## 相关链接

- [ECMWF 开放数据](https://www.ecmwf.int/en/forecasts/datasets/open-data)
- [ecmwf-opendata 文档](https://pypi.org/project/ecmwf-opendata/)
