#!/usr/bin/env python3
"""
公网下载脚本：每天获取 ECMWF 最新预报初始场，保存为 ec_inputs/YYYYMMDDHH/ 下的五个 grib2 文件。
传输整个 ec_inputs 目录到内网后，内网即可离线使用。
"""
import sys
from datetime import datetime
from pathlib import Path
from ecmwf.opendata import Client

# 高空等压面层次（与 PrepareInputs 一致）
LEVELS = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50][::-1]

def download_case(init_time: datetime, base_dir: str = "ec_inputs"):
    """下载一个起报时次的所有必要变量"""
    case_dir = Path(base_dir) / init_time.strftime("%Y%m%d%H")
    case_dir.mkdir(parents=True, exist_ok=True)

    client = Client(source="ecmwf")  # 也可用 "azure" / "aws"

    # ---- 高空大气（位势高度、温度、比湿、风场）----
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

    # ---- 地表变量 ----
    surface_params = [
        ("msl", "msl"),
        ("10u", "10u"),
        ("10v", "10v"),
        ("2t",  "2t"),
    ]
    for param, filename in surface_params:
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

    print(f"起报时次 {init_time.strftime('%Y%m%d%H')} 下载完成\n")

def main():
    # 默认下载最新起报时间；也可通过命令行参数指定具体时次
    client = Client(source="ecmwf")
    latest = client.latest(type="fc", param="msl", step=24)
    print(f"最新起报时间(UTC): {latest.strftime('%Y-%m-%d %H:%M')}")

    base_dir = sys.argv[1] if len(sys.argv) > 1 else "ec_inputs"
    download_case(latest, base_dir)

if __name__ == "__main__":
    main()