#!/usr/bin/env python3
"""
股吧爬虫模块
直接爬取guba.eastmoney.com获取帖子
"""
import requests
import time
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin

from logger import get_logger

logger = get_logger()

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("BeautifulSoup未安装，将使用简化解析")

class GubaScraper:
    """股吧爬虫"""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://guba.eastmoney.com/"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """
        解析股吧时间格式
        支持格式：
        - "05-08 14:30" (今年)
        - "2025-05-08 14:30" (完整年份)
        - "今天 14:30"
        - "14:30" (今天)
        """
        if not time_str:
            return None

        now = datetime.now()
        time_str = time_str.strip()

        try:
            # 格式: "2025-05-08 14:30"
            if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', time_str):
                return datetime.strptime(time_str, "%Y-%m-%d %H:%M")

            # 格式: "05-08 14:30"
            if re.match(r'\d{2}-\d{2} \d{2}:\d{2}', time_str):
                dt = datetime.strptime(time_str, "%m-%d %H:%M")
                return dt.replace(year=now.year)

            # 格式: "今天 14:30"
            if "今天" in time_str:
                t_match = re.search(r'(\d{2}):(\d{2})', time_str)
                if t_match:
                    h, m = int(t_match.group(1)), int(t_match.group(2))
                    return datetime(now.year, now.month, now.day, h, m)

            # 格式: "14:30" (只有时间)
            if re.match(r'\d{2}:\d{2}', time_str):
                h, m = map(int, time_str.split(':'))
                return datetime(now.year, now.month, now.day, h, m)

        except Exception as e:
            logger.debug(f"时间解析失败: {time_str}, error: {e}")

        return None

    def _is_within_24h(self, dt: Optional[datetime]) -> bool:
        """判断时间是否在24小时内"""
        if not dt:
            return False  # 无法解析的默认保留
        now = datetime.now()
        return (now - dt) < timedelta(hours=24)

    def fetch_list_page(self, stock_code: str, page: int = 1) -> Optional[str]:
        """
        获取股吧列表页HTML

        Args:
            stock_code: 股票代码
            page: 页码

        Returns:
            HTML内容，失败返回None
        """
        url = f"https://guba.eastmoney.com/list,{stock_code}_{page}.html"

        try:
            logger.info(f"爬取股吧列表页: {stock_code} 第{page}页")
            response = self.session.get(url, timeout=20)

            if response.status_code != 200:
                logger.warning(f"请求失败: {response.status_code}")
                return None

            # 修复编码问题 - 双重保障
            # 方法1: 强制设置UTF-8
            response.encoding = 'utf-8'
            html = response.text

            # 方法2: 如果检测到乱码特征，直接从content解码
            # 检查是否有典型的latin-1乱码特征
            if "å" in html or "ä" in html or "é" in html:
                logger.info("检测到编码异常，尝试备用解码方案")
                html = response.content.decode('utf-8', errors='replace')

            # 检查反爬
            if "验证" in html or "验证码" in html:
                logger.warning("检测到反爬机制，需要验证码")
                return None

            return html

        except Exception as e:
            logger.warning(f"爬取列表页异常: {e}")
            return None

    def extract_posts_from_html(self, html: str, stock_code: str) -> List[Dict]:
        """
        从HTML中提取帖子信息

        Args:
            html: 页面HTML
            stock_code: 股票代码

        Returns:
            帖子列表
        """
        posts = []
        seen_urls = set()

        if BS4_AVAILABLE:
            posts = self._extract_with_bs4(html, stock_code, seen_urls)
        else:
            posts = self._extract_with_regex(html, stock_code, seen_urls)

        logger.info(f"从列表页提取到 {len(posts)} 个帖子")
        return posts

    def _extract_with_bs4(self, html: str, stock_code: str, seen_urls: set) -> List[Dict]:
        """使用BeautifulSoup解析"""
        posts = []
        # 使用lxml解析器更快更稳定
        soup = BeautifulSoup(html, 'lxml')

        # 股吧是5列表格：阅读|评论|标题|作者|最后更新
        trs = soup.find_all("tr")
        for tr in trs:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue

            # 提取各列内容
            td_read = tds[0].get_text(strip=True)
            td_comment = tds[1].get_text(strip=True)
            td_title = tds[2]
            td_author = tds[3].get_text(strip=True)
            td_time = tds[4].get_text(strip=True)

            # 在标题列中找链接
            a_tag = td_title.find("a", href=re.compile(rf'/news,{stock_code},\d+\.html'))
            if not a_tag:
                continue

            url_suffix = a_tag.get('href', '')
            if not url_suffix:
                continue

            full_url = urljoin("https://guba.eastmoney.com", url_suffix)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # 获取标题
            title = a_tag.get_text(strip=True)

            # 清理标题
            if not title or len(title) < 2:
                continue

            # 解析阅读数和评论数
            read_count = self._parse_number(td_read)
            comment_count = self._parse_number(td_comment)

            # 解析时间
            post_time = self._parse_time(td_time)

            posts.append({
                "title": title,
                "url": full_url,
                "content": "",
                "source_type": "forum",
                "source": "guba",
                "reply_count": comment_count,
                "read_count": read_count,
                "post_time": post_time.strftime("%Y-%m-%d %H:%M:%S") if post_time else None
            })

        return posts

    def _parse_number(self, s: str) -> int:
        """解析数字字符串（支持万单位）"""
        s = s.strip()
        if not s:
            return 0

        # 处理"万"单位
        if "万" in s:
            try:
                num = float(s.replace("万", ""))
                return int(num * 10000)
            except:
                pass

        # 普通数字
        try:
            return int(re.sub(r'\D', '', s))
        except:
            return 0

    def _extract_with_regex(self, html: str, stock_code: str, seen_urls: set) -> List[Dict]:
        """使用正则表达式解析（降级方案）"""
        posts = []

        # 尝试匹配: <a ... href="/news,...">标题</a>
        link_title_pattern = rf'<a[^>]*href=["\'](/news,{stock_code},\d+\.html)["\'][^>]*>([^<]+)</a>'
        matches = re.findall(link_title_pattern, html, re.IGNORECASE)

        for url_suffix, title in matches:
            full_url = urljoin("https://guba.eastmoney.com", url_suffix)

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = title.strip()
            if not title or len(title) < 2:
                continue

            posts.append({
                "title": title,
                "url": full_url,
                "content": "",
                "source_type": "forum",
                "source": "guba"
            })

        # 如果上面没找到，尝试更简单的方法
        if not posts:
            simple_pattern = rf'(/news,{stock_code},\d+\.html)'
            urls = re.findall(simple_pattern, html)
            for url_suffix in urls[:50]:
                full_url = urljoin("https://guba.eastmoney.com", url_suffix)
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    posts.append({
                        "title": "股吧帖子",
                        "url": full_url,
                        "content": "",
                        "source_type": "forum",
                        "source": "guba"
                    })

        return posts

    def fetch_post_detail(self, url: str) -> Optional[Dict]:
        """
        获取帖子详情（可选，比较耗时）

        Args:
            url: 帖子URL

        Returns:
            帖子详情
        """
        try:
            response = self.session.get(url, timeout=15)

            if response.status_code != 200:
                return None

            # 修复编码问题
            response.encoding = 'utf-8'

            # 简单提取内容
            html = response.text

            # 尝试提取发布时间
            time_match = re.search(r'发表于\s*([^<\n]+)', html)
            post_time = None
            if time_match:
                post_time = self._parse_time(time_match.group(1))

            # 提取阅读数、评论数
            read_count = 0
            comment_count = 0

            read_match = re.search(r'阅读\D*(\d+)', html)
            if read_match:
                read_count = int(read_match.group(1))

            comment_match = re.search(r'评论\D*(\d+)', html)
            if comment_match:
                comment_count = int(comment_match.group(1))

            return {
                "url": url,
                "post_time": post_time,
                "read_count": read_count,
                "comment_count": comment_count
            }

        except Exception as e:
            logger.debug(f"获取帖子详情失败: {e}")
            return None

    def scrape_stock_posts(self, stock_code: str, max_pages: int = 10) -> List[Dict]:
        """
        爬取某只股票的股吧帖子

        Args:
            stock_code: 股票代码
            max_pages: 最大爬取页数

        Returns:
            帖子列表
        """
        all_posts = []
        seen_urls = set()

        for page in range(1, max_pages + 1):
            logger.info(f"正在爬取第 {page}/{max_pages} 页...")

            html = self.fetch_list_page(stock_code, page)
            if not html:
                logger.warning(f"第{page}页获取失败，停止爬取")
                break

            posts = self.extract_posts_from_html(html, stock_code)

            if not posts:
                logger.info(f"第{page}页未找到帖子，可能已到最后一页")
                break

            # 去重并添加
            new_count = 0
            for post in posts:
                url = post.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_posts.append(post)
                    new_count += 1

            logger.info(f"第{page}页新增 {new_count} 个帖子，累计 {len(all_posts)} 个")

            # 礼貌延迟
            if page < max_pages:
                time.sleep(1)

            # 简单终止条件：如果本页新帖子太少，可能是重复内容
            if new_count < 3 and page > 3:
                logger.info("新帖子太少，提前终止爬取")
                break

        logger.info(f"爬取完成，共获取 {len(all_posts)} 个帖子")
        return all_posts


def test_scraper():
    """测试爬虫"""
    scraper = GubaScraper()

    print("测试爬取隆基绿能股吧...")
    posts = scraper.scrape_stock_posts("601012", max_pages=2)

    print(f"\n获取到 {len(posts)} 个帖子:")
    for i, post in enumerate(posts[:10], 1):
        print(f"{i}. {post.get('title', '无标题')[:50]}")
        print(f"   {post.get('url', '')}")


if __name__ == "__main__":
    test_scraper()
