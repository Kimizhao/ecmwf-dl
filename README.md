# ECMWF 气象数据下载工具

本项目用于下载和处理 ECMWF 公开气象预报数据，支持多种分辨率（0.25°、0.4°）和数据流类型。

## 快速开始

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
├── pyproject.toml           # 项目配置
└── .github/
    └── copilot-instructions.md  # AI 协作指南
```

## 相关链接

- [ECMWF 开放数据](https://www.ecmwf.int/en/forecasts/datasets/open-data)
- [ecmwf-opendata 文档](https://pypi.org/project/ecmwf-opendata/)
