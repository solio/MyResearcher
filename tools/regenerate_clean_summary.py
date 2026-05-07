#!/usr/bin/env python3
"""
用过滤后的数据重新生成纪要
"""
import sys
import os
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from researcher import Researcher
from config import Config
from logger import get_logger

logger = get_logger()

def main():
    # 加载过滤后的数据
    filtered_data_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据-过滤后.json'

    with open(filtered_data_path, 'r', encoding='utf-8') as f:
        filtered_data = json.load(f)

    # 初始化研究员
    config = Config()
    researcher = Researcher(config)

    # 生成时间戳
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 分析数据并生成纪要
    print("正在分析数据并生成纪要...")
    summary = researcher.analyze_and_summarize(filtered_data['results'])

    # 保存纪要
    summary_path = f'/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/{timestamp}-纪要-过滤后.md'
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary)

    print(f"纪要已保存到: {summary_path}")
    print("\n" + "="*80)
    print("纪要预览:")
    print("="*80)
    print(summary[:2000] + "..." if len(summary) > 2000 else summary)

if __name__ == '__main__':
    main()
