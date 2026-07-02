#!/usr/bin/env python3
"""
ECMWF 开放数据下载脚本 - 支持定时下载和失败重试机制
支持多个数据流(stream)和多个预报时间的下载，新增定时下载功能和重试机制

失败重试机制特性:
- 指数退避算法：重试间隔会逐渐增加，避免过度请求
- 随机抖动：减少多个并发请求的碰撞概率
- 详细日志：记录每次重试的过程和最终结果
- 灵活配置：支持自定义重试次数和延迟时间
- 状态跟踪：提供下载成功率和失败详情

下载记录跟踪特性:
- 自动记录已成功下载的文件，避免重复下载
- 基于下载参数生成唯一标识符，即使文件被移动或删除也能避免重复下载
- 支持查看和清除下载记录
- 记录文件存储在 ./logs/download_records.json

使用示例:
python download_multi_streams_scheduled.py --steps 0,3,6,9,12 --streams oper,enfo --forecast-times 00,12
python download_multi_streams_scheduled.py --schedule  # 启动定时下载任务，每小时运行
python download_multi_streams_scheduled.py --max-retries 5 --retry-delay 2.0  # 自定义重试参数
python download_multi_streams_scheduled.py --show-records  # 查看下载记录
python download_multi_streams_scheduled.py --clear-records  # 清除下载记录

06和18预报
20250916060000-0h-scwv-fc.grib2       16-09-2025 13:27       4189743     164504305
wave

20250916060000-0h-scda-fc.grib2       16-09-2025 13:27     118672255     164504317
oper
"""

import argparse
import logging
import signal
import time
from datetime import datetime, timedelta
from functools import wraps
import random
import json

import schedule
from ecmwf.opendata import Client
import os
from tqdm import tqdm

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 全局常量
DOWNLOAD_RECORD_FILE = "./logs/download_records.json"


def ensure_logs_dir():
    """确保logs目录存在"""
    os.makedirs("./logs", exist_ok=True)


def load_download_records():
    """
    加载已下载文件的记录
    返回一个集合，包含所有已成功下载的文件标识符
    """
    ensure_logs_dir()
    if not os.path.exists(DOWNLOAD_RECORD_FILE):
        return set()

    try:
        with open(DOWNLOAD_RECORD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("downloaded_files", []))
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"读取下载记录文件失败: {e}，将重新创建")
        return set()


