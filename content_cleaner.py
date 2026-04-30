"""
内容清理模块
用于去除搜索结果中的页面模板部分
"""
import re
from typing import List, Set


class ContentCleaner:
    """内容清理器"""

    def __init__(self):
        # 常见页面模板关键词（中文）
        self.template_keywords_cn = [
            "首页", "导航", "导航菜单", "顶部导航", "底部导航",
            "登录", "注册", "登录注册", "退出登录",
            "关于我们", "联系方式", "联系我们", "招聘信息", "加入我们",
            "网站地图", "友情链接", "合作伙伴",
            "版权声明", "版权所有", "侵权必究", "免责声明",
            "隐私政策", "使用条款", "用户协议",
            "客服热线", "客服电话", "联系电话",
            "©", "Copyright", "All Rights Reserved",
            "移动版", "电脑版", "APP下载", "客户端下载",
            "扫一扫", "微信", "微博", "公众号",
            "热门推荐", "热门搜索", "猜你喜欢", "相关推荐",
            "热点排行", "新闻排行", "热门排行",
            "下一页", "上一页", "第1页", "共N页",
            "返回顶部", "回到顶部",
            "广告", "广告位", "广告招商",
            "公告", "通知", "系统公告",
            "友情链接", "链接", "快速链接",
            "热门搜索", "搜索热词", "热搜词",
        ]

        # 常见页面模板关键词（英文）
        self.template_keywords_en = [
            "Home", "Navigation", "Menu", "Header", "Footer",
            "Login", "Register", "Sign in", "Sign up",
            "About us", "Contact us", "Careers", "Join us",
            "Sitemap", "Links", "Partners",
            "Privacy", "Terms", "Disclaimer",
            "Copyright", "All rights reserved",
            "Mobile", "Desktop", "Download", "App",
            "WeChat", "Weibo",
            "Advertisement", "Ad", "Sponsor",
            "Next page", "Previous page", "Page",
            "Back to top",
        ]

        # 常见URL模式（通常不是内容）
        self.url_patterns = [
            r"https?://[^\s]+",  # 完整URL
            r"www\.[^\s]+",  # www开头的网址
            r"[^\s]+\.(com|cn|net|org|io|co)[^\s]*",  # 常见域名
        ]

        # 常见导航链接模式（多个中文词用分隔符连接）
        self.nav_patterns = [
            r"^[\s\S]{0,100}(首页|股票|行情|数据|公告|研报)[\s\S]{0,100}$",
            r"^[\s\S]{0,200}(首页|宏观|证券|金融|商业|全球市场|观点|地产)[\s\S]{0,200}$",
            r"^[\s\S]{0,300}(新闻|博客|论坛|股吧|雪球|微博|微信)[\s\S]{0,300}$",
        ]

        # 短文本中的分隔符模式（"·" "|" "｜" 等）
        self.separator_pattern = r"[·|｜┆┊┋┇]"

        # 重复的标点符号
        self.repeat_punctuation = r"[。！？；]{2,}"

    def is_template_content(self, text: str) -> bool:
        """
        判断是否是模板内容

        Args:
            text: 输入文本

        Returns:
            是否是模板内容
        """
        if not text or len(text.strip()) < 10:
            return False

        text_clean = text.strip()

        # 检查是否以多个链接形式出现
        separator_count = len(re.findall(self.separator_pattern, text_clean))
        if separator_count >= 3 and len(text_clean) < 200:
            return True

        # 检查是否包含多个模板关键词
        template_count = 0
        for keyword in self.template_keywords_cn + self.template_keywords_en:
            if keyword in text_clean:
                template_count += 1
                if template_count >= 3:
                    return True

        # 检查是否匹配导航模式
        for pattern in self.nav_patterns:
            if re.match(pattern, text_clean):
                return True

        # 检查是否大部分是URL
        url_count = 0
        for pattern in self.url_patterns:
            url_count += len(re.findall(pattern, text_clean))
        if url_count >= 3:
            return True

        return False

    def clean_content(self, content: str) -> str:
        """
        清理内容，去除模板部分

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        if not content:
            return ""

        # 1. 先按段落分割
        paragraphs = content.split("\n")
        cleaned_paragraphs = []

        for para in paragraphs:
            para = para.strip()

            # 跳过太短的段落
            if len(para) < 10:
                continue

            # 检查是否是模板段落
            if self.is_template_content(para):
                continue

            cleaned_paragraphs.append(para)

        # 2. 重新组合段落
        cleaned_content = "\n".join(cleaned_paragraphs)

        # 3. 清理URL
        for pattern in self.url_patterns:
            cleaned_content = re.sub(pattern, " [链接] ", cleaned_content)

        # 4. 清理重复标点
        cleaned_content = re.sub(self.repeat_punctuation, "。", cleaned_content)

        # 5. 清理多余空白
        cleaned_content = re.sub(r"\s{3,}", "\n\n", cleaned_content)
        cleaned_content = re.sub(r"\n{3,}", "\n\n", cleaned_content)

        return cleaned_content.strip()

    def filter_results(self, results: List[Dict]) -> List[Dict]:
        """
        过滤搜索结果，去除模板内容

        Args:
            results: 原始搜索结果列表

        Returns:
            过滤后的结果列表
        """
        filtered = []
        for result in results:
            content = result.get("content", "")
            if content:
                cleaned_content = self.clean_content(content)
                if len(cleaned_content) > 30:  # 过滤太短的内容
                    result["content"] = cleaned_content
                    filtered.append(result)
        return filtered
