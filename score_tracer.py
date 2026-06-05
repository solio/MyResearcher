#!/usr/bin/env python3
"""
评分计算过程追踪器
当情绪值、爆值、热值等计算结果为0时，记录完整的计算现场，
支持人工溯源验证。
"""
from typing import List, Dict, Optional, Tuple


# V1 平台权重（与 emotion.py 保持一致）
PLATFORM_WEIGHTS = {
    "PostType.XUEQIU_HOT": 0.45,
    "PostType.XUEQIU_EXPLOSIVE": 0.55,
    "PostType.GUBA_HOT": 0.25,
    "PostType.GUBA_EXPLOSIVE": 0.30,
    "PostType.GUBA_NORMAL": 0.10,
    "PostType.NEWS": 0.15,
}

PLATFORM_DISPLAY_NAME = {
    "PostType.XUEQIU_HOT": "雪球热帖",
    "PostType.XUEQIU_EXPLOSIVE": "雪球爆值帖",
    "PostType.GUBA_HOT": "股吧热帖",
    "PostType.GUBA_EXPLOSIVE": "股吧爆值帖",
    "PostType.GUBA_NORMAL": "股吧普通帖",
    "PostType.NEWS": "新闻",
}


class ScoreTracer:
    """评分计算追踪器 — 记录每一步计算现场，支持零值溯源"""

    def __init__(self, target_name: str, target_type: str = "stock"):
        self.target_name = target_name
        self.target_type = target_type

        # V1 数据
        self._total_posts_input: int = 0
        self._classified_posts: List[Dict] = []
        self._emotion_map: Dict[int, float] = {}
        self._v1_score: Optional[float] = None

        # V3 数据
        self._v3_result = None
        self._v3_news_weight: float = 0.2
        self._v3_forum_weight: float = 0.5
        self._v3_trading_weight: float = 0.3

        # V2 fallback
        self._v2_result = None

        # 阈值配置
        self._xueqiu_explosive_reply: int = 100
        self._xueqiu_explosive_like: int = 100
        self._guba_explosive_reply: int = 10
        self._guba_explosive_like: int = 10
        self._guba_hot_reply: int = 2
        self._guba_hot_like: int = 2

        # 论坛热度阈值（V3使用）
        self._forum_explosive_read: int = 10000
        self._forum_explosive_reply_v3: int = 50
        self._forum_hot_read: int = 5000
        self._forum_hot_reply_v3: int = 20

    # ==================== 数据记录方法 ====================

    def record_classification(self, raw_posts: List[Dict],
                              classified_posts, config) -> None:
        """记录 V1 帖子分类现场"""
        self._total_posts_input = len(raw_posts)
        self._classified_posts = []
        for p in classified_posts:
            self._classified_posts.append({
                "title": (p.title or "")[:80],
                "url": p.url or "",
                "source_type": p.source_type or "unknown",
                "post_type": str(p.post_type) if p.post_type else "None",
                "reply_count": getattr(p, "reply_count", 0) or 0,
                "like_count": getattr(p, "like_count", 0) or 0,
                "emotion_score": 0.0,
            })

        if config:
            self._xueqiu_explosive_reply = getattr(
                config, "EMOTION_XUEQIU_EXPLOSIVE_REPLY", 100)
            self._xueqiu_explosive_like = getattr(
                config, "EMOTION_XUEQIU_EXPLOSIVE_LIKE", 100)
            self._guba_explosive_reply = getattr(
                config, "EMOTION_GUBA_EXPLOSIVE_REPLY", 10)
            self._guba_explosive_like = getattr(
                config, "EMOTION_GUBA_EXPLOSIVE_LIKE", 10)
            self._guba_hot_reply = getattr(
                config, "EMOTION_GUBA_HOT_REPLY_BASE", 2)
            self._guba_hot_like = getattr(
                config, "EMOTION_GUBA_HOT_LIKE_BASE", 2)

    def record_emotion_map(self, emotion_map: Dict[int, float]) -> None:
        """记录 LLM 返回的情绪分值"""
        self._emotion_map = dict(emotion_map)
        for i, cp in enumerate(self._classified_posts):
            cp["emotion_score"] = emotion_map.get(i, 0.0)

    def record_v1_score(self, score: float) -> None:
        self._v1_score = score

    def record_v3_result(self, emotion_v3,
                         news_weight: float = 0.2,
                         forum_weight: float = 0.5,
                         trading_weight: float = 0.3) -> None:
        self._v3_result = emotion_v3
        self._v3_news_weight = news_weight
        self._v3_forum_weight = forum_weight
        self._v3_trading_weight = trading_weight

    def record_v2_result(self, emotion_v2) -> None:
        self._v2_result = emotion_v2

    # ==================== 零值检测 ====================

    def get_zero_items(self) -> List[Tuple[str, str, str]]:
        """
        返回所有零值项列表
        每项: (显示名称, 当前值, 原因解释)
        """
        items = []

        # --- V1 综合情绪值 ---
        if self._v1_score is not None and self._v1_score == 0.0:
            items.append(("V1综合情绪值", "0.000",
                          self._explain_v1_score_zero()))

        # --- V1 帖子分类计数 ---
        type_counts = self._count_post_types()
        for type_key, display_name in PLATFORM_DISPLAY_NAME.items():
            count = type_counts.get(type_key, 0)
            if count == 0:
                items.append((f"V1 {display_name}数", "0",
                              self._explain_post_type_zero(type_key)))

        # --- V3 子维度 ---
        if self._v3_result:
            v3 = self._v3_result

            # V3 新闻情绪分
            if v3.news_score == 0.0:
                items.append(("V3新闻情绪分", "0.000",
                              self._explain_v3_news_zero()))

            # V3 论坛情绪分
            if v3.forum_score == 0.0:
                items.append(("V3论坛情绪分", "0.000",
                              self._explain_v3_forum_zero()))

            # V3 交易情绪分
            if v3.trading_score == 0.0:
                items.append(("V3交易情绪分", "0.000",
                              self._explain_v3_trading_zero()))

            # V3 综合分
            if v3.final_score == 0.0:
                items.append(("V3综合情绪分", "0.000",
                              self._explain_v3_combined_zero()))

            # V3 论坛热度计数
            if v3.forum_metrics:
                fm = v3.forum_metrics
                if fm.hot_posts == 0:
                    items.append(("V3论坛热帖数", "0",
                                  self._explain_v3_forum_hot_zero()))
                if fm.explosive_posts == 0:
                    items.append(("V3论坛爆值帖数", "0",
                                  self._explain_v3_forum_explosive_zero()))

            # V3 新闻计数
            if v3.news_metrics and v3.news_metrics.total_news == 0:
                items.append(("V3新闻总数", "0",
                              "输入帖子中 source_type='news' 的数量为0，"
                              "无法计算新闻维度情绪值"))

        # --- V2 fallback ---
        if self._v2_result is None and self._v3_result is None:
            if self._v1_score is not None and self._v1_score == 0.0:
                pass  # already covered above

        return items

    def has_zero_values(self) -> bool:
        return len(self.get_zero_items()) > 0

    # ==================== 简要解释（嵌入报告） ====================

    def brief_explanation(self) -> str:
        """生成嵌入纪要报告的简要解释"""
        items = self.get_zero_items()
        if not items:
            return ""

        lines = ["\n### ⚠️ 争议值说明"]
        lines.append("> 以下指标计算结果为0，详细溯源见同目录下 `争议值解释.md`\n")

        for display_name, value, reason in items:
            lines.append(f"- **{display_name} = {value}**：{reason}")

        # 如果整体情绪为0，给出提示
        overall_zero = any(
            name in ("V1综合情绪值", "V3综合情绪分")
            for name, _, _ in items
        )
        if overall_zero:
            lines.append(
                "\n> 💡 综合情绪为0可能是数据不足（当日无新帖/新闻）"
                "或LLM分析异常导致，建议检查搜索数据是否完整。"
            )

        return "\n".join(lines) + "\n"

    # ==================== 详细报告（争议值解释.md） ====================

    def generate_detail_report(self) -> str:
        """生成完整的详细溯源报告"""
        md = f"# 争议值解释 — {self.target_name}\n\n"
        md += "> 本文档记录了情绪评分计算过程中所有为零的指标及其计算现场，\n"
        md += "> 所有数据均可通过 `output/` 目录下对应日期的搜索数据JSON文件人工溯源。\n\n"
        md += "---\n\n"

        # 数据摘要
        md += "## 数据摘要\n\n"
        md += f"- **输入帖子总数**: {self._total_posts_input}\n"
        md += f"- **已分类帖子数**: {len(self._classified_posts)}\n"
        md += f"- **使用版本**: {'V3' if self._v3_result else 'V2' if self._v2_result else 'V1'}\n\n"

        # V1 分类详情
        if self._classified_posts:
            md += "## V1 帖子分类详情\n\n"
            md += self._generate_v1_classification_table()
            md += "\n"

        # V1 情绪计算
        if self._v1_score is not None:
            md += "## V1 综合情绪计算过程\n\n"
            md += self._generate_v1_calculation_detail()
            md += "\n"

        # V3 详情
        if self._v3_result:
            md += "## V3 多维度情绪计算过程\n\n"
            md += self._generate_v3_calculation_detail()
            md += "\n"

        # V2 fallback
        if self._v2_result and not self._v3_result:
            md += "## V2 情绪计算（V3降级）\n\n"
            md += self._generate_v2_detail()
            md += "\n"

        # 零值汇总
        items = self.get_zero_items()
        if items:
            md += "## 零值指标汇总\n\n"
            md += "| 指标 | 值 | 原因 |\n"
            md += "|------|-----|------|\n"
            for name, value, reason in items:
                md += f"| {name} | {value} | {reason} |\n"
            md += "\n"

        md += "---\n"
        md += "*此文件由 score_tracer 自动生成，所有计算过程基于本地检索数据，可人工验证。*\n"

        return md

    # ==================== 内部：V1 详解 ====================

    def _count_post_types(self) -> Dict[str, int]:
        counts = {}
        for cp in self._classified_posts:
            t = cp["post_type"]
            counts[t] = counts.get(t, 0) + 1
        return counts

    def _generate_v1_classification_table(self) -> str:
        type_counts = self._count_post_types()

        md = "### 帖子类型分布\n\n"
        md += "| 类型 | 数量 | 阈值说明 |\n"
        md += "|------|------|----------|\n"
        md += f"| 雪球爆值帖 | {type_counts.get('PostType.XUEQIU_EXPLOSIVE', 0)} "
        md += f"| 回复>{self._xueqiu_explosive_reply} 或 点赞>{self._xueqiu_explosive_like} |\n"
        md += f"| 雪球热帖 | {type_counts.get('PostType.XUEQIU_HOT', 0)} "
        md += "| 非爆值的雪球帖 |\n"
        md += f"| 股吧爆值帖 | {type_counts.get('PostType.GUBA_EXPLOSIVE', 0)} "
        md += f"| 回复>{self._guba_explosive_reply} 或 点赞>{self._guba_explosive_like} |\n"
        md += f"| 股吧热帖 | {type_counts.get('PostType.GUBA_HOT', 0)} "
        md += f"| 回复>{self._guba_hot_reply} 或 点赞>{self._guba_hot_like} |\n"
        md += f"| 股吧普通帖 | {type_counts.get('PostType.GUBA_NORMAL', 0)} "
        md += "| 不满足以上阈值 |\n"
        md += f"| 新闻 | {type_counts.get('PostType.NEWS', 0)} "
        md += "| source_type='news' |\n"

        md += "\n### 帖子明细\n\n"
        md += ("| # | 标题 | 来源 | 分类 | 回复 | 点赞 | 情绪值 |\n"
               "|---|------|------|------|------|------|--------|\n")
        for i, cp in enumerate(self._classified_posts, 1):
            title_short = (cp["title"] or "")[:30].replace("|", "/")
            md += (f"| {i} | {title_short} | {cp['source_type']} "
                   f"| {PLATFORM_DISPLAY_NAME.get(cp['post_type'], cp['post_type'])} "
                   f"| {cp['reply_count']} | {cp['like_count']} "
                   f"| {cp['emotion_score']:.3f} |\n")

        return md

    def _generate_v1_calculation_detail(self) -> str:
        md = "### 加权平均公式\n\n"
        md += "```\n"
        md += "综合情绪值 = Σ(帖子情绪值 × 平台权重) / Σ(平台权重)\n"
        md += "结果限制在 [-1.0, 1.0] 范围内\n"
        md += "```\n\n"

        md += "### 权重配置\n\n"
        md += "| 帖子类型 | 权重 |\n"
        md += "|----------|------|\n"
        for type_key, weight in PLATFORM_WEIGHTS.items():
            md += f"| {PLATFORM_DISPLAY_NAME.get(type_key, type_key)} | {weight} |\n"

        md += "\n### 逐步计算\n\n"

        # 过滤有效帖子（有 post_type 且 emotion_score != 0 的参与计算）
        # 但实际代码中 emotion_score == 0 也参与加权（乘以权重后贡献为0）
        weighted_sum = 0.0
        total_weight = 0.0
        calc_rows = []

        for i, cp in enumerate(self._classified_posts):
            pt = cp["post_type"]
            if pt == "None":
                calc_rows.append((i + 1, cp["title"][:20], pt, 0.0, 0.0,
                                  "无类型，跳过"))
                continue
            weight = PLATFORM_WEIGHTS.get(pt, 0.1)
            emo = cp["emotion_score"]
            contrib = emo * weight
            weighted_sum += contrib
            total_weight += weight
            calc_rows.append((i + 1, cp["title"][:20],
                              PLATFORM_DISPLAY_NAME.get(pt, pt),
                              emo, weight, contrib))

        md += ("| # | 标题 | 类型 | 情绪值 | 权重 | 贡献(emo×weight) |\n"
               "|---|------|------|--------|------|-------------------|\n")
        for row in calc_rows:
            md += (f"| {row[0]} | {row[1]} | {row[2]} "
                   f"| {row[3]:.3f} | {row[4]:.2f} | {row[5]:.4f} |\n")

        if total_weight > 0:
            avg = weighted_sum / total_weight
        else:
            avg = 0.0
        clamped = max(-1.0, min(1.0, avg))

        md += f"\n**加权和 = {weighted_sum:.4f}**，**总权重 = {total_weight:.2f}**\n\n"
        md += f"**平均值 = {weighted_sum:.4f} / {total_weight:.2f} = {avg:.4f}**\n\n"
        md += f"**限制后 = {clamped:.4f}** （范围 [-1.0, 1.0]）\n\n"

        if clamped == 0.0:
            if total_weight == 0:
                md += ("### ⚠️ 为什么是0？\n\n"
                       "**总权重 = 0**，所有帖子均无有效类型（post_type=None）。\n"
                       "可能原因：\n"
                       "1. 输入帖子列表为空\n"
                       "2. 所有帖子的 source_type 既不是 'forum' 也不是 'news'\n"
                       "3. classify_posts 未能识别任何帖子的来源\n")
            elif all(cp["emotion_score"] == 0.0 for cp in self._classified_posts):
                md += ("### ⚠️ 为什么是0？\n\n"
                       "**所有帖子的LLM情绪值均为0.0**。\n"
                       "可能原因：\n"
                       "1. LLM API调用失败，analyze_batch_post_emotions 返回了全0的默认值\n"
                       "2. LLM判断所有帖子均为中性（情绪值为0）\n"
                       "3. 输入内容不足以让LLM做出情绪判断\n")
            else:
                md += ("### ⚠️ 为什么是0？\n\n"
                       "正负情绪值在加权后相互抵消，导致综合结果为0。\n")

        return md

    # ==================== 内部：V3 详解 ====================

    def _generate_v3_calculation_detail(self) -> str:
        v3 = self._v3_result
        md = "### 加权综合公式\n\n"
        md += "```\n"
        md += ("final_score = news_score × {:.1f}"
               " + forum_score × {:.1f}"
               " + trading_score × {:.1f}\n").format(
            self._v3_news_weight, self._v3_forum_weight, self._v3_trading_weight)
        md += "```\n\n"

        md += "### 各维度计算结果\n\n"
        md += "| 维度 | 分数 | 权重 | 加权贡献 |\n"
        md += "|------|------|------|----------|\n"
        n_contrib = v3.news_score * self._v3_news_weight
        f_contrib = v3.forum_score * self._v3_forum_weight
        t_contrib = v3.trading_score * self._v3_trading_weight
        md += f"| 新闻情绪 | {v3.news_score:.3f} | {self._v3_news_weight} | {n_contrib:.4f} |\n"
        md += f"| 论坛情绪 | {v3.forum_score:.3f} | {self._v3_forum_weight} | {f_contrib:.4f} |\n"
        md += f"| 交易情绪 | {v3.trading_score:.3f} | {self._v3_trading_weight} | {t_contrib:.4f} |\n"
        md += f"| **综合** | **{v3.final_score:.3f}** | 1.0 | **{n_contrib + f_contrib + t_contrib:.4f}** |\n\n"

        # 新闻维度
        md += "### 新闻维度详情\n\n"
        if v3.news_metrics:
            nm = v3.news_metrics
            md += f"- 总新闻数: {nm.total_news}\n"
            md += f"- 正面新闻: {nm.positive_news}\n"
            md += f"- 负面新闻: {nm.negative_news}\n"
            md += f"- 中性新闻: {nm.neutral_news}\n"
            md += f"- 情绪分数: {nm.sentiment_score:.3f}\n"
            if nm.total_news == 0:
                md += "\n**为0原因**: 搜索结果中无 source_type='news' 的帖子。\n"
            elif nm.positive_news == nm.negative_news == 0:
                md += "\n**为0原因**: 关键词分析判定全部新闻为中性。\n"
            elif nm.positive_news == nm.negative_news:
                md += "\n**为0原因**: 正面与负面新闻数量相等，净情绪值为0。\n"
        else:
            md += "新闻指标为空（分析未执行或失败）。\n"
        md += "\n"

        # 论坛维度
        md += "### 论坛维度详情\n\n"
        if v3.forum_metrics:
            fm = v3.forum_metrics
            md += f"- 总帖子数: {fm.total_posts}\n"
            md += f"- 热帖数: {fm.hot_posts}\n"
            md += f"- 爆值帖数: {fm.explosive_posts}\n"
            md += f"- 看多帖: {fm.bullish_posts}\n"
            md += f"- 看空帖: {fm.bearish_posts}\n"
            md += f"- 中性帖: {fm.neutral_posts}\n"
            md += f"- 总互动数: {fm.total_interactions}\n"
            md += f"- 情绪分数: {fm.sentiment_score:.3f}\n"

            md += "\n**热度分类阈值**:\n"
            md += (f"- 爆值: 阅读>{self._forum_explosive_read} "
                   f"或 回复>{self._forum_explosive_reply_v3}\n")
            md += (f"- 热帖: 阅读>{self._forum_hot_read} "
                   f"或 回复>{self._forum_hot_reply_v3}\n")

            if fm.total_posts == 0:
                md += "\n**为0原因**: 搜索结果中无 source_type='forum' 的帖子。\n"
            if fm.hot_posts == 0 and fm.total_posts > 0:
                md += (f"\n**热帖数为0原因**: 所有 {fm.total_posts} 个论坛帖子"
                       "的阅读数和回复数均未达到热帖阈值。\n")
            if fm.explosive_posts == 0 and fm.total_posts > 0:
                md += (f"\n**爆值帖数为0原因**: 所有 {fm.total_posts} 个论坛帖子"
                       "的阅读数和回复数均未达到爆值阈值。\n")
            if fm.bullish_posts == fm.bearish_posts == 0 and fm.total_posts > 0:
                md += (f"\n**情绪分为0原因**: 关键词分析判定全部 {fm.total_posts} 个帖子为中性，"
                       "看多=看空=0，净情绪值为0。\n")
        else:
            md += "论坛指标为空（分析未执行或失败）。\n"
        md += "\n"

        # 交易维度
        md += "### 交易维度详情\n\n"
        if v3.trading_metrics:
            tm = v3.trading_metrics
            md += f"- 当前价格: {tm.current_price}\n"
            md += f"- 涨跌幅: {tm.price_change_pct}%\n"
            md += f"- 量比: {tm.volume_ratio}\n"
            md += f"- 换手率: {tm.turnover_rate}%\n"
            md += f"- 主力净流入: {tm.main_net_inflow}万\n"
            md += f"- 交易信号: {tm.trading_signal}\n"
            md += f"- 交易情绪分: {tm.trading_score}\n"
        else:
            md += ("交易指标为空。\n\n"
                   "**为0原因**: QuantScraper 未能获取到交易数据。\n"
                   "可能原因：\n"
                   "1. 东方财富API请求失败\n"
                   "2. 股票代码格式问题\n"
                   "3. 网络连接异常\n")
            md += f"- 交易情绪分: {v3.trading_score:.3f}\n"
        md += "\n"

        # 综合为0的专项解释
        if v3.final_score == 0.0:
            md += "### ⚠️ V3综合分为0的诊断\n\n"
            zero_dims = []
            if v3.news_score == 0.0:
                zero_dims.append("新闻")
            if v3.forum_score == 0.0:
                zero_dims.append("论坛")
            if v3.trading_score == 0.0:
                zero_dims.append("交易")
            if zero_dims:
                md += (f"以下维度分数为0: {', '.join(zero_dims)}。"
                       "综合分 = 0.2×新闻 + 0.5×论坛 + 0.3×交易，"
                       "三个维度均为0时综合分必然为0。\n\n")

        return md

    def _generate_v2_detail(self) -> str:
        if self._v2_result is None:
            return "V2 未执行。\n\n"
        v2 = self._v2_result
        md = f"- 最终评分: {v2.final_score:.3f}\n"
        md += f"- 评级: {v2.rating_level}\n"
        md += f"- 置信度: {v2.confidence:.1%}\n"
        md += f"- 帖子总数: {v2.total_posts}\n"
        if v2.final_score == 0.0:
            md += "\n**为0原因**: LLM 判定情绪为完全中性（overall_sentiment_score=0.0）。\n"
        return md

    # ==================== 内部：单项解释（报告用，简洁） ====================

    def _explain_v1_score_zero(self) -> str:
        if self._total_posts_input == 0:
            return "输入帖子列表为空，无任何数据可计算"
        type_counts = self._count_post_types()
        valid_count = sum(
            c for t, c in type_counts.items() if t != "None")
        if valid_count == 0:
            return (f"共 {self._total_posts_input} 个帖子，"
                    "但全部未能分配到有效类型（post_type=None），总权重为0")
        all_zero = all(
            cp["emotion_score"] == 0.0 for cp in self._classified_posts
            if cp["post_type"] != "None")
        if all_zero:
            return (f"共 {valid_count} 个有效类型帖子，"
                    "但LLM返回的所有情绪值均为0.0（可能调用失败或全部判定为中性）")
        # Has valid posts with non-zero emotions but they canceled out
        return "正负情绪值在加权后相互抵消，参见详细报告"

    def _explain_post_type_zero(self, type_key: str) -> str:
        display = PLATFORM_DISPLAY_NAME.get(type_key, type_key)

        # NEWS 类型特殊处理
        if type_key == "PostType.NEWS":
            total_news = sum(
                1 for cp in self._classified_posts
                if cp["source_type"] == "news")
            if total_news == 0:
                return "搜索结果中无新闻类数据（source_type='news'），无法产生新闻分类"
            return "所有新闻帖子未被归类为NEWS类型"

        total_forum = sum(
            1 for cp in self._classified_posts
            if cp["source_type"] == "forum")
        if total_forum == 0:
            return f"搜索结果中无论坛帖子（source_type='forum'），无法产生{display}"
        # Check if forum posts exist but don't meet threshold
        if "XUEQIU" in type_key:
            has_xueqiu = any(
                "xueqiu" in cp.get("url", "").lower() or
                "雪球" in cp.get("title", "").lower()
                for cp in self._classified_posts)
            if not has_xueqiu:
                return (f"共 {total_forum} 个论坛帖子中"
                        "无雪球来源（URL不含xueqiu.com），无法产生雪球分类")
            if "EXPLOSIVE" in type_key:
                return (f"雪球帖子均未达到爆值阈值"
                        f"（回复>{self._xueqiu_explosive_reply} "
                        f"或 点赞>{self._xueqiu_explosive_like}）")
            return "所有雪球帖子被归类为爆值帖，无热帖"
        else:
            has_guba = any(
                "guba.eastmoney.com" in cp.get("url", "").lower() or
                "股吧" in cp.get("title", "").lower()
                for cp in self._classified_posts)
            if not has_guba:
                return (f"共 {total_forum} 个论坛帖子中"
                        "无股吧来源，无法产生股吧分类")
            if "EXPLOSIVE" in type_key:
                return (f"股吧帖子均未达到爆值阈值"
                        f"（回复>{self._guba_explosive_reply} "
                        f"或 点赞>{self._guba_explosive_like}）")
            return (f"股吧帖子均未达到热帖阈值"
                    f"（回复>{self._guba_hot_reply} "
                    f"或 点赞>{self._guba_hot_like}），全部归为普通帖")

    def _explain_v3_news_zero(self) -> str:
        if not self._v3_result or not self._v3_result.news_metrics:
            return "新闻维度分析未执行"
        nm = self._v3_result.news_metrics
        if nm.total_news == 0:
            return "搜索结果中无新闻类帖子（source_type='news'），新闻维度无法计分"
        if nm.positive_news == nm.negative_news == 0:
            return (f"共 {nm.total_news} 条新闻，"
                    "关键词分析判定全部为中性，净情绪值为0")
        return (f"正面({nm.positive_news}) = 负面({nm.negative_news})，"
                "净情绪抵消为0")

    def _explain_v3_forum_zero(self) -> str:
        if not self._v3_result or not self._v3_result.forum_metrics:
            return "论坛维度分析未执行"
        fm = self._v3_result.forum_metrics
        if fm.total_posts == 0:
            return "搜索结果中无论坛帖子（source_type='forum'），论坛维度无法计分"
        if fm.bullish_posts == fm.bearish_posts == 0:
            return (f"共 {fm.total_posts} 个论坛帖子，"
                    "关键词分析判定全部为中性，净情绪值为0")
        return (f"看多({fm.bullish_posts}) = 看空({fm.bearish_posts})，"
                "净情绪抵消为0")

    def _explain_v3_trading_zero(self) -> str:
        return ("QuantScraper 未获取到交易数据"
                "（API请求失败或股票代码问题），交易维度分数为0")

    def _explain_v3_combined_zero(self) -> str:
        if not self._v3_result:
            return "V3分析未执行"
        v3 = self._v3_result
        zero_dims = []
        if v3.news_score == 0.0:
            zero_dims.append("新闻")
        if v3.forum_score == 0.0:
            zero_dims.append("论坛")
        if v3.trading_score == 0.0:
            zero_dims.append("交易")
        return ("三个子维度均为0（" + "、".join(zero_dims) + "），"
                "综合分 = 0.2×0 + 0.5×0 + 0.3×0 = 0")

    def _explain_v3_forum_hot_zero(self) -> str:
        if not self._v3_result or not self._v3_result.forum_metrics:
            return "论坛分析未执行"
        fm = self._v3_result.forum_metrics
        if fm.total_posts == 0:
            return "无论坛帖子，热帖数必然为0"
        return (f"共 {fm.total_posts} 个论坛帖子，"
                f"均未达到热帖阈值"
                f"（阅读>{self._forum_hot_read} 或 回复>{self._forum_hot_reply_v3}）")

    def _explain_v3_forum_explosive_zero(self) -> str:
        if not self._v3_result or not self._v3_result.forum_metrics:
            return "论坛分析未执行"
        fm = self._v3_result.forum_metrics
        if fm.total_posts == 0:
            return "无论坛帖子，爆值帖数必然为0"
        return (f"共 {fm.total_posts} 个论坛帖子，"
                f"均未达到爆值阈值"
                f"（阅读>{self._forum_explosive_read} 或 回复>{self._forum_explosive_reply_v3}）")
