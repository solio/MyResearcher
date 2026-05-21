#!/usr/bin/env python3
"""调用deepseek-v4-pro分析情绪评分模型"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from config import get_config
from llm import LLMClient

def load_sample_data():
    """加载样本数据"""
    data_files = [
        "/Users/mac/Documents/trae_projects/prompt-engineering/output/20260508/20260508_154920-数据.json",
        "/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_101500-数据.json",
    ]

    all_data = []
    for path in data_files:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                all_data.append(data)
                print(f"加载: {path}")

    return all_data

def main():
    """主函数"""
    config = get_config()

    # 临时切换到deepseek-v4-pro
    original_model = config.DEEPSEEK_MODEL
    config.DEEPSEEK_MODEL = "deepseek-v4-pro"

    llm = LLMClient(config)

    # 加载样本数据
    sample_data = load_sample_data()

    # 准备prompt
    prompt = '''
你是一位金融量化分析专家，专注于市场情绪分析模型设计。

# 当前问题
用户对现有的情绪评分模型不满意，说：
- "我之前的算法是弄一个情绪线性回归的模型，但是我的梯度（分数计算）可能跨度太大了，做出来的评分效果不好"
- "股吧和雪球部分的数据我是基本满意的，但是有好几条数据我点进去我都发现文不对题"
- "新闻部分deepseek有没有优化意见，无效的财经seo的个股页面太多了，根本筛选不完，一直都有垃圾数据"

# 当前算法
当前情绪评分算法：
- 情绪值 = Σ( (市值/100亿 * 点赞数 + 市值/100亿 * 回帖数) * 类型权重 )
- 类型权重：雪球=0.5，股吧热度=0.2，股吧爆值=0.2，股吧普值=0.1
- 热度阈值计算：每5天平均，变化超过50%则调整
- 热度阈值：回帖数 > (市值/100亿 * 2), 点赞数 > (市值/100亿 * 2)

# 存在的问题
1. 情绪值计算跨度过大，市值高的股票天然占优势
2. 很多帖子文不对题，需要更好的内容过滤
3. 新闻源SEO垃圾太多
4. 点赞数/回帖数都是0的情况下，情绪值恒为0

# 样本数据
'''

    # 添加样本数据
    for i, data in enumerate(sample_data):
        prompt += f"\n## 样本数据 {i+1}\n"
        for result in data.get('results', [])[:2]:
            prompt += f"\n### {result.get('target_name')}\n"
            prompt += f"- 新闻数: {len(result.get('news_list', []))}\n"
            if result.get('news_list'):
                # 展示一些帖子
                prompt += "帖子示例:\n"
                for n in result.get('news_list', [])[:3]:
                    prompt += f"  - {n.get('title', '')} (reply={n.get('reply_count',0)}, like={n.get('like_count',0)}, source={n.get('source','')})\n"

    prompt += '''
# 任务
请设计一个**改进后的情绪评分模型**，要求：

1. 解决"跨度太大"的问题，做归一化处理
2. 更好处理点赞/回帖都是0的情况
3. 融入市值因素但不要让它主导
4. 需要包含：情绪极性（正面/负面/中性）的加权计算
5. 对帖子质量进行打分（过滤文不对题）
6. 详细的公式说明和参数建议

请以JSON格式返回你的设计，包含以下字段：
{
  "analysis": "对当前问题的分析",
  "model_name": "模型名称",
  "formula": "详细的数学公式，用LaTeX格式",
  "parameters": {
    "param1": "说明",
    "param2": "说明"
  },
  "steps": [
    "步骤1: ...",
    "步骤2: ..."
  ],
  "code_example": "Python伪代码实现",
  "filter_suggestions": {
    "content": "内容过滤建议",
    "url": "URL过滤建议"
  },
  "advantages": [
    "优点1",
    "优点2"
  ]
}

请只返回JSON，不要其他文字。
'''

    print("正在调用deepseek-v4-pro分析...")
    response = llm.complete(prompt)

    print("\n=== 模型分析结果 ===\n")
    print(response)

    # 保存结果
    with open("/tmp/emotion_model_analysis.json", "w", encoding="utf-8") as f:
        f.write(response)
    print(f"\n结果已保存到: /tmp/emotion_model_analysis.json")

    # 恢复原模型
    config.DEEPSEEK_MODEL = original_model

if __name__ == "__main__":
    main()
