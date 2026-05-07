"""
内容清理模块
用于去除搜索结果中的页面模板部分
"""
import re
from typing import List, Dict
from logger import get_logger

logger = get_logger()


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

        # 明显是个股行情页面的URL关键词 - 这些页面只有股价数据，无实质新闻
        self.stock_quote_url_keywords = [
            "vip.stock.finance.sina.com.cn",  # 新浪财经个股页
            "finance.sina.com.cn/realstock",  # 新浪实时行情
            "basic.10jqka.com.cn",  # 同花顺个股页
            "stock.quote.stockstar.com",  # 证券之星个股页
            "stockdata.hexun.com",  # 和讯网个股页
            "quote.eastmoney.com",  # 东方财富行情页
            "guba.eastmoney.com/list",  # 东方财富股吧列表页（非具体帖子）
            "xueqiu.com/s",  # 雪球搜索/列表页
            "xueqiu.com/S/SH", "xueqiu.com/S/SZ",  # 雪球个股行情页（注意：雪球新闻页是 /news/ 路径）
            "xueqiu.com/S/",  # 雪球个股页通用前缀
            "moomoo.com/hans/stock",  # Moomoo个股页
            "aastocks.com/tc/cnhk/quote",  # AASTOCKS个股行情页
            "hk.finance.yahoo.com/quote",  # 雅虎财经个股页
            "q.stock.sohu.com",  # 搜狐证券个股页
            "ifeng.com/zjlx",  # 凤凰网资金流向页
            "stcn.com/quotes",  # 证券时报行情页
            # 基于数据分析发现的模板页URL模式
            "data.eastmoney.com/gzfx/detail/",  # 东方财富估值分析页（模板内容）
            "data.eastmoney.com/stockdata/",  # 东方财富个股数据页
            "data.eastmoney.com/notice/",  # 东方财富公告数据页
            "data.eastmoney.com",  # 东方财富数据中心（个股数据页）
            "money.finance.sina.com.cn/corp",  # 新浪公司信息页
            ".phtml",  # 新浪的phtml格式页面通常是数据页
            "/corp/go.php",  # 新浪公司信息页通用模式
            "/stockid",  # 新浪stockid参数
            "stockid=",  # 新浪stockid参数
            # 新增模式
            "sse.com.cn/assortment/stock/list/info/company/",  # 上交所公司页
            "stockpage.10jqka.com.cn/",  # 同花顺个股页
            "iyanbao.com/search?",  # 研报搜索页
            "mguba.eastmoney.com/mguba/list/",  # 股吧列表
            # 新增更多模式
            "futunn.com/quote/",  # 富途行情页
            "junming.fun/stock/",  # 个股研究数据页
            "vip.stock.finance.sina.com.cn/corp/go.php",  # 新浪公司信息页（所有子路径）
        ]

        # 个股页面通用检测模式（正则）
        self.stock_page_patterns = [
            r"/\d{6}\.s?html?",  # 股票代码.html或.shtml等
            r"stockid=sh?\d{6}",  # stockid=sh601012或stockid=601012
            r"stockid=sz?\d{6}",  # stockid=sz000001
        ]

        # 明显是个股行情页面的标题关键词模式
        self.stock_quote_title_patterns = [
            r"^\([^)]*\)[^_]+_[^_]+$",  # 类似"(601012)股票_数据_资料"这种乱码标题
            r"^[^_]+_[^_]+_[^_]+_[^_]+$",  # 多个下划线分隔的行情页标题
            r"股票股价$",  # 结尾是"股票股价"
            r"行情走势$",  # 结尾是"行情走势"
            r"最新行情$",  # 结尾是"最新行情"
            r"最新价格$",  # 结尾是"最新价格"
            r"个股行情$",  # 结尾是"个股行情"
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

        # 模式1: 大量乱码字符
        for pattern in self.gibberish_patterns:
            if re.search(pattern, text):
                return True

        # 模式2: 非中日韩英文的字符比例过高
        total_chars = len(text)
        if total_chars == 0:
            return False

        invalid_chars = 0
        for char in text:
            code = ord(char)
            # 允许的字符范围
            if not (0x0020 <= code <= 0x007E or  # ASCII可打印
                    0x4E00 <= code <= 0x9FFF or  # 中日韩统一表意文字
                    0x3400 <= code <= 0x4DBF or  # 中日韩扩展A
                    0xFF00 <= code <= 0xFFEF or  # 全角字符
                    0x3000 <= code <= 0x303F or  # 中日韩符号
                    char in '，。！？；：""''（）【】、·——'):
                invalid_chars += 1

        if invalid_chars / total_chars > 0.3:  # 超过30%是奇怪字符
            return True

        # 模式3: 检测编码错误的典型模式（如Windows-1252误读为UTF-8的情况）
        # 典型乱码模式: 希腊/西里尔字母连续出现
        garbled_block_pattern = r'[Ͱ-ϿЀ-ӿԀ-ԯḀ-ỿ]{4,}'
        if re.search(garbled_block_pattern, text):
            return True

        return False

    def is_stock_quote_url(self, url: str) -> bool:
        """检查URL是否是个股行情页面（无实质新闻）"""
        if not url:
            return False
        url_lower = url.lower()

        # 检查关键词匹配
        for keyword in self.stock_quote_url_keywords:
            if keyword in url_lower:
                return True

        # 检查正则模式匹配（个股页面的通用模式）
        for pattern in self.stock_page_patterns:
            if re.search(pattern, url):
                return True

        # 额外检查：排除可能是新闻的URL（白名单模式）
        # 如果URL包含明显的新闻特征，即使匹配了上面的模式也可能放行
        # 但这个逻辑在filter_results中处理，这里只做排除

        return False

    def is_likely_news_url(self, url: str) -> bool:
        """检查URL是否可能是真正的新闻页面（用于白名单机制）"""
        if not url:
            return False
        url_lower = url.lower()

        # 黑名单关键词：即使包含新闻特征，如果同时包含这些也不算
        blacklist_keywords = [
            "data.eastmoney.com/gzfx",  # 东方财富估值分析页
            "data.eastmoney.com/data",  # 东方财富数据中心
            "data.eastmoney.com/stockdata",  # 东方财富个股数据页
            "stock.finance.sina.com.cn/stock/go.php/vreport_list",  # 新浪研报列表页
            "basic.10jqka.com.cn",  # 同花顺数据页
        ]
        for keyword in blacklist_keywords:
            if keyword in url_lower:
                return False

        # 雪球特殊处理：只有 /news/ 路径才是新闻，其他 /S/ 路径都是个股页
        if "xueqiu.com/s/" in url_lower and "/news/" not in url_lower:
            return False

        # 新闻相关关键词
        news_keywords = [
            "/news", "/article", "/story", "/content",
            "/notice", "/bulletin", "/announcement", "/report",
            "news_id", "article_id", "content_id",
            ".shtml?", ".html?",  # 带参数的动态新闻页面
            # 新增：研报相关关键词
            "/vreport_", "/research",
            "kind=search", "symbol=",  # 新浪研报搜索特征
        ]

        # 注意："/detail/" 被移除，因为它在数据页也常出现

        for keyword in news_keywords:
            if keyword in url_lower:
                return True

        return False

    def is_stock_quote_title(self, title: str) -> bool:
        """检查标题是否是个股行情页面"""
        if not title:
            return False
        for pattern in self.stock_quote_title_patterns:
            if re.search(pattern, title):
                return True
        return False

    def is_likely_quote_content(self, content: str) -> bool:
        """检查内容是否像行情页面（只有股价、成交量等数据，无实质新闻）"""
        if not content:
            return False

        # 检查是否是行情数据特征（多个连续数据标签）
        quote_indicators = [
            r"开盘价[：:].*?收盘价[：:]",  # 开盘价...收盘价...
            r"最高[：:].*?最低[：:]",  # 最高...最低...
            r"成交量[：:].*?成交额[：:]",  # 成交量...成交额...
            r"市盈率[：:].*?市净率[：:]",  # 市盈率...市净率...
            r"[一-龥][：:]\s*[\d\-\.]+.*?[一-龥][：:]\s*[\d\-\.]+",  # 多个"标签:数字"模式
            r"@high@", r"@low@", r"@amount@", r"@turnover@",  # 模板变量标记
        ]

        indicator_count = 0
        for indicator in quote_indicators:
            if re.search(indicator, content):
                indicator_count += 1
                if indicator_count >= 2:
                    return True

        # 检查是否是纯数据表格特征
        if re.search(r"[\|│┃].*?[\|│┃].*?[\|│┃]", content) and len(content) < 500:
            # 有表格线且内容较短，很可能是行情数据
            return True

        return False

    def is_template_nav_content(self, content: str) -> bool:
        """检查内容是否是纯导航模板（无实质内容，只有菜单链接）"""
        if not content:
            return False

        # 纯导航特征：大量的"|"分隔的菜单（基于数据分析发现的模式）
        nav_indicators = [
            r"指数\|期指\|期权",  # 东方财富典型导航
            r"资金流向\|千股千评\|公告",
            r"龙虎榜单\|大宗交易",
            r"自选股\|自选基金",
            r"数据中心\|估值分析",
            r"财务数据\|核心题材",
            r"主力持仓\|股东分析",
            # 基于数据分析发现的常见开头模板
            r"指数\|期指\|期权\|个股\|板块\|排行",  # 典型东方财富导航开头
            r"期指\|期权\|个股\|板块\|排行\|新股",
            r"股吧\|基金\|港股\|美股\|期货",
            r"外汇\|黄金\|自选股\|自选基金",
        ]

        nav_count = 0
        for indicator in nav_indicators:
            if re.search(indicator, content):
                nav_count += 1
                if nav_count >= 2:  # 2个及以上导航特征
                    return True

        # 检查是否有大量的"|"且实际文本内容很少
        pipe_count = content.count("|")
        if pipe_count >= 5:  # 有很多分隔线（基于数据分析，5个以上就很可疑）
            # 计算非|字符的比例
            non_pipe_ratio = len([c for c in content if c != "|"]) / max(len(content), 1)
            if non_pipe_ratio < 0.7:  # |占比超过30%
                return True

        # 检查雪球个股页特征："# XXX(SH:XXXXXX)股票股价_股价行情_财报_数据报告
        xueqiu_pattern = r"# [^)]+\(SH:\d+\)股票股价"
        if re.search(xueqiu_pattern, content):
            return True

        # 检查是否只有表格头没有实质数据
        table_header_patterns = [
            r"序号\|股票简称\|",
            r"数据日期\|当日收盘价",
            r"股票简称.*?PE.*?市净率",
        ]
        for pattern in table_header_patterns:
            if re.search(pattern, content):
                return True

        # 检查股吧模板内容
        guba_template_patterns = [
            r"股吧，股民朋友可以在这里畅所欲言",
            r"股吧提供实时股票行情、热门股票讨论",
        ]
        for pattern in guba_template_patterns:
            if re.search(pattern, content):
                return True

        # 检查雪球行情页特征（更多变体）
        xueqiu_patterns = [
            r"# [^)]+\(SH:\d+\)股票股价",
            r"# [^)]+\(SZ:\d+\)股票股价",
            r"股票股价_股价行情_财报_数据报告",
        ]
        for pattern in xueqiu_patterns:
            if re.search(pattern, content):
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
        # 但研报列表页可能有价值，所以放宽这个限制
        if (self.is_news_list_title(title) and len(content) < 300):
            # 检查是否可能是研报列表页，如果是，可能有价值
            if "研报" in title or "报告" in title:
                return True
            return False

        # 研报相关特征（高优先级）
        report_indicators = ["研报", "研究报告", "券商", "评级", "目标价", "盈利预测", "投资建议", "买入", "增持", "中性", "卖出", "华泰", "中信", "国泰", "招商", "海通"]
        # 普通新闻特征
        news_indicators = ["公告", "分析", "业绩", "营收", "利润", "亏损", "涨停", "跌停"]
        # 更强的新闻特征：包含具体数字或年份
        strong_indicators = [r"\d{4}年", r"营收\d", r"利润\d", r"亏损\d", r"\d亿元", r"\d万", r"\d月\d日", r"\d日"]

        # 检查研报特征（优先级最高）
        for indicator in report_indicators:
            if indicator in title or indicator in content:
                return True

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
        filtered_count = 0
        filtered_reasons = {}

        for result in results:
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")
            filter_reason = None

            # 去重
            if url and url in seen_urls:
                filter_reason = "重复URL"
            if url:
                seen_urls.add(url)

            if not filter_reason:
                # 基本检查：标题和内容都为空的跳过
                if not title.strip() and not content.strip():
                    filter_reason = "空内容"

            if not filter_reason:
                # 内容太短的跳过
                if len(content.strip()) < 30 and len(title.strip()) < 10:
                    filter_reason = "内容过短"

            if not filter_reason:
                # 明显是乱码的跳过
                if self.is_gibberish(content) and self.is_gibberish(title):
                    filter_reason = "乱码"

            # 先检查是否有明确的单篇新闻特征
            has_news = self.has_valid_news_content(title, content)
            # 检查是否可能是真正的新闻URL
            is_news_url = self.is_likely_news_url(url)

            # 快速检查：股吧模板内容直接过滤（不管URL）
            if not filter_reason and content:
                if "股吧，股民朋友可以在这里畅所欲言" in content or "股吧提供实时股票行情" in content:
                    filter_reason = "股吧模板内容"

            if not filter_reason:
                # --- 严格过滤：先检查是否在强黑名单中 ---
                # 这些URL模式几乎总是模板页面，即使有一些新闻特征也很可能是误判
                strong_blacklist_patterns = [
                    "data.eastmoney.com/gzfx/detail/",  # 估值分析页（纯模板）
                    "data.eastmoney.com/stockdata/",  # 个股数据页
                    "data.eastmoney.com/notice/",  # 公告列表页（非具体公告）
                    "xueqiu.com/s/sh", "xueqiu.com/s/sz",  # 雪球个股行情页（小写）
                    "xueqiu.com/s/",  # 雪球个股页通用前缀（小写）
                    "quote.eastmoney.com",  # 行情页
                    "basic.10jqka.com.cn",  # 同花顺F10
                    "stcn.com/quotes",  # 证券时报行情页
                    "quotes.sina.cn",  # 新浪行情页
                    "moomoo.com/hans/stock/",  # Moomoo个股页
                    "aastocks.com/tc/cnhk/quote/",  # AASTOCKS行情页
                    "sse.com.cn/assortment/stock/list/info/company/",  # 上交所公司页
                    "stockpage.10jqka.com.cn/",  # 同花顺个股页
                    "iyanbao.com/search?",  # 研报搜索页
                    "longi.com/cn/bulletin/",  # 隆基公告列表
                    "longi.com/cn/news/",  # 隆基新闻列表
                    "longi.com/tw/bulletin/",  # 台湾版公告列表
                    "longi.com/tw/news/",  # 台湾版新闻列表
                    "longi.com/cn/suppliers/announcement/",  # 供应商公告列表
                    "longi.com/cn/sustainability/",  # 可持续发展页
                    "longi.com/cn/", "longi.com/cn/?", "longi.com/cn/#",  # 首页
                    "mguba.eastmoney.com/mguba/list/",  # 股吧列表
                    "guba.eastmoney.com/list,",  # 股吧列表页
                    "stock.finance.sina.com.cn/stock/go.php/vreport_list",  # 新浪研报列表页
                    "nxny.com/stock/",  # 研报列表页
                    "q.stock.sohu.com/cn/",  # 搜狐个股页
                    "jrj.com.cn/stock/",  # 金融界个股页
                    # 新增更多模式
                    "futunn.com/quote/",  # 富途行情页
                    "ifeng.com/zjlx/",  # 凤凰网资金流向页
                    "junming.fun/stock/",  # 个股研究数据页
                    "vip.stock.finance.sina.com.cn/corp/go.php",  # 新浪公司信息页（所有子路径）
                ]

                is_strong_blacklist = False
                url_lower = url.lower()
                for pattern in strong_blacklist_patterns:
                    if pattern in url_lower:
                        # 例外1：PDF文件 - 总是保留
                        if url_lower.endswith(".pdf"):
                            continue
                        # 例外2：雪球的 /news/ 路径且有具体新闻ID的可能是真新闻
                        # 但像 news?page=38 这样的还是列表页，需要过滤
                        if "xueqiu.com/s/" in url_lower:
                            # 检查是否是具体新闻：路径中有 /news/ 且后面有数字ID，且没有分页参数 ?
                            path_parts = url_lower.split("/")
                            is_specific_news = False
                            for i, part in enumerate(path_parts):
                                if part == "news" and i + 1 < len(path_parts):
                                    next_part = path_parts[i + 1]
                                    # 检查是否有数字ID且没有分页参数 ?
                                    if next_part and any(c.isdigit() for c in next_part) and "?" not in url_lower:
                                        is_specific_news = True
                                        break
                            if is_specific_news:
                                # 看起来像具体新闻，保留
                                continue
                            # 其他雪球个股页（包括 notices, hots, news?page= 等）都过滤
                            is_strong_blacklist = True
                            break
                        # 例外3：隆基的 /news/ 路径 - 需要具体判断
                        if "longi.com/cn/news/" in url_lower or "longi.com/tw/news/" in url_lower:
                            # 如果只是 /news/ 结尾或者带 ? 参数，是列表页
                            if url_lower.endswith("/news/") or "?" in url_lower:
                                is_strong_blacklist = True
                                break
                            else:
                                # 否则可能是具体新闻，保留
                                continue
                        if "longi.com/cn/bulletin/" in url_lower or "longi.com/tw/bulletin/" in url_lower:
                            # 如果只是 /bulletin/ 结尾或者带 ? 参数，是列表页
                            if url_lower.endswith("/bulletin/") or "?" in url_lower:
                                is_strong_blacklist = True
                                break
                            else:
                                # 否则可能是具体公告，保留
                                continue
                        # 例外4：东方财富的 notices/detail/ 路径（具体公告正文）
                        if "data.eastmoney.com/notices/detail/" in url_lower:
                            # 这是具体的公告正文，保留
                            continue
                        # 例外5：Moomoo的 /news/ 路径且有实际新闻内容
                        if "moomoo.com/hans/stock/" in url_lower and "/news" in url_lower:
                            # 检查是否有实际新闻内容（不是空模板）
                            if content and len(content) > 50 and "最新新闻" in content:
                                # 有实际新闻内容，保留
                                continue
                        # 例外6：股吧具体帖子（非列表，且内容不是模板）
                        if "guba.eastmoney.com/news," in url_lower:
                            # 检查是否是模板内容
                            if "股吧，股民朋友可以在这里畅所欲言" not in content and "股吧提供实时股票行情" not in content:
                                # 不是模板内容，保留
                                continue
                        # 过滤模式：?page=, ?keyword=, ?symbol=, /list/ 结尾等
                        if "?page=" in url_lower or "?keyword=" in url_lower or "?symbol=" in url_lower:
                            # 这些参数通常表示列表页
                            is_strong_blacklist = True
                            break
                        # 检查是否是隆基的列表页（以 /bulletin/ 或 /news/ 结尾）
                        if "longi.com/cn/bulletin/" in url_lower and (url_lower.endswith("/bulletin/") or "/bulletin/?" in url_lower):
                            is_strong_blacklist = True
                            break
                        if "longi.com/cn/news/" in url_lower and (url_lower.endswith("/news/") or "/news/?" in url_lower):
                            is_strong_blacklist = True
                            break
                        # 其他情况直接匹配
                        is_strong_blacklist = True
                        break

                if is_strong_blacklist:
                    # 强黑名单URL直接过滤，不考虑新闻特征
                    filter_reason = "强黑名单URL"

            if not filter_reason:
                # --- 过滤个股行情页面 ---
                # 如果是行情页面URL，且没有明确的新闻特征，且URL不像新闻页，跳过
                if self.is_stock_quote_url(url) and not has_news and not is_news_url:
                    filter_reason = "个股数据页"

            if not filter_reason:
                # 如果标题看起来像行情页，且没有新闻特征，跳过
                if self.is_stock_quote_title(title) and not has_news:
                    filter_reason = "行情页标题"

            if not filter_reason:
                # 如果内容看起来像行情数据，且没有新闻特征，跳过
                if self.is_likely_quote_content(content) and not has_news:
                    filter_reason = "行情数据内容"

            if not filter_reason:
                # 如果内容是纯导航模板，且没有新闻特征，跳过
                if self.is_template_nav_content(content) and not has_news:
                    filter_reason = "导航模板"

            if not filter_reason:
                # 明显是模板页面且没有新闻特征的跳过
                if (self.is_template_url(url) or self.is_template_title(title)) and not has_news:
                    filter_reason = "模板页面"

            if not filter_reason:
                # 新闻列表页且没有新闻特征的跳过
                if (self.is_news_list_url(url) or self.is_news_list_title(title)) and not has_news:
                    filter_reason = "新闻列表页"

            if not filter_reason:
                # 内容较短且像模板且没有新闻特征的跳过
                if self.is_likely_template_content(content) and len(content) < 200 and not has_news:
                    filter_reason = "模板内容"

            # 记录过滤原因
            if filter_reason:
                filtered_count += 1
                filtered_reasons[filter_reason] = filtered_reasons.get(filter_reason, 0) + 1
                # 调试级别日志记录过滤详情
                logger.debug(f"过滤[{filter_reason}]: {title[:50]}... | URL: {url[:80]}...")
                continue

            # 简单清理多余空白
            if content:
                cleaned_content = re.sub(r"\s+", " ", content).strip()
                result["content"] = cleaned_content

            filtered.append(result)

        # 记录过滤统计
        if filtered_count > 0:
            reason_str = ", ".join([f"{k}:{v}" for k, v in filtered_reasons.items()])
            logger.info(f"过滤完成: 原始{len(results)}条 -> 保留{len(filtered)}条，过滤{filtered_count}条 ({reason_str})")
        else:
            logger.info(f"过滤完成: 保留全部{len(filtered)}条")

        return filtered
