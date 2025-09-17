#!/usr/bin/env python3
"""
一键下载指定日期的4种ECMWF数据流
这个脚本会下载图片中提到的4个文件类型：oper, enfo, wave, waef
"""

try:
    from ecmwf.opendata import Client
except ImportError:
    print("❌ 缺少依赖: pip install ecmwf-opendata")
    exit(1)

import datetime
import os


def download_four_streams():
    """
    下载图片中提到的4种数据流（基于2025-09-16日期）
    """
    
    # 根据图片中的日期设置
    date = '2025-09-16'
    time = '00'
    step = 0  # 0小时预报
    
    # 创建数据目录
    data_dir = './ecmwf_data'
    os.makedirs(data_dir, exist_ok=True)
    
    # 定义要下载的4种数据流（对应图片中的4个文件）
    streams_config = [
        # {
        #     'stream': 'oper',     # 业务预报
        #     'type': 'fc',         # forecast
        #     'params': ['2t', 'sp'],  # 基础变量
        #     'suffix': 'oper-fc'
        # },
        # {
        #     'stream': 'enfo',     # 集合预报  
        #     'type': 'ef',         # ensemble forecast
        #     'params': ['2t', 'sp'],
        #     'suffix': 'enfo-ef'
        # },
        {
            'stream': 'wave',     # 波浪预报
            'type': 'fc',         # forecast
            # 'params': ['swh'],    # 有效波高
            'params': None,
            'suffix': 'wave-fc'
        },
        # {
        #     'stream': 'waef',     # 波浪集合预报
        #     'type': 'ef',         # ensemble forecast
        #     # 'params': ['swh'],    # 有效波高
        #     'params': None,
        #     'suffix': 'waef-ef'
        # }
    ]
    
    print(f"开始下载 {date} {time}Z 的4种ECMWF数据流...")
    print(f"目标目录: {data_dir}")
    
    successful_downloads = []
    failed_downloads = []
    
    for i, config in enumerate(streams_config, 1):
        try:
            print(f"\n[{i}/4] 正在下载 {config['stream']} 数据...")
            
            # 创建客户端
            client = Client(source='ecmwf')
            
            # 生成文件名 - 按照图片格式：YYYYMMDDHHMMSS-0h-{stream}-{type}.grib2
            date_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
            filename = f"{date_obj.strftime('%Y%m%d')}{time}0000-{step}h-{config['suffix']}.grib2"
            target_path = os.path.join(data_dir, filename)
            
            # 下载数据
            retrieve_args = {
                'date': date,
                'time': time,
                'type': config['type'],
                'stream': config['stream'],
                'step': str(step),
                'target': target_path
            }
            
            # 只有在params不为None时才添加param参数
            if config['params'] is not None:
                retrieve_args['param'] = config['params']
                
            client.retrieve(**retrieve_args)
            
            print(f"✅ 成功: {filename}")
            successful_downloads.append(filename)
            
        except Exception as e:
            error_msg = f"下载 {config['stream']} 失败: {str(e)}"
            print(f"❌ {error_msg}")
            failed_downloads.append(config['stream'])
            continue
    
    # 输出结果摘要
    print(f"\n{'='*60}")
    print("下载结果摘要:")
    print(f"✅ 成功下载 {len(successful_downloads)}/4 个文件")
    
    if successful_downloads:
        print("\n成功下载的文件:")
        for file in successful_downloads:
            print(f"  - {file}")
    
    if failed_downloads:
        print(f"\n❌ 失败的数据流: {', '.join(failed_downloads)}")
        print("   可能原因: 网络问题、数据暂时不可用、或参数配置需要调整")
    
    print(f"\n文件保存位置: {os.path.abspath(data_dir)}")


if __name__ == "__main__":
    print("ECMWF 多数据流下载工具")
    print("将下载图片中提到的4种数据类型")
    print("日期: 2025-09-16 00Z")
    print("-" * 40)
    
    download_four_streams()