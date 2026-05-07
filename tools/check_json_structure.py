#!/usr/bin/env python3
import json

json_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("JSON类型:", type(data))
if isinstance(data, dict):
    print("键:", list(data.keys())[:10])
    # 查看第一个值
    if data:
        first_key = list(data.keys())[0]
        first_value = data[first_key]
        print(f"\n第一个键: {first_key}")
        print(f"第一个值类型: {type(first_value)}")
        if isinstance(first_value, dict):
            print(f"第一个值键: {list(first_value.keys())}")
        elif isinstance(first_value, list):
            print(f"第一个值长度: {len(first_value)}")
            if first_value:
                print(f"第一个元素: {first_value[0]}")
elif isinstance(data, list):
    print(f"长度: {len(data)}")
    if data:
        print(f"第一个元素: {data[0]}")

# 打印前500个字符查看结构
with open(json_path, 'r', encoding='utf-8') as f:
    preview = f.read(2000)
    print("\n" + "="*80)
    print("预览:")
    print("="*80)
    print(preview)
