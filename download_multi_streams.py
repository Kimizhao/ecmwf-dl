#!/usr/bin/env python3
"""
下载多种ECMWF数据流的脚本
支持下载 oper(业务预报)、enfo(集合预报)、wave(波浪预报)、waef(波浪集合) 数据
"""

from ecmwf.opendata import Client
import datetime
import os
from tqdm import tqdm


def download_ecmwf_multi_streams(date=None, time='00', step=0, target_dir='./data'):
    """
    下载多种ECMWF数据流
    
    参数:
    - date: 预报日期，格式 'YYYY-MM-DD'，默认为当天
    - time: 预报时间，可选 '00', '06', '12', '18'
    - step: 预报步长（小时）
    - target_dir: 目标目录
    """
    
    # 如果未指定日期，使用当天
    if date is None:
        date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # 创建目标目录
    os.makedirs(target_dir, exist_ok=True)
    
    # 定义数据流配置
    # 根据ECMWF文档和图片中的文件名格式
    data_streams = [
        # {
        #     'source': 'ecmwf',
        #     'stream': 'oper',  # 业务预报
        #     'type': 'fc',      # forecast
        #     'params': ['2t', 'sp'],  # 2米温度和表面气压
        #     'suffix': 'oper-fc'
        # },
        # {
        #     'source': 'ecmwf', 
        #     'stream': 'enfo',  # 集合预报
        #     'type': 'ef',      # ensemble forecast
        #     'params': ['2t', 'sp'],
        #     'suffix': 'enfo-ef'
        # },
        {
            'source': 'ecmwf',
            'stream': 'wave',  # 波浪预报
            'type': 'fc',      # forecast
            # 'params': ['swh', 'mwp'],  # 有效波高和平均波周期
            'params': None,
            'suffix': 'wave-fc'
        },
        # {
        #     'source': 'ecmwf',
        #     'stream': 'waef',  # 波浪集合预报
        #     'type': 'ef',      # ensemble forecast  
        #     'params': ['swh', 'mwp'],
        #     'suffix': 'waef-ef'
        # }
    ]
    
    print(f"开始下载 {date} {time}Z 起报的多种ECMWF数据...")
    
    for stream_config in data_streams:
        try:
            print(f"\n正在下载 {stream_config['stream']} 数据...")
            
            # 创建客户端
            client = Client(source=stream_config['source'])
            
            # 生成文件名 - 遵循图片中显示的格式
            # 格式：YYYYMMDDHHMMSS-{step}h-{stream}-{type}.grib2
            date_str = datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%Y%m%d')
            time_str = f"{time}0000"  # 添加分钟和秒
            filename = f"{date_str}{time_str}-{step}h-{stream_config['suffix']}.grib2"
            target_path = os.path.join(target_dir, filename)
            
            # 下载数据
            retrieve_args = {
                'date': date,
                'time': time,
                'type': stream_config['type'],
                'stream': stream_config['stream'],
                'step': str(step),
                'target': target_path
            }
            
            # 只有在params不为None时才添加param参数
            if stream_config['params'] is not None:
                retrieve_args['param'] = stream_config['params']
                
            client.retrieve(**retrieve_args)
            
            print(f"✅ 成功下载: {filename}")
            
        except Exception as e:
            print(f"❌ 下载 {stream_config['stream']} 失败: {str(e)}")
            continue
    
    print(f"\n下载完成！文件保存在: {target_dir}")


def download_multi_steps(date=None, time='00', steps=range(0, 12, 3), target_dir='./data'):
    """
    下载多个时间步长的数据
    
    参数:
    - date: 预报日期
    - time: 预报时间
    - steps: 预报步长列表，默认 [0, 3, 6, 9]
    - target_dir: 目标目录
    """
    
    for step in tqdm(steps, desc="下载不同时间步长"):
        print(f"\n=== 下载 {step}h 预报数据 ===")
        download_ecmwf_multi_streams(date=date, time=time, step=step, target_dir=target_dir)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="下载多种ECMWF数据流")
    parser.add_argument('--date', type=str, help='预报日期 (YYYY-MM-DD)，默认今天')
    parser.add_argument('--time', type=str, default='00', choices=['00', '06', '12', '18'], 
                       help='预报时间 (默认: 00)')
    parser.add_argument('--step', type=int, default=0, help='预报步长（小时，默认: 0）')
    parser.add_argument('--multi-steps', action='store_true', help='下载多个时间步长 (0,3,6,9h)')
    parser.add_argument('--target-dir', type=str, default='./data', help='目标目录 (默认: ./data)')
    
    args = parser.parse_args()
    
    if args.multi_steps:
        download_multi_steps(date=args.date, time=args.time, target_dir=args.target_dir)
    else:
        download_ecmwf_multi_streams(
            date=args.date, 
            time=args.time, 
            step=args.step, 
            target_dir=args.target_dir
        )