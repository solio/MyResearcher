#!/usr/bin/env python3
"""
量化指标抓取模块
从东方财富等固定网站抓取个股短线交易指标
"""
import requests
import time
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from logger import get_logger

logger = get_logger()

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("BeautifulSoup未安装，将使用简化解析")


class TradingSignal(Enum):
    """交易信号"""
    STRONG_SELL = "强烈卖出"
    SELL = "卖出"
    NEUTRAL = "中性"
    BUY = "买入"
    STRONG_BUY = "强烈买入"


@dataclass
class TradingMetrics:
    """短线交易指标"""
    # 基础信息
    stock_code: str
    stock_name: str
    fetch_time: str

    # 价格指标
    current_price: Optional[float] = None
    price_change: Optional[float] = None  # 涨跌额
    price_change_pct: Optional[float] = None  # 涨跌幅
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    open_price: Optional[float] = None
    prev_close: Optional[float] = None

    # 成交量指标
    volume: Optional[int] = None  # 成交量（手）
    turnover_rate: Optional[float] = None  # 换手率
    volume_ratio: Optional[float] = None  # 量比

    # 资金流向
    main_net_inflow: Optional[float] = None  # 主力净流入（万元）
    super_large_net_inflow: Optional[float] = None  # 超大单净流入
    large_net_inflow: Optional[float] = None  # 大单净流入
    medium_net_inflow: Optional[float] = None  # 中单净流入
    small_net_inflow: Optional[float] = None  # 小单净流入

    # 市场情绪指标
    margin_trading_balance: Optional[float] = None  # 融资余额
    short_selling_balance: Optional[float] = None  # 融券余额
    long_short_ratio: Optional[float] = None  # 多空比

    # 盘口指标
    bid_ask_ratio: Optional[float] = None  # 委比
    inner_market: Optional[int] = None  # 内盘
    outer_market: Optional[int] = None  # 外盘

    # 技术指标
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None
    rsi_6: Optional[float] = None
    rsi_12: Optional[float] = None
    rsi_24: Optional[float] = None

    # 计算出的交易信号
    trading_signal: Optional[str] = None
    trading_score: Optional[float] = None  # -3.0 ~ +3.0，对应情绪分级


@dataclass
class NewsMetrics:
    """新闻情绪指标"""
    total_news: int
    positive_news: int
    negative_news: int
    neutral_news: int
    sentiment_score: float  # -3.0 ~ +3.0


@dataclass
class ForumMetrics:
    """论坛情绪指标"""
    total_posts: int
    hot_posts: int
    explosive_posts: int
    bullish_posts: int
    bearish_posts: int
    neutral_posts: int
    total_interactions: int  # 总互动（阅读+回复）
    sentiment_score: float  # -3.0 ~ +3.0


@dataclass
class EmotionScoreV3:
    """V3 多维度情绪评分"""
    stock_code: str
    stock_name: str
    market_cap: float
    analysis_time: str

    # 各维度指标
    news_metrics: Optional[NewsMetrics] = None
    forum_metrics: Optional[ForumMetrics] = None
    trading_metrics: Optional[TradingMetrics] = None

    # 加权综合评分
    news_score: float = 0.0
    forum_score: float = 0.0
    trading_score: float = 0.0
    final_score: float = 0.0

    rating_level: str = "中性"
    rating_emoji: str = "😐"
    confidence: float = 0.8


