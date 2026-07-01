"""
个股历史数据回填模块
补齐过去几个月的股吧/雪球/Tavily新闻数据 + V3情绪分析
- 不修改任何纪要文件，仅写入数据 JSON + 情绪分析结果
"""
import os
import json
import time
import random
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from config import get_config, Config
from logger import get_logger
from console import print_warning

logger = get_logger()


class HistoricalPriceFetcher:
    """东方财富 K 线历史数据获取器"""

    KLINE_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://quote.eastmoney.com/",
        })

    def fetch_kline(self, stock_code: str, beg: str, end: str) -> dict:
        """
        获取历史 K 线数据

        Args:
            stock_code: 股票代码
            beg: 开始日期 YYYYMMDD
            end: 结束日期 YYYYMMDD

        Returns:
            {"trading_days": ["20260302", ...],
             "prices": {"20260302": {"open": ..., "close": ..., ...}}}
        """
        market = 1 if stock_code.startswith("6") else 0
        secid = f"{market}.{stock_code}"

        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",      # 日K线
            "fqt": "1",        # 前复权
            "beg": beg,
            "end": end,
            "lmt": "200",
        }

        try:
            resp = self.session.get(self.KLINE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"获取 K 线数据失败: {e}")
            return {"trading_days": [], "prices": {}}

        klines = data.get("data", {}).get("klines", [])
        if not klines:
            logger.warning(f"K 线 API 返回空数据: {stock_code} {beg}~{end}")
            return {"trading_days": [], "prices": {}}

        prices = {}
        trading_days = []
        for line in klines:
            parts = line.split(",")
            # 格式: date,open,close,high,low,volume,amount,amplitude,
            #        pct_change,change,turnover
            date_str = parts[0]  # "2026-03-02"
            if date_str == beg or date_str == end:
                continue  # 跳过边界值（可能是 API 占位）
            day_key = date_str.replace("-", "")  # → "20260302"
            try:
                prices[day_key] = {
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": int(parts[5]),
                    "amount": float(parts[6]),
                    "pct_change": float(parts[8]) if parts[8] and parts[8] != "-" else 0.0,
                    "turnover": float(parts[10]) if len(parts) > 10 and parts[10] and parts[10] != "-" else None,
                }
                trading_days.append(day_key)
            except (ValueError, IndexError):
                continue

        return {"trading_days": trading_days, "prices": prices}


# XueqiuScraper 已移至 xueqiu_scraper.py，此处导入复用
from xueqiu_scraper import XueqiuScraper  # noqa: E402


