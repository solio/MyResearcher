# Search-Engine Skill 接口契约

`prompt-engineering` 是一个研究散户情绪指标的财经投研项目，之前是一个基于 Tavily API 的项目。现在基于成本考虑，需要切换到本地部署的 SearxNG 搜索引擎。
> 本文档仅定义 `search-engine/skill/skill.py` 模块需要提供的接口。**内部实现方式不做修改和限制，只要满足此契约即可。**

---

## Skill 模块位置

```
search-engine/
└── skill/
    └── skill.py          # ← 唯一需要提供的模块
```

---

## 一、必须提供的函数

### `search()` 函数

**文件**：`search-engine/skill/skill.py`

```python
def search(
    query: str,
    targeted: bool = False,
    debug: bool = False,
    use_mock: bool = False,
) -> Dict[str, Any]:
    """
    搜索函数

    Args:
        query: 搜索关键词
        targeted: 是否定向搜索（仅优质站点）
        debug: 是否返回详细评估信息
        use_mock: 是否使用 mock 模式（返回测试数据）

    Returns:
        搜索结果字典，格式见下文
    """
```

---

## 二、返回数据格式

```python
{
    "query": "搜索关键词",
    "search_time": "2026-05-07T11:30:00.000000",
    "mode": "定向搜索" or "普通搜索",
    "result_count": 10,
    "total_results": 20,
    "passed_results": 10,
    "filtered_results": 10,
    "filter_rate": "50.0%",
    "filter_reasons": {},
    "total_spam_keywords": 0,
    "bad_url_count": 0,
    "low_quality_count": 0,
    "problems": [],
    "needs_param_update": False,
    "param_update_suggestion": None,
    "failure_reason": None,
    "failure_message": None,
    "results": [
        {
            "title": "文章标题",
            "url": "https://example.com/article",
            "domain": "example.com",
            "content": "文章摘要内容",
            "is_quality_site": True,
            "score": 0.95
        }
    ]
}
```

### 单个结果字段

| 字段 | 类型 | 必填 |
|------|------|------|
| `title` | str | 是 |
| `url` | str | 是 |
| `domain` | str | 是 |
| `content` | str | 是 |
| `is_quality_site` | bool | 是 |
| `score` | float | 是 |

---

## 三、验证方式

```bash
cd search-engine
python -c "from skill.skill import search; r = search('测试'); print(r)"
```

---

**文档版本**：v1.1
