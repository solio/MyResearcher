#!/usr/bin/env python3
"""
投研数据看板服务
从 output/ 目录读取历史数据，提供交互式 Chart.js 可视化面板。

用法:
    python dashboard.py              # 启动看板服务（默认端口 8099）
    python dashboard.py --port 8099  # 指定端口
    python dashboard.py --refresh    # 强制刷新数据缓存

访问: http://localhost:8099
"""
import json
import os
import sys
import argparse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional
from collections import defaultdict
from urllib.parse import urlparse, parse_qs

from logger import get_logger

logger = get_logger()

# ==================== 数据提取层 ====================

# 关心的指标列表
STOCK_METRICS = [
    # V3 情绪
    "final_score", "news_score", "forum_score", "trading_score", "confidence",
    # 论坛
    "total_posts", "hot_posts", "explosive_posts",
    "bullish_posts", "bearish_posts", "neutral_posts",
    "total_interactions",
    # 新闻
    "total_news", "positive_news", "negative_news", "neutral_news",
    # 交易
    "current_price", "price_change_pct", "volume_ratio",
    "turnover_rate", "main_net_inflow", "bid_ask_ratio",
    # 回填
    "backfill_price",
]


def _safe_float(val, default=None):
    """安全转 float，None / 异常值返回 default"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _find_data_files() -> Dict[str, List]:
    """保留函数签名以供兼容，实际已改用数据库"""
    return {}


def extract_stock_time_series(force_refresh: bool = False) -> Dict:
    """从数据库提取每只股票的时间序列"""
    from database import init_db, get_all_stock_results, load_emotion_thresholds

    init_db()
    logger.info("正在从数据库提取时间序列数据...")
    rows = get_all_stock_results()

    if not rows:
        logger.warning("数据库中无数据")
        return {"stocks": [], "dates": [], "series": {}}

    # 收集所有股票和日期
    all_stocks: Dict[str, str] = {}
    all_dates_set = set()
    raw_series: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict))

    for row in rows:
        code = row.get("stock_code", "")
        if not code:
            continue
        # 从 target_name 提取名称
        tn = row.get("target_name", "")
        name = tn.split("(")[0] if "(" in tn else tn
        all_stocks[code] = name

        date_str = row.get("date", "")
        all_dates_set.add(date_str)

        # V3 情绪
        for key in ["final_score", "news_score", "forum_score",
                    "trading_score", "confidence"]:
            val = row.get(key)
            if val is not None:
                raw_series[code][key][date_str] = _safe_float(val)

        # 论坛指标
        fm = row.get("forum_metrics")
        if fm:
            for key in ["total_posts", "hot_posts", "explosive_posts",
                        "bullish_posts", "bearish_posts", "neutral_posts",
                        "total_interactions"]:
                val = fm.get(key)
                if val is not None:
                    raw_series[code][key][date_str] = _safe_float(val, 0)

        # 新闻指标
        nm = row.get("news_metrics")
        if nm:
            for key in ["total_news", "positive_news", "negative_news",
                        "neutral_news"]:
                val = nm.get(key)
                if val is not None:
                    raw_series[code][key][date_str] = _safe_float(val, 0)

        # 交易指标
        tm = row.get("trading_metrics")
        if tm:
            for key in ["current_price", "price_change_pct",
                        "volume_ratio", "turnover_rate",
                        "main_net_inflow", "bid_ask_ratio"]:
                val = tm.get(key)
                if val is not None:
                    raw_series[code][key][date_str] = _safe_float(val)

            # 回填数据
            if row.get("is_backfill"):
                val = tm.get("current_price")
                if val is not None:
                    raw_series[code]["backfill_price"][date_str] = _safe_float(val)

    sorted_dates = sorted(all_dates_set)
    stocks_list = [{"code": c, "name": n} for c, n in all_stocks.items()]
    series_output = {}

    for code in all_stocks:
        stock_series = {}
        for metric in STOCK_METRICS:
            metric_data = raw_series.get(code, {}).get(metric, {})
            values = []
            for d in sorted_dates:
                v = metric_data.get(d)
                values.append(v)
            if any(v is not None for v in values):
                stock_series[metric] = values
        series_output[code] = stock_series

    # 阈值从数据库加载
    thresholds = {}
    try:
        threshold_data = load_emotion_thresholds(list(all_stocks.keys()))
        for code, td in threshold_data.items():
            thresholds[code] = {
                "hot_reply": td.get("hot_reply_threshold"),
                "hot_like": td.get("hot_like_threshold"),
                "explosive_reply": 10,
                "explosive_like": 10,
            }
    except Exception:
        pass

    return {
        "stocks": stocks_list,
        "dates": sorted_dates,
        "series": series_output,
        "thresholds": thresholds,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ==================== HTTP 服务层 ====================

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投研数据看板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background:#0d1117; color:#c9d1d9; min-height:100vh; }
.header { background:#161b22; border-bottom:1px solid #30363d;
          padding:12px 24px; display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
.header h1 { font-size:1.2rem; color:#58a6ff; white-space:nowrap; }
.header select { background:#21262d; color:#c9d1d9; border:1px solid #30363d;
                 padding:6px 12px; border-radius:6px; font-size:0.9rem; cursor:pointer; min-width:200px; }
.header select:focus { outline:none; border-color:#58a6ff; }
.header .info { font-size:0.8rem; color:#8b949e; margin-left:auto; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(500px, 1fr));
        gap:16px; padding:16px; }
.card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }
.card h2 { font-size:0.95rem; color:#58a6ff; margin-bottom:12px; font-weight:600; }
.card canvas { width:100% !important; max-height:280px; }
.loading { text-align:center; padding:60px; color:#8b949e; font-size:1.1rem; }
.footer { text-align:center; padding:16px; color:#484f58; font-size:0.75rem;
          border-top:1px solid #30363d; margin-top:16px; }
.posts-section { margin:0 16px 16px 16px; background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }
.posts-header { display:flex; align-items:center; gap:12px; margin-bottom:12px; flex-wrap:wrap; }
.posts-header h2 { font-size:0.95rem; color:#58a6ff; font-weight:600; margin:0; }
.posts-header select { background:#21262d; color:#c9d1d9; border:1px solid #30363d; padding:4px 10px; border-radius:6px; font-size:0.85rem; cursor:pointer; }
.posts-header select:focus { outline:none; border-color:#58a6ff; }
.day-tabs { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid #30363d; }
.day-tab { padding:4px 12px; background:#21262d; border:1px solid #30363d; border-radius:16px; color:#8b949e; font-size:0.8rem; cursor:pointer; transition:all .15s; white-space:nowrap; }
.day-tab:hover { border-color:#58a6ff; color:#c9d1d9; }
.day-tab.active { background:#1f6feb33; border-color:#58a6ff; color:#58a6ff; }
.post-list { max-height:500px; overflow-y:auto; }
.post-list::-webkit-scrollbar { width:6px; }
.post-list::-webkit-scrollbar-track { background:#0d1117; }
.post-list::-webkit-scrollbar-thumb { background:#30363d; border-radius:3px; }
.post-list::-webkit-scrollbar-thumb:hover { background:#484f58; }
.post-item { padding:10px 12px; border-bottom:1px solid #21262d; display:flex; align-items:flex-start; gap:10px; }
.post-item:last-child { border-bottom:none; }
.post-item:hover { background:#1c2128; }
.post-title { color:#c9d1d9; font-size:0.85rem; text-decoration:none; line-height:1.4; flex:1; word-break:break-all; }
.post-title:hover { color:#58a6ff; }
.post-meta { display:flex; gap:12px; font-size:0.75rem; color:#8b949e; margin-top:4px; flex-wrap:wrap; }
.post-meta span { white-space:nowrap; }
.badge { display:inline-block; padding:1px 8px; border-radius:10px; font-size:0.7rem; font-weight:600; flex-shrink:0; margin-top:2px; }
.badge-explosive { background:#f8514933; color:#f85149; }
.badge-hot { background:#f7816633; color:#f78166; }
.post-empty { text-align:center; padding:32px; color:#8b949e; font-size:0.9rem; }
@media (max-width:600px) { .grid { grid-template-columns:1fr; } }
</style>
</head>
<body>
<div class="header">
  <h1>📊 投研数据看板</h1>
  <select id="stockSelect" onchange="switchStock()"></select>
  <span class="info" id="info"></span>
</div>
<div class="grid" id="charts"></div>
<div class="posts-section" id="postsSection" style="display:none;">
  <div class="posts-header">
    <h2>📋 帖子列表</h2>
    <select id="monthSelect" onchange="onMonthChange()">
      <option value="">选择月份</option>
    </select>
  </div>
  <div class="day-tabs" id="dayTabs"></div>
  <div class="post-list" id="postList"></div>
</div>
<div class="footer">数据来源: output/ 目录 · 自动生成</div>

<script>
// ===== 全局状态 =====
let allData = null;
let currentStock = null;
let charts = {};
let postsData = null;
let currentMonth = null;
let currentDay = null;

function classifyRank(p) {
  if (p.read_count > 10000 || p.reply_count > 50) return 0;
  if (p.read_count > 5000 || p.reply_count > 20) return 1;
  return 2;
}
const COLORS = {
  final_score:     { border:'#58a6ff', bg:'rgba(88,166,255,0.1)' },
  news_score:      { border:'#3fb950', bg:'rgba(63,185,80,0.1)' },
  forum_score:     { border:'#d29922', bg:'rgba(210,153,34,0.1)' },
  trading_score:   { border:'#f78166', bg:'rgba(247,129,102,0.1)' },

  confidence:      { border:'#8b949e', bg:'rgba(139,148,158,0.1)' },
  total_posts:     { border:'#58a6ff', bg:'rgba(88,166,255,0.1)' },
  hot_posts:       { border:'#f78166', bg:'rgba(247,129,102,0.1)' },
  explosive_posts: { border:'#f85149', bg:'rgba(248,81,73,0.1)' },
  bullish_posts:   { border:'#3fb950', bg:'rgba(63,185,80,0.1)' },
  bearish_posts:   { border:'#f85149', bg:'rgba(248,81,73,0.1)' },
  neutral_posts:   { border:'#8b949e', bg:'rgba(139,148,158,0.1)' },
  total_interactions:{ border:'#d29922', bg:'rgba(210,153,34,0.1)' },
  total_news:      { border:'#58a6ff', bg:'rgba(88,166,255,0.1)' },
  positive_news:   { border:'#3fb950', bg:'rgba(63,185,80,0.1)' },
  negative_news:   { border:'#f85149', bg:'rgba(248,81,73,0.1)' },
  neutral_news:    { border:'#8b949e', bg:'rgba(139,148,158,0.1)' },
  current_price:   { border:'#f0883e', bg:'rgba(240,136,62,0.1)' },
  price_change_pct:{ border:'#f78166', bg:'rgba(247,129,102,0.1)' },
  volume_ratio:    { border:'#d29922', bg:'rgba(210,153,34,0.1)' },
  turnover_rate:   { border:'#bc8cff', bg:'rgba(188,140,255,0.1)' },
  main_net_inflow: { border:'#3fb950', bg:'rgba(63,185,80,0.1)' },
  bid_ask_ratio:   { border:'#f78166', bg:'rgba(247,129,102,0.1)' },
  backfill_price:  { border:'#ff7b72', bg:'rgba(255,123,114,0.1)' },
};

// 图表分组定义
const CHART_GROUPS = [
  {
    id: 'emotion',
    title: '🎯 V3 多维度情绪评分',
    metrics: ['final_score', 'news_score', 'forum_score', 'trading_score'],
    yLabel: '情绪分 (-3 ~ +3)',
    yMin: -3, yMax: 3
  },
  {
    id: 'forum_activity',
    title: '💬 论坛活跃度',
    metrics: ['total_posts', 'hot_posts', 'explosive_posts'],
    yLabel: '帖子数',
    yMin: 0, yMax: null
  },
  {
    id: 'forum_sentiment',
    title: '📊 论坛情绪分布',
    metrics: ['bullish_posts', 'bearish_posts', 'neutral_posts'],
    yLabel: '帖子数',
    yMin: 0, yMax: null
  },
  {
    id: 'forum_interactions',
    title: '🔥 论坛总互动数',
    metrics: ['total_interactions'],
    yLabel: '互动数',
    yMin: 0, yMax: null
  },
  {
    id: 'news_metrics',
    title: '📰 新闻情绪分布',
    metrics: ['total_news', 'positive_news', 'negative_news'],
    yLabel: '新闻数',
    yMin: 0, yMax: null,
    skipIfAllZero: true
  },
  {
    id: 'price_emotion',
    title: '💰 股价 vs 综合情绪',
    metrics: ['current_price', 'final_score'],
    yLabel: '价格(元) / 情绪分',
    yMin: null, yMax: null,
    dualAxis: true
  },
  {
    id: 'trading',
    title: '📉 交易指标',
    metrics: ['price_change_pct', 'volume_ratio', 'main_net_inflow'],
    yLabel: '% / 倍',
    yMin: null, yMax: null,
    rightAxis: ['main_net_inflow'],
    rightLabel: '万元'
  },
  {
    id: 'confidence',
    title: '🎯 情绪置信度',
    metrics: ['confidence'],
    yLabel: '置信度 (0~1)',
    yMin: 0, yMax: 1
  },
  {
    id: 'backfill_emotion_price',
    title: '📈 回填分析：情绪 vs 股价',
    metrics: ['final_score', 'backfill_price'],
    yLabel: '情绪分 (-3 ~ +3)',
    yMin: -3, yMax: 3,
    dualAxis: true,
    isBackfill: true
  },
];

const COMMON_CHART_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode:'index', intersect:false },
  plugins: {
    legend: { labels:{ color:'#8b949e', usePointStyle:true, pointStyle:'circle',
              padding:16, font:{size:11} } },
    tooltip: { backgroundColor:'#161b22', borderColor:'#30363d', borderWidth:1,
               titleColor:'#58a6ff', bodyColor:'#c9d1d9' }
  },
  scales: {
    x: { grid:{ color:'#21262d' }, ticks:{ color:'#8b949e', maxTicksLimit:12,
          callback:function(v){return this.getLabelForValue(v).slice(4);} } },
    y: { grid:{ color:'#21262d' }, ticks:{ color:'#8b949e' },
         beginAtZero: false }
  }
};

// ===== 初始化 =====
fetch('/api/data')
  .then(r => r.json())
  .then(data => {
    allData = data;
    const sel = document.getElementById('stockSelect');
    data.stocks.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.code;
      opt.textContent = `${s.name}(${s.code})`;
      sel.appendChild(opt);
    });
    if (data.stocks.length > 0) {
      currentStock = data.stocks[0].code;
      sel.value = currentStock;
    }
    document.getElementById('info').textContent =
      `日期范围: ${data.dates[0]} ~ ${data.dates[data.dates.length-1]} · ${data.dates.length}天 · ${data.stocks.length}只股票`;
    renderAll();
    document.getElementById('charts').classList.remove('loading');
    loadPostMonths();
  })
  .catch(e => {
    document.getElementById('charts').innerHTML =
      `<div class="loading">❌ 数据加载失败: ${e.message}</div>`;
  });

// 初始状态
document.getElementById('charts').innerHTML =
  '<div class="loading">⏳ 正在加载数据...</div>';

function switchStock() {
  currentStock = document.getElementById('stockSelect').value;
  renderAll();
  loadPostMonths();
}

// ===== 帖子列表 =====
async function loadPostsForMonth(yearMonth) {
  const resp = await fetch(`/api/posts?stock_code=${currentStock}&year_month=${yearMonth}`);
  const data = await resp.json();
  if (data.error) { console.error(data.error); return; }

  postsData = data;
  currentMonth = yearMonth;
  currentDay = null;

  const availableMonths = data.available_months || [];
  const sel = document.getElementById('monthSelect');
  sel.innerHTML = '<option value="">选择月份</option>';
  availableMonths.forEach(ym => {
    const opt = document.createElement('option');
    opt.value = ym;
    opt.textContent = ym.substring(0,4) + '-' + ym.substring(4,6);
    if (ym === yearMonth) opt.selected = true;
    sel.appendChild(opt);
  });

  renderDayTabs();
  document.getElementById('postsSection').style.display = 'block';
}

function loadPostMonths() {
  if (!allData || !allData.dates || allData.dates.length === 0) return;
  const latestDate = allData.dates[allData.dates.length - 1];
  const latestMonth = latestDate.substring(0, 6);
  loadPostsForMonth(latestMonth);
}

function onMonthChange() {
  const val = document.getElementById('monthSelect').value;
  if (val) {
    loadPostsForMonth(val);
  } else {
    currentMonth = null;
    currentDay = null;
    document.getElementById('dayTabs').innerHTML = '';
    document.getElementById('postList').innerHTML = '';
  }
}

function renderDayTabs() {
  const container = document.getElementById('dayTabs');
  container.innerHTML = '';

  if (!postsData || !postsData.dates || Object.keys(postsData.dates).length === 0) {
    container.innerHTML = '<span class="post-empty" style="padding:8px;">该月暂无帖子</span>';
    document.getElementById('postList').innerHTML = '';
    return;
  }

  const dates = Object.keys(postsData.dates).sort();
  dates.forEach(d => {
    const tab = document.createElement('span');
    tab.className = 'day-tab';
    tab.textContent = d.substring(4,6) + '-' + d.substring(6,8);
    tab.onclick = () => { currentDay = d; renderDayTabs(); renderPostList(); };
    if (d === currentDay) tab.classList.add('active');
    container.appendChild(tab);
  });

  if (!currentDay && dates.length > 0) {
    currentDay = dates[0];
    renderDayTabs();
    return;
  }
  renderPostList();
}

function renderPostList() {
  const container = document.getElementById('postList');
  container.innerHTML = '';

  if (!postsData || !postsData.dates || !currentDay) {
    container.innerHTML = '<div class="post-empty">请选择日期查看帖子</div>';
    return;
  }

  let posts = postsData.dates[currentDay] || [];
  if (posts.length === 0) {
    container.innerHTML = '<div class="post-empty">该日期暂无帖子</div>';
    return;
  }

  // 排序：爆 > 热 > 普通，同类按阅读量降序
  posts = [...posts].sort((a, b) => {
    const d = classifyRank(a) - classifyRank(b);
    if (d !== 0) return d;
    return (b.read_count || 0) - (a.read_count || 0);
  });

  posts.forEach(post => {
    const item = document.createElement('div');
    item.className = 'post-item';

    const rank = classifyRank(post);
    const badge = document.createElement('span');
    if (rank === 0) { badge.className = 'badge badge-explosive'; badge.textContent = '爆'; }
    else if (rank === 1) { badge.className = 'badge badge-hot'; badge.textContent = '热'; }
    else { badge.style.cssText = 'flex-shrink:0; margin-top:2px;'; badge.innerHTML = '&nbsp;'; }

    const titleEl = document.createElement('a');
    titleEl.className = 'post-title';
    titleEl.textContent = post.title || '(无标题)';
    if (post.url) { titleEl.href = post.url; titleEl.target = '_blank'; titleEl.rel = 'noopener'; }

    const meta = document.createElement('div');
    meta.className = 'post-meta';
    meta.innerHTML =
      `<span>📖 ${post.read_count || 0}</span>` +
      `<span>💬 ${post.reply_count || 0}</span>` +
      `<span>👍 ${post.like_count || 0}</span>` +
      (post.source ? `<span>${post.source}</span>` : '');

    const wrap = document.createElement('div');
    wrap.style.flex = '1';
    wrap.appendChild(titleEl);
    wrap.appendChild(meta);

    item.appendChild(badge);
    item.appendChild(wrap);
    container.appendChild(item);
  });
}

function makeDataset(metric, data, dates, color, yAxisID) {
  return {
    label: metricLabel(metric),
    data: data,
    borderColor: color.border,
    backgroundColor: color.bg,
    borderWidth: 2,
    pointRadius: 2,
    pointHoverRadius: 5,
    tension: 0.2,
    spanGaps: false,
    yAxisID: yAxisID || 'y'
  };
}

function metricLabel(m) {
  const map = {
    final_score:'综合情绪', news_score:'新闻情绪', forum_score:'论坛情绪',
    trading_score:'交易情绪', confidence:'置信度',
    total_posts:'总帖子', hot_posts:'热帖', explosive_posts:'爆值帖',
    bullish_posts:'看多', bearish_posts:'看空', neutral_posts:'中性',
    total_interactions:'总互动', total_news:'总新闻', positive_news:'正面新闻',
    negative_news:'负面新闻', neutral_news:'中性新闻',
    current_price:'股价', price_change_pct:'涨跌幅%', volume_ratio:'量比',
    turnover_rate:'换手率%', main_net_inflow:'主力净流入(万)',
    bid_ask_ratio:'委比',
    backfill_price:'回填收盘价'
  };
  return map[m] || m;
}

function renderAll() {
  if (!allData || !currentStock) return;
  const stockData = allData.series[currentStock];
  if (!stockData) return;

  const dates = allData.dates;
  const grid = document.getElementById('charts');
  grid.innerHTML = '';

  CHART_GROUPS.forEach(group => {
    // 检查是否有数据
    const available = group.metrics.filter(m => stockData[m] && stockData[m].some(v => v !== null));
    if (available.length === 0) return;

    // 如果配置了 skipIfAllZero，检查是否所有值均为 0（如新闻数全为 0 说明管道无新闻数据）
    if (group.skipIfAllZero) {
      const hasData = available.some(m => stockData[m].some(v => v !== null && v !== 0));
      if (!hasData) return;
    }

    // 创建卡片
    const card = document.createElement('div');
    card.className = 'card';
    const title = document.createElement('h2');
    title.textContent = group.title;
    card.appendChild(title);

    // 论坛活跃度：展示热帖/爆值帖的阈值
    if (group.id === 'forum_activity' && allData.thresholds && allData.thresholds[currentStock]) {
      const t = allData.thresholds[currentStock];
      const sub = document.createElement('div');
      sub.style.cssText = 'font-size:0.75rem;color:#8b949e;margin-bottom:8px;';
      const hotReply = t.hot_reply ? t.hot_reply.toFixed(1) : '?';
      const hotLike = t.hot_like ? t.hot_like.toFixed(1) : '?';
      sub.textContent = `热帖阈值: 回帖≥${hotReply} 点赞≥${hotLike} | 爆值阈值: 回帖≥${t.explosive_reply} 点赞≥${t.explosive_like}`;
      card.appendChild(sub);
    }

    const canvas = document.createElement('canvas');
    card.appendChild(canvas);
    grid.appendChild(card);

    // 创建 chart
    const ctx = canvas.getContext('2d');
    const datasets = [];
    const scales = {};

    available.forEach((metric, idx) => {
      const color = COLORS[metric] || { border:'#8b949e', bg:'rgba(139,148,158,0.1)' };
      let yAxisID = 'y';
      if (group.rightAxis && group.rightAxis.includes(metric)) yAxisID = 'y1';
      else if (group.dualAxis && idx === 1) yAxisID = 'y1';
      datasets.push(makeDataset(metric, stockData[metric], dates, color, yAxisID));
    });

    // y 轴配置
    const yOpts = JSON.parse(JSON.stringify(COMMON_CHART_OPTS.scales.y));
    if (group.yMin !== null) yOpts.min = group.yMin;
    if (group.yMax !== null) yOpts.max = group.yMax;
    yOpts.title = { display: true, text: group.yLabel, color: '#8b949e' };
    scales['y'] = yOpts;

    if (group.dualAxis || group.rightAxis) {
      scales['y1'] = {
        position: 'right',
        grid: { drawOnChartArea: false },
        ticks: { color: '#8b949e' },
        title: { display: true, text: group.rightLabel || '价格(元)', color: '#8b949e' }
      };
    }

    const opts = JSON.parse(JSON.stringify(COMMON_CHART_OPTS));
    opts.scales = scales;

    charts[`${currentStock}_${group.id}`] = new Chart(ctx, {
      type: 'line',
      data: { labels: dates, datasets },
      options: opts
    });
  });
}
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理"""

    dashboard_data: Dict = {}

    def log_message(self, format, *args):
        """使用项目 logger 记录请求"""
        logger.debug(f"HTTP {args[0]}")

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html(DASHBOARD_HTML)
        elif self.path == "/api/data":
            self._send_json(self.dashboard_data)
        elif self.path == "/api/refresh":
            logger.info("强制刷新数据缓存...")
            DashboardHandler.dashboard_data = extract_stock_time_series(
                force_refresh=True)
            self._send_json({"status": "ok", "message": "缓存已刷新"})
        elif self.path.startswith("/api/posts"):
            qs = parse_qs(urlparse(self.path).query)
            stock_code = qs.get("stock_code", [None])[0]
            year_month = qs.get("year_month", [None])[0]
            if not stock_code or not year_month:
                self._send_json({"error": "Missing stock_code or year_month"}, 400)
            else:
                from database import get_posts_by_stock_month
                data = get_posts_by_stock_month(stock_code, year_month)
                self._send_json(data)
        else:
            self.send_response(404)
            self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="投研数据看板服务")
    parser.add_argument("--port", type=int, default=8099, help="服务端口（默认 8099）")
    parser.add_argument("--refresh", action="store_true", help="启动时强制刷新数据缓存")
    args = parser.parse_args()

    # 提取数据
    logger.info("正在准备看板数据...")
    DashboardHandler.dashboard_data = extract_stock_time_series(
        force_refresh=args.refresh)

    stock_count = len(DashboardHandler.dashboard_data.get("stocks", []))
    date_count = len(DashboardHandler.dashboard_data.get("dates", []))
    logger.info(f"数据就绪: {stock_count} 只股票, {date_count} 个交易日")

    # 启动服务
    server = HTTPServer(("0.0.0.0", args.port), DashboardHandler)
    print(f"\n  📊 投研数据看板已启动")
    print(f"  🌐 访问地址: http://localhost:{args.port}")
    print(f"  🔄 刷新缓存: http://localhost:{args.port}/api/refresh")
    print(f"  ⏹  按 Ctrl+C 停止服务\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
