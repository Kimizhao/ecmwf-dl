#!/usr/bin/env python3
"""
公网下载脚本：获取 ECMWF 最新预报初始场，保存为 ec_inputs/YYYYMMDDHH/ 下的五个 grib2 文件。
传输整个 ec_inputs 目录到内网后，内网即可离线使用。
"""

import argparse
import json
import logging
import os
import random
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path

import schedule
from ecmwf.opendata import Client

# 高空等压面层次（与 PrepareInputs 一致）
LEVELS = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50][::-1]
ATMOSPHERE_PARAMS = ["gh", "t", "q", "u", "v"]
SURFACE_PARAMS = [
    ("msl", "msl"),
    ("10u", "10u"),
    ("10v", "10v"),
    ("2t", "2t"),
]
DEFAULT_STEPS = [0, 6]
DOWNLOAD_RECORD_FILE = Path("logs/download_inputs_scheduled.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def ensure_logs_dir() -> None:
    """确保 logs 目录存在。"""
    DOWNLOAD_RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_download_records() -> set[str]:
    """加载已成功下载的文件记录。"""
    ensure_logs_dir()
    if not DOWNLOAD_RECORD_FILE.exists():
        return set()

    try:
        with DOWNLOAD_RECORD_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return set(data.get("downloaded_files", []))
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        logger.warning("读取下载记录失败，将重新创建: %s", exc)
        return set()


def save_download_records(downloaded_files: set[str]) -> None:
    """保存已成功下载的文件记录。"""
    ensure_logs_dir()
    data = {
        "downloaded_files": sorted(downloaded_files),
        "last_updated": datetime.now().isoformat(),
    }
    tmp_path = DOWNLOAD_RECORD_FILE.with_suffix(".json.tmp")

    try:
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        os.replace(tmp_path, DOWNLOAD_RECORD_FILE)
    except OSError as exc:
        logger.error("保存下载记录失败: %s", exc)


def file_identifier(init_time: datetime, name: str, steps: list[int]) -> str:
    """生成下载记录标识，避免重复下载同一份数据。"""
    step_text = ",".join(str(step) for step in steps)
    return f"{init_time:%Y%m%d%H}_{name}_steps_{step_text}"


def parse_steps(value: str) -> list[int]:
    """解析逗号分隔的预报步长。"""
    try:
        steps = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("steps 必须是逗号分隔的整数，例如 0,6") from exc

    if not steps:
        raise argparse.ArgumentTypeError("steps 不能为空")
    return steps


def parse_init_time(value: str) -> datetime:
    """解析起报时次，支持 YYYYMMDDHH 或 YYYY-MM-DDTHH。"""
    for fmt in ("%Y%m%d%H", "%Y-%m-%dT%H", "%Y-%m-%d %H"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError("起报时次格式应为 YYYYMMDDHH 或 YYYY-MM-DDTHH")


def build_client(source: str) -> Client:
    """创建 ECMWF Open Data 客户端。"""
    return Client(source=source)


def retrieve_with_retries(
    client: Client,
    request: dict,
    target: Path,
    max_retries: int,
    retry_delay: float,
) -> bool:
    """下载单个文件，失败后指数退避重试，并用临时文件避免半成品。"""
    tmp_target = target.with_suffix(target.suffix + ".tmp")
    if tmp_target.exists():
        tmp_target.unlink()

    for attempt in range(max_retries + 1):
        try:
            client.retrieve(request, target=tmp_target)
            os.replace(tmp_target, target)
            logger.info("下载完成: %s", target.name)
            return True
        except Exception as exc:
            if tmp_target.exists():
                tmp_target.unlink()

            if attempt >= max_retries:
                logger.error("下载失败: %s，已重试 %s 次，错误: %s", target.name, max_retries, exc)
                return False

            delay = min(retry_delay * (2**attempt), 60.0)
            delay *= 0.5 + random.random() * 0.5
            logger.warning("下载 %s 第 %s 次失败: %s", target.name, attempt + 1, exc)
            logger.info("等待 %.1f 秒后重试...", delay)
            time.sleep(delay)

    return False


def download_file(
    client: Client,
    init_time: datetime,
    name: str,
    request: dict,
    target: Path,
    steps: list[int],
    downloaded_files: set[str],
    max_retries: int,
    retry_delay: float,
    force: bool,
) -> bool:
    """下载并记录一个文件。"""
    record_id = file_identifier(init_time, name, steps)
    if not force and record_id in downloaded_files:
        logger.info("记录显示该文件已下载过，跳过下载 (可能已被移动或删除): %s", target.name)
        return True

    if target.exists() and target.stat().st_size == 0:
        logger.warning("发现空文件，重新下载: %s", target)
        target.unlink()

    if retrieve_with_retries(client, request, target, max_retries, retry_delay):
        downloaded_files.add(record_id)
        save_download_records(downloaded_files)
        return True
    return False


def download_case(
    init_time: datetime,
    base_dir: str = "ec_inputs",
    source: str = "ecmwf",
    steps: list[int] | None = None,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    force: bool = False,
) -> dict:
    """下载一个起报时次的所有必要变量。"""
    steps = steps or DEFAULT_STEPS
    case_dir = Path(base_dir) / init_time.strftime("%Y%m%d%H")
    case_dir.mkdir(parents=True, exist_ok=True)
    client = build_client(source)
    downloaded_files = load_download_records()
    failed_files = []
    date_str = init_time.strftime("%Y-%m-%d")
    time_str = init_time.strftime("%H")

    logger.info("开始下载起报时次 %s 到 %s", init_time.strftime("%Y%m%d%H"), case_dir)

    atmosphere_request = {
        "param": ATMOSPHERE_PARAMS,
        "type": "fc",
        "date": date_str,
        "time": time_str,
        "step": steps,
        "levtype": "pl",
        "levelist": LEVELS,
    }
    if not download_file(
        client,
        init_time,
        "atmosphere",
        atmosphere_request,
        case_dir / "atmosphere.grib2",
        steps,
        downloaded_files,
        max_retries,
        retry_delay,
        force,
    ):
        failed_files.append("atmosphere.grib2")

    for param, filename in SURFACE_PARAMS:
        surface_request = {
            "param": [param],
            "type": "fc",
            "date": date_str,
            "time": time_str,
            "step": steps,
        }
        target = case_dir / f"{filename}.grib2"
        if not download_file(
            client,
            init_time,
            filename,
            surface_request,
            target,
            steps,
            downloaded_files,
            max_retries,
            retry_delay,
            force,
        ):
            failed_files.append(target.name)

    success_count = len(ATMOSPHERE_PARAMS[:1]) + len(SURFACE_PARAMS) - len(failed_files)
    logger.info("起报时次 %s 下载完成，成功 %s/5", init_time.strftime("%Y%m%d%H"), success_count)
    if failed_files:
        logger.warning("失败文件: %s", ", ".join(failed_files))

    return {
        "case_dir": str(case_dir),
        "success_count": success_count,
        "total_count": 5,
        "failed_files": failed_files,
    }


def get_latest_run(source: str) -> datetime:
    """获取 ECMWF 最新起报时间。"""
    client = build_client(source)
    latest = client.latest(type="fc", param="msl", step=24)
    logger.info("最新起报时间(UTC): %s", latest.strftime("%Y-%m-%d %H:%M"))
    return latest


def build_recent_runs(latest: datetime, lookback_hours: int) -> list[datetime]:
    """生成最近若干小时内的 6 小时间隔起报时次。"""
    runs = []
    for hours_back in range(0, lookback_hours + 1, 6):
        run_time = latest - timedelta(hours=hours_back)
        run_time = run_time.replace(minute=0, second=0, microsecond=0)
        if run_time not in runs:
            runs.append(run_time)
    return sorted(runs)


def scheduled_download_task(args: argparse.Namespace) -> None:
    """定时下载任务：下载最近若干小时的起报时次。"""
    try:
        logger.info("开始定时下载任务")
        latest = get_latest_run(args.source)
        run_times = build_recent_runs(latest, args.lookback_hours)

        logger.info("计划下载以下起报时次:")
        for run_time in run_times:
            logger.info("  - %s", run_time.strftime("%Y%m%d%H"))

        for run_time in run_times:
            download_case(
                init_time=run_time,
                base_dir=args.base_dir,
                source=args.source,
                steps=args.steps,
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
                force=args.force,
            )
        logger.info("定时下载任务完成")
    except Exception as exc:
        logger.exception("定时下载任务异常，本轮跳过: %s", exc)


def run_scheduler(args: argparse.Namespace) -> None:
    """运行定时调度器。"""
    logger.info("启动定时下载任务，每 %s 分钟运行一次", args.interval_minutes)

    def stop_scheduler(signum, frame):
        logger.info("收到停止信号，正在退出...")
        schedule.clear()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, stop_scheduler)
    signal.signal(signal.SIGTERM, stop_scheduler)

    scheduled_download_task(args)
    schedule.every(args.interval_minutes).minutes.do(scheduled_download_task, args)

    while True:
        schedule.run_pending()
        time.sleep(30)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="下载 ECMWF PrepareInputs 所需的五个 grib2 文件")
    parser.add_argument("base_dir_pos", nargs="?", help="兼容旧用法的位置参数：输出目录")
    parser.add_argument("--base-dir", default=None, help="输出根目录，默认 ec_inputs")
    parser.add_argument("--init-time", type=parse_init_time, help="指定起报时次，如 2026070100")
    parser.add_argument("--source", default="ecmwf", choices=["ecmwf", "azure", "aws"], help="数据源")
    parser.add_argument("--steps", type=parse_steps, default=DEFAULT_STEPS, help="预报步长，逗号分隔，默认 0,6")
    parser.add_argument("--max-retries", type=int, default=3, help="最大重试次数，默认 3")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="基础重试等待秒数，默认 2.0")
    parser.add_argument("--force", action="store_true", help="忽略记录并强制重新下载")
    parser.add_argument("--schedule", action="store_true", help="启动定时下载")
    parser.add_argument("--interval-minutes", type=int, default=5, help="定时任务间隔分钟，默认 5")
    parser.add_argument("--lookback-hours", type=int, default=24, help="定时任务回看小时数，默认 24")
    parser.add_argument("--show-records", action="store_true", help="显示下载记录")
    parser.add_argument("--clear-records", action="store_true", help="清空下载记录")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.base_dir = args.base_dir or args.base_dir_pos or "ec_inputs"

    if args.max_retries < 0:
        parser.error("--max-retries 不能小于 0")
    if args.retry_delay <= 0:
        parser.error("--retry-delay 必须大于 0")
    if args.interval_minutes <= 0:
        parser.error("--interval-minutes 必须大于 0")
    if args.lookback_hours < 0:
        parser.error("--lookback-hours 不能小于 0")

    if args.clear_records:
        if DOWNLOAD_RECORD_FILE.exists():
            DOWNLOAD_RECORD_FILE.unlink()
            logger.info("已清空下载记录")
        else:
            logger.info("下载记录不存在，无需清空")
        return

    if args.show_records:
        records = load_download_records()
        logger.info("当前记录 %s 个文件", len(records))
        for record in sorted(records):
            logger.info("  - %s", record)
        return

    if args.schedule:
        run_scheduler(args)
        return

    init_time = args.init_time or get_latest_run(args.source)
    download_case(
        init_time=init_time,
        base_dir=args.base_dir,
        source=args.source,
        steps=args.steps,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        force=args.force,
    )


if __name__ == "__main__":
    main()