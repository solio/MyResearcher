#!/usr/bin/env python3
"""
股吧爬虫模块
直接爬取guba.eastmoney.com获取帖子
"""
import time
import re
import random
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

# curl_cffi: 模拟浏览器 TLS 指纹，绕过反爬
try:
    from curl_cffi import requests as curl_cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    curl_cffi_requests = None
    CURL_CFFI_AVAILABLE = False

import requests  # 标准 requests 作为回退


class GubaScraper:
    """股吧爬虫"""

    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]

    def __init__(self, use_curl_cffi: bool = True):
        self.headers = {
            "User-Agent": self.USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://guba.eastmoney.com/"
        }
        self._ua_index = 0

        if use_curl_cffi and CURL_CFFI_AVAILABLE:
            self.session = curl_cffi_requests.Session()
            # 模拟 Chrome 120 的 TLS 指纹
            self.session.impersonate = "chrome120"
            logger.info("股吧爬虫使用 curl_cffi (TLS 指纹模拟 chrome120)")
        else:
            if use_curl_cffi and not CURL_CFFI_AVAILABLE:
                logger.warning("curl_cffi 未安装，回退到标准 requests")
            self.session = requests.Session()

        self.session.headers.update(self.headers)

    def _rotate_ua(self):
        self._ua_index = (self._ua_index + 1) % len(self.USER_AGENTS)
        self.session.headers["User-Agent"] = self.USER_AGENTS[self._ua_index]

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

            # 检查反爬：真正的验证码页面不会有正常帖子链接
            post_links = re.findall(rf'/news,{stock_code},\d+\.html', html)
            if len(post_links) < 3 and ("验证码" in html or "人机验证" in html or "geetest" in html.lower()):
                logger.warning(f"检测到反爬机制，需要验证码（帖子链接数: {len(post_links)}）")
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
        # 找到帖子列表区域，通常在一个class含"listbody"或"datatable"的table里
        target_table = None
        for table in soup.find_all("table"):
            # 检查table中是否有该股票的帖子链接
            if table.find("a", href=re.compile(rf'/news,{stock_code},\d+\.html')):
                target_table = table
                break

        # 如果没找到特定table，降级到找所有tr
        trs = []
        if target_table:
            trs = target_table.find_all("tr")
        else:
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

            # 在标题列中找链接 - 必须精确匹配当前股票代码！
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

            # 清理标题 - 更严格的验证
            if not title or len(title) < 2:
                continue

            # 【重要】验证标题是否与股票相关，过滤明显不相关的垃圾信息
            # 常见的股吧广告/垃圾标题特征
            skip_patterns = [
                "张楠", "飞书", "天猫好房", "基金经理", "钟南山", "新冠疫苗",
                "恒大", "抖音", "快手", "淘宝", "京东", "拼多多",
                "加微信", "QQ群", "vx", "v信", "老师", "带你",
                "合作", "分成", "盈利", "解套", "指导", "诊股"
            ]
            if any(p in title for p in skip_patterns):
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

    def scrape_stock_posts(self, stock_code: str, max_pages: int = 10,
                           target_date: str = None,
                           only_24h: bool = False) -> List[Dict]:
        """
        爬取某只股票的股吧帖子

        Args:
            stock_code: 股票代码
            max_pages: 最大爬取页数
            target_date: 目标日期，格式YYYYMMDD。指定时仅返回该日期及之前的帖子，
                         自动增加翻页数直到找到目标日期的内容。
            only_24h: 仅保留24小时内的帖子（target_date 为 None 时生效）

        Returns:
            帖子列表
        """
        all_posts = []
        seen_urls = set()
        target_dt = None
        cutoff_24h = None

        if target_date:
            target_dt = datetime.strptime(target_date, "%Y%m%d")
            days_ago = (datetime.now() - target_dt).days
            if days_ago > 0:
                scaled_pages = max_pages + days_ago * 3
                max_pages = min(scaled_pages, 200)
                logger.info(f"指定日期 {target_date}（{days_ago}天前），翻页数调整为 {max_pages}")
            target_date_str = target_dt.strftime("%Y-%m-%d")
        elif only_24h:
            cutoff_24h = datetime.now() - timedelta(hours=24)
            logger.info(f"仅保留24小时内帖子（{cutoff_24h.strftime('%Y-%m-%d %H:%M')} 之后）")

        found_target_date = False  # 是否已找到目标日期的帖子
        gone_past_target = False   # 是否已翻过目标日期（帖子早于目标日期）
        consecutive_empty = 0      # 连续无新帖的页数，用于安全终止

        for page in range(1, max_pages + 1):
            logger.info(f"正在爬取第 {page}/{max_pages} 页...")

            # 获取页面，遇到反爬时等待重试
            html = None
            for retry in range(3):
                html = self.fetch_list_page(stock_code, page)
                if html:
                    break
                if retry < 2:
                    wait = 5 * (retry + 1) + random.random() * 3
                    logger.warning(f"第{page}页获取失败，{wait:.0f}秒后重试 ({retry+1}/3)...")
                    self._rotate_ua()
                    time.sleep(wait)
            if not html:
                logger.warning(f"第{page}页重试3次仍失败，停止爬取")
                break

            posts = self.extract_posts_from_html(html, stock_code)

            if not posts:
                logger.info(f"第{page}页未找到帖子，可能已到最后一页")
                break

            # 去重并添加（带日期过滤）
            new_count = 0
            page_has_target_date = False
            page_oldest_time = None

            for post in posts:
                url = post.get("url", "")
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)

                post_time_str = post.get("post_time")
                post_dt = None
                if post_time_str:
                    try:
                        post_dt = datetime.strptime(post_time_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

                # 24小时过滤
                if cutoff_24h and post_dt:
                    if post_dt < cutoff_24h:
                        # 跟踪最老的帖子时间
                        if page_oldest_time is None or post_dt < page_oldest_time:
                            page_oldest_time = post_dt
                        continue  # 跳过超过24小时的帖子

                if post_time_str and target_dt:
                    try:
                        post_dt = datetime.strptime(post_time_str, "%Y-%m-%d %H:%M:%S")
                        post_date_str = post_dt.strftime("%Y-%m-%d")

                        # 跟踪本页最老的帖子时间
                        if page_oldest_time is None or post_dt < page_oldest_time:
                            page_oldest_time = post_dt

                        # 跳过晚于目标日期的帖子
                        if post_date_str > target_date_str:
                            continue

                        # 检测是否到达目标日期
                        if post_date_str == target_date_str:
                            page_has_target_date = True
                            found_target_date = True
                    except ValueError:
                        pass

                all_posts.append(post)
                new_count += 1

            # 安全终止：连续太多页无新帖
            if new_count == 0:
                consecutive_empty += 1
                if consecutive_empty >= 10:
                    logger.info(f"连续 {consecutive_empty} 页无新帖，停止爬取")
                    break
            else:
                consecutive_empty = 0

            logger.info(f"第{page}页新增 {new_count} 个帖子，累计 {len(all_posts)} 个")

            # 礼貌延迟 + 随机抖动（避免触发反爬）
            if page < max_pages:
                delay = 2.5 + random.random() * 2.0  # 2.5~4.5 秒
                time.sleep(delay)
            # 每 10 页换一次 UA
            if page % 10 == 0:
                self._rotate_ua()

            # 终止条件判断
            if target_dt:
                # 如果本页最老的帖子已经早于目标日期，说明已翻过目标日期，可以停止
                if page_oldest_time and page_oldest_time.strftime("%Y-%m-%d") < target_date_str:
                    logger.info(f"已翻过目标日期 {target_date_str}（本页最老: {page_oldest_time.strftime('%Y-%m-%d')}），停止爬取")
                    gone_past_target = True
                    break

                # 如果已经找到目标日期且本页没有目标日期的帖子，
                # 且本页最老帖子已经是更早的日期，也停止
                if found_target_date and not page_has_target_date:
                    if page_oldest_time and page_oldest_time.strftime("%Y-%m-%d") < target_date_str:
                        logger.info(f"已找到目标日期且已翻过，停止爬取")
                        break
            else:
                # 24小时模式：本页最老帖子已超过24小时，且新增不足一页时停止
                if cutoff_24h and page_oldest_time and page_oldest_time < cutoff_24h:
                    if new_count < 20:  # 大部分帖子已过24h，终止
                        logger.info(f"已翻过24小时窗口（最老帖: {page_oldest_time.strftime('%m-%d %H:%M')}），停止")
                        break
                # 无目标日期时：新帖子太少就停
                elif new_count < 3 and page > 3:
                    logger.info("新帖子太少，提前终止爬取")
                    break

        logger.info(f"爬取完成，共获取 {len(all_posts)} 个帖子"
                    f"{f'（目标日期: {target_date}）' if target_date else ''}")
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
