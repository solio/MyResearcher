#!/usr/bin/env python3
"""
用过滤后的数据重新生成纪要（简化版）
"""
import sys
import os
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from llm import DeepSeekLLMProvider, StockAnalyzer
from logger import get_logger

logger = get_logger()

def generate_markdown(data):
    """生成Markdown报告"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = f"# 个股价值投研纪要\n\n"
    md += f"生成时间: {timestamp}\n\n"
    md += "---\n\n"

    for result in data['results']:
        target_name = result['target_name']
        news_list = result.get('news_list', [])

        if '隆基绿能' in target_name or '泛微网络' in target_name:
            md += f"## 📈 个股研究: {target_name}\n\n"
        else:
            md += f"## 🏭 行业研究: {target_name}\n\n"

        # 新闻列表
        md += "### 新闻列表\n\n"
        if news_list:
            for i, news in enumerate(news_list, 1):
                title = news.get('title', '')
                url = news.get('url', '')
                if url:
                    md += f"{i}. 📰 [{title}]({url})\n"
                else:
                    md += f"{i}. 📰 {title}\n"
                content = news.get('content', '')
                if content:
                    md += f"   - {content[:200]}...\n\n"
        else:
            md += "暂无新闻\n\n"

        md += "---\n\n"

    return md

def main():
    # 加载过滤后的数据
    filtered_data_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据-过滤后.json'

    with open(filtered_data_path, 'r', encoding='utf-8') as f:
        filtered_data = json.load(f)

    # 初始化配置和LLM
    config = Config()
    llm_provider = DeepSeekLLMProvider(
        api_key=config.DEEPSEEK_API_KEY,
        api_base=config.DEEPSEEK_API_BASE,
        model=config.DEEPSEEK_MODEL
    )
    analyzer = StockAnalyzer(llm_provider)

    # 先生成不带分析的markdown看看
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    simple_md = generate_markdown(filtered_data)

    simple_path = f'/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/{timestamp}-纪要-简单版.md'
    with open(simple_path, 'w', encoding='utf-8') as f:
        f.write(simple_md)

    print(f"简单版纪要已保存到: {simple_path}")
    print("\n正在为隆基绿能和泛微网络生成深度分析...")

    # 为这两个股票生成深度分析
    for result in filtered_data['results']:
        target_name = result['target_name']
        if '隆基绿能' in target_name or '泛微网络' in target_name:
            news_list = result.get('news_list', [])
            print(f"\n正在分析: {target_name} ({len(news_list)}条新闻)")
            analysis = analyzer.analyze_news_with_sentiment(news_list, target_name, "stock")
            if analysis:
                print(f"分析完成:\n{analysis[:500]}...")
                result['analysis'] = analysis

    # 重新生成带分析的markdown
    final_md = f"# 个股价值投研纪要\n\n"
    final_md += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    final_md += "---\n\n"

    for result in filtered_data['results']:
        target_name = result['target_name']
        news_list = result.get('news_list', [])

        if '隆基绿能' in target_name or '泛微网络' in target_name:
            final_md += f"## 📈 个股研究: {target_name}\n\n"
        else:
            final_md += f"## 🏭 行业研究: {target_name}\n\n"

        # 新闻列表
        final_md += "### 新闻列表\n\n"
        if news_list:
            for i, news in enumerate(news_list, 1):
                title = news.get('title', '')
                url = news.get('url', '')
                if url:
                    final_md += f"{i}. 📰 [{title}]({url})\n"
                else:
                    final_md += f"{i}. 📰 {title}\n"
                content = news.get('content', '')
                if content:
                    final_md += f"   - {content[:200]}...\n\n"
        else:
            final_md += "暂无新闻\n\n"

        # 分析摘要
        if 'analysis' in result:
            final_md += "### 分析摘要\n\n"
            final_md += result['analysis'] + "\n\n"

        final_md += "---\n\n"

    final_path = f'/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/{timestamp}-纪要-过滤后.md'
    with open(final_path, 'w', encoding='utf-8') as f:
        f.write(final_md)

    print(f"\n最终版纪要已保存到: {final_path}")
    print("\n完成！")

if __name__ == '__main__':
    main()