def save_download_records(downloaded_files):
    """
    保存已下载文件的记录
    """
    ensure_logs_dir()
    data = {
        "downloaded_files": list(downloaded_files),
        "last_updated": datetime.now().isoformat(),
    }

    try:
        with open(DOWNLOAD_RECORD_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存下载记录失败: {e}")


def generate_file_identifier(date, time, step, stream, type_):
    """
    生成文件的唯一标识符，用于判断是否已下载
    基于下载参数而不是文件名，因为文件可能被移动或删除
    """
    return f"{date}_{time}_{step}_{stream}_{type_}"


def is_file_downloaded(date, time, step, stream, type_, downloaded_files):
    """
    检查文件是否已经下载过
    """
    file_id = generate_file_identifier(date, time, step, stream, type_)
    return file_id in downloaded_files


def mark_file_downloaded(date, time, step, stream, type_, downloaded_files):
    """
    标记文件为已下载
    """
    file_id = generate_file_identifier(date, time, step, stream, type_)
    downloaded_files.add(file_id)
    save_download_records(downloaded_files)
    logger.info(f"已标记文件为已下载: {file_id}")


def retry_on_failure(
    max_retries=3, base_delay=1, max_delay=60, backoff_factor=2, jitter=True
):
    """
    重试装饰器，支持指数退避和抖动

    参数:
    - max_retries: 最大重试次数
    - base_delay: 基础延迟时间（秒）
    - max_delay: 最大延迟时间（秒）
    - backoff_factor: 退避因子
    - jitter: 是否添加随机抖动，避免惊群效应
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt == max_retries:
                        # 最后一次重试失败，抛出异常
                        logger.error(
                            f"函数 {func.__name__} 在 {max_retries} 次重试后仍然失败: {str(e)}"
                        )
                        raise e

                    # 计算延迟时间
                    delay = min(base_delay * (backoff_factor**attempt), max_delay)

                    # 添加抖动
                    if jitter:
                        delay *= 0.5 + random.random() * 0.5  # 在 50%-100% 之间随机

                    logger.warning(
                        f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {str(e)}"
                    )
                    logger.info(f"等待 {delay:.1f} 秒后进行第 {attempt + 2} 次尝试...")

                    time.sleep(delay)

            # 理论上不会到达这里
            raise last_exception

        return wrapper

    return decorator


def download_single_stream(client, retrieve_args, filename, max_retries=3):
    """
    下载单个数据流的函数，包含重试机制

    参数:
    - client: ECMWF 客户端
    - retrieve_args: 下载参数字典
    - filename: 文件名（用于日志）
    - max_retries: 最大重试次数
    """
    for attempt in range(max_retries + 1):
        try:
            client.retrieve(**retrieve_args)
            logger.info(f"✅ 成功下载: {filename}")
            # 修改缓存文件名*.grib2.tmp为*.grib2
            final_filename = retrieve_args["target"].replace(".grib2.tmp", ".grib2")
            if os.path.exists(retrieve_args["target"]):
                os.rename(retrieve_args["target"], final_filename)
                logger.info(f"已将临时文件重命名为: {os.path.basename(final_filename)}")
            return True

        except Exception as e:
            if attempt == max_retries:
                logger.error(
                    f"❌ 下载 {filename} 在 {max_retries} 次重试后仍然失败: {str(e)}"
                )
                return False

            # 计算延迟时间（指数退避）
            delay = min(2**attempt + random.uniform(0, 1), 30)  # 最大延迟30秒

            logger.warning(f"⚠️  下载 {filename} 第 {attempt + 1} 次尝试失败: {str(e)}")
            logger.info(f"等待 {delay:.1f} 秒后进行第 {attempt + 2} 次尝试...")

            time.sleep(delay)

    return False


def download_ecmwf_multi_streams(
    date=None, time="00", step=0, target_dir="./data", max_retries=3, retry_delay_base=1
):
    """
    下载多种ECMWF数据流

    参数:
    - date: 预报日期，格式 'YYYY-MM-DD'，默认为当天
    - time: 预报时间，可选 '00', '06', '12', '18'
    - step: 预报步长（小时）
    - target_dir: 目标目录
    - max_retries: 最大重试次数，默认3次
    - retry_delay_base: 重试基础延迟时间（秒），默认1秒
    """

    # 如果未指定日期，使用当天
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # 创建目标目录
    os.makedirs(target_dir, exist_ok=True)

    # 加载已下载文件的记录
    downloaded_files = load_download_records()

    # 定义数据流配置
    # 根据ECMWF文档和图片中的文件名格式
    data_streams = [
        {
            "source": "ecmwf",
            "stream": "oper",  # 业务预报
            "type": "fc",  # forecast
            "levtype": "pl",  # 压力层
            "levelist": [
                1000,
                925,
                850,
                700,
                500,
                200,
            ],
            "params": ["u", "v", "t", "q", "gh"],  # 2米温度和表面气压
            # "params": None,
            "suffix": "oper-fc",
        },
        # {
        #     'source': 'ecmwf',
        #     'stream': 'enfo',  # 集合预报
        #     'type': 'ef',      # ensemble forecast
        #     # 'params': ['2t', 'sp'],
        #     'params': None,
        #     'suffix': 'enfo-ef'
        # },
        # {
        #     'source': 'ecmwf',
        #     'stream': 'wave',  # 波浪预报
        #     'type': 'fc',      # forecast
        #     # 'params': ['swh', 'mwp'],  # 有效波高和平均波周期
        #     'params': None,
        #     'suffix': 'wave-fc'
        # },
        # {
        #     'source': 'ecmwf',
        #     'stream': 'waef',  # 波浪集合预报
        #     'type': 'ef',      # ensemble forecast
        #     # 'params': ['swh', 'mwp'],
        #     'params': None,
        #     'suffix': 'waef-ef'
        # }
    ]

    logger.info(f"开始下载 {date} {time}Z 起报的多种ECMWF数据...")

    success_count = 0
    total_count = len(data_streams)
    failed_downloads = []
    skipped_count = 0

    for stream_config in data_streams:
        try:
            # 检查文件是否已经下载过
            if is_file_downloaded(
                date,
                time,
                step,
                stream_config["stream"],
                stream_config["type"],
                downloaded_files,
            ):
                logger.info(
                    f"⏭️  跳过已下载的文件: {stream_config['stream']} ({date} {time}Z +{step}h)"
                )
                skipped_count += 1
                success_count += 1  # 算作成功，因为文件已存在
                continue

            logger.info(f"正在下载 {stream_config['stream']} 数据...")

            # 创建客户端
            client = Client(source=stream_config["source"])

            # 生成文件名 - 遵循图片中显示的格式
            # 格式：YYYYMMDDHHMMSS-{step}h-{stream}-{type}.grib2
            date_str = datetime.strptime(date, "%Y-%m-%d").strftime("%Y%m%d")
            # time_str = f"{time}0000"  # 添加分钟和秒

            if time in ["06", "18"]:
                if stream_config["stream"] == "wave":
                    stream_config["suffix"] = "scwv-fc"
                elif stream_config["stream"] == "oper":
                    stream_config["suffix"] = "scda-fc"

            # filename = (
            #     f"{date_str}{time_str}-{step}h-{stream_config['suffix']}.grib2.tmp"
            # )

            filename = f"{stream_config['source']}_{stream_config['levtype']}_{date_str}{time}_step{step:03d}.grib2.tmp"

            target_path = os.path.join(target_dir, filename)

            # 检查缓存文件是否已存在，如果存在则删除
            if os.path.exists(target_path):
                file_size = os.path.getsize(target_path) / (1024 * 1024)  # 转换为MB
                logger.info(f"存在缓存文件: {filename} ({file_size:.2f} MB)，删除")
                os.remove(target_path)

            # 准备下载参数
            retrieve_args = {
                "date": date,
                "time": time,
                "type": stream_config["type"],
                "stream": stream_config["stream"],
                "step": str(step),
                "target": target_path,
                "resol": "0p25",
            }

            # 只有在params不为None时才添加param参数
            if stream_config["params"] is not None:
                retrieve_args["param"] = stream_config["params"]

            # 只有在levtype和levelist存在时才添加
            if "levtype" in stream_config and "levelist" in stream_config:
                retrieve_args["levtype"] = stream_config["levtype"]
                retrieve_args["levelist"] = stream_config["levelist"]

            # 使用重试机制下载数据
            download_success = download_single_stream(
                client, retrieve_args, filename, max_retries
            )

            if download_success:
                success_count += 1
                # 记录文件已成功下载
                mark_file_downloaded(
                    date,
                    time,
                    step,
                    stream_config["stream"],
                    stream_config["type"],
                    downloaded_files,
                )
            else:
                failed_downloads.append(
                    {
                        "stream": stream_config["stream"],
                        "filename": filename,
                        "error": "多次重试后仍然失败",
                    }
                )

        except Exception as e:
            logger.error(f"❌ 下载 {stream_config['stream']} 发生意外错误: {str(e)}")
            failed_downloads.append(
                {
                    "stream": stream_config["stream"],
                    "filename": f"未知文件名 ({stream_config['stream']})",
                    "error": str(e),
                }
            )
            continue

    # 汇总下载结果
    logger.info(
        f"下载完成！成功: {success_count}/{total_count} (其中跳过已下载: {skipped_count})"
    )
    if failed_downloads:
        logger.warning(f"失败的下载任务 ({len(failed_downloads)} 个):")
        for failed in failed_downloads:
            logger.warning(
                f"  - {failed['stream']}: {failed['filename']} - {failed['error']}"
            )

    logger.info(f"文件保存在: {target_dir}")

    return {
        "success_count": success_count,
        "total_count": total_count,
        "skipped_count": skipped_count,
        "failed_downloads": failed_downloads,
    }


def download_multi_steps(
    date=None,
    forecast_time="00",
    steps=range(0, 12, 3),
    target_dir="./data",
    max_retries=3,
    retry_delay_base=1,
):
    """下载多个时间步长的数据"""
    for step in tqdm(steps, desc="下载不同时间步长"):
        download_ecmwf_multi_streams(
            date, forecast_time, step, target_dir, max_retries, retry_delay_base
        )


def download_multi_times(
    date=None,
    times=["00", "06", "12", "18"],
    step=0,
    target_dir="./data",
    max_retries=3,
    retry_delay_base=1,
):
    """下载多个预报时间的数据"""
    for forecast_time in tqdm(times, desc="下载不同预报时间"):
        download_ecmwf_multi_streams(
            date, forecast_time, step, target_dir, max_retries, retry_delay_base
        )


def download_multi_times_steps(
    date=None,
    times=["00", "06", "12", "18"],
    steps=range(0, 12, 3),
    target_dir="./data",
    max_retries=3,
    retry_delay_base=1,
):
    """下载多个预报时间和多个时间步长的组合"""
    for forecast_time in tqdm(times, desc="下载不同预报时间"):
        for step in steps:
            download_ecmwf_multi_streams(
                date, forecast_time, step, target_dir, max_retries, retry_delay_base
            )


def scheduled_download_task():
    """定时下载任务：下载近一天的数据，考虑跨天情况"""

    logger.info(f"开始定时下载任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 获取近24小时的预报时间（每6小时一次：00Z, 06Z, 12Z, 18Z）
    client = Client(source="ecmwf")
    # 获取最新起报时 (UTC)
    start_time = client.latest(type="fc")
    print(f"Latest run (UTC): {start_time}")

    # current_time = datetime.utcnow()
    current_time = start_time + timedelta(hours=6)
    download_tasks = []

    # 获取过去72小时内的预报时间，考虑跨天情况
    for hours_back in range(0, 73, 6):  # 0, 6, 12, 18, 24 小时前
        forecast_time = current_time - timedelta(hours=hours_back)
        # 调整到最近的6小时边界
        forecast_hour = (forecast_time.hour // 6) * 6
        forecast_time = forecast_time.replace(
            hour=forecast_hour, minute=0, second=0, microsecond=0
        )

        # 生成下载任务：(日期, 时间)
        date_str = forecast_time.strftime("%Y-%m-%d")
        time_str = forecast_time.strftime("%H")

        task = (date_str, time_str)
        if task not in download_tasks:
            download_tasks.append(task)

    # 按日期和时间排序
    download_tasks.sort()

    logger.info("计划下载以下预报时间的数据:")
    for date_str, time_str in download_tasks:
        logger.info(f"  - {date_str} {time_str}Z")

    try:
        # 分别下载每个预报时间的数据
        for date_str, time_str in download_tasks:
            logger.info(f"下载 {date_str} {time_str}Z 起报的数据...")
            download_multi_steps(
                date=date_str,
                forecast_time=time_str,
                steps=[0, 3, 6],
                target_dir="./ecmwf_data",
                max_retries=5,  # 定时任务中使用更多重试次数
                retry_delay_base=2.0,  # 更长的延迟时间
            )

        logger.info(
            f"定时下载任务完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        logger.error(
            f"定时下载任务出错 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {e}"
        )


def run_scheduler():
    """运行定时调度器"""

    logger.info("启动定时下载任务...")
    logger.info("每小时下载一次近一天的ECMWF数据")
    logger.info("按 Ctrl+C 停止")

    # 设置每10分钟运行一次
    schedule.every(10).minutes.do(scheduled_download_task)

    # 立即运行一次
    logger.info("立即执行首次下载...")
    scheduled_download_task()

    # 优雅停止的信号处理
    def signal_handler(sig, frame):
        logger.info("收到停止信号，正在退出...")
        schedule.clear()
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 主循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("定时任务已停止")
        schedule.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="下载多种ECMWF数据流")
    parser.add_argument("--date", type=str, help="预报日期 (YYYY-MM-DD)，默认今天")
    parser.add_argument(
        "--time",
        type=str,
        default="00",
        choices=["00", "06", "12", "18"],
        help="预报时间 (默认: 00)",
    )
    parser.add_argument(
        "--times",
        type=str,
        nargs="+",
        choices=["00", "06", "12", "18"],
        help="多个预报时间，如 --times 00 12",
    )
    parser.add_argument("--step", type=int, default=0, help="预报步长（小时，默认: 0）")
    parser.add_argument(
        "--steps", type=int, nargs="+", help="多个预报步长，如 --steps 0 3 6 9"
    )
    parser.add_argument(
        "--multi-steps", action="store_true", help="下载多个时间步长 (0,3,6,9h)"
    )
    parser.add_argument(
        "--multi-times", action="store_true", help="下载多个预报时间 (00,06,12,18Z)"
    )
    parser.add_argument(
        "--multi-all", action="store_true", help="下载多个预报时间和多个时间步长的组合"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="启动定时下载任务（每小时下载近一天数据）",
    )
    parser.add_argument(
        "--target-dir", type=str, default="./data", help="目标目录 (默认: ./data)"
    )

    # 重试机制相关参数
    parser.add_argument(
        "--max-retries", type=int, default=3, help="最大重试次数 (默认: 3)"
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="重试基础延迟时间（秒，默认: 1.0）",
    )

    # 下载记录管理参数
    parser.add_argument("--clear-records", action="store_true", help="清除所有下载记录")
    parser.add_argument("--show-records", action="store_true", help="显示当前下载记录")

    args = parser.parse_args()

    # 处理下载记录管理命令
    if args.clear_records:
        ensure_logs_dir()
        if os.path.exists(DOWNLOAD_RECORD_FILE):
            os.remove(DOWNLOAD_RECORD_FILE)
            logger.info("已清除所有下载记录")
        else:
            logger.info("下载记录文件不存在，无需清除")
        exit(0)

    if args.show_records:
        downloaded_files = load_download_records()
        if downloaded_files:
            logger.info(f"当前已下载 {len(downloaded_files)} 个文件:")
            for file_id in sorted(downloaded_files):
                logger.info(f"  - {file_id}")
        else:
            logger.info("暂无下载记录")
        exit(0)

    # 如果指定了定时任务，启动调度器
    if args.schedule:
        run_scheduler()
        exit(0)

    # 确定要使用的时间列表
    if args.times:
        times_list = args.times
    elif args.multi_times or args.multi_all:
        times_list = ["00", "06", "12", "18"]
    else:
        times_list = [args.time]

    # 确定要使用的步长列表
    if args.steps:
        steps_list = args.steps
    elif args.multi_steps or args.multi_all:
        steps_list = list(range(0, 12, 3))
    else:
        steps_list = [args.step]

    # 根据参数选择相应的下载函数
    if args.multi_all or (len(times_list) > 1 and len(steps_list) > 1):
        # 下载多个时间和多个步长的组合
        download_multi_times_steps(
            date=args.date,
            times=times_list,
            steps=steps_list,
            target_dir=args.target_dir,
            max_retries=args.max_retries,
            retry_delay_base=args.retry_delay,
        )
    elif len(times_list) > 1:
        # 下载多个预报时间，单个步长
        download_multi_times(
            date=args.date,
            times=times_list,
            step=args.step,
            target_dir=args.target_dir,
            max_retries=args.max_retries,
            retry_delay_base=args.retry_delay,
        )
    elif len(steps_list) > 1:
        # 下载单个预报时间，多个步长
        download_multi_steps(
            date=args.date,
            forecast_time=args.time,
            steps=steps_list,
            target_dir=args.target_dir,
            max_retries=args.max_retries,
            retry_delay_base=args.retry_delay,
        )
    else:
        # 下载单个时间和步长
        download_ecmwf_multi_streams(
            date=args.date,
            time=args.time,
            step=args.step,
            target_dir=args.target_dir,
            max_retries=args.max_retries,
            retry_delay_base=args.retry_delay,
        )