"""
搜索模块
支持多种搜索API，可替换，自带重试机制
"""
import requests
import hashlib
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from abc import ABC, abstractmethod

from logger import get_logger
from console import print_error, highlight_search_error
from content_cleaner import ContentCleaner

logger = get_logger()


class NewsDeduplicator:
    """新闻去重器"""

    def __init__(self):
        self.seen_urls: Set[str] = set()
        self.seen_title_hashes: Set[str] = set()

    def _hash_title(self, title: str) -> str:
        """计算标题的哈希值"""
        return hashlib.md5(title.strip().lower().encode('utf-8')).hexdigest()

    def is_duplicate(self, news: Dict) -> bool:
        """
        检查新闻是否重复

        Args:
            news: 新闻字典

        Returns:
            是否重复
        """
        url = news.get("url", "")
        title = news.get("title", "")

        # 按URL去重
        if url and url in self.seen_urls:
            return True

        # 按标题去重
        title_hash = self._hash_title(title)
        if title_hash in self.seen_title_hashes:
            return True

        return False

    def add(self, news: Dict):
        """
        添加新闻到已见集合

        Args:
            news: 新闻字典
        """
        url = news.get("url", "")
        title = news.get("title", "")

        if url:
            self.seen_urls.add(url)
        if title:
            self.seen_title_hashes.add(self._hash_title(title))

    def deduplicate(self, news_list: List[Dict]) -> List[Dict]:
        """
        对新闻列表去重

        Args:
            news_list: 原始新闻列表

        Returns:
            去重后的新闻列表
        """
        result = []
        for news in news_list:
            if not self.is_duplicate(news):
                result.append(news)
                self.add(news)
        return result


