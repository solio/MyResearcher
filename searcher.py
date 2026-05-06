"""
搜索模块
支持多种搜索API，可替换，自带重试机制
"""
import requests
import hashlib
import time
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from abc import ABC, abstractmethod

from logger import get_logger
from console import print_warning, highlight_search_error
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

    def __init__(self, api_key: str, timeout: int = 40, max_retries: int = 3,
                 tavily_time_range_days: int = 2):
        """
        初始化

        Args:
            api_key: Tavily API Key
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
            tavily_time_range_days: Tavily搜索的时间范围（天数，默认2天）
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.tavily_time_range_days = tavily_time_range_days
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
               time_range_days: Optional[int] = None,
               enable_cleanup: bool = True,
               max_pages: int = 3) -> List[Dict]:
        """
        执行搜索（带重试、翻页、结果不足时的fallback）

        Args:
            query: 搜索关键词
            max_results: 返回结果数量
            time_range_days: 时间范围（天数，None则使用默认的tavily_time_range_days）
            enable_cleanup: 是否清理内容
            max_pages: 最大翻页次数

        Returns:
            搜索结果列表
        """
        # 使用默认的Tavily时间范围（2天）如果没有指定
        if time_range_days is None:
            time_range_days = self.tavily_time_range_days
        """
        执行搜索（带重试、翻页、结果不足时的fallback）

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

        # 策略1: 先用带时间限制的搜索
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"搜索尝试 {attempt}/{self.max_retries}: {query[:60]}...")
                result = self._search_once(
                    query, max_results * 2,  # 多请求一些，留出过滤空间
                    time_range_days=time_range_days
                )
                all_results = self._format_results(result)

                # 清理内容
                if enable_cleanup and self.content_cleaner:
                    all_results = self.content_cleaner.filter_results(all_results)

                break

            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"搜索失败（尝试 {attempt}/{self.max_retries}）: {e}")
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        # 策略2: 如果结果太少，放宽时间限制再试一次
        if len(all_results) < max_results // 2 and time_range_days:
            logger.info(f"结果不足({len(all_results)}条)，放宽时间限制重新搜索...")
            try:
                result = self._search_once(
                    query, max_results * 2,
                    time_range_days=None  # 不限制时间
                )
                more_results = self._format_results(result)

                # 清理内容
                if enable_cleanup and self.content_cleaner:
                    more_results = self.content_cleaner.filter_results(more_results)

                # 合并去重
                seen_urls = set(r.get("url", "") for r in all_results)
                for r in more_results:
                    if r.get("url", "") not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(r.get("url", ""))

                logger.info(f"放宽时间后新增 {len(more_results)} 条，共 {len(all_results)} 条")

            except Exception as e:
                logger.warning(f"放宽时间搜索失败: {e}")

        # 策略3: 如果还是很少，尝试不带时间的简单query再搜索
        if len(all_results) < max_results // 2:
            logger.info(f"结果仍然不足，尝试简化搜索词...")
            try:
                # 提取核心关键词（取前几个词）
                simple_query = " ".join(query.split()[:3])
                result = self._search_once(
                    simple_query, max_results * 3,
                    time_range_days=None
                )
                more_results = self._format_results(result)

                if enable_cleanup and self.content_cleaner:
                    more_results = self.content_cleaner.filter_results(more_results)

                seen_urls = set(r.get("url", "") for r in all_results)
                for r in more_results:
                    if r.get("url", "") not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(r.get("url", ""))

                logger.info(f"简化搜索后共 {len(all_results)} 条")

            except Exception as e:
                logger.warning(f"简化搜索失败: {e}")

        # 全部失败
        if not all_results and last_error:
            error_msg = highlight_search_error(last_error)
            print_warning(f"搜索query失败: {query[:50]}...")

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


