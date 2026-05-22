#!/usr/bin/env python3
"""测试量化API返回数据格式"""
import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

session = requests.Session()
session.headers.update(headers)

stock_code = "601012"
market = 1
url = f"http://push2.eastmoney.com/api/qt/stock/get?secid={market}.{stock_code}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f57,f58,f60,f107,f116,f117,f127,f162,f163,f164,f165,f166,f167,f168,f169,f170,f171"

print("测试API:", url)
response = session.get(url, timeout=10)
data = response.json()

print(f"状态码: {data.get('rc')}")
print(f"数据: {data.get('data')}")

if data.get('data'):
    q = data['data']
    print(f"\n字段值:")
    print(f"f58(名称): {q.get('f58')}")
    print(f"f43(最新价): {q.get('f43')}")
    print(f"f60(昨收): {q.get('f60')}")
    print(f"f170(涨跌幅): {q.get('f170')}")
    print(f"f169(涨跌额): {q.get('f169')}")
    print(f"f168(换手率): {q.get('f168')}")
    print(f"f163(量比): {q.get('f163')}")
    print(f"f47(成交量): {q.get('f47')}")
    print(f"f48(内盘): {q.get('f48')}")
    print(f"f49(外盘): {q.get('f49')}")
