#!/usr/bin/env python3
"""测试编码修复"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from guba_scraper import GubaScraper

def test_encoding():
    """测试编码问题修复"""
    print("测试股吧爬虫编码修复...")
    scraper = GubaScraper()

    # 获取第一页
    html = scraper.fetch_list_page("601888", 1)
    if not html:
        print("获取页面失败")
        return False

    # 测试提取帖子
    posts = scraper.extract_posts_from_html(html, "601888")
    print(f"\n提取到 {len(posts)} 个帖子")

    # 显示前10个帖子的标题
    print("\n前10个帖子标题:")
    for i, post in enumerate(posts[:10], 1):
        title = post.get("title", "")
        print(f"{i}. {title}")

    # 检查是否还有乱码
    has_mojibake = any("å" in post.get("title", "") for post in posts[:20])

    print(f"\n检测到乱码: {'是' if has_mojibake else '否'}")
    return not has_mojibake

if __name__ == "__main__":
    success = test_encoding()
    sys.exit(0 if success else 1)
