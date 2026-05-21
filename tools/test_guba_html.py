#!/usr/bin/env python3
"""测试股吧HTML结构"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup

def test_guba_html():
    """测试股吧列表页HTML"""
    url = "https://guba.eastmoney.com/list,601012.html"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    print(f"请求: {url}")
    response = requests.get(url, headers=headers, timeout=20)
    print(f"状态码: {response.status_code}")

    # 保存HTML
    with open("/tmp/guba_test.html", "w", encoding="utf-8") as f:
        f.write(response.text)

    print(f"HTML已保存到: /tmp/guba_test.html")
    print(f"长度: {len(response.text)}")

    # 用BeautifulSoup解析
    soup = BeautifulSoup(response.text, "lxml")

    # 查找表格
    print("\n=== 查找表格 ===")
    tables = soup.find_all("table")
    print(f"找到 {len(tables)} 个表格")

    for i, table in enumerate(tables[:2]):
        print(f"\n表格 {i}:")
        print(table.get_text()[:500])

    # 查找包含"阅读"的元素
    print("\n=== 查找含'阅读'的元素 ===")
    elements_with_read = soup.find_all(text=lambda x: x and "阅读" in x)
    print(f"找到 {len(elements_with_read)} 个含'阅读'的文本")
    for elem in elements_with_read[:10]:
        print(f"  - {elem.strip()}")
        parent = elem.parent
        if parent:
            print(f"    父标签: {parent.name}")
            print(f"    父内容: {parent.get_text()[:200]}")

    # 查找帖子链接
    print("\n=== 查找帖子链接 ===")
    import re
    links = soup.find_all("a", href=re.compile(r'/news,601012,\d+\.html'))
    print(f"找到 {len(links)} 个帖子链接")
    for a in links[:5]:
        print(f"\n链接: {a.get('href')}")
        print(f"标题: {a.get_text(strip=True)}")
        parent = a.parent
        if parent:
            print(f"父标签: {parent.name}")
            print(f"父内容: {parent.get_text()[:300]}")

            # 查找兄弟元素
            print(f"兄弟元素:")
            for sibling in parent.previous_siblings:
                if hasattr(sibling, 'name'):
                    print(f"  - 前: {sibling.name} = {sibling.get_text()[:100]}")
            for sibling in parent.next_siblings:
                if hasattr(sibling, 'name'):
                    print(f"  - 后: {sibling.name} = {sibling.get_text()[:100]}")

    # 尝试查找tr行
    print("\n=== 查找tr行 ===")
    trs = soup.find_all("tr")
    print(f"找到 {len(trs)} 个tr")
    for tr in trs[:10]:
        text = tr.get_text().strip()
        if "阅读" in text or "评论" in text:
            print(f"\nTR内容: {text[:200]}")
            tds = tr.find_all("td")
            print(f"  TD数: {len(tds)}")
            for i, td in enumerate(tds):
                print(f"    TD{i}: {td.get_text().strip()[:50]}")

if __name__ == "__main__":
    test_guba_html()
