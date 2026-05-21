#!/usr/bin/env python3
"""简单调用deepseek-v4-pro分析情绪模型"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-0a3f7ffc68eb4f84b9a906085d9842e3")
API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")


def call_model(prompt, model="deepseek-v4-pro"):
    """调用DeepSeek模型"""
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 3000
    }
    print(f"正在调用 {model}...")
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def main():
    """主函数"""
    prompt = """你是一位金融量化分析专家，专注于市场情绪分析模型设计。

【当前问题】
用户对现有的情绪评分模型不满意，说：
- "我之前的算法是弄一个情绪线性回归的模型，但是我的梯度（分数计算）可能跨度太大了，做出来的评分效果不好"
- "股吧和雪球部分的数据我是基本满意的，但是有好几条数据我点进去我都发现文不对题"
- "新闻部分deepseek有没有优化意见，无效的财经seo的个股页面太多了，根本筛选不完，一直都有垃圾数据"

【当前算法】
当前情绪评分算法：
- 情绪值 = Σ( (市值/100亿 * 点赞数 + 市值/100亿 * 回帖数) * 类型权重 )
- 类型权重：雪球=0.5，股吧热度=0.2，股吧爆值=0.2，股吧普值=0.1
- 热度阈值计算：每5天平均，变化超过50%则调整
- 热度阈值：回帖数 > (市值/100亿 * 2), 点赞数 > (市值/100亿 * 2)

【存在的问题】
1. 情绪值计算跨度过大，市值高的股票天然占优势
2. 很多帖子文不对题，需要更好的内容过滤
3. 新闻源SEO垃圾太多
4. 点赞数/回帖数都是0的情况下，情绪值恒为0

请设计一个**改进后的情绪评分模型**。请用JSON格式返回，包含以下字段：
{
  "analysis": "对当前问题的分析（100字以内）",
  "model_name": "模型名称",
  "formula": "详细的数学公式，用纯文本描述（不要用LaTeX）",
  "parameters": {
    "param1": "说明",
    "param2": "说明"
  },
  "steps": [
    "步骤1: ...",
    "步骤2: ..."
  ],
  "code_example": "Python伪代码实现（只写关键计算部分）",
  "filter_suggestions": {
    "content": "内容过滤建议",
    "url": "URL过滤建议"
  },
  "advantages": [
    "优点1",
    "优点2",
    "优点3"
  ]
}

请只返回JSON，不要其他文字。"""

    result = call_model(prompt, "deepseek-v4-pro")
    print("\n" + "="*80 + "\n")
    print(result)
    print("\n" + "="*80 + "\n")

    # 保存
    with open("/tmp/emotion_model_analysis.json", "w", encoding="utf-8") as f:
        f.write(result)
    print("已保存到 /tmp/emotion_model_analysis.json")


if __name__ == "__main__":
    main()
