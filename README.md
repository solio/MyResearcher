# 个股价值投研助手

一个基于价值投资理念的个股投研自动化工具，定时搜索和分析个股及行业新闻，包含市场情绪分析。

## 功能特性

- 定时搜索个股热门新闻和话题（默认每3小时）
- 定时搜索行业热门新闻和话题
- **雪球、股吧等论坛搜索与情绪分析**
- **双搜索引擎支持**：
  - search-engine skill（默认，本地搜索引擎 + 智能过滤）
  - Tavily API（备选，多源搜索）
- 基于 DeepSeek API 的智能分析（价值投资 + 逆向思维）
- **新闻去重，避免重复分析浪费 Token**
- **与上一日对比，内容相似时跳过分析**
- **按日期组织的目录结构，文件名带时间**
- **完善的日志记录，出错继续执行**
- **搜索 API 和 LLM 可替换，支持超时和重试配置**
- **失败高亮显示，友好的错误提示**

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制配置模板并填入真实配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入以下信息：

```env
# DeepSeek API 配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Tavily 搜索 API 配置（使用tavily搜索时需要）
TAVILY_API_KEY=your_tavily_api_key_here

# ========== 搜索方式选择 ==========
# 使用 search-engine skill（默认，推荐）
SEARCH_PROVIDER=skill
SEARCH_ENGINE_PATH=../search-engine
SKILL_USE_TARGETED=false
SKILL_USE_MOCK=false

# 或使用 Tavily API（备选）
# SEARCH_PROVIDER=tavily
# Tavily搜索的时间范围（天数，默认2天，保证新闻时效性）
# TAVILY_SEARCH_TIME_RANGE_DAYS=2

# 关注的股票列表
STOCK_LIST=601012|隆基绿能,002407|多氟多,603039|泛微,003000|劲仔

# 关注的行业列表
INDUSTRY_LIST=光伏行业|玻璃行业|锂电行业|IT软件开发|休闲零食

# 是否启用论坛搜索
ENABLE_FORUM_SEARCH=true

# 超时和重试配置
SEARCH_TIMEOUT=40
SEARCH_MAX_RETRIES=3
LLM_TIMEOUT=90
LLM_MAX_RETRIES=2
```

### 3. 运行

执行一次投研：
```bash
python main.py --mode once
```

定时运行（每3小时）：
```bash
python main.py --mode daemon
```

## 输出目录结构

```
output/
├── 20260429/
│   ├── 20260429_093000-纪要.md    # 投研纪要（带时间）
│   └── 20260429_093000-数据.json  # 原始数据（带时间）
└── logs/
    └── 20260429.log              # 运行日志
```

## 核心投资理念

- **价值投资**：关注基本面
- **逆向思维**："他人恐惧我贪婪，他人贪婪我逃避"
- **情绪分析**：从股吧、雪球等论坛感知市场温度

## 扩展开发

### 添加新的搜索API提供者

继承 `BaseSearchProvider` 类并实现 `search` 方法：

```python
from searcher import BaseSearchProvider

class MySearchProvider(BaseSearchProvider):
    def search(self, query: str, max_results: int = 5):
        # 实现你的搜索逻辑
        pass
```

### 添加新的 LLM 提供者

继承 `BaseLLMProvider` 类并实现 `chat` 方法：

```python
from llm import BaseLLMProvider

class MyLLMProvider(BaseLLMProvider):
    def chat(self, messages, temperature=0.7, max_tokens=2000):
        # 实现你的 LLM 调用逻辑
        pass
```

## 项目结构

```
.
├── main.py           # 主入口
├── scheduler.py      # 定时调度模块
├── researcher.py     # 投研主流程模块
├── searcher.py       # 搜索模块（可替换API）
├── llm.py            # LLM 模块（可替换API）
├── config.py         # 配置管理模块
├── logger.py         # 日志模块
├── console.py        # 终端彩色输出模块
├── requirements.txt  # 依赖列表
├── .env.example      # 配置模板
└── README.md
```
