"""
内容清理模块
用于去除搜索结果中的页面模板部分
"""
import re
from typing import List, Dict


class ContentCleaner:
    """内容清理器"""

    def __init__(self):
        # 明显是模板页面的URL关键词
        self.template_url_keywords = [
            "aboutus", "about-us", "about", "contact", "contactus",
            "recruit", "zhaopin", "job", "careers", "joinus",
            "sitemap", "link", "partner", "privacy", "terms",
            "download", "app", "mobile", "copyright",
            "index", "home", "default", "main",
            "case", "cases", "example", "demo",
            "intro", "introduction", "profile", "company",
        ]

        # 明显是新闻列表页的URL关键词
        self.news_list_url_keywords = [
            "/news", "/news-list", "/newslist", "/bulletin",
            "/list", "/news_", "/news.", "-news",
            "/activity", "/events",
        ]

        # 明显是模板页面的标题关键词
        self.template_title_keywords = [
            "公司简介", "公司介绍", "关于我们", "联系方式",
            "招聘", "诚聘", "招贤纳士", "加入我们",
            "网站地图", "友情链接", "合作伙伴",
            "隐私政策", "用户协议", "使用条款",
            "版权声明", "版权所有",
            "APP下载", "客户端下载", "移动版",
            "成功案例", "客户案例",
            "产品中心", "产品介绍",
            "官网", "首页", "网站主页",
        ]

        # 明显是新闻列表页的标题关键词
        self.news_list_title_keywords = [
            "最新新闻", "最新动态", "新闻列表", "新闻中心",
            "最新消息", "最新资讯", "最新公告",
            "新闻", "公告", "动态", "资讯",
        ]

        # 明显是模板内容的关键词组合
        self.template_content_patterns = [
            r"成立于\d{4}年",  # 公司成立时间（太常见于简介）
            r"总部位于",  # 总部地址
            r"专注于",  # 公司业务描述
            r"国家规划布局",  # 资质描述
            r"上市公司",  # 上市信息
            r"战略投资",  # 投资信息
            r"客户案例",  # 案例
            r"运营中心",  # 运营信息
            r"细分行业",  # 行业描述
            r"企业文化",  # 文化
            r"公司历程",  # 历程
            r"投资者关系",  # IR
            r"员工生活",  # 员工
        ]

        # 乱码检测模式
        self.gibberish_patterns = [
            r"[\|│┃┆┊┋┇┈┉┊┋]{3,}",  # 大量表格线条
            r"[^\x00-\x7F一-鿿\w\s，。！？；：""''（）【】、]{5,}",  # 大量奇怪字符
        ]

    def is_template_url(self, url: str) -> bool:
        """检查URL是否是模板页面"""
        if not url:
            return False
        url_lower = url.lower()
        for keyword in self.template_url_keywords:
            if keyword in url_lower:
                return True
        return False

    def is_template_title(self, title: str) -> bool:
        """检查标题是否是模板页面"""
        if not title:
            return False
        for keyword in self.template_title_keywords:
            if keyword in title:
                return True
        return False

    def is_news_list_url(self, url: str) -> bool:
        """检查URL是否是新闻列表页"""
        if not url:
            return False
        url_lower = url.lower()
        for keyword in self.news_list_url_keywords:
            if keyword in url_lower:
                return True
        return False

    def is_news_list_title(self, title: str) -> bool:
        """检查标题是否是新闻列表页"""
        if not title:
            return False
        for keyword in self.news_list_title_keywords:
            # 只有当标题主要就是这些关键词时才认为是列表页
            # 避免把"XX公司最新新闻"这种单篇新闻标题误判
            if title.strip() == keyword or title.strip().endswith(keyword) or title.strip().startswith(keyword):
                return True
        return False

    def is_gibberish(self, text: str) -> bool:
        """检测是否是乱码"""
        if not text:
            return False
        for pattern in self.gibberish_patterns:
            if re.search(pattern, text):
                return True
        return False

    def is_likely_template_content(self, content: str) -> bool:
        """检查内容是否像模板"""
        if not content:
            return False

        # 检查是否包含多个模板内容模式
        pattern_count = 0
        for pattern in self.template_content_patterns:
            if re.search(pattern, content):
                pattern_count += 1
                if pattern_count >= 2:  # 2个及以上模板特征
                    return True

        return False

    def has_valid_news_content(self, title: str, content: str) -> bool:
        """
        检查是否有有效的单篇新闻内容
        """
        # 排除只是列表页的情况（标题只有"最新新闻"等，但没有具体新闻内容）
        if (self.is_news_list_title(title) and len(content) < 300):
            return False

        # 如果有具体的新闻特征词（不是只在标题里说"新闻"）
        news_indicators = ["公告", "研报", "分析", "业绩", "营收", "利润", "亏损", "涨停", "跌停"]
        # 更强的新闻特征：包含具体数字或年份
        strong_indicators = [r"\d{4}年", r"营收\d", r"利润\d", r"亏损\d", r"\d亿元", r"\d万"]

        # 检查强特征
        for pattern in strong_indicators:
            if re.search(pattern, title) or re.search(pattern, content):
                return True

        # 检查普通特征，但要确保不是只有"新闻"这个词
        for indicator in news_indicators:
            if indicator in title or indicator in content:
                return True

        return False

    def filter_results(self, results: List[Dict]) -> List[Dict]:
        """
        过滤搜索结果（智能策略）

        Args:
            results: 原始搜索结果列表

        Returns:
            过滤后的结果列表
        """
        filtered = []
        seen_urls = set()

        for result in results:
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")

            # 去重
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            # 基本检查：标题和内容都为空的跳过
            if not title.strip() and not content.strip():
                continue

            # 内容太短的跳过
            if len(content.strip()) < 30 and len(title.strip()) < 10:
                continue

            # 明显是乱码的跳过
            if self.is_gibberish(content) and self.is_gibberish(title):
                continue

            # 先检查是否有明确的单篇新闻特征
            has_news = self.has_valid_news_content(title, content)

            # 明显是模板页面且没有新闻特征的跳过
            if (self.is_template_url(url) or self.is_template_title(title)) and not has_news:
                continue

            # 新闻列表页且没有新闻特征的跳过
            if (self.is_news_list_url(url) or self.is_news_list_title(title)) and not has_news:
                continue

            # 内容较短且像模板且没有新闻特征的跳过
            if self.is_likely_template_content(content) and len(content) < 200 and not has_news:
                continue

            # 简单清理多余空白
            if content:
                cleaned_content = re.sub(r"\s+", " ", content).strip()
                result["content"] = cleaned_content

            filtered.append(result)

        return filtered
