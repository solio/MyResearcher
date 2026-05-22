#!/usr/bin/env python3
"""
测试V3情绪分析完整集成
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from config import get_config
from researcher import StockResearcher
from logger import get_logger, setup_logger
import os
from datetime import datetime


def test_single_stock():
    """测试单只股票的V3情绪分析"""
    config = get_config()

    # 设置日志
    log_dir = os.path.join(config.OUTPUT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    setup_logger(log_dir=log_dir, log_level="INFO")
    logger = get_logger()

    # 修改配置，只测试一只股票
    config.STOCK_LIST = [
        {"code": "601012", "name": "隆基绿能", "industry": "光伏", "market_cap": 2000.0},
    ]
    config.INDUSTRY_LIST = []

    logger.info("=" * 60)
    logger.info("测试V3多维度情绪分析")
    logger.info("=" * 60)

    # 创建研究器
    researcher = StockResearcher(config)

    # 运行
    results = researcher.run_all()

    # 保存结果
    researcher.save_results(results)

    # 查看结果
    logger.info("=" * 60)
    logger.info("分析完成")
    logger.info("=" * 60)

    for result in results:
        if result.target_type == "stock" and result.emotion_v3:
            logger.info(f"{result.target_name}:")
            logger.info(f"  新闻分数: {result.emotion_v3.news_score:.3f}")
            logger.info(f"  论坛分数: {result.emotion_v3.forum_score:.3f}")
            logger.info(f"  交易分数: {result.emotion_v3.trading_score:.3f}")
            logger.info(f"  综合分数: {result.emotion_v3.final_score:.3f}")
            logger.info(f"  评级: {result.emotion_v3.rating_emoji} {result.emotion_v3.rating_level}")


if __name__ == "__main__":
    test_single_stock()