class QuantScraper:
    """量化指标爬虫"""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_stock_quote(self, stock_code: str) -> Optional[TradingMetrics]:
        """
        获取个股行情数据
        stock_code格式：601012（沪市）或003000（深市）
        """
        metrics = TradingMetrics(
            stock_code=stock_code,
            stock_name="",
            fetch_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        try:
            # 确定市场代码：1=沪市，0=深市
            market = 1 if stock_code.startswith('6') else 0
            url = f"http://push2.eastmoney.com/api/qt/stock/get?secid={market}.{stock_code}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f57,f58,f60,f107,f116,f117,f127,f162,f163,f164,f165,f166,f167,f168,f169,f170,f171"

            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"获取行情数据失败: {response.status_code}")
                return None

            data = response.json()
            if data.get('rc') != 0:
                logger.warning(f"行情数据返回错误: {data.get('rc')}")
                return None

            q = data.get('data', {})

            # 基础信息
            metrics.stock_name = q.get('f58', '')
            metrics.current_price = self._parse_price_value(q.get('f43'))  # 最新价
            metrics.prev_close = self._parse_price_value(q.get('f60'))  # 昨收
            metrics.open_price = self._parse_price_value(q.get('f46'))  # 今开
            metrics.high_price = self._parse_price_value(q.get('f44'))  # 最高
            metrics.low_price = self._parse_price_value(q.get('f45'))  # 最低
            metrics.price_change = self._parse_price_value(q.get('f169'))  # 涨跌额
            metrics.price_change_pct = self._parse_price_value(q.get('f170'))  # 涨跌幅

            # 成交量指标
            metrics.volume = q.get('f47')  # 成交量（手）
            metrics.turnover_rate = self._parse_price_value(q.get('f168'))  # 换手率
            metrics.volume_ratio = self._parse_price_value(q.get('f163'))  # 量比

            # 盘口指标
            metrics.inner_market = q.get('f48')  # 内盘
            metrics.outer_market = q.get('f49')  # 外盘
            if (metrics.inner_market is not None and metrics.outer_market is not None
                and (metrics.inner_market + metrics.outer_market) > 0):
                metrics.bid_ask_ratio = (metrics.outer_market - metrics.inner_market) / (metrics.inner_market + metrics.outer_market)

            logger.info(f"获取{metrics.stock_name}({stock_code})行情数据成功")

            return metrics

        except Exception as e:
            logger.warning(f"获取行情数据异常: {e}")
            return None

    def fetch_capital_flow(self, stock_code: str, metrics: TradingMetrics) -> TradingMetrics:
        """获取资金流向数据"""
        try:
            market = 1 if stock_code.startswith('6') else 0
            url = f"http://push2.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=1&klt=1&secid={market}.{stock_code}&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"

            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return metrics

            data = response.json()
            if data.get('rc') != 0:
                return metrics

            klines = data.get('data', {}).get('klines', [])
            if not klines:
                return metrics

            # 解析最新一日数据
            latest = klines[-1]
            parts = latest.split(',')

            if len(parts) >= 13:
                metrics.main_net_inflow = self._parse_float(parts[1])  # 主力净流入
                metrics.super_large_net_inflow = self._parse_float(parts[5])  # 超大单
                metrics.large_net_inflow = self._parse_float(parts[3])  # 大单
                metrics.medium_net_inflow = self._parse_float(parts[7])  # 中单
                metrics.small_net_inflow = self._parse_float(parts[9])  # 小单

            logger.debug(f"获取{stock_code}资金流向数据成功")

        except Exception as e:
            logger.debug(f"获取资金流向数据异常: {e}")

        return metrics

    def fetch_margin_trading(self, stock_code: str, metrics: TradingMetrics) -> TradingMetrics:
        """获取融资融券数据"""
        try:
            # 这个API可能需要不同的参数，简化处理
            market = 1 if stock_code.startswith('6') else 0
            url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPTA_OP_FINANCE&columns=ALL&filter=(TRADE_DATE%3E%3D%272026-05-01%27)(SECURITY_CODE%3D%22{stock_code}%22)&pageNumber=1&pageSize=5"

            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return metrics

            data = response.json()
            if data.get('code') != 0:
                return metrics

            result = data.get('result', {})
            items = result.get('data', [])
            if items:
                latest = items[0]
                metrics.margin_trading_balance = latest.get('RZYE')  # 融资余额
                metrics.short_selling_balance = latest.get('RQYE')  # 融券余额

                if metrics.margin_trading_balance and metrics.short_selling_balance:
                    if metrics.short_selling_balance > 0:
                        metrics.long_short_ratio = metrics.margin_trading_balance / metrics.short_selling_balance
                    else:
                        metrics.long_short_ratio = 10.0

            logger.debug(f"获取{stock_code}融资融券数据成功")

        except Exception as e:
            logger.debug(f"获取融资融券数据异常: {e}")

        return metrics

    def calculate_trading_score(self, metrics: TradingMetrics) -> TradingMetrics:
        """
        基于交易指标计算交易情绪分数 (-3.0 ~ +3.0)
        作为短线交易专家，综合各维度分析
        """
        score = 0.0
        factors = []

        # 1. 价格走势 (权重0.3)
        if metrics.price_change_pct is not None:
            # 涨跌幅映射到-1.5~+1.5
            price_score = max(-1.5, min(1.5, metrics.price_change_pct / 3.0))
            factors.append(("price", price_score, 0.3))

        # 2. 量比 (权重0.15)
        if metrics.volume_ratio is not None:
            if 0.8 <= metrics.volume_ratio <= 1.5:
                volume_score = 0  # 正常水平
            elif metrics.volume_ratio > 2:
                volume_score = min(1.0, (metrics.volume_ratio - 1) / 2)  # 放量
            elif metrics.volume_ratio < 0.5:
                volume_score = max(-1.0, (metrics.volume_ratio - 0.5) / 0.5)  # 缩量
            else:
                volume_score = 0
            factors.append(("volume", volume_score, 0.15))

        # 3. 换手率 (权重0.1)
        if metrics.turnover_rate is not None:
            if 3 <= metrics.turnover_rate <= 10:
                turnover_score = 0.5  # 健康水平
            elif metrics.turnover_rate > 15:
                turnover_score = -0.5  # 过高，可能出货
            elif metrics.turnover_rate < 1:
                turnover_score = -0.3  # 过低，无关注
            else:
                turnover_score = 0
            factors.append(("turnover", turnover_score, 0.1))

        # 4. 资金流向 (权重0.3)
        if metrics.main_net_inflow is not None:
            if metrics.main_net_inflow > 1000:
                capital_score = 1.5  # 大幅流入
            elif metrics.main_net_inflow > 500:
                capital_score = 0.8  # 中等流入
            elif metrics.main_net_inflow > 0:
                capital_score = 0.3  # 小幅流入
            elif metrics.main_net_inflow > -500:
                capital_score = -0.3  # 小幅流出
            elif metrics.main_net_inflow > -1000:
                capital_score = -0.8  # 中等流出
            else:
                capital_score = -1.5  # 大幅流出
            factors.append(("capital", capital_score, 0.3))

        # 5. 内外盘比 (权重0.15)
        if metrics.bid_ask_ratio is not None:
            bid_ask_score = max(-1.0, min(1.0, metrics.bid_ask_ratio * 2))
            factors.append(("bid_ask", bid_ask_score, 0.15))

        # 计算加权总分
        total_weight = sum(w for _, _, w in factors)
        if total_weight > 0:
            score = sum(s * w for _, s, w in factors) / total_weight

        # 限制在-3.0 ~ +3.0
        metrics.trading_score = max(-3.0, min(3.0, score))

        # 确定交易信号
        if metrics.trading_score <= -2.0:
            metrics.trading_signal = TradingSignal.STRONG_SELL.value
        elif metrics.trading_score <= -1.0:
            metrics.trading_signal = TradingSignal.SELL.value
        elif metrics.trading_score <= -0.5:
            metrics.trading_signal = TradingSignal.NEUTRAL.value
        elif metrics.trading_score < 0.5:
            metrics.trading_signal = TradingSignal.NEUTRAL.value
        elif metrics.trading_score < 1.0:
            metrics.trading_signal = TradingSignal.BUY.value
        elif metrics.trading_score < 2.0:
            metrics.trading_signal = TradingSignal.BUY.value
        else:
            metrics.trading_signal = TradingSignal.STRONG_BUY.value

        logger.info(f"{metrics.stock_name}交易分数: {metrics.trading_score:.3f}, 信号: {metrics.trading_signal}")

        return metrics

    def _parse_price_value(self, value) -> Optional[float]:
        """解析价格数值，处理可能的单位格式"""
        if value is None:
            return None
        try:
            # 如果是整数，可能需要除以100或1000来得到正确的价格
            if isinstance(value, int) and value > 10000:
                # 东方财富API价格通常是除以100的格式
                return value / 100.0
            return float(value)
        except (ValueError, TypeError):
            return None

    def scrape(self, stock_code: str) -> Optional[TradingMetrics]:
        """完整抓取所有量化指标"""
        # 1. 获取基本行情
        metrics = self.fetch_stock_quote(stock_code)
        if not metrics:
            return None

        # 2. 获取资金流向
        metrics = self.fetch_capital_flow(stock_code, metrics)

        # 3. 获取融资融券
        metrics = self.fetch_margin_trading(stock_code, metrics)

        # 4. 计算交易分数
        metrics = self.calculate_trading_score(metrics)

        return metrics

    def _parse_float(self, s: str) -> Optional[float]:
        """解析浮点数"""
        try:
            return float(s)
        except:
            return None


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


def calculate_combined_emotion(
    news_score: float,
    forum_score: float,
    trading_score: float,
    news_weight: float = 0.2,
    forum_weight: float = 0.5,
    trading_weight: float = 0.3
) -> Tuple[float, str, str]:
    """
    计算多维度加权综合情绪评分
    默认权重：新闻0.2、论坛0.5、交易0.3
    """
    # 计算加权平均
    final_score = (news_score * news_weight +
                   forum_score * forum_weight +
                   trading_score * trading_weight)

    # 限制范围
    final_score = max(-3.0, min(3.0, final_score))

    # 获取评级
    rating_level, rating_emoji = get_rating_for_score(final_score)

    return final_score, rating_level, rating_emoji


if __name__ == "__main__":
    scraper = QuantScraper()
    metrics = scraper.scrape("601012")
    if metrics:
        print(json.dumps(asdict(metrics), ensure_ascii=False, indent=2))
