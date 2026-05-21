#!/usr/bin/env python3
"""测试修复后的股吧爬虫"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guba_scraper import GubaScraper

def test():
    scraper = GubaScraper()
    posts = scraper.scrape_stock_posts("601012", max_pages=1)

    print(f"\n获取到 {len(posts)} 个帖子\n")

    for i, post in enumerate(posts[:20]):
        print(f"{i+1}. {post['title'][:50]}")
        print(f"   阅读={post.get('read_count',0)}, 评论={post.get('reply_count',0)}, 时间={post.get('post_time')}")
        print(f"   {post['url']}")
        print()

if __name__ == "__main__":
    test()
