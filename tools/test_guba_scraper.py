#!/usr/bin/env python3
"""
测试直接爬取股吧
"""
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict

def test_guba_list(stock_code: str = "601012", page: int = 1) -> bool:
    """测试访问股吧列表页"""
    url = f"https://guba.eastmoney.com/list,{stock_code}_{page}.html"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://guba.eastmoney.com/"
    }

    try:
        print(f"尝试访问: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            print(f"响应长度: {len(response.text)} 字符")

            # 检查是否有反爬特征
            if "验证" in response.text or "验证码" in response.text or "安全检查" in response.text:
                print("⚠️  检测到反爬机制（需要验证码）")
                return False

            # 检查是否有帖子数据
            if "newslist" in response.text or "listitem" in response.text or stock_code in response.text:
                print("✅ 页面正常，找到帖子列表特征")
                print("\n=== 响应预览（前500字符）===")
                print(response.text[:500])
                return True
            else:
                print("⚠️  页面返回但未找到帖子列表特征")
                print("\n=== 响应预览（前1000字符）===")
                print(response.text[:1000])
                return False
        else:
            print(f"❌ 请求失败，状态码 {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def test_guba_post(post_url: str) -> bool:
    """测试访问股吧帖子详情页"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://guba.eastmoney.com/"
    }

    try:
        print(f"\n尝试访问帖子: {post_url}")
        response = requests.get(post_url, headers=headers, timeout=15)
        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            if "验证" in response.text or "验证码" in response.text:
                print("⚠️  检测到反爬机制")
                return False

            print("✅ 帖子详情页正常")
            print(f"响应长度: {len(response.text)}")
            return True
        else:
            return False

    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("股吧爬取可行性测试")
    print("=" * 60)

    # 测试列表页
    success = test_guba_list("601012", 1)

    if success:
        print("\n✅ 列表页访问成功！")

        # 等待一下再测试详情页
        time.sleep(2)

        # 测试一个已知的帖子
        test_url = "https://guba.eastmoney.com/news,601012,1688684946.html"
        test_guba_post(test_url)
    else:
        print("\n❌ 列表页访问失败，需要退回搜索引擎方式")

    print("\n" + "=" * 60)