class BaseSearchProvider(ABC):
    """搜索提供者基类（可替换）"""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        执行搜索

        Args:
            query: 搜索关键词
            max_results: 返回结果数量

        Returns:
            搜索结果列表，每项包含title, url, content
        """
        pass


class TavilySearchProvider(BaseSearchProvider):
    """Tavily搜索提供者"""

    def __init__(self, api_key: str, timeout: int = 40, max_retries: int = 3):
        """
        初始化

        Args:
            api_key: Tavily API Key
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = "https://api.tavily.com/search"
        self.content_cleaner = ContentCleaner()

    def _search_once(self, query: str, max_results: int,
                     search_depth: str = "basic",
                     include_answer: bool = False,
                     time_range_days: Optional[int] = None) -> Dict:
        """执行一次搜索"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 构建查询
        full_query = query
        if time_range_days:
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=time_range_days)
            date_str = f" after:{start_date.strftime('%Y-%m-%d')}"
            full_query = query + date_str

        payload = {
            "query": full_query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_images": False,
            "include_raw_content": False,
        }

        response = requests.post(self.base_url, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def search(self, query: str, max_results: int = 5,
               time_range_days: Optional[int] = 60,
               enable_cleanup: bool = True,
               max_pages: int = 3) -> List[Dict]:
        """
        执行搜索（带重试、翻页）

        Args:
            query: 搜索关键词
            max_results: 返回结果数量
            time_range_days: 时间范围（天数）
            enable_cleanup: 是否清理内容
            max_pages: 最大翻页次数

        Returns:
            搜索结果列表
        """
        all_results = []
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"搜索尝试 {attempt}/{self.max_retries}: {query[:50]}...")
                result = self._search_once(
                    query, max_results,
                    time_range_days=time_range_days
                )
                all_results = self._format_results(result)

                # 清理内容
                if enable_cleanup and self.content_cleaner:
                    all_results = self.content_cleaner.filter_results(all_results)

                # 如果结果太少，尝试翻页（Tavily不直接支持翻页，但可以调整搜索条件或接受）
                # 这里如果结果太少，尝试去除时间限制再搜索一次
                if len(all_results) < max_results // 2 and time_range_days:
                    logger.info(f"搜索结果较少，尝试扩大搜索范围...")
                    try:
                        result_no_time = self._search_once(query, max_results)
                        results_no_time = self._format_results(result_no_time)
                        if enable_cleanup and self.content_cleaner:
                            results_no_time = self.content_cleaner.filter_results(results_no_time)
                        # 合并去重
                        deduplicator = NewsDeduplicator()
                        combined = deduplicator.deduplicate(all_results + results_no_time)
                        if len(combined) > len(all_results):
                            all_results = combined
                    except Exception as e:
                        logger.warning(f"扩展搜索失败: {e}")

                break

            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"搜索失败（尝试 {attempt}/{self.max_retries}）: {e}")
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        # 全部失败
        if not all_results and last_error:
            error_msg = highlight_search_error(last_error)
            print_error(error_msg)
            logger.error(f"搜索最终失败: {last_error}")

        return all_results

    def _format_results(self, raw_result: Dict) -> List[Dict]:
        """格式化搜索结果"""
        if "error" in raw_result:
            return []

        results = raw_result.get("results", [])
        formatted = []

        for item in results:
            formatted.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "published_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": item.get("source", "")
            })

        return formatted


class StockSearcher:
    """股票投研搜索器"""

    def __init__(self, search_provider: BaseSearchProvider, enable_forum: bool = True,
                 time_range_days: int = 60, enable_cleanup: bool = True):
        """
        初始化

        Args:
            search_provider: 搜索提供者（可替换）
            enable_forum: 是否启用论坛搜索
            time_range_days: 搜索时间范围（天数）
            enable_cleanup: 是否清理模板内容
        """
        self.provider = search_provider
        self.enable_forum = enable_forum
        self.time_range_days = time_range_days
        self.enable_cleanup = enable_cleanup

    def search_stock_news(self, stock_code: str, stock_name: str,
                           max_results: int = 5) -> List[Dict]:
        """
        搜索个股相关新闻（包含新闻和论坛）

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            max_results: 每类搜索结果数量

        Returns:
            新闻列表
        """
        all_news = []

        # 1. 搜索新闻资讯
        try:
            query = f"{stock_name} {stock_code} 股票最新新闻"
            results = self.provider.search(
                query, max_results=max_results,
                time_range_days=self.time_range_days,
                enable_cleanup=self.enable_cleanup
            )
            for r in results:
                r["source_type"] = "news"
            all_news.extend(results)
        except Exception as e:
            logger.warning(f"搜索个股新闻失败: {stock_name}, error={e}")

        # 2. 搜索雪球热帖
        if self.enable_forum:
            try:
                query = f"site:xueqiu.com {stock_name} {stock_code} 热帖 讨论"
                results = self.provider.search(
                    query, max_results=max_results,
                    time_range_days=self.time_range_days,
                    enable_cleanup=self.enable_cleanup
                )
                for r in results:
                    r["source_type"] = "forum"
                all_news.extend(results)
            except Exception as e:
                logger.warning(f"搜索雪球失败: {stock_name}, error={e}")

        # 3. 搜索股吧热帖
        if self.enable_forum:
            try:
                query = f"site:guba.eastmoney.com {stock_name} {stock_code} 股吧 评论"
                results = self.provider.search(
                    query, max_results=max_results,
                    time_range_days=self.time_range_days,
                    enable_cleanup=self.enable_cleanup
                )
                for r in results:
                    r["source_type"] = "forum"
                all_news.extend(results)
            except Exception as e:
                logger.warning(f"搜索股吧失败: {stock_name}, error={e}")

        # 去重
        deduplicator = NewsDeduplicator()
        all_news = deduplicator.deduplicate(all_news)

        return all_news

    def search_industry_news(self, industry_name: str,
                              max_results: int = 5) -> List[Dict]:
        """
        搜索行业相关新闻

        Args:
            industry_name: 行业名称
            max_results: 返回结果数量

        Returns:
            新闻列表
        """
        all_news = []

        # 1. 搜索行业新闻
        try:
            query = f"{industry_name} 行业最新新闻 市场分析"
            results = self.provider.search(
                query, max_results=max_results,
                time_range_days=self.time_range_days,
                enable_cleanup=self.enable_cleanup
            )
            for r in results:
                r["source_type"] = "news"
            all_news.extend(results)
        except Exception as e:
            logger.warning(f"搜索行业新闻失败: {industry_name}, error={e}")

        # 2. 搜索行业论坛讨论
        if self.enable_forum:
            try:
                query = f"{industry_name} 投资者讨论 雪球 股吧"
                results = self.provider.search(
                    query, max_results=max_results,
                    time_range_days=self.time_range_days,
                    enable_cleanup=self.enable_cleanup
                )
                for r in results:
                    r["source_type"] = "forum"
                all_news.extend(results)
            except Exception as e:
                logger.warning(f"搜索行业论坛失败: {industry_name}, error={e}")

        # 去重
        deduplicator = NewsDeduplicator()
        all_news = deduplicator.deduplicate(all_news)

        return all_news


# ========== 兼容旧代码的类名 ==========
class TavilySearcher(StockSearcher):
    """兼容旧代码的包装类"""

    def __init__(self, api_key: str, timeout: int = 40, max_retries: int = 3, enable_forum: bool = True):
        provider = TavilySearchProvider(api_key, timeout, max_retries)
        super().__init__(provider, enable_forum)
