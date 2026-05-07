"""
个股价值投研助手 - 主入口
"""
import sys
import argparse
import os

from config import get_config
from researcher import StockResearcher
from scheduler import ResearchScheduler
from logger import get_logger, setup_logger


def run_once():
    """运行一次投研任务"""
    config = get_config()

    # 设置日志
    setup_logger(log_dir=os.path.join(config.OUTPUT_DIR, "logs"),
                 log_level=config.LOG_LEVEL)
    logger = get_logger()

    if not config.validate():
        logger.error("配置验证失败，请检查 .env 文件")
        return

    researcher = StockResearcher(config)
    results = researcher.run_all()
    researcher.save_results(results)


def run_search_only():
    """仅搜索数据，不做分析，不生成纪要"""
    config = get_config()

    # 设置日志
    setup_logger(log_dir=os.path.join(config.OUTPUT_DIR, "logs"),
                 log_level=config.LOG_LEVEL)
    logger = get_logger()

    if not config.validate():
        logger.error("配置验证失败，请检查 .env 文件")
        return

    researcher = StockResearcher(config)
    results = researcher.search_only()
    researcher.save_search_data(results)


def run_daemon():
    """以守护进程方式运行（定时执行）"""
    scheduler = ResearchScheduler()
    scheduler.start()


def main():
    parser = argparse.ArgumentParser(description="个股价值投研助手")
    parser.add_argument(
        "--mode",
        choices=["once", "daemon", "searchOnly"],
        default="once",
        help="运行模式: once=执行一次完整投研, daemon=定时执行, searchOnly=仅搜索数据不分析"
    )

    args = parser.parse_args()

    if args.mode == "once":
        run_once()
    elif args.mode == "searchOnly":
        run_search_only()
    else:
        run_daemon()


if __name__ == "__main__":
    main()
