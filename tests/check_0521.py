#!/usr/bin/env python3
"""
检查0521的数据，看看股吧帖子是否文不对题
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_data():
    data_dir = Path(__file__).parent.parent / "output" / "20260521"
    data_files = list(data_dir.glob("*-数据.json"))
    if not data_files:
        print("找不到0521的数据文件")
        return None
    with open(sorted(data_files)[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def check_stock(data, target_name):
    for result in data.get("results", []):
        name = result.get("target_name", "")
        if target_name in name:
            print("="*80)
            print(f"{name}")
            print("="*80)

            news_list = result.get("news_list", [])
            forum_posts = [p for p in news_list if p.get("source_type") == "forum"]

            print(f"\n总帖子数: {len(news_list)}, 论坛帖子: {len(forum_posts)}")

            print("\n前20个帖子:")
            for i, post in enumerate(forum_posts[:20], 1):
                title = post.get("title", "")
                url = post.get("url", "")
                source = post.get("source", "")
                print(f"\n{i:2d}. [{source}] {title[:60]}")
                print(f"    {url}")

            return result


def main():
    data = load_data()
    if not data:
        return 1

    check_stock(data, "玲珑轮胎")
    print("\n\n")
    check_stock(data, "隆基绿能")

    return 0


if __name__ == "__main__":
    sys.exit(main())
