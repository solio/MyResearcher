"""
个股价值投研助手 - 主入口
"""
import sys
import argparse
import os
from datetime import datetime

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
    parser.add_argument(
        "--backfill",
        type=str,
        default=None,
        metavar="STOCK_CODE",
        help="回填某只股票的历史股吧/雪球数据及情绪分析。如 --backfill 601012"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="回填多少个月的历史数据（默认 3）。与 --from-date / --to-date 互斥"
    )
    parser.add_argument(
        "--from-date",
        type=str,
        default=None,
        metavar="YYYYMMDD",
        help="回填起始日期，如 20260501。需同时指定 --to-date"
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default=None,
        metavar="YYYYMMDD",
        help="回填结束日期，如 20260615。需同时指定 --from-date"
    )
    parser.add_argument(
        "--stock-name",
        type=str,
        default=None,
        help="回填股票的名称（当股票代码不在配置列表中时需要手动指定）"
    )

    args = parser.parse_args()

    # 验证日期格式
    target_date = None
    if args.date:
        try:
            datetime.strptime(args.date, "%Y%m%d")
            target_date = args.date
        except ValueError:
            print(f"错误: 日期格式无效 '{args.date}'，请使用 YYYYMMDD 格式，如 20260527")
            sys.exit(1)

    # 验证回填日期范围
    if bool(args.from_date) != bool(args.to_date):
        print("错误: --from-date 和 --to-date 必须同时指定")
        sys.exit(1)
    if args.from_date:
        try:
            datetime.strptime(args.from_date, "%Y%m%d")
            datetime.strptime(args.to_date, "%Y%m%d")
        except ValueError:
            print(f"错误: 日期格式无效，请使用 YYYYMMDD 格式")
            sys.exit(1)
        if args.from_date > args.to_date:
            print(f"错误: --from-date ({args.from_date}) 不能晚于 --to-date ({args.to_date})")
            sys.exit(1)

    if args.backfill:
        from backfill import backfill_main
        backfill_main(args)
    elif args.mode == "once":
        run_once(target_date=target_date, start_from=args.start_from)
    elif args.mode == "searchOnly":
        run_search_only(target_date=target_date)
    else:
        run_daemon()


if __name__ == "__main__":
    main()
