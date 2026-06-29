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
import time
import argparse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional
from collections import defaultdict

from logger import get_logger

logger = get_logger()

# ==================== 数据提取层 ====================

OUTPUT_DIR = Path(__file__).parent / "output"
CACHE_FILE = Path(__file__).parent / "output" / "dashboard_cache.json"

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


def _find_data_files() -> Dict[str, List[Path]]:
    """扫描 output/ 目录，按日期归类数据文件路径。返回 {date_str: [path, ...]}"""
    date_files = defaultdict(list)
    if not OUTPUT_DIR.exists():
        return date_files

    for entry in sorted(OUTPUT_DIR.iterdir()):
        if not entry.is_dir():
            continue
        dir_name = entry.name
        # 只匹配 YYYYMMDD 格式的目录
        if len(dir_name) != 8 or not dir_name.isdigit():
            continue
        for f in entry.glob("*数据.json"):
            date_files[dir_name].append(f)

    return dict(date_files)


def extract_stock_time_series(force_refresh: bool = False) -> Dict:
    """
    从所有历史数据文件中提取每只股票的时间序列。
    结果缓存到 dashboard_cache.json，后续加载优先用缓存。
    """
    if not force_refresh and CACHE_FILE.exists():
        cache_age = time.time() - CACHE_FILE.stat().st_mtime
        if cache_age < 3600:  # 1 小时内不过期
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    logger.info(f"加载缓存: {CACHE_FILE} ({(cache_age/60):.0f}分钟前)")
                    return json.load(f)
            except Exception:
                pass

    logger.info("正在从 output/ 提取时间序列数据...")
    date_files = _find_data_files()
    if not date_files:
        logger.warning("未找到任何数据文件")
        return {"stocks": [], "dates": [], "series": {}}

    # 按日期排序
    sorted_dates = sorted(date_files.keys())
    logger.info(f"发现 {len(sorted_dates)} 个日期目录，"
                f"共 {sum(len(v) for v in date_files.values())} 个数据文件")

    # 收集所有股票代码
    all_stocks: Dict[str, str] = {}  # code -> name
    raw_series: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict))  # code -> metric -> date -> value

    for date_str in sorted_dates:
        # 取该日期最新的数据文件
        files = sorted(date_files[date_str], reverse=True)
        data_file = files[0]

        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.debug(f"跳过 {data_file}: {e}")
            continue

        for result in data.get("results", []):
            if result.get("target_type") != "stock":
                continue

            target_name = result.get("target_name", "")
            # 从 "隆基绿能(601012)" 解析代码
            if "(" in target_name and ")" in target_name:
                stock_name = target_name.split("(")[0]
                stock_code = target_name.split("(")[1].rstrip(")")
            else:
                continue

            all_stocks[stock_code] = stock_name

            # --- V3 情绪 ---
            ev3 = result.get("emotion_v3")
            if ev3:
                for key in ["final_score", "news_score", "forum_score",
                            "trading_score", "confidence"]:
                    val = ev3.get(key)
                    if val is not None:
                        raw_series[stock_code][key][date_str] = _safe_float(val)

                # 论坛指标
                fm = ev3.get("forum_metrics")
                if fm:
                    for key in ["total_posts", "hot_posts", "explosive_posts",
                                "bullish_posts", "bearish_posts", "neutral_posts",
                                "total_interactions"]:
                        val = fm.get(key)
                        if val is not None:
                            raw_series[stock_code][key][date_str] = _safe_float(val, 0)

                # 新闻指标
                nm = ev3.get("news_metrics")
                if nm:
                    for key in ["total_news", "positive_news", "negative_news",
                                "neutral_news"]:
                        val = nm.get(key)
                        if val is not None:
                            raw_series[stock_code][key][date_str] = _safe_float(val, 0)

                # 交易指标
                tm = ev3.get("trading_metrics")
                if tm:
                    for key in ["current_price", "price_change_pct",
                                "volume_ratio", "turnover_rate",
                                "main_net_inflow", "bid_ask_ratio"]:
                        val = tm.get(key)
                        if val is not None:
                            raw_series[stock_code][key][date_str] = _safe_float(val)

                    # 回填数据：单独记录回填日的股价（来自 K 线收盘价）
                    if data.get("backfill"):
                        val = tm.get("current_price")
                        if val is not None:
                            raw_series[stock_code]["backfill_price"][date_str] = _safe_float(val)

    # 构建最终输出：补全缺失日期为 None（Chart.js 会跳过）
    stocks_list = [{"code": c, "name": n} for c, n in all_stocks.items()]
    series_output = {}

    for code in all_stocks:
        stock_series = {}
        for metric in STOCK_METRICS:
            metric_data = raw_series.get(code, {}).get(metric, {})
            values = []
            for d in sorted_dates:
                v = metric_data.get(d)
                values.append(v)  # None for missing, Chart.js spanGaps or skip
            # 如果整列全 None 就跳过
            if any(v is not None for v in values):
                stock_series[metric] = values
        series_output[code] = stock_series

    # 读取情绪阈值（用于论坛活跃度图表展示）
    thresholds = {}
    params_file = OUTPUT_DIR / "emotion_params.json"
    if params_file.exists():
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                ep = json.load(f)
            for code, sd in ep.get("stocks", {}).items():
                thresholds[code] = {
                    "hot_reply": sd.get("guba_hot_reply_threshold"),
                    "hot_like": sd.get("guba_hot_like_threshold"),
                    "explosive_reply": 10,  # 来自 config 默认值
                    "explosive_like": 10,
                }
        except Exception:
            pass

    result = {
        "stocks": stocks_list,
        "dates": sorted_dates,
        "series": series_output,
        "thresholds": thresholds,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 写缓存
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        logger.info(f"缓存已更新: {CACHE_FILE}")
    except Exception as e:
        logger.warning(f"缓存写入失败: {e}")

    return result


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
<div class="footer">数据来源: output/ 目录 · 自动生成</div>

<script>
// ===== 全局状态 =====
let allData = null;
let currentStock = null;
let charts = {};
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
