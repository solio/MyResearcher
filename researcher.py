"""
投研主流程模块
整合搜索、LLM分析，生成完整的投研报告
"""
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from difflib import SequenceMatcher

from config import Config
from searcher import TavilySearchProvider, StockSearcher, NewsDeduplicator
from llm import DeepSeekLLMProvider, StockAnalyzer
from logger import get_logger
from console import print_warning

logger = get_logger()


class ResearchResult:
    """单个研究结果"""

    def __init__(self, target_type: str, target_name: str):
        """
        初始化研究结果

        Args:
            target_type: 研究类型 ("stock" 或 "industry")
            target_name: 研究目标名称
        """
        self.target_type = target_type
        self.target_name = target_name
        self.news_list = []
        self.analysis = ""
        self.summary = ""
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.is_no_update = False  # 标记是否与上期相同
        self.failure_reason = ""  # 失败原因

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "target_type": self.target_type,
            "target_name": self.target_name,
            "news_list": self.news_list,
            "analysis": self.analysis,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "is_no_update": self.is_no_update,
            "failure_reason": self.failure_reason
        }


class HistoryManager:
    """历史结果管理器"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def get_yesterday_date_str(self) -> Optional[str]:
        """获取昨天的日期字符串"""
        yesterday = datetime.now() - timedelta(days=1)
        return yesterday.strftime("%Y%m%d")

    def _find_latest_data_file(self, date_str: str) -> Optional[str]:
        """找到指定日期最新的数据文件"""
        date_dir = os.path.join(self.output_dir, date_str)
        if not os.path.exists(date_dir):
            return None

        # 找所有数据文件
        data_files = []
        for f in os.listdir(date_dir):
            if f.startswith(date_str) and "数据" in f and f.endswith(".json"):
                data_files.append(f)

        if not data_files:
            return None

        # 按时间排序，取最新的
        data_files.sort(reverse=True)
        return os.path.join(date_dir, data_files[0])

    def load_yesterday_summary(self, target_name: str) -> Optional[str]:
        """
        加载昨日的摘要

        Args:
            target_name: 研究目标名称

        Returns:
            摘要字符串，找不到返回 None
        """
        yesterday = self.get_yesterday_date_str()
        if not yesterday:
            return None

        data_file = self._find_latest_data_file(yesterday)
        if not data_file:
            return None

        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for result in data.get("results", []):
                if result.get("target_name") == target_name:
                    return result.get("summary", "")
        except Exception as e:
            logger.warning(f"加载昨日数据失败: {e}")

        return None

    def is_similar_content(self, summary1: str, summary2: str, threshold: float = 0.7) -> bool:
        """
        判断两个摘要是否相似

        Args:
            summary1: 摘要1
            summary2: 摘要2
            threshold: 相似度阈值

        Returns:
            是否相似
        """
        if not summary1 or not summary2:
            return False

        similarity = SequenceMatcher(None, summary1, summary2).ratio()
        return similarity >= threshold


class StockResearcher:
    """个股投研器"""

    def __init__(self, config: Config):
        """
        初始化投研器

        Args:
            config: 配置对象
        """
        self.config = config

        # 初始化搜索提供者
        search_provider = TavilySearchProvider(
            api_key=config.TAVILY_API_KEY,
            timeout=config.SEARCH_TIMEOUT,
            max_retries=config.SEARCH_MAX_RETRIES
        )
        self.searcher = StockSearcher(search_provider, config.ENABLE_FORUM_SEARCH)

        # 初始化 LLM 提供者
        llm_provider = DeepSeekLLMProvider(
            api_key=config.DEEPSEEK_API_KEY,
            api_base=config.DEEPSEEK_API_BASE,
            model=config.DEEPSEEK_MODEL,
            timeout=config.LLM_TIMEOUT,
            max_retries=config.LLM_MAX_RETRIES
        )
        self.analyzer = StockAnalyzer(llm_provider)

        self.history_manager = HistoryManager(config.OUTPUT_DIR)
        self.results = []
        self.today_str = datetime.now().strftime("%Y%m%d")
        self.now_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    def research_stock(self, stock: Dict) -> ResearchResult:
        """
        研究单只股票

        Args:
            stock: 股票字典

        Returns:
            研究结果
        """
        target_name = f"{stock['name']}({stock['code']})"
        logger.info(f"正在研究股票: {target_name}")

        result = ResearchResult("stock", target_name)

        try:
            # 1. 搜索新闻
            result.news_list = self.searcher.search_stock_news(
                stock['code'],
                stock['name'],
                max_results=self.config.SEARCH_RESULT_COUNT
            )

            # 2. 生成今日摘要
            if result.news_list:
                result.summary = self.analyzer.generate_summary(result.news_list) or ""

            # 3. 与昨日对比
            yesterday_summary = self.history_manager.load_yesterday_summary(target_name)
            if yesterday_summary and self.history_manager.is_similar_content(result.summary, yesterday_summary):
                logger.info(f"{target_name} 内容与昨日相似，跳过重复分析")
                result.is_no_update = True
                result.analysis = "今日无重大更新，内容与上期相似。"
                return result

            # 4. LLM 深度分析
            if result.news_list:
                analysis = self.analyzer.analyze_news_with_sentiment(
                    result.news_list,
                    target_name,
                    "stock"
                )
                if analysis == "分析失败":
                    result.failure_reason = "LLM 分析失败"
                    print_warning(f"{target_name} 分析摘要环节失败")
                result.analysis = analysis

        except Exception as e:
            logger.error(f"研究股票失败: {target_name}, error={e}", exc_info=True)
            result.failure_reason = str(e)
            result.analysis = f"研究失败：{str(e)}"
            print_warning(f"{target_name} 研究失败: {str(e)}")

        return result

    def research_industry(self, industry_name: str) -> ResearchResult:
        """
        研究单个行业

        Args:
            industry_name: 行业名称

        Returns:
            研究结果
        """
        logger.info(f"正在研究行业: {industry_name}")

        result = ResearchResult("industry", industry_name)

        try:
            # 1. 搜索新闻
            result.news_list = self.searcher.search_industry_news(
                industry_name,
                max_results=self.config.SEARCH_RESULT_COUNT
            )

            # 2. 生成今日摘要
            if result.news_list:
                result.summary = self.analyzer.generate_summary(result.news_list) or ""

            # 3. 与昨日对比
            yesterday_summary = self.history_manager.load_yesterday_summary(industry_name)
            if yesterday_summary and self.history_manager.is_similar_content(result.summary, yesterday_summary):
                logger.info(f"{industry_name} 内容与昨日相似，跳过重复分析")
                result.is_no_update = True
                result.analysis = "今日无重大更新，内容与上期相似。"
                return result

            # 4. LLM 深度分析
            if result.news_list:
                analysis = self.analyzer.analyze_news_with_sentiment(
                    result.news_list,
                    industry_name,
                    "industry"
                )
                if analysis == "分析失败":
                    result.failure_reason = "LLM 分析失败"
                    print_warning(f"{industry_name} 分析摘要环节失败")
                result.analysis = analysis

        except Exception as e:
            logger.error(f"研究行业失败: {industry_name}, error={e}", exc_info=True)
            result.failure_reason = str(e)
            result.analysis = f"研究失败：{str(e)}"
            print_warning(f"{industry_name} 研究失败: {str(e)}")

        return result

    def run_all(self) -> List[ResearchResult]:
        """
        运行所有研究任务（出错继续）

        Returns:
            所有研究结果列表
        """
        logger.info("=" * 60)
        logger.info("开始投研任务")
        logger.info("=" * 60)

        all_results = []

        # 研究个股
        logger.info("--- 研究个股 ---")
        for stock in self.config.STOCK_LIST:
            try:
                result = self.research_stock(stock)
                all_results.append(result)
            except Exception as e:
                logger.error(f"研究股票异常: {stock}, error={e}", exc_info=True)
                # 即使失败也继续下一个

        # 研究行业
        logger.info("--- 研究行业 ---")
        for industry in self.config.INDUSTRY_LIST:
            try:
                result = self.research_industry(industry)
                all_results.append(result)
            except Exception as e:
                logger.error(f"研究行业异常: {industry}, error={e}", exc_info=True)
                # 即使失败也继续下一个

        self.results = all_results
        return all_results

    def save_results(self, results: List[ResearchResult]) -> str:
        """
        保存研究结果到文件（按日期目录组织，文件名带时间）

        Args:
            results: 研究结果列表

        Returns:
            保存的纪要文件路径
        """
        # 获取今日目录
        output_dir = self.config.get_output_dir_for_date(self.today_str)

        # 1. 保存原始数据（JSON）
        data_file = os.path.join(output_dir, f"{self.now_str}-数据.json")
        data = {
            "date": self.today_str,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": [r.to_dict() for r in results]
        }
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 2. 保存投研纪要（Markdown）
        md_file = os.path.join(output_dir, f"{self.now_str}-纪要.md")
        md_content = self._generate_markdown_report(results)
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"结果已保存:")
        logger.info(f"  - {data_file}")
        logger.info(f"  - {md_file}")

        return md_file

    def _generate_markdown_report(self, results: List[ResearchResult]) -> str:
        """
        生成 Markdown 格式报告

        Args:
            results: 研究结果列表

        Returns:
            Markdown 字符串
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        md = f"# 个股价值投研纪要\n\n"
        md += f"生成时间: {timestamp}\n\n"
        md += "---\n\n"

        for result in results:
            if result.target_type == "stock":
                md += f"## 📈 个股研究: {result.target_name}\n\n"
            else:
                md += f"## 🏭 行业研究: {result.target_name}\n\n"

            # 如果是无更新，简单显示
            if result.is_no_update:
                md += "⚠️ 今日无重大更新，内容与上期相似。\n\n"
                md += "---\n\n"
                continue

            # 如果失败，显示失败原因
            if result.failure_reason:
                md += f"❌ 研究失败: {result.failure_reason}\n\n"
                md += "---\n\n"
                continue

            md += f"### 新闻列表\n\n"
            if result.news_list:
                for i, news in enumerate(result.news_list, 1):
                    source_tag = "📰 新闻" if news.get("source_type") == "news" else "💬 论坛"
                    md += f"{i}. {source_tag} [{news['title']}]({news['url']})\n"
                    md += f"   - {news['content'][:150]}...\n\n"
            else:
                md += "暂无新闻\n\n"

            if result.analysis:
                md += f"### 分析摘要\n\n"
                if result.analysis == "分析失败":
                    md += "❌ 分析失败\n\n"
                else:
                    md += result.analysis + "\n\n"

            md += "---\n\n"

        return md
