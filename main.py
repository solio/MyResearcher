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


def supplement_news(data_file: str):
    """为已有投研数据补充Tavily新闻搜索，重算V3情绪并更新纪要"""
    import json
    from pathlib import Path
    from searcher import TavilySearchProvider, NewsDeduplicator
    from llm import DeepSeekLLMProvider, StockAnalyzer
    from emotion import EmotionAnalyzer

    config = get_config()
    setup_logger(log_dir=os.path.join(config.OUTPUT_DIR, "logs"),
                 log_level=config.LOG_LEVEL)
    logger = get_logger()

    # 加载数据文件
    data_path = Path(data_file)
    if not data_path.exists():
        logger.error(f"数据文件不存在: {data_file}")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results_data = data.get("results", [])
    date_str = data.get("date", "")

    # 统计需要补充的标的（缺少新闻或缺少雪球）
    need_supplement = []
    for r in results_data:
        news_count = sum(1 for n in r.get("news_list", [])
                        if n.get("source_type") == "news" and not n.get("is_warning"))
        xueqiu_count = sum(1 for n in r.get("news_list", [])
                          if n.get("source") == "xueqiu")
        if r["target_type"] == "stock":
            if news_count == 0 or xueqiu_count == 0:
                need_supplement.append(r)
        elif news_count == 0:
            need_supplement.append(r)

    if not need_supplement:
        logger.info("所有标的已有新闻+雪球数据，无需补充")
        return

    logger.info(f"共 {len(need_supplement)} 个标的需补充（新闻/雪球），开始...")

    # 初始化搜索
    provider = TavilySearchProvider(
        api_keys=config.TAVILY_API_KEYS,
        tavily_time_range_days=config.TAVILY_SEARCH_TIME_RANGE_DAYS
    )
    deduplicator = NewsDeduplicator()

    # 初始化 LLM
    llm = DeepSeekLLMProvider(
        api_key=config.DEEPSEEK_API_KEY,
        api_base=config.DEEPSEEK_API_BASE,
        model=config.DEEPSEEK_MODEL,
        timeout=config.LLM_TIMEOUT,
        max_retries=config.LLM_MAX_RETRIES
    )
    analyzer = StockAnalyzer(llm)
    emotion = EmotionAnalyzer(config)

    # 构建股票代码→信息映射
    stock_map = {s["code"]: s for s in config.STOCK_LIST}

    updated_count = 0
    for r in results_data:
        target_name = r["target_name"]
        # 提取股票代码
        import re
        code_match = re.search(r'\((\d{6})\)', target_name)
        stock_code = code_match.group(1) if code_match else None
        stock_name = target_name.split("(")[0] if "(" in target_name else target_name

        # 检查是否需要补充（新闻或雪球任一缺失都要补）
        news_count = sum(1 for n in r.get("news_list", [])
                        if n.get("source_type") == "news" and not n.get("is_warning"))
        xueqiu_count = sum(1 for n in r.get("news_list", [])
                          if n.get("source") == "xueqiu")
        if news_count > 0 and xueqiu_count > 0:
            logger.info(f"  跳过 {target_name}（已有 {news_count} 条新闻 + {xueqiu_count} 条雪球）")
            continue
        if r["target_type"] == "industry" and news_count > 0:
            logger.info(f"  跳过 {target_name}（已有 {news_count} 条新闻）")
            continue

        logger.info(f">>> 补充: {target_name} (缺新闻={news_count==0}, 缺雪球={xueqiu_count==0 and r['target_type']=='stock'})")

        try:
            all_new_items = []
            need_news = (news_count == 0)
            need_xueqiu = (xueqiu_count == 0 and r["target_type"] == "stock" and config.ENABLE_FORUM_SEARCH)

            # ========== 1. 搜索 Tavily 新闻（仅缺失时） ==========
            if need_news:
                if r["target_type"] == "stock":
                    news_queries = [
                        f"{stock_name} {stock_code} 最新新闻",
                        f"{stock_name} 股票分析 研报",
                        f"{stock_name} 最新消息 公告",
                        f"{stock_name} 财报 业绩 营收",
                        f"{stock_name} {stock_code} 券商研报",
                    ]
                else:
                    news_queries = [
                        f"{r['target_name']} 最新动态",
                        f"{r['target_name']} 行业分析",
                        f"{r['target_name']} 发展趋势",
                    ]

                for q in news_queries:
                    try:
                        results = provider.search(q, max_results=8,
                                                  time_range_days=config.TAVILY_SEARCH_TIME_RANGE_DAYS,
                                                  enable_cleanup=True)
                        for item in results:
                            if not deduplicator.is_duplicate(item):
                                deduplicator.add(item)
                                item["source_type"] = "news"
                                all_new_items.append(item)
                    except Exception as e:
                        logger.warning(f"  新闻搜索失败: {q[:30]}... {e}")

                logger.info(f"  Tavily新闻: {len([x for x in all_new_items if x.get('source_type')=='news'])} 条")

            # ========== 2. 搜索雪球论坛（直连爬虫，不消耗 Tavily 额度） ==========
            if need_xueqiu:
                try:
                    from xueqiu_scraper import XueqiuScraper
                    xq = XueqiuScraper()
                    xueqiu_results = xq.search_recent_posts(
                        stock_code, max_results=30,
                        time_range_days=config.TAVILY_SEARCH_TIME_RANGE_DAYS
                    )
                    for item in xueqiu_results:
                        if not deduplicator.is_duplicate(item):
                            deduplicator.add(item)
                            all_new_items.append(item)
                    logger.info(f"  雪球直连: {len(xueqiu_results)} 帖")
                except Exception as e:
                    logger.warning(f"  雪球直连失败: {e}")

            # ========== 3. 合并数据 ==========
            if all_new_items:
                existing = r.get("news_list", [])
                seen = set(n.get("url", "") for n in existing)
                truly_new = [x for x in all_new_items if x.get("url", "") not in seen]
                r["news_list"] = truly_new + existing
                logger.info(f"  合并新增: {len(truly_new)} 条 (新闻+雪球)，共 {len(r['news_list'])} 条")
            else:
                logger.warning(f"  {target_name} 未获取到新数据，跳过重算")
                continue

            # ========== 4. 重算 V3 情绪 & 分析 ==========
            stock_info = stock_map.get(stock_code, {"code": stock_code or "", "name": stock_name, "market_cap": 100.0})
            classified = emotion.classify_posts(r["news_list"], stock_info)

            import emotion_v3
            v3 = emotion_v3.analyze_emotion_v3(
                posts=r["news_list"],
                stock_name=stock_name,
                stock_code=stock_code or "",
                market_cap=stock_info.get("market_cap", 100.0),
                llm_provider=llm,
                news_weight=0.2, forum_weight=0.5, trading_weight=0.3
            )
            if v3:
                r["emotion_v3"] = emotion_v3.emotion_score_v3_to_dict(v3)
                r["emotion_score"] = v3.final_score / 3.0
                logger.info(f"  V3重算: {v3.rating_emoji} {v3.rating_level} ({v3.final_score:.3f})")

            new_analysis = analyzer.analyze_news_with_sentiment(
                r["news_list"], target_name, r["target_type"],
                r.get("emotion_score", 0), classified
            )
            if new_analysis and new_analysis != "分析失败":
                r["analysis"] = new_analysis
                r["failure_reason"] = ""

            updated_count += 1

        except Exception as e:
            logger.error(f"  补充 {target_name} 失败: {e}")

    # 覆盖原数据JSON（原地补充）
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 覆盖原纪要MD
    md_path = str(data_path).replace("-数据.json", "-纪要.md").replace("-数据-补充.json", "-纪要.md")
    if os.path.exists(md_path):
        md = _generate_markdown_from_dict(results_data, data.get("timestamp", ""))
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
        logger.info(f"  纪要已更新: {md_path}")
    else:
        # 原纪要不存在（可能是searchOnly产物），新生成
        md_path = str(data_path).replace("-数据.json", "-纪要.md")
        md = _generate_markdown_from_dict(results_data, data.get("timestamp", ""))
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
        logger.info(f"  纪要已创建: {md_path}")

    logger.info(f"补充完成: {updated_count} 个标的")
    logger.info(f"  数据已更新: {data_path}")


