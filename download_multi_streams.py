#!/usr/bin/env python3
"""
下载多种ECMWF数据流的脚本
支持下载 oper(业务预报)、enfo(集合预报)、wave(波浪预报)、waef(波浪集合) 数据

使用示例:
1. 下载单个时间和步长:
   python download_multi_streams.py --date 2025-09-17 --time 00 --step 0

2. 下载多个预报时间 (00Z, 06Z, 12Z, 18Z):
   python download_multi_streams.py --multi-times
   python download_multi_streams.py --times 00 12  # 仅下载00Z和12Z

3. 下载多个时间步长 (0, 3, 6, 9小时):
   python download_multi_streams.py --multi-steps
   python download_multi_streams.py --steps 0 6 12  # 仅下载指定步长

4. 下载多个预报时间和多个时间步长的组合:
   python download_multi_streams.py --multi-all

5. 自定义组合:
   python download_multi_streams.py --times 00 12 --steps 0 3 6
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
        {
            'source': 'ecmwf',
            'stream': 'oper',  # 业务预报
            'type': 'fc',      # forecast
            'params': ['gh', 'q', 't', 'u', 'v'],
            'levelist': ['1000', '925', '850', '700', '500', '200'],
            'suffix': 'pl'
        }
        # {
        #     'source': 'ecmwf', 
        #     'stream': 'enfo',  # 集合预报
        #     'type': 'ef',      # ensemble forecast
        #     'params': ['2t', 'sp'],
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
            
            if stream_config['suffix'] == 'pl':
                # 遵循 ecmwf_pl_YYYYMMDDHH_stepXXX.grib2 格式
                filename = f"ecmwf_pl_{date_str}{time}_step{int(step):03d}.grib2"
            else:
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
                
            # 只有在levelist存在且不为None时才添加levelist参数
            if 'levelist' in stream_config and stream_config['levelist'] is not None:
                retrieve_args['levelist'] = stream_config['levelist']
                
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


def download_multi_times(date=None, times=['00', '06', '12', '18'], step=0, target_dir='./data'):
    """
    下载多个预报时间的数据
    
    参数:
    - date: 预报日期，格式 'YYYY-MM-DD'，默认为当天
    - times: 预报时间列表，默认 ['00', '06', '12', '18']
    - step: 预报步长（小时）
    - target_dir: 目标目录
    """
    
    for time in tqdm(times, desc="下载不同预报时间"):
        print(f"\n=== 下载 {time}Z 起报数据 ===")
        download_ecmwf_multi_streams(date=date, time=time, step=step, target_dir=target_dir)


def download_multi_times_steps(date=None, times=['00', '06', '12', '18'], steps=range(0, 12, 3), target_dir='./data'):
    """
    下载多个预报时间和多个时间步长的数据
    
    参数:
    - date: 预报日期，格式 'YYYY-MM-DD'，默认为当天
    - times: 预报时间列表，默认 ['00', '06', '12', '18']
    - steps: 预报步长列表，默认 [0, 3, 6, 9]
    - target_dir: 目标目录
    """
    
    total_tasks = len(times) * len(steps)
    print(f"将下载 {len(times)} 个预报时间 × {len(steps)} 个时间步长 = {total_tasks} 个数据集")
    
    for time in times:
        print(f"\n🕐 开始下载 {time}Z 起报的所有时间步长...")
        for step in tqdm(steps, desc=f"下载 {time}Z 不同时间步长"):
            print(f"\n=== 下载 {time}Z 起报 {step}h 预报数据 ===")
            download_ecmwf_multi_streams(date=date, time=time, step=step, target_dir=target_dir)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="下载多种ECMWF数据流")
    parser.add_argument('--date', type=str, help='预报日期 (YYYY-MM-DD)，默认今天')
    parser.add_argument('--time', type=str, default='00', choices=['00', '06', '12', '18'], 
                       help='预报时间 (默认: 00)')
    parser.add_argument('--times', type=str, nargs='+', choices=['00', '06', '12', '18'],
                       help='多个预报时间，如 --times 00 12')
    parser.add_argument('--step', type=int, default=0, help='预报步长（小时，默认: 0）')
    parser.add_argument('--steps', type=int, nargs='+', help='多个预报步长，如 --steps 0 3 6 9')
    parser.add_argument('--multi-steps', action='store_true', help='下载多个时间步长 (0,3,6,9h)')
    parser.add_argument('--multi-times', action='store_true', help='下载多个预报时间 (00,06,12,18Z)')
    parser.add_argument('--multi-all', action='store_true', help='下载多个预报时间和多个时间步长的组合')
    parser.add_argument('--target-dir', type=str, default='./data', help='目标目录 (默认: ./data)')
    
    args = parser.parse_args()
    
    # 确定要使用的时间列表
    if args.times:
        times_list = args.times
    elif args.multi_times or args.multi_all:
        times_list = ['00', '06', '12', '18']
    else:
        times_list = [args.time]
    
    # 确定要使用的步长列表  
    if args.steps:
        steps_list = args.steps
    elif args.multi_steps or args.multi_all:
        steps_list = list(range(0, 12, 3))
    else:
        steps_list = [args.step]
    
    # 根据参数选择执行模式
    if args.multi_all or (args.multi_times and args.multi_steps):
        # 下载多个时间和多个步长的组合
        download_multi_times_steps(
            date=args.date, 
            times=times_list, 
            steps=steps_list,
            target_dir=args.target_dir
        )
    elif args.multi_times or len(times_list) > 1:
        # 下载多个预报时间
        download_multi_times(
            date=args.date, 
            times=times_list, 
            step=args.step,
            target_dir=args.target_dir
        )
    elif args.multi_steps or len(steps_list) > 1:
        # 下载多个时间步长
        download_multi_steps(
            date=args.date, 
            time=args.time, 
            steps=steps_list,
            target_dir=args.target_dir
        )
    else:
        # 下载单个时间和步长
        download_ecmwf_multi_streams(
            date=args.date, 
            time=args.time, 
            step=args.step, 
            target_dir=args.target_dir
        )