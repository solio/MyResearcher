#!/usr/bin/env python3
"""
雪球论坛直连爬虫模块
直接请求 xueqiu.com API，不消耗 Tavily 额度
"""
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from logger import get_logger

logger = get_logger()

# curl_cffi: 模拟浏览器 TLS 指纹
try:
    from curl_cffi import requests as curl_cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    curl_cffi_requests = None
    CURL_CFFI_AVAILABLE = False

import requests


class XueqiuScraper:
    """雪球论坛直连爬虫（不消耗 Tavily 额度）"""

    SEARCH_URL = "https://xueqiu.com/statuses/search.json"

    def __init__(self, use_curl_cffi: bool = False):
        if use_curl_cffi and CURL_CFFI_AVAILABLE:
            self.session = curl_cffi_requests.Session()
            self.session.impersonate = "chrome120"
            logger.info("雪球爬虫使用 curl_cffi (TLS 指纹模拟 chrome120)")
        else:
            if use_curl_cffi:
                logger.warning("curl_cffi 未安装，回退到标准 requests")
            self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://xueqiu.com/",
        })

    def _init_cookies(self):
        """访问首页获取基础 cookie（WAF 前置校验）"""
        try:
            self.session.get("https://xueqiu.com/", timeout=10)
        except Exception:
            pass

    def _stock_code_to_symbol(self, stock_code: str) -> str:
        """股票代码转雪球 symbol 格式"""
        code = stock_code.strip()
        if code.startswith(("6", "5", "9")):
            return f"SH{code}"
        elif code.startswith(("0", "3", "2")):
            return f"SZ{code}"
        return code

    def search_recent_posts(self, stock_code: str, max_results: int = 30,
                            time_range_days: int = 7) -> List[Dict]:
        """
        搜索个股近期雪球帖子（不限具体日期）

        Args:
            stock_code: 股票代码
            max_results: 最大结果数
            time_range_days: 时间范围（天）

        Returns:
            帖子列表
        """
        self._init_cookies()

        cutoff = datetime.now() - timedelta(days=time_range_days)
        all_posts = []
        seen_urls = set()

        for page in range(1, 5):  # 最多4页
            params = {
                "count": 20,
                "page": page,
                "q": stock_code,
                "sort": "time",
                "comment": "0",
                "_": int(time.time() * 1000),
            }
            try:
                resp = self.session.get(
                    self.SEARCH_URL, params=params, timeout=10
                )
                if resp.status_code != 200:
                    logger.debug(f"雪球 API 返回 {resp.status_code} (page={page})")
                    break

                data = resp.json()
                items = data.get("list", [])
                if not items:
                    break

                new_count = 0
                for item in items:
                    created_at = item.get("created_at", 0)
                    if not created_at:
                        continue
                    post_dt = datetime.fromtimestamp(created_at / 1000)

                    # 时间范围过滤
                    if post_dt < cutoff:
                        continue

                    url = f"https://xueqiu.com{item.get('target', '')}"
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = (item.get("title") or "").strip()
                    if not title:
                        text = item.get("text") or ""
                        title = text[:100].replace("\n", " ").strip()

                    reply_count = item.get("reply_count", 0) or 0
                    like_count = item.get("like_count", 0) or 0
                    view_count = item.get("view_count", 0) or 0

                    all_posts.append({
                        "title": title,
                        "url": url,
                        "content": item.get("text", "") or item.get("description", ""),
                        "source_type": "forum",
                        "source": "xueqiu",
                        "reply_count": reply_count,
                        "like_count": like_count,
                        "read_count": view_count,
                        "post_time": post_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    new_count += 1

                logger.debug(f"雪球 page={page}: 新增 {new_count} 帖")
                if new_count == 0:
                    break
                if len(all_posts) >= max_results:
                    break

            except (requests.RequestException, ValueError, KeyError) as e:
                logger.debug(f"雪球搜索失败 (page={page}): {e}")
                break

            time.sleep(0.6 + random.random() * 0.8)

        logger.info(f"雪球直连: {stock_code} 获取 {len(all_posts)} 帖")
        return all_posts

    def search_posts_by_date(self, stock_code: str, target_date: str,
                             max_pages: int = 3) -> List[Dict]:
        """
        搜索指定日期的雪球帖子（用于回填）

        Args:
            stock_code: 股票代码
            target_date: 目标日期 YYYYMMDD
            max_pages: 最大翻页数

        Returns:
            帖子列表（可能因 WAF 拦截而为空）
        """
        self._init_cookies()

        try:
            target_dt = datetime.strptime(target_date, "%Y%m%d")
            target_date_str = target_dt.strftime("%Y-%m-%d")
        except ValueError:
            return []

        all_posts = []
        for page in range(1, max_pages + 1):
            params = {
                "count": 20,
                "page": page,
                "q": stock_code,
                "sort": "time",
                "comment": "0",
                "_": int(time.time() * 1000),
            }
            try:
                resp = self.session.get(
                    self.SEARCH_URL, params=params, timeout=10
                )
                if resp.status_code != 200:
                    logger.debug(f"雪球 API 返回 {resp.status_code} (page={page})")
                    break

                data = resp.json()
                items = data.get("list", [])
                if not items:
                    break

                for item in items:
                    created_at = item.get("created_at", 0)
                    if not created_at:
                        continue
                    post_dt = datetime.fromtimestamp(created_at / 1000)
                    post_date_str = post_dt.strftime("%Y-%m-%d")

                    if post_date_str > target_date_str:
                        continue
                    if post_date_str < target_date_str:
                        return all_posts

                    title = (item.get("title") or "").strip()
                    if not title:
                        text = item.get("text") or ""
                        title = text[:100].replace("\n", " ").strip()

                    all_posts.append({
                        "title": title,
                        "url": f"https://xueqiu.com{item.get('target', '')}",
                        "content": item.get("text", ""),
                        "source_type": "forum",
                        "source": "xueqiu",
                        "reply_count": item.get("reply_count", 0) or 0,
                        "like_count": item.get("like_count", 0) or 0,
                        "read_count": item.get("view_count", 0) or 0,
                        "post_time": post_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    })

            except (requests.RequestException, ValueError, KeyError) as e:
                logger.debug(f"雪球搜索失败 (page={page}): {e}")
                break

            time.sleep(0.8)

        return all_posts