class SkillSearchProvider(BaseSearchProvider):
    """
    Search-Engine Skill搜索提供者
    使用../search-engine中的skill进行搜索
    """

    def __init__(
        self,
        search_engine_path: str = "../search-engine",
        use_targeted: bool = False,
        use_mock: bool = False,
        enable_cleanup: bool = True,
    ):
        """
        初始化Skill搜索提供者

        Args:
            search_engine_path: search-engine目录路径
            use_targeted: 是否使用定向搜索（仅优质站点）
            use_mock: 是否使用mock模式
            enable_cleanup: 是否清理内容
        """
        self.search_engine_path = Path(search_engine_path).resolve()
        self.use_targeted = use_targeted
        self.use_mock = use_mock
        self.enable_cleanup = enable_cleanup
        self.content_cleaner = ContentCleaner() if enable_cleanup else None

        # 确保search-engine目录存在
        if not self.search_engine_path.exists():
            logger.warning(f"search-engine目录不存在: {self.search_engine_path}")
        else:
            # 添加路径以便导入skill
            if str(self.search_engine_path) not in sys.path:
                sys.path.insert(0, str(self.search_engine_path))

    def _search_with_skill(self, query: str) -> Optional[Dict]:
        """
        使用skill进行搜索

        Args:
            query: 搜索关键词

        Returns:
            搜索结果字典，失败返回None
        """
        try:
            # 尝试导入skill模块
            if str(self.search_engine_path) not in sys.path:
                sys.path.insert(0, str(self.search_engine_path))

            from skill.skill import search as skill_search

            # 调用skill搜索
            result = skill_search(
                query=query,
                targeted=self.use_targeted,
                use_mock=self.use_mock,
            )

            return result

        except ImportError as e:
            logger.warning(f"无法导入skill模块: {e}")
            return None
        except Exception as e:
            logger.warning(f"skill搜索失败: {e}")
            return None

    def search(
        self,
        query: str,
        max_results: int = 5,
        time_range_days: Optional[int] = 60,
        enable_cleanup: bool = True,
        max_pages: int = 3,
    ) -> List[Dict]:
        """
        执行搜索

        Args:
            query: 搜索关键词
            max_results: 返回结果数量
            time_range_days: 时间范围（天数）- skill使用time_range参数，这里做兼容
            enable_cleanup: 是否清理内容
            max_pages: 最大翻页次数

        Returns:
            搜索结果列表
        """
        all_results = []

        # 第一层：使用skill搜索
        result = self._search_with_skill(query)
        if result:
            all_results = self._format_skill_results(result)

            # 清理内容
            if enable_cleanup and self.content_cleaner:
                all_results = self.content_cleaner.filter_results(all_results)

            logger.info(f"skill搜索返回 {len(all_results)} 条结果")

        # 如果结果不足，尝试简化关键词
        if len(all_results) < max_results // 2 and len(query.split()) > 2:
            logger.info(f"结果不足，尝试简化关键词搜索")
            simple_query = " ".join(query.split()[:3])
            result_simple = self._search_with_skill(simple_query)
            if result_simple:
                more_results = self._format_skill_results(result_simple)
                if enable_cleanup and self.content_cleaner:
                    more_results = self.content_cleaner.filter_results(more_results)

                # 合并去重
                seen_urls = set(r.get("url", "") for r in all_results)
                for r in more_results:
                    if r.get("url", "") not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(r.get("url", ""))

        return all_results[:max_results]

    def _format_skill_results(self, skill_result: Dict) -> List[Dict]:
        """
        格式化skill搜索结果

        Args:
            skill_result: skill返回的结果

        Returns:
            格式化后的结果列表
        """
        results = []
        for item in skill_result.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "published_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": item.get("domain", ""),
                "score": item.get("score", 0.0),
                "is_quality_site": item.get("is_quality_site", False),
            })

        return results


