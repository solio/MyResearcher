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


def run_once(target_date: str = None, start_from: str = None):
    """运行一次投研任务"""
    config = get_config()

    # 设置日志
    setup_logger(log_dir=os.path.join(config.OUTPUT_DIR, "logs"),
                 log_level=config.LOG_LEVEL)
    logger = get_logger()

    if not config.validate():
        logger.error("配置验证失败，请检查 .env 文件")
        return

    researcher = StockResearcher(config, target_date=target_date)
    researcher.run_all(start_from=start_from)


def run_search_only(target_date: str = None):
    """仅搜索数据，不做分析，不生成纪要"""
    config = get_config()

    # 设置日志
    setup_logger(log_dir=os.path.join(config.OUTPUT_DIR, "logs"),
                 log_level=config.LOG_LEVEL)
    logger = get_logger()

    if not config.validate():
        logger.error("配置验证失败，请检查 .env 文件")
        return

    researcher = StockResearcher(config, target_date=target_date)
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
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="指定调研日期，格式YYYYMMDD（如 20260527）。股吧和雪球精确到指定日期，新闻尽量不晚于该日期。"
    )
    parser.add_argument(
        "--from",
        type=str,
        default=None,
        dest="start_from",
        help="从指定股票代码或行业名称开始分析，跳过之前的标的。如 --from 002407 或 --from 光伏行业。"
    )

    args = parser.parse_args()

    # 验证日期格式
    target_date = None
    if args.date:
        try:
            from datetime import datetime
            datetime.strptime(args.date, "%Y%m%d")
            target_date = args.date
        except ValueError:
            print(f"错误: 日期格式无效 '{args.date}'，请使用 YYYYMMDD 格式，如 20260527")
            sys.exit(1)

    if args.mode == "once":
        run_once(target_date=target_date, start_from=args.start_from)
    elif args.mode == "searchOnly":
        run_search_only(target_date=target_date)
    else:
        run_daemon()


if __name__ == "__main__":
    main()
