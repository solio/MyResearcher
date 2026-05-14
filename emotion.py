"""
情绪分析模块
负责情绪参数管理、帖子分类、情绪值计算
"""
import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from logger import get_logger

logger = get_logger()


class PostType(Enum):
    """帖子类型"""
    XUEQIU_HOT = "xueqiu_hot"  # 雪球热帖
    XUEQIU_EXPLOSIVE = "xueqiu_explosive"  # 雪球爆值帖
    GUBA_HOT = "guba_hot"  # 股吧热度帖
    GUBA_EXPLOSIVE = "guba_explosive"  # 股吧爆值帖
    GUBA_NORMAL = "guba_normal"  # 股吧普通帖
    NEWS = "news"  # 新闻（也参与情绪分析）


@dataclass
class PostData:
    """帖子数据"""
    title: str
    url: str
    content: str
    source_type: str  # "xueqiu" or "guba" or "news"
    reply_count: int = 0
    like_count: int = 0
    post_type: Optional[PostType] = None
    emotion_score: float = 0.0  # LLM 分析后的情绪分（-1到1）


@dataclass
class StockEmotionParams:
    """个股情绪参数"""
    stock_code: str
    stock_name: str
    market_cap: float  # 市值（亿）

    # 当前参数
    guba_hot_reply_threshold: float = 2.0
    guba_hot_like_threshold: float = 2.0

    # 历史数据（用于动态调整）
    history: List[Dict] = None  # 存储每天的热度统计

    def __post_init__(self):
        if self.history is None:
            self.history = []
        # 初始化阈值 = 市值/100亿 * 基数
        self._update_thresholds()

    def _update_thresholds(self):
        """根据市值更新阈值"""
        factor = self.market_cap / 100.0
        # 用当前因子，但不低于最小值1
        self.guba_hot_reply_threshold = max(1.0, factor * 2.0)
        self.guba_hot_like_threshold = max(1.0, factor * 2.0)

    def update_market_cap(self, new_market_cap: float):
        """更新市值"""
        self.market_cap = new_market_cap
        self._update_thresholds()

    def record_daily_stats(self, date_str: str, hot_post_count: int, explosive_post_count: int,
                           avg_reply_count: float, avg_like_count: float):
        """记录每日统计数据"""
        self.history.append({
            "date": date_str,
            "hot_post_count": hot_post_count,
            "explosive_post_count": explosive_post_count,
            "avg_reply_count": avg_reply_count,
            "avg_like_count": avg_like_count
        })

    def check_param_update(self, config) -> Optional[str]:
        """
        检查是否需要更新参数

        规则：
        - 平均每5天大于之前的50%，则向上更新
        - 平均每5天小于之前的50%，则向下更新

        Returns:
            更新建议，如无更新返回 None
        """
        if len(self.history) < config.EMOTION_PARAM_UPDATE_DAYS:
            return None

        recent = self.history[-config.EMOTION_PARAM_UPDATE_DAYS:]
        avg_reply = sum(d["avg_reply_count"] for d in recent) / len(recent)
        avg_like = sum(d["avg_like_count"] for d in recent) / len(recent)

        suggestion = []

        # 检查回复数
        if avg_reply > self.guba_hot_reply_threshold * (1 + config.EMOTION_PARAM_CHANGE_THRESHOLD):
            old = self.guba_hot_reply_threshold
            self.guba_hot_reply_threshold = min(100.0, self.guba_hot_reply_threshold * 1.5)
            suggestion.append(f"热度回复阈值: {old:.1f} -> {self.guba_hot_reply_threshold:.1f} (向上调整)")
        elif avg_reply < self.guba_hot_reply_threshold * (1 - config.EMOTION_PARAM_CHANGE_THRESHOLD):
            old = self.guba_hot_reply_threshold
            self.guba_hot_reply_threshold = max(config.EMOTION_PARAM_MIN, self.guba_hot_reply_threshold * 0.7)
            suggestion.append(f"热度回复阈值: {old:.1f} -> {self.guba_hot_reply_threshold:.1f} (向下调整)")

        # 检查点赞数
        if avg_like > self.guba_hot_like_threshold * (1 + config.EMOTION_PARAM_CHANGE_THRESHOLD):
            old = self.guba_hot_like_threshold
            self.guba_hot_like_threshold = min(100.0, self.guba_hot_like_threshold * 1.5)
            suggestion.append(f"热度点赞阈值: {old:.1f} -> {self.guba_hot_like_threshold:.1f} (向上调整)")
        elif avg_like < self.guba_hot_like_threshold * (1 - config.EMOTION_PARAM_CHANGE_THRESHOLD):
            old = self.guba_hot_like_threshold
            self.guba_hot_like_threshold = max(config.EMOTION_PARAM_MIN, self.guba_hot_like_threshold * 0.7)
            suggestion.append(f"热度点赞阈值: {old:.1f} -> {self.guba_hot_like_threshold:.1f} (向下调整)")

        if suggestion:
            return "\n".join(suggestion)
        return None