def _generate_markdown_from_dict(results_data: list, timestamp: str) -> str:
    """直接从dict生成Markdown纪要（避免重建复杂对象）"""
    md = f"# 个股价值投研纪要\n\n生成时间: {timestamp}\n\n---\n\n"
    for r in results_data:
        target_type = r.get("target_type", "stock")
        target_name = r.get("target_name", "")
        if target_type == "stock":
            md += f"## 📈 个股研究: {target_name}\n\n"
        else:
            md += f"## 🏭 行业研究: {target_name}\n\n"
        # 失败情况
        if r.get("failure_reason"):
            md += f"❌ 研究失败: {r['failure_reason']}\n\n---\n\n"
            continue
        # V3 情绪
        ev3 = r.get("emotion_v3")
        if ev3:
            md += "### 情绪指标 V3 (多维度加权评分)\n\n"
            md += f"- 最终评分: **{ev3.get('final_score', 0):.3f}**\n"
            md += f"- 情绪评级: {ev3.get('rating_emoji', '😐')} {ev3.get('rating_level', '中性')}\n"
            md += f"- 置信度: {ev3.get('confidence', 0):.1%}\n\n"
            md += "#### 维度明细\n\n"
            md += f"- 📰 新闻情绪: {ev3.get('news_score', 0):.3f} (权重 0.2)\n"
            md += f"- 💬 论坛情绪: {ev3.get('forum_score', 0):.3f} (权重 0.5)\n"
            md += f"- 📊 交易情绪: {ev3.get('trading_score', 0):.3f} (权重 0.3)\n\n"
            nm = ev3.get("news_metrics")
            if nm:
                md += "#### 新闻统计\n\n"
                md += f"- 总新闻数: {nm.get('total_news', 0)}\n"
                md += f"- 正面新闻: {nm.get('positive_news', 0)}\n"
                md += f"- 负面新闻: {nm.get('negative_news', 0)}\n"
                md += f"- 中性新闻: {nm.get('neutral_news', 0)}\n\n"
            fm = ev3.get("forum_metrics")
            if fm:
                md += "#### 论坛统计\n\n"
                md += f"- 总帖子数: {fm.get('total_posts', 0)}\n"
                md += f"- 热帖数: {fm.get('hot_posts', 0)}\n"
                md += f"- 爆值帖数: {fm.get('explosive_posts', 0)}\n"
                md += f"- 看多帖: {fm.get('bullish_posts', 0)}\n"
                md += f"- 看空帖: {fm.get('bearish_posts', 0)}\n"
                md += f"- 总互动数: {fm.get('total_interactions', 0)}\n\n"
            tm = ev3.get("trading_metrics")
            if tm:
                md += "#### 交易指标\n\n"
                if tm.get("current_price"):
                    md += f"- 当前价格: {tm['current_price']:.2f}\n"
                if tm.get("price_change_pct") is not None:
                    md += f"- 涨跌幅: {tm['price_change_pct']:.2f}%\n"
                if tm.get("volume_ratio"):
                    md += f"- 量比: {tm['volume_ratio']:.2f}\n"
                if tm.get("turnover_rate") is not None:
                    md += f"- 换手率: {tm['turnover_rate']:.2f}%\n"
                if tm.get("main_net_inflow") is not None:
                    md += f"- 主力净流入: {tm['main_net_inflow']:.0f}万\n"
                if tm.get("trading_signal"):
                    md += f"- 交易信号: {tm['trading_signal']}\n"
                md += "\n"
        # 新闻列表
        md += "### 新闻列表\n\n"
        news_list = r.get("news_list", [])
        if news_list:
            for i, n in enumerate(news_list, 1):
                if n.get("is_warning"):
                    md += f"⚠️ **{n.get('title', '')}**\n\n"
                else:
                    source_tag = "📰 新闻" if n.get("source_type") == "news" else "💬 论坛"
                    title = n.get("title", "")
                    url = n.get("url", "")
                    if url:
                        md += f"{i}. {source_tag} [{title}]({url})\n"
                    else:
                        md += f"{i}. {source_tag} {title}\n"
                    content = n.get("content", "")
                    if content and len(content) > 10:
                        md += f"   - {content[:200]}...\n\n"
        else:
            md += "暂无新闻\n\n"
        # 分析摘要
        analysis = r.get("analysis", "")
        if analysis:
            md += "### 分析摘要\n\n"
            md += analysis + "\n\n"
        md += "---\n\n"
    return md


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
        "--supplement",
        type=str,
        default=None,
        metavar="DATA_FILE",
        help="为已有投研数据补充Tavily新闻并重算V3情绪。如 --supplement output/20260629/20260629_230134-数据.json"
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

    if args.supplement:
        supplement_news(args.supplement)
    elif args.backfill:
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
