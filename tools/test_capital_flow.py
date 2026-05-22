#!/usr/bin/env python3
"""测试资金流向API返回数据格式"""
import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

session = requests.Session()
session.headers.update(headers)

stock_code = "601012"
market = 1
url = f"http://push2.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=1&klt=1&secid={market}.{stock_code}&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"

print("测试API:", url)
response = session.get(url, timeout=10)
data = response.json()

print(f"状态码: {data.get('rc')}")

if data.get('data'):
    klines = data['data'].get('klines', [])
    if klines:
        latest = klines[-1]
        print(f"\n最新数据: {latest}")
        parts = latest.split(',')
        print(f"\n字段数: {len(parts)}")
        if len(parts) >= 10:
            print(f"主力净流入(parts[1]): {parts[1]}")
            print(f"超大单净流入(parts[5]): {parts[5]}")
