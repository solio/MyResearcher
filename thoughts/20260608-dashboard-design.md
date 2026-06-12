# 投研数据看板 — 设计笔记

日期: 2026-06-08

## 设计决策

### 架构选型：单文件 Python HTTP Server + Chart.js

- **后端**: Python stdlib `http.server`，零依赖，无需 Flask/Streamlit
- **前端**: Chart.js 4.x CDN，内嵌在 Python 文件中作为模板字符串
- **数据层**: 从 `output/YYYYMMDD/*数据.json` 提取时间序列，缓存到 `output/dashboard_cache.json`

**选择理由**:
- 不需要额外安装依赖（requests 已有）
- 单文件部署，复制即用
- Chart.js 成熟稳定，交互开箱即用
- 数据量小（25天 × 13只股票），本地提取 < 1秒

### 数据流

```
output/YYYYMMDD/*数据.json → extract_stock_time_series()
  → 按 stock_code 聚合时间序列
  → 补全缺失日期为 null（Chart.js spanGaps 处理）
  → 缓存到 output/dashboard_cache.json
  → /api/data 返回 JSON
  → 前端 Chart.js 渲染
```

### 缓存策略

- 首次访问自动提取全部历史数据
- 缓存 1 小时内有效，之后自动刷新
- 手动刷新: `python dashboard.py --refresh` 或访问 `/api/refresh`
- 缓存文件: `output/dashboard_cache.json`

---

## 图表设计（共 9 组）

| # | 图表 | 指标 | 用途 |
|---|------|------|------|
| 1 | V3 多维度情绪 | final_score, news_score, forum_score, trading_score | 看整体情绪趋势和子维度分歧 |
| 2 | V1 综合情绪值 | emotion_score_v1 | 对比 V1/V3 差异 |
| 3 | 论坛活跃度 | total_posts, hot_posts, explosive_posts | 判断当日讨论热度 |
| 4 | 论坛情绪分布 | bullish_posts, bearish_posts, neutral_posts | 看多/看空力量对比 |
| 5 | 论坛总互动数 | total_interactions | 帖子阅读+回复总量，反映关注度 |
| 6 | 新闻情绪分布 | total_news, positive_news, negative_news | 新闻面的正负比例 |
| 7 | 股价 vs 情绪 | current_price(右轴), final_score(左轴) | 双轴对比，验证情绪-价格相关性 |
| 8 | 交易指标 | price_change_pct, volume_ratio, main_net_inflow | 量价资金变化 |
| 9 | 置信度 | confidence | 数据质量监控 |

### 图表交互

- 鼠标悬停查看具体数值
- 图例点击切换显示/隐藏
- index 模式：悬停时显示同一日期所有指标
- 下拉框切换股票，所有图表同步更新

---

## 当前数据情况

- **日期范围**: 20260429 ~ 20260605（25 个交易日）
- **股票数量**: 13 只
- **有效 V3 数据**: 20260522 起（11 天），之前只有 V1
- **数据文件大小**: 每个 3-5MB（含完整 news_list）
- **缓存文件大小**: ~50KB（仅提取的时序数据）

---

## 后续优化建议

### 1. 行业情绪面板
目前 dashboard 只展示个股。可以增加一个"行业"tab，展示 6 个行业的情绪时间序列。

### 2. 热力图
用日期 × 股票的矩阵热力图，一眼看到哪些股票在某天情绪异常。

### 3. 异常检测标记
当 final_score 绝对值 > 2.0 或单日变化 > 1.5 时，在图表上标注异常点。

### 4. 股价-情绪相关性系数
在"股价 vs 情绪"图表上叠加 Pearson 相关系数，量化情绪对价格的预测能力。

### 5. 数据完整性监控
新增一张"数据健康"卡片，显示：
- 每只股票的缺失数据天数
- 搜索结果为 0 的天数
- LLM 分析失败的天数
- trading_metrics 为空的次数

### 6. emotion_params 历史
从 `emotion_params.json` 读取 `guba_hot_reply_threshold` 等参数的历史变化，观察阈值自适应调整效果。

### 7. 多股票对比
支持选择 2-3 只股票在同一张图上对比（如隆基绿能 vs 旗滨集团，同属光伏/玻璃产业链）。

### 8. 转为静态 HTML 导出
支持 `python dashboard.py --export` 生成一个完全自包含的 HTML 文件（内嵌数据），可直接邮件发送或存档。

### 9. 数据存储格式优化（可选）
当前每个 `*数据.json` 文件 3-5MB，主要是 `news_list` 的原始内容。dashboard 只需要指标数据。如果每次运行额外写一个 `*指标.json`（只含 emotion_v3 + trading_metrics，约 5KB），dashboard 加载速度会更快，也省去了从大 JSON 中提取的开销。不过目前 25 个文件 × 4MB = 100MB，本地读取还 OK。

---

## 启动方式

```bash
# 默认端口 8099
python dashboard.py

# 指定端口
python dashboard.py --port 8080

# 强制刷新缓存
python dashboard.py --refresh

# 访问
open http://localhost:8099
```
