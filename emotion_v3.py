#!/usr/bin/env python3
"""
V3 多维度情绪评分模块
- 新闻情绪 (0.2)
- 论坛情绪 (0.5)
- 交易情绪 (0.3)
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
from emotion_v2 import EmotionScoreV2, get_rating_for_score
from quant_scraper import (
    QuantScraper, TradingMetrics, NewsMetrics, ForumMetrics,
    EmotionScoreV3, calculate_combined_emotion
)

logger = get_logger()


def analyze_news_sentiment_with_llm(
    posts: List[Dict],
    stock_name: str,
    market_cap: float,
    llm_provider
) -> Tuple[NewsMetrics, float]:
    """
    用LLM分析新闻情绪
    返回：NewsMetrics对象, 新闻情绪分数 (-3.0 ~ +3.0)
    """
    if not posts:
        return NewsMetrics(0, 0, 0, 0, 0.0), 0.0

    # 筛选新闻类型帖子
    news_posts = [p for p in posts if p.get('source_type') == 'news']

    if not news_posts:
        return NewsMetrics(0, 0, 0, 0, 0.0), 0.0

    # 构建提示词，用LLM分析
    try:
        from emotion_v2 import build_emotion_prompt, parse_llm_response
        prompt = build_emotion_prompt(news_posts[:25], stock_name, market_cap)

        # 修改系统提示词，明确是分析新闻
        llm_result = llm_provider.chat([{"role": "user", "content": prompt}],
                                      temperature=0.4, max_tokens=1500)

        if llm_result:
            parsed = parse_llm_response(llm_result)
            if parsed:
                score = parsed.get('overall_sentiment_score', 0.0)
                logger.info(f"新闻LLM情绪分数: {score:.3f}")

                # 同时也统计一下关键词做参考
                positive_count, negative_count, neutral_count = _count_keywords(news_posts, 'news')
                return NewsMetrics(len(news_posts), positive_count, negative_count, neutral_count, score), score

    except Exception as e:
        logger.debug(f"新闻LLM情绪分析异常: {e}")

    # 如果LLM失败，返回关键词分析
    return analyze_news_sentiment(posts)


def analyze_forum_sentiment_with_llm(
    posts: List[Dict],
    stock_name: str,
    market_cap: float,
    llm_provider
) -> Tuple[ForumMetrics, float]:
    """
    用LLM分析论坛情绪
    返回：ForumMetrics对象, 论坛情绪分数 (-3.0 ~ +3.0)
    """
    if not posts:
        return ForumMetrics(0, 0, 0, 0, 0, 0, 0, 0.0), 0.0

    # 筛选论坛类型帖子
    forum_posts = [p for p in posts if p.get('source_type') == 'forum']

    if not forum_posts:
        return ForumMetrics(0, 0, 0, 0, 0, 0, 0, 0.0), 0.0

    # 分类帖子热度
    hot_count = 0
    explosive_count = 0
    total_interactions = 0

    for post in forum_posts:
        read_count = post.get('read_count', 0)
        reply_count = post.get('reply_count', 0)
        total_interactions += read_count + reply_count

        if read_count > 10000 or reply_count > 50:
            explosive_count += 1
        elif read_count > 5000 or reply_count > 20:
            hot_count += 1

    # 主要用LLM分析
    try:
        from emotion_v2 import build_emotion_prompt, parse_llm_response
        prompt = build_emotion_prompt(forum_posts[:25], stock_name, market_cap)
        llm_result = llm_provider.chat([{"role": "user", "content": prompt}],
                                      temperature=0.4, max_tokens=1500)

        if llm_result:
            parsed = parse_llm_response(llm_result)
            if parsed:
                score = parsed.get('overall_sentiment_score', 0.0)
                logger.info(f"论坛LLM情绪分数: {score:.3f}")

                # 同时也统计一下关键词做参考
                bullish_count, bearish_count, neutral_count = _count_keywords(forum_posts, 'forum')
                return ForumMetrics(
                    len(forum_posts), hot_count, explosive_count,
                    bullish_count, bearish_count, neutral_count,
                    total_interactions, score
                ), score

    except Exception as e:
        logger.debug(f"论坛LLM情绪分析异常: {e}")

    # 如果LLM失败，返回关键词分析
    return analyze_forum_sentiment(posts)


def _count_keywords(posts: List[Dict], post_type: str) -> Tuple[int, int, int]:
    """用关键词统计情绪（辅助方法）"""
    positive_count = 0
    negative_count = 0
    neutral_count = 0

    if post_type == 'news':
        positive_keywords = ['涨', '利好', '增长', '盈利', '突破', '新高', '增持', '回购', '中标', '签约']
        negative_keywords = ['跌', '利空', '亏损', '下降', '风险', '警示', '立案', '调查', '处罚', '减持']
    else:
        positive_keywords = ['涨', '买入', '看多', '抄底', '底部', '反弹', '牛市', '利好',
                           '涨停', '持有', '加仓', '看好', '起飞', '突破', '新高']
        negative_keywords = ['跌', '卖出', '看空', '割肉', '顶部', '崩盘', '熊市', '利空',
                           '跌停', '清仓', '减仓', '看衰', '暴跌', '破位', '新低']

    for post in posts:
        title = post.get('title', '')
        content = post.get('content', '')
        text = f"{title} {content}"

        pos_count = sum(1 for k in positive_keywords if k in text)
        neg_count = sum(1 for k in negative_keywords if k in text)

        if pos_count > neg_count:
            positive_count += 1
        elif neg_count > pos_count:
            negative_count += 1
        else:
            neutral_count += 1

    return positive_count, negative_count, neutral_count


def analyze_news_sentiment(posts: List[Dict]) -> Tuple[NewsMetrics, float]:
    """
    关键词分析新闻情绪（备用方案）
    返回：NewsMetrics对象, 新闻情绪分数 (-3.0 ~ +3.0)
    """
    if not posts:
        return NewsMetrics(0, 0, 0, 0, 0.0), 0.0

    # 筛选新闻类型帖子
    news_posts = [p for p in posts if p.get('source_type') == 'news']

    if not news_posts:
        return NewsMetrics(0, 0, 0, 0, 0.0), 0.0

    positive_count, negative_count, neutral_count = _count_keywords(news_posts, 'news')

    # 计算情绪分数
    total = len(news_posts)
    if total == 0:
        sentiment_score = 0.0
    else:
        sentiment_score = ((positive_count - negative_count) / total) * 3.0
        sentiment_score = max(-3.0, min(3.0, sentiment_score))

    metrics = NewsMetrics(
        total_news=total,
        positive_news=positive_count,
        negative_news=negative_count,
        neutral_news=neutral_count,
        sentiment_score=sentiment_score
    )

    logger.info(f"新闻情绪分析: {positive_count}正/{negative_count}负/{neutral_count}中, 分数: {sentiment_score:.3f}")

    return metrics, sentiment_score


def analyze_forum_sentiment(posts: List[Dict]) -> Tuple[ForumMetrics, float]:
    """
    关键词分析论坛情绪（备用方案）
    返回：ForumMetrics对象, 论坛情绪分数 (-3.0 ~ +3.0)
    """
    if not posts:
        return ForumMetrics(0, 0, 0, 0, 0, 0, 0, 0.0), 0.0

    # 筛选论坛类型帖子
    forum_posts = [p for p in posts if p.get('source_type') == 'forum']

    if not forum_posts:
        return ForumMetrics(0, 0, 0, 0, 0, 0, 0, 0.0), 0.0

    # 分类帖子热度
    hot_count = 0
    explosive_count = 0
    total_interactions = 0

    for post in forum_posts:
        read_count = post.get('read_count', 0)
        reply_count = post.get('reply_count', 0)
        total_interactions += read_count + reply_count

        if read_count > 10000 or reply_count > 50:
            explosive_count += 1
        elif read_count > 5000 or reply_count > 20:
            hot_count += 1

    bullish_count, bearish_count, neutral_count = _count_keywords(forum_posts, 'forum')

    # 计算情绪分数
    total = len(forum_posts)
    if total == 0:
        sentiment_score = 0.0
    else:
        sentiment_score = ((bullish_count - bearish_count) / total) * 3.0
        sentiment_score = max(-3.0, min(3.0, sentiment_score))

    metrics = ForumMetrics(
        total_posts=total,
        hot_posts=hot_count,
        explosive_posts=explosive_count,
        bullish_posts=bullish_count,
        bearish_posts=bearish_count,
        neutral_posts=neutral_count,
        total_interactions=total_interactions,
        sentiment_score=sentiment_score
    )

    logger.info(f"论坛情绪分析: {bullish_count}多/{bearish_count}空/{neutral_count}中, 分数: {sentiment_score:.3f}")

    return metrics, sentiment_score


def analyze_trading_sentiment(stock_code: str) -> Tuple[Optional[TradingMetrics], float]:
    """
    分析交易情绪
    返回：TradingMetrics对象, 交易情绪分数 (-3.0 ~ +3.0)
    """
    try:
        scraper = QuantScraper()
        metrics = scraper.scrape(stock_code)

        if metrics and metrics.trading_score is not None:
            logger.info(f"交易情绪分数: {metrics.trading_score:.3f}")
            return metrics, metrics.trading_score

        return None, 0.0

    except Exception as e:
        logger.warning(f"交易情绪分析异常: {e}")
        return None, 0.0


def analyze_emotion_v3(
    posts: List[Dict],
    stock_name: str,
    stock_code: str,
    market_cap: float,
    llm_provider,
    news_weight: float = 0.2,
    forum_weight: float = 0.5,
    trading_weight: float = 0.3
) -> Optional[EmotionScoreV3]:
    """
    V3 多维度情绪分析主函数
    主要依赖LLM分析，关键词只是备用方案

    Args:
        posts: 帖子列表
        stock_name: 股票名称
        stock_code: 股票代码
        market_cap: 市值（亿）
        llm_provider: LLM提供者
        news_weight: 新闻权重（默认0.2）
        forum_weight: 论坛权重（默认0.5）
        trading_weight: 交易权重（默认0.3）

    Returns:
        EmotionScoreV3对象
    """
    from llm import StockAnalyzer

    if not posts:
        return None

    logger.info(f"开始V3多维度情绪分析: {stock_name}({stock_code})")

    # 1. 分析新闻情绪（先尝试LLM，失败用关键词）
    news_metrics, news_score = analyze_news_sentiment_with_llm(
        posts, stock_name, market_cap, llm_provider
    )

    # 2. 分析论坛情绪（先尝试LLM，失败用关键词）
    forum_metrics, forum_score = analyze_forum_sentiment_with_llm(
        posts, stock_name, market_cap, llm_provider
    )

    # 3. 分析交易情绪
    trading_metrics, trading_score = analyze_trading_sentiment(stock_code)

    # 4. 计算加权综合分数
    final_score, rating_level, rating_emoji = calculate_combined_emotion(
        news_score=news_score,
        forum_score=forum_score,
        trading_score=trading_score,
        news_weight=news_weight,
        forum_weight=forum_weight,
        trading_weight=trading_weight
    )

    # 5. 计算置信度
    confidence_factors = []
    if news_metrics.total_news >= 5:
        confidence_factors.append(0.9)
    elif news_metrics.total_news >= 2:
        confidence_factors.append(0.7)
    else:
        confidence_factors.append(0.5)

    if forum_metrics.total_posts >= 20:
        confidence_factors.append(0.95)
    elif forum_metrics.total_posts >= 10:
        confidence_factors.append(0.8)
    else:
        confidence_factors.append(0.6)

    if trading_metrics:
        confidence_factors.append(0.9)
    else:
        confidence_factors.append(0.5)

    confidence = sum(confidence_factors) / len(confidence_factors)

    # 构建结果对象
    result = EmotionScoreV3(
        stock_code=stock_code,
        stock_name=stock_name,
        market_cap=market_cap,
        analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        news_metrics=news_metrics,
        forum_metrics=forum_metrics,
        trading_metrics=trading_metrics,
        news_score=news_score,
        forum_score=forum_score,
        trading_score=trading_score,
        final_score=final_score,
        rating_level=rating_level,
        rating_emoji=rating_emoji,
        confidence=confidence
    )

    logger.info(f"V3情绪分析完成: "
                f"新闻={news_score:.3f}({news_weight}), "
                f"论坛={forum_score:.3f}({forum_weight}), "
                f"交易={trading_score:.3f}({trading_weight}), "
                f"综合={final_score:.3f}, "
                f"评级={rating_level}")

    return result


def emotion_score_v3_to_dict(score: EmotionScoreV3) -> Dict:
    """转换为字典"""
    data = asdict(score)
    # 处理嵌套对象
    if score.news_metrics:
        data['news_metrics'] = asdict(score.news_metrics)
    if score.forum_metrics:
        data['forum_metrics'] = asdict(score.forum_metrics)
    if score.trading_metrics:
        data['trading_metrics'] = asdict(score.trading_metrics)
    return data
