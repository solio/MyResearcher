#!/usr/bin/env python3
"""
重新分析 20260515 数据，使用新的 V2 7级情绪评分模型
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# 确保能导入模块
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from emotion_v2 import EmotionAnalyzerV2
from llm import DeepSeekLLMProvider, StockAnalyzer

def load_old_data():
    """加载20260515的原始数据"""
    data_path = Path(__file__).parent / "output" / "20260515" / "20260515_163040-数据.json"

    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return None

    print(f"✅ 加载数据文件: {data_path}")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def analyze_with_v2(news_list, stock_name, stock_code, market_cap, config):
    """使用V2模型分析单个股票"""
    print(f"\n" + "=" * 80)
    print(f"分析股票: {stock_name} ({stock_code})")
    print("=" * 80)

    # 分离帖子和新闻
    forum_posts = [p for p in news_list if p.get("source_type") == "forum"]
    news_items = [n for n in news_list if n.get("source_type") == "news"]

    print(f" - 论坛帖子: {len(forum_posts)} 条")
    print(f" - 新闻资讯: {len(news_items)} 条")
    print(f" - 市值: {market_cap} 亿")

    # 初始化LLM
    llm_provider = DeepSeekLLMProvider(
        api_key=config.DEEPSEEK_API_KEY,
        api_base=config.DEEPSEEK_API_BASE,
        model=config.DEEPSEEK_MODEL,
        timeout=180,
        max_retries=2
    )

    analyzer = StockAnalyzer(llm_provider)

    # 只取前15个帖子来测试
    test_posts = forum_posts[:15]

    print(f"\n使用前{len(test_posts)}个帖子进行分析...")

    # 构建一个简化的提示词
    posts_text = ""
    for i, post in enumerate(test_posts, 1):
        title = post.get("title", "")
        content = post.get("content", "")
        posts_text += f"{i}. {title}\n"

    prompt = f"""你是一位专业的A股市场情绪分析师。

请分析以下关于{stock_name}的帖子情绪：

{posts_text}

请按以下JSON格式输出（只输出JSON，不要其他文字）：
{{
    "overall_sentiment_score": -2.5,
    "confidence": 0.85,
    "analysis_summary": "简要分析"
}}

评分范围：-3.0（极度恐惧）到3.0（极度乐观）"""

    print(f"\n提示词长度: {len(prompt)}")

    messages = [{"role": "user", "content": prompt}]
    result = llm_provider.chat(messages, temperature=0.4, max_tokens=1000)

    print(f"\nLLM返回结果:")
    print("-" * 80)
    print(repr(result)[:500] if result else "None")
    print("-" * 80)

    if not result:
        print("\n❌ LLM返回None")
        return None

    # 解析
    try:
        result_clean = result.strip()
        json_start = result_clean.find("{")
        json_end = result_clean.rfind("}") + 1
        if json_start >=0 and json_end > json_start:
            json_str = result_clean[json_start:json_end]
            analysis_result = json.loads(json_str)
            print(f"\n✅ 解析成功: {analysis_result}")

            # 创建一个简化的结果对象
            from dataclasses import dataclass
            @dataclass
            class SimpleResult:
                final_score: float
                rating_level: str
                confidence: float
                stock_code: str
                stock_name: str
                total_posts: int
                trend_analysis: str

            # 评级映射
            score = analysis_result["overall_sentiment_score"]
            if score <= -2.5:
                rating = "极度恐惧"
                emoji = "😱"
            elif score <= -1.5:
                rating = "恐惧"
                emoji = "😟"
            elif score <= -0.5:
                rating = "迷茫"
                emoji = "🤔"
            elif score < 0.5:
                rating = "中性"
                emoji = "😐"
            elif score < 1.5:
                rating = "乐观"
                emoji = "🙂"
            elif score < 2.5:
                rating = "积极"
                emoji = "😊"
            else:
                rating = "极度乐观"
                emoji = "🤩"

            return SimpleResult(
                final_score=score,
                rating_level=f"{emoji} {rating}",
                confidence=analysis_result.get("confidence", 0.8),
                stock_code=stock_code,
                stock_name=stock_name,
                total_posts=len(forum_posts),
                trend_analysis=analysis_result.get("analysis_summary", "")
            )

    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()

    return None


def generate_report(results, data):
    """生成修正后的Markdown报告"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = f"# 个股价值投研纪要 (V2 模型修正版)\n\n"
    md += f"原始日期: 2026-05-15\n"
    md += f"重新分析时间: {timestamp}\n\n"
    md += "---\n\n"

    for i, stock_result in enumerate(results):
        original_result = data["results"][i]

        md += f"## 📈 个股研究: {stock_result.stock_name}({stock_result.stock_code})\n\n"

        # V2 精细情绪分析显示
        md += "### 情绪指标 V2 (7级精细评分)\n\n"
        md += f"- 最终评分: **{stock_result.final_score:.3f}**\n"
        md += f"- 情绪评级: {stock_result.rating_level}\n"
        md += f"- 置信度: {stock_result.confidence:.1%}\n\n"

        md += "#### 样本统计\n\n"
        md += f"- 帖子总数: {stock_result.total_posts}\n\n"

        if stock_result.trend_analysis:
            md += "#### 趋势分析\n\n"
            md += f"{stock_result.trend_analysis}\n\n"

        # 与原V1版本对比
        old_emotion = original_result.get("emotion_score", 0)

        md += "---\n\n"
        md += "#### 📊 V1 vs V2 对比\n\n"
        md += f"| 指标 | V1 版本 | V2 版本 |\n"
        md += f"|------|---------|--------|\n"
        md += f"| 情绪值 | {old_emotion:.3f} | {stock_result.final_score:.3f} |\n"
        md += f"| 评级体系 | 5级 | 7级 |\n\n"

        md += "---\n\n"

    return md


def main():
    print("=" * 80)
    print("重新分析 20260515 数据 - V2 7级情绪评分模型")
    print("=" * 80)

    # 加载配置
    config = get_config()
    print(f"使用模型: {config.DEEPSEEK_MODEL}")

    # 加载旧数据
    data = load_old_data()
    if not data:
        return 1

    # 分析每只股票（只分析第一只 - 隆基绿能）
    results = []
    for i, result_item in enumerate(data["results"]):
        if result_item.get("target_type") == "stock":
            # 提取股票信息
            target_name = result_item.get("target_name", "")
            if "(" in target_name and ")" in target_name:
                stock_name = target_name.split("(")[0]
                stock_code = target_name.split("(")[1].rstrip(")")
            else:
                stock_name = target_name
                stock_code = "000000"

            # 只分析隆基绿能
            if stock_code != "601012":
                continue

            news_list = result_item.get("news_list", [])

            # 分析
            v2_result = analyze_with_v2(news_list, stock_name, stock_code, 1000.0, config)
            if v2_result:
                results.append(v2_result)

    if not results:
        print("\n❌ 没有可分析的结果")
        return 1

    # 生成报告
    print(f"\n" + "=" * 80)
    print(f"生成修正后的纪要文件...")
    print("=" * 80)

    report = generate_report(results, data)

    # 保存报告
    output_dir = Path(__file__).parent / "output" / "20260515"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"{timestamp}-纪要-V2修正版.md"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 报告已保存: {report_path}")

    print(f"\n" + "=" * 80)
    print("全部完成！🎉")
    print("=" * 80)

    print(f"\n📂 输出文件:")
    print(f"   - {report_path.name}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
