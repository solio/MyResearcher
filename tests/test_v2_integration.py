#!/usr/bin/env python3
"""
测试V2情绪模型的完整集成
使用20260515的数据测试
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# 确保能导入模块
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from researcher import StockResearcher, ResearchResult


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


def test_v2_analysis():
    """测试V2情绪分析集成"""
    print("=" * 80)
    print("测试V2情绪模型集成")
    print("=" * 80)

    # 加载配置
    config = get_config()
    print(f"使用模型: {config.DEEPSEEK_MODEL}")

    # 加载旧数据
    data = load_old_data()
    if not data:
        return 1

    # 创建Researcher实例
    researcher = StockResearcher(config)

    # 只分析第一只股票（隆基绿能）
    for result_item in data["results"]:
        if result_item.get("target_type") == "stock":
            target_name = result_item.get("target_name", "")
            if "601012" not in target_name:
                continue

            print(f"\n分析股票: {target_name}")

            # 创建ResearchResult
            result = ResearchResult("stock", target_name)
            result.news_list = result_item.get("news_list", [])

            # 模拟research_stock中的V2分析部分
            result.use_v2_emotion = True

            # 分离帖子和新闻
            forum_posts = [p for p in result.news_list if p.get("source_type") == "forum"]
            print(f"  - 论坛帖子: {len(forum_posts)} 条")

            # 调用V2分析
            import emotion_v2
            stock = {
                "name": "隆基绿能",
                "code": "601012",
                "market_cap": 1000.0
            }
            result.emotion_v2 = emotion_v2.analyze_emotion_v2(
                posts=forum_posts,
                stock_name=stock["name"],
                stock_code=stock["code"],
                market_cap=stock.get("market_cap", 100.0),
                llm_provider=researcher.llm_provider
            )

            if result.emotion_v2:
                result.emotion_score = result.emotion_v2.final_score / 3.0
                print(f"\n✅ V2分析成功:")
                print(f"  评分: {result.emotion_v2.final_score:.3f}")
                print(f"  评级: {result.emotion_v2.rating_emoji} {result.emotion_v2.rating_level}")
                print(f"  置信度: {result.emotion_v2.confidence:.1%}")

                # 测试生成Markdown
                print(f"\n测试生成Markdown...")
                md = researcher._generate_markdown_report([result])
                print(md)

                # 保存测试结果
                test_output = Path(__file__).parent / "output" / "test_v2_integration.md"
                with open(test_output, 'w', encoding='utf-8') as f:
                    f.write(md)
                print(f"\n✅ 测试报告已保存: {test_output}")

                # 测试to_dict
                print(f"\n测试to_dict...")
                d = result.to_dict()
                print(f"  emotion_v2存在: {'emotion_v2' in d}")
                if 'emotion_v2' in d:
                    print(f"  final_score: {d['emotion_v2']['final_score']}")

            else:
                print("\n❌ V2分析失败")
                return 1

            break

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_v2_analysis())
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
