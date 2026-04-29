"""
搜索模块
支持多种搜索API，可替换，自带重试机制
"""
import requests
import hashlib
import time
from typing import List, Dict, Optional, Set
from datetime import datetime
from abc import ABC, abstractmethod

from logger import get_logger
from console import print_error, print_warning, highlight_search_error

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
            news: 新闻字典，包含 url 和 title

        Returns:
            是否重复
        """
        url = news.get("url", "")
        title = news.get("title", "")

        # 按 URL 去重
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
            搜索结果列表，每项包含 title, url, content
        """
        pass


class TavilySearchProvider(BaseSearchProvider):
    """Tavily 搜索提供者"""

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

    def _search_once(self, query: str, max_results: int,
                     search_depth: str = "basic",
                     include_answer: bool = False) -> Dict:
        """执行一次搜索"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_images": False,
            "include_raw_content": False
        }

        response = requests.post(self.base_url, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        执行搜索（带重试）

        Args:
            query: 搜索关键词
            max_results: 返回结果数量

        Returns:
            搜索结果列表
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"搜索尝试 {attempt}/{self.max_retries}: {query}")
                result = self._search_once(query, max_results)
                return self._format_results(result)
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"搜索失败（尝试 {attempt}/{self.max_retries}）: {e}")
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        # 全部失败
        error_msg = highlight_search_error(last_error)
        print_error(error_msg)
        logger.error(f"搜索最终失败: {query}, error={last_error}")
        return []

    def _format_results(self, raw_result: Dict) -> List[Dict]:
        """格式化搜索结果"""
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

    def __init__(self, search_provider: BaseSearchProvider, enable_forum: bool = True):
        """
        初始化

        Args:
            search_provider: 搜索提供者（可替换）
            enable_forum: 是否启用论坛搜索
        """
        self.provider = search_provider
        self.enable_forum = enable_forum

    def search_stock_news(self, stock_code: str, stock_name: str,
                          max_results: int = 5) -> List[Dict]:
        """
        搜索个股相关新闻（包含新闻和论坛）

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            max_results: 返回结果数量

        Returns:
            新闻列表
        """
        all_news = []

        # 1. 搜索新闻
        try:
            query = f"{stock_name} {stock_code} 最新新闻 市场动态"
            logger.info(f"搜索个股新闻: {query}")
            results = self.provider.search(query, max_results=max_results)
            for r in results:
                r["source_type"] = "news"
            all_news.extend(results)
        except Exception as e:
            logger.warning(f"搜索个股新闻失败: {stock_name}, error={e}")

        # 2. 搜索论坛（雪球、股吧）
        if self.enable_forum:
            try:
                query = f"{stock_name} {stock_code} 雪球 股吧 论坛讨论 投资者情绪"
                logger.info(f"搜索个股论坛: {query}")
                results = self.provider.search(query, max_results=max_results)
                for r in results:
                    r["source_type"] = "forum"
                all_news.extend(results)
            except Exception as e:
                logger.warning(f"搜索个股论坛失败: {stock_name}, error={e}")

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
            query = f"{industry_name} 最新新闻 市场分析 政策动态"
            logger.info(f"搜索行业新闻: {query}")
            results = self.provider.search(query, max_results=max_results)
            for r in results:
                r["source_type"] = "news"
            all_news.extend(results)
        except Exception as e:
            logger.warning(f"搜索行业新闻失败: {industry_name}, error={e}")

        # 2. 搜索行业论坛讨论
        if self.enable_forum:
            try:
                query = f"{industry_name} 投资者讨论 市场情绪 雪球 股吧"
                logger.info(f"搜索行业论坛: {query}")
                results = self.provider.search(query, max_results=max_results)
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