class EmotionAnalyzer:
    """情绪分析器"""

    def __init__(self, config):
        self.config = config
        self.stock_params: Dict[str, StockEmotionParams] = {}
        self._load_params()

    def _load_params(self):
        """加载历史参数"""
        if os.path.exists(self.config.EMOTION_DATA_FILE):
            try:
                with open(self.config.EMOTION_DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for stock_code, param_data in data.get("stocks", {}).items():
                        # 重构 StockEmotionParams
                        param = StockEmotionParams(
                            stock_code=param_data["stock_code"],
                            stock_name=param_data["stock_name"],
                            market_cap=param_data["market_cap"]
                        )
                        param.guba_hot_reply_threshold = param_data.get("guba_hot_reply_threshold", 2.0)
                        param.guba_hot_like_threshold = param_data.get("guba_hot_like_threshold", 2.0)
                        param.history = param_data.get("history", [])
                        self.stock_params[stock_code] = param
                logger.info(f"已加载情绪参数: {len(self.stock_params)} 只股票")
            except Exception as e:
                logger.warning(f"加载情绪参数失败: {e}")

    def save_params(self):
        """保存参数到文件"""
        os.makedirs(os.path.dirname(self.config.EMOTION_DATA_FILE), exist_ok=True)
        data = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": {
                code: {
                    "stock_code": p.stock_code,
                    "stock_name": p.stock_name,
                    "market_cap": p.market_cap,
                    "guba_hot_reply_threshold": p.guba_hot_reply_threshold,
                    "guba_hot_like_threshold": p.guba_hot_like_threshold,
                    "history": p.history
                }
                for code, p in self.stock_params.items()
            }
        }
        try:
            with open(self.config.EMOTION_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("情绪参数已保存")
        except Exception as e:
            logger.error(f"保存情绪参数失败: {e}")

    def get_or_create_params(self, stock: Dict) -> StockEmotionParams:
        """获取或创建个股参数"""
        code = stock["code"]
        if code not in self.stock_params:
            self.stock_params[code] = StockEmotionParams(
                stock_code=code,
                stock_name=stock["name"],
                market_cap=stock.get("market_cap", 100.0)
            )
        return self.stock_params[code]

    def _extract_number_from_text(self, text: str, keywords: List[str]) -> int:
        """
        从文本中提取数字（改进版本）
        尝试从标题、内容中提取类似"10评论"、"5点赞"等信息

        Args:
            text: 文本
            keywords: 关键词列表（如["评论", "回复", "点赞"]）

        Returns:
            提取到的数字，默认0
        """
        text = str(text)
        for keyword in keywords:
            # 模式: 数字+关键词，例如"10评论"、"5点赞"
            pattern = r'(\d+)\s*' + keyword
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))

            # 模式: 关键词+数字，例如"评论:10"、"点赞 5"
            pattern = keyword + r'[\s:：]*(\d+)'
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))

        # 尝试从URL中提取（某些网站URL包含数据）
        # 这里暂时不做复杂处理

        return 0

    def classify_posts(self, posts: List[Dict], stock: Dict) -> List[PostData]:
        """
        分类帖子

        Args:
            posts: 帖子列表（来自搜索结果）
            stock: 股票信息

        Returns:
            分类后的帖子列表
        """
        params = self.get_or_create_params(stock)
        results = []

        for post in posts:
            # 提取回帖和点赞数（改进提取逻辑）
            # 优先用帖子中已有的数据
            reply_count = post.get("reply_count", 0)
            like_count = post.get("like_count", 0)

            # 如果没有，尝试从文本中提取
            if reply_count == 0 and like_count == 0:
                full_text = post.get("title", "") + " " + post.get("content", "")
                reply_count = self._extract_number_from_text(full_text, ["评论", "回复", "评", "评论数"])
                like_count = self._extract_number_from_text(full_text, ["点赞", "喜欢", "赞", "👍", "点赞数"])

            # 特殊处理：如果还是0，给一个小的基础值（确保所有帖子都能参与计算）
            if reply_count == 0 and like_count == 0:
                # 股吧普通帖子给一个小基础值，确保能参与情绪计算
                reply_count = 1
                like_count = 1

            post_data = PostData(
                title=post.get("title", ""),
                url=post.get("url", ""),
                content=post.get("content", ""),
                source_type=post.get("source_type", "unknown"),
                reply_count=reply_count,
                like_count=like_count
            )

            # 分类
            if post_data.source_type == "forum":
                # 判断是雪球还是股吧（从URL/标题中推断）
                url = post_data.url.lower()
                title = post_data.title.lower()
                is_xueqiu = "xueqiu.com" in url or "雪球" in title
                is_guba = "guba.eastmoney.com" in url or "股吧" in title

                if is_xueqiu:
                    # 雪球帖子
                    if reply_count > self.config.EMOTION_XUEQIU_EXPLOSIVE_REPLY or \
                       like_count > self.config.EMOTION_XUEQIU_EXPLOSIVE_LIKE:
                        post_data.post_type = PostType.XUEQIU_EXPLOSIVE
                    else:
                        post_data.post_type = PostType.XUEQIU_HOT
                elif is_guba:
                    # 股吧帖子
                    if reply_count > self.config.EMOTION_GUBA_EXPLOSIVE_REPLY or \
                       like_count > self.config.EMOTION_GUBA_EXPLOSIVE_LIKE:
                        post_data.post_type = PostType.GUBA_EXPLOSIVE
                    elif reply_count > params.guba_hot_reply_threshold or \
                         like_count > params.guba_hot_like_threshold:
                        post_data.post_type = PostType.GUBA_HOT
                    else:
                        post_data.post_type = PostType.GUBA_NORMAL
                else:
                    # 未知来源，默认按股吧普通处理
                    post_data.post_type = PostType.GUBA_NORMAL
            else:
                # 新闻来源，也参与情绪分析
                post_data.post_type = PostType.NEWS

            results.append(post_data)

        return results

    def calculate_emotion_score(self, posts: List[PostData], stock: Dict) -> float:
        """
        计算综合情绪值（ASEN-Adaptive Sentiment Normalization Model）

        改进后的算法：
        - 使用对数标准化去除市值影响
        - Z-score归一化处理跨股票可比性
        - 处理零互动情况
        - 最终情绪值范围：-1到1

        Args:
            posts: 已分类的帖子列表（需要已设置emotion_score）
            stock: 股票信息

        Returns:
            综合情绪值（-1到1）
        """
        import math
        import random

        params = self.get_or_create_params(stock)

        if not posts:
            return 0.0

        # 平台权重配置
        platform_weights = {
            PostType.XUEQIU_HOT: 0.45,
            PostType.XUEQIU_EXPLOSIVE: 0.55,  # 爆值帖权重更高
            PostType.GUBA_HOT: 0.25,
            PostType.GUBA_EXPLOSIVE: 0.30,
            PostType.GUBA_NORMAL: 0.10,
            PostType.NEWS: 0.15
        }

        # ===== 步骤1: 计算每条帖子的贡献 =====
        contributions = []
        for post in posts:
            if not post.post_type:
                continue

            # 互动数据
            likes = post.like_count
            replies = post.reply_count

            # ===== 步骤2: 归一化互动强度 =====
            if likes == 0 and replies == 0:
                # 零互动：添加小噪声项避免恒为0
                raw_engagement = random.normalvariate(0, 0.01)
            else:
                # 对数标准化：log(1+x) 压缩大数值
                log_likes = math.log1p(likes)
                log_replies = math.log1p(replies)

                # 动态混合系数（以评论为准）
                alpha = 0.4  # 点赞权重
                beta = 0.6  # 回复权重
                raw_engagement = log_likes * alpha + log_replies * beta

            # ===== 步骤3: 平台权重 =====
            weight = platform_weights.get(post.post_type, 0.1)

            # ===== 步骤4: 计算贡献 =====
            # 贡献 = 情绪值 * 互动强度 * 平台权重
            contribution = post.emotion_score * (1.0 + raw_engagement) * weight
            contributions.append(contribution)

        if not contributions:
            return 0.0

        # ===== 步骤5: 综合得分与归一化 =====
        avg_contribution = sum(contributions) / len(contributions)

        # ===== 步骤6: tanh归一化到(-1, 1)区间 =====
        # tanh(x)可以自然地把任意实数映射到(-1,1)
        normalized_score = math.tanh(avg_contribution * 1.5)  # 放大系数使区分度更好

        return max(-1.0, min(1.0, normalized_score))

    def record_stock_daily_stats(self, stock_code: str, posts: List[PostData], date_str: str):
        """记录个股每日统计"""
        if stock_code not in self.stock_params:
            return

        params = self.stock_params[stock_code]

        hot_count = sum(1 for p in posts if p.post_type in [PostType.GUBA_HOT, PostType.XUEQIU_HOT])
        explosive_count = sum(1 for p in posts if p.post_type in [PostType.GUBA_EXPLOSIVE, PostType.XUEQIU_EXPLOSIVE])

        if posts:
            avg_reply = sum(p.reply_count for p in posts) / len(posts)
            avg_like = sum(p.like_count for p in posts) / len(posts)
        else:
            avg_reply = 0.0
            avg_like = 0.0

        params.record_daily_stats(date_str, hot_count, explosive_count, avg_reply, avg_like)
