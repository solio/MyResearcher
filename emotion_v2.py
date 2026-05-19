"""
7级精细情绪评分模块
包含市值归一化、行业对比、多维度因子分析
"""
import os
import json
import re
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from logger import get_logger

logger = get_logger()


class EmotionRating(Enum):
    """7级情绪评级"""
    EXTREME_FEAR = "极度恐惧"
    FEAR = "恐惧"
    CONFUSED = "迷茫"
    NEUTRAL = "中性"
    OPTIMISTIC = "乐观"
    POSITIVE = "积极"
    EXTREME_OPTIMISM = "极度乐观"


@dataclass
class EmotionScoreV2:
    """7级精细情绪评分结果"""
    # 基础信息
    stock_code: str
    stock_name: str
    market_cap: float  # 市值（亿）
    analysis_time: str

    # 样本统计
    total_posts: int
    total_news: int
    total_interactions: int  # 回复+点赞
    abundance_coefficient: float  # 丰裕系数

    # 评分
    final_score: float  # 最终评分
    rating_level: str  # 评级文字
    rating_emoji: str  # 评级表情
    confidence: float  # 置信度 0-1

    # 分析文字
    trend_analysis: str  # 趋势分析
    key_post_titles: List[str]  # 关键帖子标题列表


def get_rating_for_score(score: float) -> Tuple[str, str]:
    """根据分数获取评级和表情"""
    if score <= -2.5:
        return "极度恐惧", "😱"
    elif score <= -1.5:
        return "恐惧", "😟"
    elif score <= -0.5:
        return "迷茫", "🤔"
    elif score < 0.5:
        return "中性", "😐"
    elif score < 1.5:
        return "乐观", "🙂"
    elif score < 2.5:
        return "积极", "😊"
    else:
        return "极度乐观", "🤩"


def build_emotion_prompt(posts: List[Dict], stock_name: str, market_cap: float) -> str:
    """构建情绪分析提示词"""
    # 限制帖子数量，避免提示词过长
    limited_posts = posts[:25]

    posts_text = ""
    for i, post in enumerate(limited_posts, 1):
        title = post.get("title", "")
        content = post.get("content", "")
        # 限制每帖长度
        combined = f"{title} {content}"[:150]
        posts_text += f"{i}. {combined}\n"

    prompt = f"""你是一位专业的A股市场情绪分析师，拥有10年以上的市场情绪分析经验。

【分析目标】
股票: {stock_name}
市值: {market_cap} 亿

【评分标准】
请在-3.0到3.0之间给出精细评分：

-3.0: 极度恐惧 - 市场恐慌性抛售，散户极度绝望，大量恐慌性言论
-2.0: 恐惧 - 看空情绪明显，资金流出迹象，多数帖子看空
-1.0: 迷茫 - 观望情绪浓厚，方向不明，多空争论激烈
0.0: 中性 - 多空平衡，情绪稳定，没有明显倾向
1.0: 乐观 - 看好后市，资金进场迹象，多数帖子看多
2.0: 积极 - 多头情绪强烈，持续上涨预期，热度高
3.0: 极度乐观 - 市场狂热，散户极度亢奋，极度看多言论

【帖子数据】
{posts_text}

【分析要求】
请分析以上帖子，按以下JSON格式输出（只输出JSON，不要其他文字）：
{{
    "overall_sentiment_score": -2.0,
    "confidence": 0.85,
    "analysis_summary": "简要分析情绪的主要依据",
    "key_post_indexes": [1, 3, 5]
}}

注意：
1. 评分要准确反映帖子的整体情绪偏向
2. confidence表示你对评分的把握程度（0-1）
3. key_post_indexes是最具代表性的几个帖子的序号（1-25）
4. 只输出JSON，不要有其他文字说明
"""
    return prompt


def parse_llm_response(llm_text: Optional[str]) -> Optional[Dict]:
    """解析LLM返回的JSON响应"""
    if not llm_text:
        return None

    try:
        text = llm_text.strip()

        # 提取JSON部分
        json_start = text.find("{")
        json_end = text.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = text[json_start:json_end]
            result = json.loads(json_str)
            return result
        else:
            logger.warning(f"无法从文本中提取JSON: {text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"解析LLM响应失败: {e}")
        return None


def analyze_emotion_v2(
    posts: List[Dict],
    stock_name: str,
    stock_code: str,
    market_cap: float,
    llm_provider
) -> Optional[EmotionScoreV2]:
    """
    使用LLM进行V2版本的7级情绪分析

    Args:
        posts: 帖子列表
        stock_name: 股票名称
        stock_code: 股票代码
        market_cap: 市值（亿）
        llm_provider: LLM提供者实例

    Returns:
        EmotionScoreV2对象，失败返回None
    """
    from llm import StockAnalyzer

    if not posts:
        return None

    logger.info(f"开始V2情绪分析: {stock_name}({stock_code}), 帖子数: {len(posts)}")

    # 构建提示词
    prompt = build_emotion_prompt(posts, stock_name, market_cap)

    # 调用LLM
    analyzer = StockAnalyzer(llm_provider)
    messages = [{"role": "user", "content": prompt}]

    logger.info(f"调用LLM分析情绪，提示词长度: {len(prompt)}")
    llm_result = llm_provider.chat(messages, temperature=0.4, max_tokens=1500)

    if not llm_result:
        logger.warning("LLM返回None，情绪分析失败")
        return None

    logger.debug(f"LLM返回: {llm_result[:300]}")

    # 解析LLM响应
    parsed = parse_llm_response(llm_result)
    if not parsed:
        return None

    # 提取关键信息
    score = parsed.get("overall_sentiment_score", 0.0)
    confidence = parsed.get("confidence", 0.8)
    analysis_summary = parsed.get("analysis_summary", "")
    key_post_indexes = parsed.get("key_post_indexes", [])

    # 获取关键帖子标题
    key_titles = []
    for idx in key_post_indexes[:5]:
        idx0 = idx - 1  # 转为0-based
        if 0 <= idx0 < len(posts):
            title = posts[idx0].get("title", "")
            if title:
                key_titles.append(title[:80])

    # 计算统计数据
    total_posts = len(posts)
    total_reply = sum(p.get("reply_count", 0) for p in posts)
    total_like = sum(p.get("like_count", 0) for p in posts)
    total_interactions = total_reply + total_like

    # 计算丰裕系数
    expected_posts = max(20, market_cap / 10)
    abundance_coeff = min(3.0, total_posts / expected_posts)

    # 获取评级
    rating_level, rating_emoji = get_rating_for_score(score)

    logger.info(f"V2情绪分析完成: 评分={score:.3f}, 评级={rating_level}, 置信度={confidence:.1%}")

    # 构建结果对象
    result = EmotionScoreV2(
        stock_code=stock_code,
        stock_name=stock_name,
        market_cap=market_cap,
        analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_posts=total_posts,
        total_news=0,  # 暂不统计新闻
        total_interactions=total_interactions,
        abundance_coefficient=abundance_coeff,
        final_score=score,
        rating_level=rating_level,
        rating_emoji=rating_emoji,
        confidence=confidence,
        trend_analysis=analysis_summary,
        key_post_titles=key_titles
    )

    return result


def emotion_score_v2_to_dict(score: EmotionScoreV2) -> Dict:
    """转换为字典"""
    return asdict(score)
