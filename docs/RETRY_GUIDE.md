# ECMWF 下载脚本重试机制使用说明

## 新增功能

本次更新为 ECMWF 数据下载脚本添加了强大的失败重试机制，大大提高了下载的可靠性和成功率。

## 主要特性

### 1. 智能重试机制

- **指数退避算法**：重试间隔会逐渐增加（1秒 → 2秒 → 4秒 → 8秒...），避免过度请求服务器
- **随机抖动**：在延迟时间基础上添加随机变化，减少多个并发请求的碰撞概率
- **最大延迟限制**：重试延迟最长不超过30秒，避免过长等待

### 2. 详细的状态跟踪

- **实时日志**：每次重试都会记录详细信息
- **成功率统计**：显示总体下载成功情况
- **失败详情**：列出所有失败的下载任务及其原因

### 3. 灵活配置

- **可配置重试次数**：默认3次，可通过 `--max-retries` 参数调整
- **可配置延迟时间**：默认1秒基础延迟，可通过 `--retry-delay` 参数调整

## 使用方法

### 基本使用（使用默认重试设置）

```bash
# 默认：最多重试3次，基础延迟1秒
python download_multi_streams_scheduled.py --time 00 --step 0
```

### 自定义重试参数

```bash
# 更保守的重试策略：最多重试5次，基础延迟2秒
python download_multi_streams_scheduled.py --time 00 --step 0 --max-retries 5 --retry-delay 2.0

# 更激进的重试策略：最多重试10次，基础延迟0.5秒
python download_multi_streams_scheduled.py --time 00 --step 0 --max-retries 10 --retry-delay 0.5
```

### 批量下载（推荐设置）

```bash
# 批量下载多个时间步长，使用较多重试次数确保稳定性
python download_multi_streams_scheduled.py --multi-steps --max-retries 5 --retry-delay 1.5

# 下载全部预报时间和步长，使用最保守设置
python download_multi_streams_scheduled.py --multi-all --max-retries 8 --retry-delay 3.0
```

### 定时任务（自动使用优化设置）

```bash
# 定时任务会自动使用 5次重试，2秒基础延迟的保守设置
python download_multi_streams_scheduled.py --schedule
```

## 日志示例

### 成功下载

```
2025-09-17 14:30:15 - __main__ - INFO - 正在下载 oper 数据...
2025-09-17 14:30:18 - __main__ - INFO - ✅ 成功下载: 20250917000000-0h-oper-fc.grib2
```

### 重试过程

```
2025-09-17 14:30:15 - __main__ - INFO - 正在下载 wave 数据...
2025-09-17 14:30:20 - __main__ - WARNING - ⚠️  下载 20250917000000-0h-wave-fc.grib2 第 1 次尝试失败: Connection timeout
2025-09-17 14:30:20 - __main__ - INFO - 等待 1.2 秒后进行第 2 次尝试...
2025-09-17 14:30:23 - __main__ - WARNING - ⚠️  下载 20250917000000-0h-wave-fc.grib2 第 2 次尝试失败: HTTP 503 Service Unavailable
2025-09-17 14:30:23 - __main__ - INFO - 等待 2.7 秒后进行第 3 次尝试...
2025-09-17 14:30:27 - __main__ - INFO - ✅ 成功下载: 20250917000000-0h-wave-fc.grib2
```

### 最终统计

```
2025-09-17 14:35:42 - __main__ - INFO - 下载完成！成功: 3/4
2025-09-17 14:35:42 - __main__ - WARNING - 失败的下载任务 (1 个):
2025-09-17 14:35:42 - __main__ - WARNING -   - enfo: 20250917000000-0h-enfo-ef.grib2 - 多次重试后仍然失败
```

## 推荐配置

### 日常使用

- **交互式下载**：`--max-retries 3 --retry-delay 1.0`（默认设置）
- **批量下载**：`--max-retries 5 --retry-delay 1.5`
- **网络不稳定环境**：`--max-retries 8 --retry-delay 2.0`

### 自动化任务

- **定时任务**：已内置优化设置（5次重试，2秒延迟）
- **CI/CD 环境**：`--max-retries 10 --retry-delay 3.0`

## 错误处理

重试机制会自动处理以下类型的错误：

- 网络连接超时
- HTTP 5xx 服务器错误
- 临时网络中断
- ECMWF 服务器临时不可用

对于以下错误，重试机制不会生效（会立即失败）：

- HTTP 4xx 客户端错误（如401未授权、404文件不存在）
- 磁盘空间不足
- 权限问题

## 性能考虑

- **延迟开销**：重试会增加总体下载时间，建议根据网络环境合理设置
- **服务器友好**：指数退避和随机抖动设计避免对ECMWF服务器造成过大压力
- **资源消耗**：重试过程中会保持连接，注意系统资源使用情况

## 故障排除

如果重试机制仍然无法解决下载问题：

1. 检查网络连接稳定性
2. 确认ECMWF服务器状态：<https://www.ecmwf.int/>
3. 尝试增加重试次数和延迟时间
4. 检查磁盘空间是否充足
5. 确认文件权限设置正确
