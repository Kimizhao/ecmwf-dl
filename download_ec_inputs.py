#!/usr/bin/env python3
"""
公网下载脚本：每天获取 ECMWF 最新预报初始场，保存为 ec_inputs/YYYYMMDDHH/ 下的五个 grib2 文件。
传输整个 ec_inputs 目录到内网后，内网即可离线使用。
"""
import sys
import json
from datetime import datetime
from pathlib import Path
from ecmwf.opendata import Client

# 高空等压面层次（与 PrepareInputs 一致）
LEVELS = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50][::-1]

RECORD_FILE = Path("logs/download_ec_inputs.json")

def load_records() -> set[str]:
    """从本地 JSON 文件加载已成功下载的记录标识"""
    if not RECORD_FILE.exists():
        return set()
    try:
        with open(RECORD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("downloaded_files", []))
    except Exception as e:
        print(f"读取下载记录失败，将重新创建: {e}")
        return set()

def save_record(record_id: str):
    """保存下载成功的记录标识到本地 JSON 文件"""
    RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    records = load_records()
    records.add(record_id)
    try:
        # 使用临时文件写入再重命名，防止写入过程中损坏文件
        tmp_file = RECORD_FILE.with_suffix(".json.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "downloaded_files": sorted(list(records)),
                    "last_updated": datetime.now().isoformat()
                },
                f,
                indent=4,
                ensure_ascii=False
            )
        tmp_file.replace(RECORD_FILE)
    except Exception as e:
        print(f"保存下载记录失败: {e}")

def download_case(init_time: datetime, base_dir: str = "ec_inputs"):
    """下载一个起报时次的所有必要变量"""
    init_time_str = init_time.strftime("%Y%m%d%H")
    case_dir = Path(base_dir) / init_time_str
    case_dir.mkdir(parents=True, exist_ok=True)

    client = Client(source="ecmwf")  # 也可用 "azure" / "aws"
    records = load_records()

    # ---- 高空大气（位势高度、温度、比湿、风场）----
    atm_record = f"{init_time_str}_atmosphere"
    if atm_record in records:
        print(f"高空大气变量 ({init_time_str}) 已记录在下载历史中，跳过下载。")
    else:
        print(f"下载高空变量...")
        client.retrieve(
            {
                "param": ["gh", "t", "q", "u", "v"],
                "type": "fc",
                "date": init_time,
                "step": [0, 6],
                "levelist": LEVELS,
            },
            target=case_dir / "atmosphere.grib2"
        )
        save_record(atm_record)

    # ---- 地表变量 ----
    surface_params = [
        ("msl", "msl"),
        ("10u", "10u"),
        ("10v", "10v"),
        ("2t",  "2t"),
    ]
    for param, filename in surface_params:
        surf_record = f"{init_time_str}_{filename}"
        if surf_record in records:
            print(f"地表变量 {param} ({init_time_str}) 已记录在下载历史中，跳过下载。")
            continue
        print(f"下载地表变量: {param}")
        client.retrieve(
            {
                "param": [param],
                "type": "fc",
                "date": init_time,
                "time": 0,
                "step": [0, 6],
            },
            target=case_dir / f"{filename}.grib2"
        )
        save_record(surf_record)

    print(f"起报时次 {init_time_str} 下载流程处理完毕。\n")

def main():
    # 默认下载最新起报时间；也可通过命令行参数指定具体时次
    client = Client(source="ecmwf")
    latest = client.latest(type="fc", param="msl", step=24)
    print(f"最新起报时间(UTC): {latest.strftime('%Y-%m-%d %H:%M')}")

    base_dir = sys.argv[1] if len(sys.argv) > 1 else "ec_inputs"
    download_case(latest, base_dir)

if __name__ == "__main__":
    main()