class StockSearcher:
    """股票投研搜索器"""

    def __init__(self, search_provider: BaseSearchProvider = None, enable_forum: bool = True,
                 time_range_days: int = 60, enable_cleanup: bool = True,
                 search_provider_type: str = "skill",
                 tavily_api_key: str = "",
                 tavily_time_range_days: int = 2,
                 search_engine_path: str = "../search-engine",
                 skill_use_targeted: bool = False,
                 skill_use_mock: bool = False):
        """
        初始化

        Args:
            search_provider: 搜索提供者实例（优先使用）
            enable_forum: 是否启用论坛搜索
            time_range_days: 搜索时间范围（天数）
            enable_cleanup: 是否清理模板内容
            search_provider_type: 搜索提供者类型 "skill" 或 "tavily"
            tavily_api_key: Tavily API Key（tavily模式需要）
            tavily_time_range_days: Tavily搜索的时间范围（天数，默认2天）
            search_engine_path: search-engine目录路径（skill模式需要）
            skill_use_targeted: skill是否使用定向搜索
            skill_use_mock: skill是否使用mock模式
        """
        if search_provider:
            self.provider = search_provider
        elif search_provider_type == "tavily":
            self.provider = TavilySearchProvider(
                api_key=tavily_api_key,
                tavily_time_range_days=tavily_time_range_days
            )
        else:
            # 默认使用skill
            self.provider = SkillSearchProvider(
                search_engine_path=search_engine_path,
                use_targeted=skill_use_targeted,
                use_mock=skill_use_mock,
                enable_cleanup=enable_cleanup,
            )

        self.enable_forum = enable_forum
        self.time_range_days = time_range_days
        self.enable_cleanup = enable_cleanup

    def _multi_query_search(self, queries: List[str], max_results_per_query: int = 3) -> List[Dict]:
        """
        多query组合搜索

        Args:
            queries: 多个搜索query
            max_results_per_query: 每个query返回的结果数

        Returns:
            合并后的结果
        """
        all_results = []
        deduplicator = NewsDeduplicator()

        for query in queries:
            try:
                results = self.provider.search(
                    query, max_results_per_query,
                    self.time_range_days,
                    self.enable_cleanup
                )
                for r in results:
                    if not deduplicator.is_duplicate(r):
                        deduplicator.add(r)
                        all_results.append(r)
            except Exception as e:
                logger.warning(f"搜索query失败: {query[:50]}..., error: {e}")

        return all_results

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
        # 更多query组合搜索新闻
        news_queries = [
            f"{stock_name} {stock_code} 最新新闻",
            f"{stock_name} 股票分析 研报",
            f"{stock_name} 最新消息 公告",
            f"{stock_name} 股市 动态",
            f"{stock_name} 行业 资讯",
        ]

        all_news = self._multi_query_search(news_queries, max_results_per_query=5)

        # 更多query组合搜索论坛
        if self.enable_forum:
            forum_queries = [
                f"site:xueqiu.com {stock_name} {stock_code}",
                f"site:guba.eastmoney.com {stock_name} {stock_code}",
                f"{stock_name} 雪球 讨论",
                f"{stock_name} 股吧 热议",
                f"{stock_name} 股民 讨论",
            ]
            forum_results = self._multi_query_search(forum_queries, max_results_per_query=4)
            for r in forum_results:
                r["source_type"] = "forum"
                all_news.append(r)

        # 标记新闻来源
        for r in all_news:
            if "source_type" not in r:
                r["source_type"] = "news"

        # 最后整体去重
        final_deduplicator = NewsDeduplicator()
        all_news = final_deduplicator.deduplicate(all_news)

        # 如果结果仍然为空，添加一个标记条目
        if not all_news:
            logger.warning(f"{stock_name}({stock_code}) 未搜索到任何新闻")
            all_news = [{
                "title": f"【注意】{stock_name} 近期新闻不足",
                "url": "",
                "content": "根据搜索结果，近期没有找到足够的相关新闻。可能原因：1. 市场关注度较低；2. 搜索时间范围内无重大事件；3. 需要检查搜索配置。",
                "published_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "系统提示",
                "source_type": "news",
                "is_warning": True
            }]

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
        # 更多query组合搜索新闻
        news_queries = [
            f"{industry_name} 行业 最新新闻 分析",
            f"{industry_name} 产业链 政策",
            f"{industry_name} 发展趋势",
            f"{industry_name} 市场 动态",
            f"{industry_name} 投资 资讯",
        ]

        all_news = self._multi_query_search(news_queries, max_results_per_query=5)

        # 搜索论坛讨论
        if self.enable_forum:
            forum_queries = [
                f"{industry_name} 行业讨论 雪球",
                f"{industry_name} 投资讨论",
                f"{industry_name} 股吧 热议",
            ]
            forum_results = self._multi_query_search(forum_queries, max_results_per_query=4)
            for r in forum_results:
                r["source_type"] = "forum"
                all_news.append(r)

        # 标记新闻来源
        for r in all_news:
            if "source_type" not in r:
                r["source_type"] = "news"

        # 最后整体去重
        final_deduplicator = NewsDeduplicator()
        all_news = final_deduplicator.deduplicate(all_news)

        # 如果结果仍然为空，添加一个标记条目
        if not all_news:
            logger.warning(f"{industry_name} 未搜索到任何新闻")
            all_news = [{
                "title": f"【注意】{industry_name} 近期新闻不足",
                "url": "",
                "content": "根据搜索结果，近期没有找到足够的相关行业新闻。可能原因：1. 行业整体关注度较低；2. 搜索时间范围内无重大事件；3. 需要检查搜索配置。",
                "published_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "系统提示",
                "source_type": "news",
                "is_warning": True
            }]

        return all_news


# ========== 兼容旧代码的类名 ==========
class TavilySearcher(StockSearcher):
    """兼容旧代码的包装类"""

    def __init__(self, api_key: str, timeout: int = 40, max_retries: int = 3, enable_forum: bool = True):
        provider = TavilySearchProvider(api_key, timeout, max_retries)
        super().__init__(provider, enable_forum)
