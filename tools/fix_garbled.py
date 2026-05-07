#!/usr/bin/env python3
import json
import re
from urllib.parse import urlparse

def is_garbled(text):
    """判断是否是乱码"""
    if not text or not isinstance(text, str):
        return False

    # 常见的乱码模式统计
    # 统计非中、日、韩、英文、数字、常用标点的字符比例
    valid_chars = 0
    total_chars = len(text)

    if total_chars == 0:
        return False

    for char in text:
        code = ord(char)
        # 允许的字符范围
        if (0x0020 <= code <= 0x007E or  # ASCII可打印字符
            0x4E00 <= code <= 0x9FFF or  # 中日韩统一表意文字
            0x3400 <= code <= 0x4DBF or  # 中日韩统一表意文字扩展A
            0x20000 <= code <= 0x2A6DF or # 中日韩统一表意文字扩展B
            0xFF00 <= code <= 0xFFEF or  # 半角及全角形式
            0x3000 <= code <= 0x303F or  # 中日韩符号和标点
            char in '，。、；：？！「」『』【】（）〈〉《》〔〕—…'):
            valid_chars += 1

    # 如果有效字符比例低于70%，认为是乱码
    if valid_chars / total_chars < 0.7:
        return True

    # 检查特定的乱码模式
    # 模式1: 连续的西里尔/希腊字母
    garbled_pattern1 = re.compile(r'[Ѐ-ӿԀ-ԯḀ-ỿⰀ-ⱟꙀ-ꚟͰ-Ͽ̀-ͯ]{4,}')
    if garbled_pattern1.search(text):
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
        elif 'stcn' in domain:
            return '证券时报'
        elif 'aastocks' in domain:
            return 'AASTOCKS'
        elif 'yahoo' in domain:
            return 'Yahoo财经'
        elif 'jiemian' in domain:
            return '界面新闻'
        elif 'chaguwang' in domain:
            return '查股网'
        elif 'unifuncs' in domain:
            return 'U深搜'
        elif 'nxny' in domain:
            return '宁夏天利'
        elif 'gelonghui' in domain:
            return '格隆汇'
        elif 'dfcfw' in domain:
            return '东方财富'
        elif 'sse' in domain:
            return '上海证券交易所'
        elif 'sohu' in domain:
            return '搜狐证券'
        elif 'ifeng' in domain:
            return '凤凰网财经'
        elif 'baike.baidu' in domain:
            return '百度百科'
        elif 'news.cn' in domain:
            return '新华网'
        elif 'zhihu' in domain:
            return '知乎'
        elif 'investing' in domain:
            return '英为财情'
        elif '55188' in domain:
            return '理想论坛'
        elif 'junming' in domain:
            return '智研'
        elif 'iyanbao' in domain:
            return '研报网'
        elif 'q.stock' in domain:
            return '搜狐证券'
        else:
            return domain
    except:
        return url

def parse_stock_name(target_name):
    """解析股票名称和代码"""
    # 格式: "隆基绿能(601012)"
    match = re.match(r'(.+?)\((\d+)\)', target_name)
    if match:
        return match.group(1), match.group(2)
    return target_name, ''

def create_clean_title(url, stock_name):
    """根据URL和股票名称创建干净的标题"""
    site_name = get_site_name(url)
    return f"{stock_name} - {site_name}"

def analyze_and_fix():
    json_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据.json'

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=" * 80)
    print("分析乱码问题")
    print("=" * 80)

    total_fixed = 0

    # 遍历所有结果
    for result in data.get('results', []):
        target_name = result.get('target_name', '')
        stock_name, stock_code = parse_stock_name(target_name)
        print(f"\n股票: {target_name}")
        print("-" * 80)

        news_list = result.get('news_list', [])
        for idx, item in enumerate(news_list):
            title = item.get('title', '')
            content = item.get('content', '')

            title_garbled = is_garbled(title)
            content_garbled = is_garbled(content)

            if title_garbled or content_garbled:
                print(f"  序号 {idx+1}: 乱码!")
                if title_garbled:
                    print(f"    原标题: {repr(title[:80])}")
                    new_title = create_clean_title(item.get('url', ''), stock_name)
                    result['news_list'][idx]['title'] = new_title
                    print(f"    新标题: {new_title}")
                if content_garbled:
                    print(f"    原内容: {repr(content[:80])}")
                    site_name = get_site_name(item.get('url', ''))
                    new_content = f"来自{site_name}的{stock_name}相关资讯"
                    result['news_list'][idx]['content'] = new_content
                    print(f"    新内容: {new_content}")
                total_fixed += 1

    print(f"\n总计修复 {total_fixed} 个条目")

    # 保存
    backup_path = json_path + '.backup'
    import os
    os.rename(json_path, backup_path)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已备份原文件: {backup_path}")
    print(f"已保存修复后的文件: {json_path}")

if __name__ == '__main__':
    analyze_and_fix()
