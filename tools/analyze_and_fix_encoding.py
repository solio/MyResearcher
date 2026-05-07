#!/usr/bin/env python3
import json
import re
import sys
from urllib.parse import urlparse
import chardet

def detect_encoding(text):
    """检测文本编码"""
    if not text or not isinstance(text, str):
        return None
    try:
        result = chardet.detect(text.encode('latin-1', errors='ignore'))
        return result
    except:
        return None

def is_garbled(text):
    """判断是否是乱码"""
    if not text or not isinstance(text, str):
        return False

    # 统计乱码字符模式
    # 常见的乱码模式：多个连续的非ASCII、非中日韩文字符
    garbled_pattern = re.compile(r'[Ѐ-ӿԀ-ԯḀ-ỿⰀ-ⱟꙀ-ꚟͰ-Ͽ̀-ͯ]{3,}')

    # 统计看起来像乱码的字符
    garbled_chars = 0
    total_chars = len(text)

    if total_chars == 0:
        return False

    for char in text:
        code = ord(char)
        # 如果字符在这些范围内，可能是乱码
        if (0x0400 <= code <= 0x04FF or  # 西里尔字母
            0x0500 <= code <= 0x052F or  # 西里尔字母补充
            0x1E00 <= code <= 0x1EFF or  # 拉丁字母扩展附加
            0x2C00 <= code <= 0x2C5F or  # 格拉哥里字母
            0xA640 <= code <= 0xA69F or  # 西里尔字母扩展B
            0x0370 <= code <= 0x03FF or  # 希腊字母和科普特字母
            0x0300 <= code <= 0x036F): # 组合附加符号
            garbled_chars += 1

    # 如果超过30%的字符看起来像乱码，或者有乱码模式
    if (garbled_chars / total_chars > 0.3 or
        garbled_pattern.search(text)):
        return True

    return False

def get_site_name(url):
    """从URL获取站点名称"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if 'sina' in domain:
            return '新浪财经'
        elif '10jqka' in domain:
            return '同花顺'
        elif 'stockstar' in domain:
            return '证券之星'
        elif 'hexun' in domain:
            return '和讯网'
        elif 'eastmoney' in domain:
            return '东方财富网'
        elif 'xueqiu' in domain:
            return '雪球'
        elif 'moomoo' in domain:
            return '富途牛牛'
        elif 'weaver' in domain:
            return '泛微网络'
        elif 'longi' in domain:
            return '隆基绿能'
        else:
            return domain
    except:
        return url

def create_clean_title(url, stock_name):
    """根据URL和股票名称创建干净的标题"""
    site_name = get_site_name(url)
    return f"{stock_name} - {site_name}"

def analyze_json_file(file_path):
    """分析JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=" * 80)
    print("分析乱码问题")
    print("=" * 80)

    # 记录需要修复的条目
    items_to_fix = []

    # 遍历所有股票
    for stock_code, stock_data in data.items():
        stock_name = stock_data.get('name', '')
        print(f"\n股票: {stock_name} ({stock_code})")
        print("-" * 80)

        # 检查搜索结果
        search_results = stock_data.get('search_results', [])
        for idx, item in enumerate(search_results):
            title = item.get('title', '')
            content = item.get('content', '')

            title_garbled = is_garbled(title)
            content_garbled = is_garbled(content)

            if title_garbled or content_garbled:
                print(f"  序号 {idx+1}: 乱码!")
                print(f"    标题: {title[:100]}")
                if title_garbled:
                    print(f"    -> 标题乱码")
                if content_garbled:
                    print(f"    -> 内容乱码")
                print(f"    URL: {item.get('url', '')}")
                items_to_fix.append({
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'index': idx,
                    'item': item,
                    'title_garbled': title_garbled,
                    'content_garbled': content_garbled
                })

    print(f"\n总计发现 {len(items_to_fix)} 个乱码条目")
    return data, items_to_fix

def fix_json_data(data, items_to_fix):
    """修复JSON数据"""
    for fix_info in items_to_fix:
        stock_code = fix_info['stock_code']
        stock_name = fix_info['stock_name']
        idx = fix_info['index']
        item = fix_info['item']
        url = item.get('url', '')

        # 修复标题
        if fix_info['title_garbled']:
            new_title = create_clean_title(url, stock_name)
            data[stock_code]['search_results'][idx]['title'] = new_title
            print(f"修复标题: {item.get('title', '')[:50]}... -> {new_title}")

        # 修复内容 - 简化为站点描述
        if fix_info['content_garbled']:
            site_name = get_site_name(url)
            new_content = f"{site_name}提供的{stock_name}相关信息"
            data[stock_code]['search_results'][idx]['content'] = new_content
            print(f"修复内容: {item.get('content', '')[:50]}... -> {new_content}")

    return data

def save_json_file(data, output_path):
    """保存JSON文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已保存修复后的文件: {output_path}")

def main():
    json_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据.json'
    output_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据_已修复.json'

    print("开始分析...")
    data, items_to_fix = analyze_json_file(json_path)

    if items_to_fix:
        print("\n开始修复...")
        fixed_data = fix_json_data(data, items_to_fix)
        save_json_file(fixed_data, output_path)

        # 备份原文件并替换
        import os
        backup_path = json_path + '.backup'
        os.rename(json_path, backup_path)
        os.rename(output_path, json_path)
        print(f"已备份原文件: {backup_path}")
        print(f"已替换原文件: {json_path}")
    else:
        print("\n未发现需要修复的乱码问题")

if __name__ == '__main__':
    main()