class BackfillRunner:
    """个股历史数据回填执行器"""

    def __init__(self, config: Config, stock_code: str, months: int = 3,
                 delay: float = 2.5, from_date: str = None, to_date: str = None):
        self.config = config
        self.stock_code = stock_code
        self.months = months
        self.delay = delay
        self.from_date = from_date  # YYYYMMDD，显式指定起始日期
        self.to_date = to_date      # YYYYMMDD，显式指定结束日期

        stock_info = self._resolve_stock(stock_code)
        self.stock_name = stock_info["name"]
        self.market_cap = stock_info.get("market_cap", 100.0)

        self.price_fetcher = HistoricalPriceFetcher()

        from searcher import TavilySearchProvider
        self.tavily_provider = TavilySearchProvider(
            api_keys=config.TAVILY_API_KEYS,
            tavily_time_range_days=getattr(config, 'TAVILY_SEARCH_TIME_RANGE_DAYS', 7)
        )

        from llm import DeepSeekLLMProvider
        self.llm_provider = DeepSeekLLMProvider(
            api_key=config.DEEPSEEK_API_KEY,
            api_base=config.DEEPSEEK_API_BASE,
            model=config.DEEPSEEK_MODEL,
            timeout=config.LLM_TIMEOUT,
            max_retries=config.LLM_MAX_RETRIES
        )

    def _resolve_stock(self, stock_code: str) -> dict:
        """从配置中查找股票信息"""
        for s in self.config.STOCK_LIST:
            if s["code"] == stock_code:
                return s
        raise ValueError(
            f"股票代码 {stock_code} 不在配置的 STOCK_LIST 中，"
            f"请使用 --stock-name 参数手动指定名称"
        )

    def _check_already_backfilled(self, date_str: str) -> bool:
        """检查某日期是否已有该股票的数据"""
        from database import check_backfilled
        return check_backfilled(date_str, self.stock_code)

    def _scrape_guba(self, date_str: str) -> List[Dict]:
        """抓取股吧指定日期的帖子（逐天接口，保留兼容）"""
        try:
            from guba_scraper import GubaScraper
            scraper = GubaScraper(use_curl_cffi=getattr(self.config, 'GUBA_USE_CURL_CFFI', True))
            posts = scraper.scrape_stock_posts(
                self.stock_code,
                max_pages=self.config.GUBA_MAX_PAGES,
                target_date=date_str
            )
            for p in posts:
                p.setdefault("source_type", "forum")
                p.setdefault("source", "guba")
                if "content" not in p or not p["content"]:
                    p["content"] = p.get("title", "")
            return posts
        except Exception as e:
            logger.warning(f"股吧抓取失败 ({date_str}): {e}")
            return []

    # 股吧反爬限制：单次会话最多安全访问 ~6 页后 IP 被 tarpit
    GUBA_SAFE_PAGE_LIMIT = 6

    def _estimate_guba_page_for_date(self, target_date_str: str) -> int:
        """估算目标日期对应的股吧页码。

        股吧按最后回复时间倒序排列，活跃股每天约 80 帖 = 1 页。
        所以 page ≈ (today - target_date).days。
        返回估算页码（最小为 1）。
        """
        try:
            target_dt = datetime.strptime(target_date_str, "%Y%m%d")
            days_ago = (datetime.now() - target_dt).days
            return max(1, days_ago)
        except ValueError:
            return 1

    def _scrape_guba_batch(self, trading_days: List[str]) -> Dict[str, List[Dict]]:
        """稀疏跳跃式爬取股吧帖子，按日期分配到各交易日。

        股吧反爬严格：顺序翻页在第 7 页触发验证码，随机跳跃约 30 次
        后 IP 被 tarpit（所有页返回相同内容）。因此本方法：

        1. 估算目标日期范围对应的页码范围
        2. 从中均匀选取最多 GUBA_SAFE_PAGE_LIMIT 个样本页
        3. 随机顺序访问，长延迟（8-12s），UA 轮换
        4. 仅返回成功爬取页中的帖子

        返回: {date_str: [posts]}，大部分交易日列表为空是正常现象。
        """
        date_posts: Dict[str, List[Dict]] = {d: [] for d in trading_days}
        if not trading_days:
            return date_posts

        try:
            from guba_scraper import GubaScraper
            scraper = GubaScraper(use_curl_cffi=getattr(self.config, 'GUBA_USE_CURL_CFFI', True))
        except Exception as e:
            logger.warning(f"股吧爬虫初始化失败: {e}")
            return date_posts

        # 估算页码范围
        latest_day = max(trading_days)
        earliest_day = min(trading_days)
        page_start = self._estimate_guba_page_for_date(latest_day)
        page_end = self._estimate_guba_page_for_date(earliest_day)

        # 均匀选取样本页，最多 GUBA_SAFE_PAGE_LIMIT 页
        total_pages = max(1, page_end - page_start + 1)
        sample_count = min(self.GUBA_SAFE_PAGE_LIMIT, total_pages)
        if sample_count <= 1:
            sample_pages = [page_start]
        else:
            step = total_pages / sample_count
            sample_pages = sorted(set(
                int(page_start + i * step) for i in range(sample_count)
            ))

        # 随机打乱访问顺序（避免被检测为顺序扫描）
        visit_order = list(sample_pages)
        random.shuffle(visit_order)

        logger.info(
            f"股吧稀疏采样: {len(trading_days)} 个交易日, "
            f"页码范围 {page_start}~{page_end}, "
            f"采样 {len(sample_pages)} 页 (安全上限 {self.GUBA_SAFE_PAGE_LIMIT})"
        )

        success_count = 0
        for page in visit_order:
            if success_count >= self.GUBA_SAFE_PAGE_LIMIT:
                break

            logger.info(f"  股吧采样页 {page} ...")
            html = scraper.fetch_list_page(self.stock_code, page)

            # 反爬重试（仅 1 次，节省安全配额）
            if not html:
                scraper._rotate_ua()
                time.sleep(5 + random.random() * 3)
                html = scraper.fetch_list_page(self.stock_code, page)

            if not html:
                logger.warning(f"  股吧页 {page} 获取失败（可能触发反爬），跳过")
                continue

            posts = scraper.extract_posts_from_html(html, self.stock_code)
            if not posts:
                logger.info(f"  股吧页 {page} 无帖子")
                continue

            success_count += 1
            matched_days = 0
            for p in posts:
                pt = p.get("post_time")
                if not pt:
                    continue
                try:
                    pdt = datetime.strptime(pt, "%Y-%m-%d %H:%M:%S")
                    pd_str = pdt.strftime("%Y%m%d")
                    if pd_str in date_posts:
                        p.setdefault("source_type", "forum")
                        p.setdefault("source", "guba")
                        if "content" not in p or not p["content"]:
                            p["content"] = p.get("title", "")
                        date_posts[pd_str].append(p)
                        matched_days += 1
                except ValueError:
                    pass

            # 长延迟，避免触发反爬
            if success_count < self.GUBA_SAFE_PAGE_LIMIT:
                delay = 8 + random.random() * 4
                time.sleep(delay)
            scraper._rotate_ua()

        total = sum(len(v) for v in date_posts.values())
        days_with = sum(1 for v in date_posts.values() if v)
        logger.info(
            f"股吧稀疏采样完成: {success_count}/{len(sample_pages)} 页成功, "
            f"{total} 帖覆盖 {days_with}/{len(trading_days)} 天 "
            f"(安全上限 {self.GUBA_SAFE_PAGE_LIMIT} 页，仅覆盖采样页对应的交易日)"
        )
        return date_posts

    def _search_xueqiu(self, date_str: str) -> List[Dict]:
        """直接爬取雪球指定日期的帖子（不走 Tavily）"""
        scraper = XueqiuScraper()
        posts = scraper.search_posts_by_date(
            self.stock_code, date_str, max_pages=3
        )
        if posts:
            logger.info(f"  雪球直接爬取: {len(posts)} 帖")
        else:
            logger.debug(f"  雪球无数据 ({date_str})，可能被 WAF 拦截或无当日讨论")
        return posts

    def _prefetch_tavily_news_by_week(self, trading_days: List[str]) -> Dict[str, List[Dict]]:
        """按周批量搜索 Tavily 新闻，将结果分配到各交易日。
        3 个月数据从 ~300 次调用降至 ~60 次。
        """
        from itertools import groupby

        # 按 ISO 周分组（周一~周日）
        def week_key(day_str: str):
            dt = datetime.strptime(day_str, "%Y%m%d")
            return dt.strftime("%Y-W%W")

        weeks: Dict[str, List[str]] = {}
        for day in trading_days:
            wk = week_key(day)
            if wk not in weeks:
                weeks[wk] = []
            weeks[wk].append(day)

        logger.info(f"Tavily 新闻按周批量搜索: {len(trading_days)} 个交易日 → {len(weeks)} 周")
        day_news: Dict[str, List[Dict]] = {d: [] for d in trading_days}

        for wk, days in weeks.items():
            first_dt = datetime.strptime(days[0], "%Y%m%d")
            last_dt = datetime.strptime(days[-1], "%Y%m%d")
            month_kw = f"{first_dt.year}年{first_dt.month}月"

            news_queries = [
                f"{self.stock_name} {self.stock_code} 新闻",
                f"{self.stock_name} 公告",
                f"{self.stock_name} {self.stock_code} 研报",
                f"{self.stock_name} {month_kw} 新闻",
                f"{self.stock_name} {month_kw} 公告",
            ]

            all_results = []
            seen_urls = set()
            for query in news_queries:
                try:
                    results = self.tavily_provider.search(
                        query, max_results=5,
                        time_range_days=None,
                        enable_cleanup=True
                    )
                    for r in results:
                        url = r.get("url", "")
                        if url and url in seen_urls:
                            continue
                        seen_urls.add(url)
                        r["source_type"] = "news"
                        all_results.append(r)
                except Exception as e:
                    logger.debug(f"Tavily 搜索失败 ({query[:30]}): {e}")

            if len(all_results) > 30:
                all_results = all_results[:30]

            # 分配到该周的交易日
            dated = {}   # date_str -> [news]
            undated = []
            for r in all_results:
                pd_str = r.get("published_date", "")
                matched = None
                if pd_str:
                    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d"]:
                        try:
                            pd_dt = datetime.strptime(pd_str[:10], "%Y-%m-%d")
                            pd_key = pd_dt.strftime("%Y%m%d")
                            if pd_key in days:
                                matched = pd_key
                            break
                        except ValueError:
                            continue
                if matched:
                    dated.setdefault(matched, []).append(r)
                else:
                    undated.append(r)

            # 无日期新闻均匀分配给该周所有交易日
            if undated and days:
                for i, r in enumerate(undated):
                    day_idx = i % len(days)
                    dated.setdefault(days[day_idx], []).append(r)

            for d, news in dated.items():
                day_news[d].extend(news)

            logger.info(f"  {wk}: {len(days)}天, 获取 {len(all_results)} 条新闻")

        total = sum(len(v) for v in day_news.values())
        logger.info(f"Tavily 新闻批量搜索完成: {total} 条新闻覆盖 {len(trading_days)} 天")
        return day_news

    def _run_v3_emotion(self, posts: List[Dict]) -> Optional[Dict]:
        """运行 V3 多维度情绪分析"""
        if not posts:
            logger.warning("无帖子数据，跳过 V3 情绪分析")
            return None

        try:
            from emotion_v3 import analyze_emotion_v3, emotion_score_v3_to_dict
            v3_result = analyze_emotion_v3(
                posts=posts,
                stock_name=self.stock_name,
                stock_code=self.stock_code,
                market_cap=self.market_cap,
                llm_provider=self.llm_provider
            )
            if v3_result:
                return emotion_score_v3_to_dict(v3_result)
        except Exception as e:
            logger.warning(f"V3 情绪分析失败: {e}")
        return None

    def _override_trading_with_kline(self, emotion_v3: Dict,
                                      price_data: dict) -> None:
        """用 K 线历史数据替换 real-time trading_metrics"""
        if not emotion_v3 or not price_data:
            return

        tm = emotion_v3.get("trading_metrics", {})
        pct = price_data.get("pct_change", 0.0) or 0.0

        # 用 K 线数据覆盖
        tm["current_price"] = price_data.get("close")
        tm["price_change_pct"] = pct
        tm["turnover_rate"] = price_data.get("turnover")
        tm["fetch_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tm["volume_ratio"] = None
        tm["main_net_inflow"] = None
        tm["bid_ask_ratio"] = None

        # 基于涨跌幅重新计算 trading_score
        if pct > 3:
            tm["trading_score"] = 2.0
            tm["trading_signal"] = "强势上涨"
        elif pct > 1:
            tm["trading_score"] = 1.0
            tm["trading_signal"] = "温和上涨"
        elif pct > -1:
            tm["trading_score"] = 0.0
            tm["trading_signal"] = "横盘"
        elif pct > -3:
            tm["trading_score"] = -1.0
            tm["trading_signal"] = "温和下跌"
        else:
            tm["trading_score"] = -2.0
            tm["trading_signal"] = "明显下跌"

        # 重新计算 final_score
        news_w = 0.2
        forum_w = 0.5
        trading_w = 0.3
        news_score = emotion_v3.get("news_score", 0.0) or 0.0
        forum_score = emotion_v3.get("forum_score", 0.0) or 0.0
        trading_score = tm["trading_score"]
        final_score = news_score * news_w + forum_score * forum_w + trading_score * trading_w
        emotion_v3["final_score"] = round(max(-3.0, min(3.0, final_score)), 2)
        emotion_v3["trading_score"] = trading_score

    def _save_day_data(self, date_str: str, v3_dict: Optional[Dict],
                        posts: List[Dict]) -> int:
        """保存单日数据到数据库，返回 result_id"""
        from database import insert_run, insert_result

        target_name = f"{self.stock_name}({self.stock_code})"
        result = {
            "target_type": "stock",
            "target_name": target_name,
            "news_list": posts,
            "analysis": "",
            "summary": "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_no_update": False,
            "failure_reason": "",
            "emotion_score": v3_dict["final_score"] / 3.0 if v3_dict else 0.0,
            "classified_posts": [],
            "param_suggestion": "",
            "use_v2_emotion": False,
            "use_v3_emotion": v3_dict is not None,
            "emotion_v3": v3_dict or {},
        }

        run_id = insert_run(date_str, search_provider="backfill", is_backfill=True)
        result_id = insert_result(run_id, result)
        return result_id

    def run(self) -> dict:
        """执行回填主流程"""
        if self.from_date and self.to_date:
            end_date = self.to_date
            beg_date = self.from_date
        else:
            end_date = datetime.now().strftime("%Y%m%d")
            beg_date = (datetime.now() - timedelta(days=self.months * 31)).strftime("%Y%m%d")

        logger.info(f"开始回填: {self.stock_name}({self.stock_code}), "
                     f"{self.months} 个月 ({beg_date} ~ {end_date})")

        # 1. 获取交易日 + 历史股价
        kline_data = self.price_fetcher.fetch_kline(
            self.stock_code, beg_date, end_date
        )
        trading_days = kline_data["trading_days"]
        prices = kline_data["prices"]

        if not trading_days:
            logger.error("未获取到任何交易日数据，回填终止")
            return {"status": "failed", "reason": "no_trading_days"}

        logger.info(f"共 {len(trading_days)} 个交易日待回填")

        # 2. 批量预取 Tavily 新闻（按周分组，大幅减少 API 调用）
        tavily_news_cache = self._prefetch_tavily_news_by_week(trading_days)

        # 2.5 批量扫描股吧帖子（一次翻页到底，避免每天独立从第1页翻导致的重复请求和反爬）
        guba_cache = self._scrape_guba_batch(trading_days)

        # 3. 遍历交易日
        completed = 0
        skipped = 0
        failed = 0

        for i, day in enumerate(trading_days):
            # 跳过已回填的
            if self._check_already_backfilled(day):
                skipped += 1
                continue

            logger.info(f"[{i+1}/{len(trading_days)}] 回填 {day} ...")

            try:
                # 从批量缓存中取股吧帖子
                guba_posts = guba_cache.get(day, [])
                # 搜索雪球
                xueqiu_posts = self._search_xueqiu(day)
                # 从周批量缓存中取 Tavily 新闻
                tavily_news = tavily_news_cache.get(day, [])
                # 合并：论坛(股吧+雪球) + 新闻(Tavily)
                all_posts = guba_posts + xueqiu_posts + tavily_news

                if not all_posts:
                    logger.info(f"  {day}: 无任何数据，跳过")
                    failed += 1
                    continue

                logger.info(f"  股吧 {len(guba_posts)} 帖, 雪球 {len(xueqiu_posts)} 帖, Tavily新闻 {len(tavily_news)} 条")

                # V3 情绪分析
                v3_dict = self._run_v3_emotion(all_posts)

                # 用 K 线历史价格覆盖 real-time trading
                if v3_dict and day in prices:
                    self._override_trading_with_kline(v3_dict, prices[day])

                # 保存到数据库
                result_id = self._save_day_data(day, v3_dict, all_posts)
                logger.info(f"  ✓ 已保存: result_id={result_id}")
                completed += 1

            except Exception as e:
                logger.error(f"  ✗ {day} 回填失败: {e}")
                failed += 1

            # 节流
            if i < len(trading_days) - 1:
                time.sleep(self.delay)

        summary = {
            "status": "completed",
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "trading_days": len(trading_days),
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
        }
        logger.info(f"回填完成: 完成 {completed}, 跳过 {skipped}, 失败 {failed}")
        return summary


def backfill_main(args) -> None:
    """从 main.py 调用的入口函数"""
    from logger import setup_logger

    config = get_config()
    setup_logger(
        log_dir=os.path.join(config.OUTPUT_DIR, "logs"),
        log_level=config.LOG_LEVEL
    )

    stock_code = args.backfill
    months = getattr(args, "months", 3)
    from_date = getattr(args, "from_date", None)
    to_date = getattr(args, "to_date", None)

    # 检查是否需要手动指定股票名
    stock_info = None
    for s in config.STOCK_LIST:
        if s["code"] == stock_code:
            stock_info = s
            break

    if stock_info is None:
        stock_name = getattr(args, "stock_name", None)
        if not stock_name:
            print(f"错误: 股票代码 {stock_code} 不在配置列表中，"
                  f"请使用 --stock-name 参数指定名称")
            return
        # 临时添加到配置
        config.STOCK_LIST.append({
            "code": stock_code,
            "name": stock_name,
            "market_cap": 100.0,
        })

    runner = BackfillRunner(config, stock_code, months=months,
                           from_date=from_date, to_date=to_date)
    summary = runner.run()

    date_info = ""
    if from_date:
        date_info = f" ({from_date} ~ {to_date})"
    print(f"\n回填结果: {summary['stock_name']}({summary['stock_code']}){date_info}")
    print(f"  交易日总数: {summary['trading_days']}")
    print(f"  成功回填:   {summary['completed']}")
    print(f"  跳过(已存在): {summary['skipped']}")
    print(f"  失败:       {summary['failed']}")
    print(f"\n运行 dashboard 查看: python dashboard.py")
