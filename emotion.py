"""
情绪分析模块
负责情绪参数管理、帖子分类、情绪值计算
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
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


@dataclass
class PostData:
    """帖子数据"""
    title: str
    url: str
    content: str
    source_type: str  # "xueqiu" or "guba"
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
            # 提取回帖和点赞数（从内容中尽可能提取，Tavily不一定有这个数据）
            reply_count = self._extract_number(post.get("content", ""), ["回复", "评论", "回帖"])
            like_count = self._extract_number(post.get("content", ""), ["点赞", "喜欢", "👍"])

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
                # 判断是雪球还是股吧（从URL或标题猜）
                is_xueqiu = "xueqiu" in post_data.url.lower() or "雪球" in post_data.title
                is_guba = "guba" in post_data.url.lower() or "股吧" in post_data.title

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
                    # 未知来源，按股吧普通处理
                    post_data.post_type = PostType.GUBA_NORMAL

            results.append(post_data)

        return results

    def _extract_number(self, text: str, keywords: List[str]) -> int:
        """
        从文本中提取数字（简单实现）

        Args:
            text: 文本
            keywords: 关键词列表

        Returns:
            提取到的数字，默认0
        """
        # TODO: 更智能的提取逻辑
        # 暂时返回0，因为Tavily搜索结果不包含结构化的回复/点赞数据
        return 0

    def calculate_emotion_score(self, posts: List[PostData], stock: Dict) -> float:
        """
        计算综合情绪值

        公式：
        情绪值 = (市值/100亿 * 点赞数 + 市值/100亿 * 回帖数) * 权重

        各类型权重：
        - 雪球值：0.5
        - 股吧热度：0.2
        - 股吧爆值：0.2
        - 股吧普值：0.1

        Args:
            posts: 已分类的帖子列表（需要已设置emotion_score）
            stock: 股票信息

        Returns:
            综合情绪值（-1到1）
        """
        params = self.get_or_create_params(stock)
        factor = params.market_cap / 100.0

        total_score = 0.0
        total_weight = 0.0

        for post in posts:
            if not post.post_type:
                continue

            # 计算该帖子的影响力（基于回复和点赞）
            influence = factor * (post.reply_count + post.like_count)

            # 根据类型给权重
            weight = 0.0
            if post.post_type == PostType.XUEQIU_HOT:
                weight = self.config.EMOTION_XUEQIU_WEIGHT
            elif post.post_type == PostType.XUEQIU_EXPLOSIVE:
                weight = self.config.EMOTION_XUEQIU_WEIGHT * 1.5  # 爆值帖权重更高
            elif post.post_type == PostType.GUBA_HOT:
                weight = self.config.EMOTION_GUBA_HOT_WEIGHT
            elif post.post_type == PostType.GUBA_EXPLOSIVE:
                weight = self.config.EMOTION_GUBA_EXPLOSIVE_WEIGHT
            elif post.post_type == PostType.GUBA_NORMAL:
                weight = self.config.EMOTION_GUBA_NORMAL_WEIGHT

            total_score += post.emotion_score * influence * weight
            total_weight += influence * weight

        if total_weight == 0:
            return 0.0

        return max(-1.0, min(1.0, total_score / total_weight))

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
