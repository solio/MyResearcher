#!/usr/bin/env python3
"""
从已修复的JSON数据重新生成纪要文件
"""
import json
import os
from datetime import datetime

def regenerate_markdown_from_json(json_path):
    """从JSON重新生成Markdown纪要"""

    # 读取JSON数据
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    timestamp = data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    md = "# 个股价值投研纪要\n\n"
    md += f"生成时间: {timestamp}\n\n"
    md += "---\n\n"

    for result in data.get('results', []):
        target_name = result.get('target_name', '')
        target_type = result.get('target_type', '')

        if target_type == "stock":
            md += f"## 📈 个股研究: {target_name}\n\n"
        else:
            md += f"## 🏭 行业研究: {target_name}\n\n"

        # 无更新情况
        if result.get('is_no_update'):
            md += "⚠️ 今日无重大更新，内容与上期相似。\n\n"
            md += "---\n\n"
            continue

        # 失败情况
        if result.get('failure_reason'):
            md += f"❌ 研究失败: {result.get('failure_reason')}\n\n"
            md += "---\n\n"
            continue

        # 情绪指标
        if target_type == "stock":
            emotion_score = result.get('emotion_score', 0.0)
            emotion_label = "中性"
            if emotion_score > 0.6:
                emotion_label = "😃 极度贪婪"
            elif emotion_score > 0.2:
                emotion_label = "🙂 贪婪"
            elif emotion_score < -0.6:
                emotion_label = "😱 极度恐惧"
            elif emotion_score < -0.2:
                emotion_label = "😟 恐惧"

            md += "### 情绪指标\n\n"
            md += f"- 综合情绪值: **{emotion_score:.3f}**\n"
            md += f"- 情绪标签: {emotion_label}\n\n"

            # 参数调整建议
            param_suggestion = result.get('param_suggestion', '')
            if param_suggestion:
                md += f"### 参数调整建议\n\n"
                md += param_suggestion + "\n\n"

        # 新闻列表
        md += "### 新闻列表\n\n"
        news_list = result.get('news_list', [])
        if news_list:
            for i, news in enumerate(news_list, 1):
                if news.get("is_warning"):
                    md += f"⚠️ **{news.get('title', '')}**\n\n"
                    md += f"   {news.get('content', '')}\n\n"
                else:
                    source_tag = "📰 新闻" if news.get("source_type") == "news" else "💬 论坛"
                    title = news.get('title', '')
                    url = news.get('url', '')
                    if url:
                        md += f"{i}. {source_tag} [{title}]({url})\n"
                    else:
                        md += f"{i}. {source_tag} {title}\n"
                    content = news.get('content', '')
                    if content:
                        md += f"   - {content}\n\n"
        else:
            md += "暂无新闻\n\n"

        # 分析摘要
        analysis = result.get('analysis', '')
        if analysis:
            md += "### 分析摘要\n\n"
            if analysis == "分析失败":
                md += "❌ 分析失败\n\n"
            else:
                md += analysis + "\n\n"

        md += "---\n\n"

    return md

def main():
    json_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据.json'
    md_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-纪要.md'

    print("正在重新生成纪要文件...")
    md_content = regenerate_markdown_from_json(json_path)

    # 备份原纪要
    backup_md = md_path + '.backup'
    if os.path.exists(md_path):
        os.rename(md_path, backup_md)
        print(f"已备份原纪要: {backup_md}")

    # 保存新纪要
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"已重新生成纪要: {md_path}")
    print("\n完成！")

if __name__ == '__main__':
    main()
