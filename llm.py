"""
LLM 模块
支持可替换的 LLM 提供者，自带重试机制
"""
import requests
import time
from typing import List, Dict, Optional
from abc import ABC, abstractmethod

from logger import get_logger
from console import print_error, highlight_deepseek_error

logger = get_logger()


class BaseLLMProvider(ABC):
    """LLM 提供者基类（可替换）"""

    @abstractmethod
    def chat(self, messages: List[Dict], temperature: float = 0.7,
             max_tokens: int = 2000) -> Optional[str]:
        """
        发送聊天请求

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            LLM 回复内容，失败返回 None
        """
        pass


class DeepSeekLLMProvider(BaseLLMProvider):
    """DeepSeek LLM 提供者"""

    def __init__(self, api_key: str, api_base: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat", timeout: int = 90, max_retries: int = 2):
        """
        初始化

        Args:
            api_key: API Key
            api_base: API 基础 URL
            model: 模型名称
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def _chat_once(self, messages: List[Dict], temperature: float,
                   max_tokens: int) -> str:
        """执行一次聊天请求"""
        url = f"{self.api_base}/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = requests.post(url, headers=self.headers,
                                 json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def chat(self, messages: List[Dict], temperature: float = 0.7,
             max_tokens: int = 2500) -> Optional[str]:
        """
        发送聊天请求（带重试）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            LLM 回复内容，失败返回 None
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"LLM 请求尝试 {attempt}/{self.max_retries}")
                return self._chat_once(messages, temperature, max_tokens)
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"LLM 请求失败（尝试 {attempt}/{self.max_retries}）: {e}")
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        # 全部失败，高亮显示
        error_msg = highlight_deepseek_error(last_error)
        print_error(error_msg)
        logger.error(f"LLM 请求最终失败: {last_error}")
        return None


class StockAnalyzer:
    """股票投研分析器"""

    def __init__(self, llm_provider: BaseLLMProvider):
        """
        初始化

        Args:
            llm_provider: LLM 提供者（可替换）
        """
        self.llm = llm_provider

    def analyze_news_with_sentiment(self, news_list: List[Dict],
                                    target_name: str,
                                    target_type: str = "stock") -> Optional[str]:
        """
        分析新闻并进行市场情绪分析

        Args:
            news_list: 新闻列表
            target_name: 研究目标名称
            target_type: 研究类型

        Returns:
            分析摘要，失败返回 None
        """
        if not news_list:
            return "暂无新闻信息"

        # 区分新闻和论坛帖子
        news_items = [n for n in news_list if n.get("source_type") == "news"]
        forum_items = [n for n in news_list if n.get("source_type") == "forum"]

        # 构建新闻文本
        news_text = ""
        if news_items:
            news_text += "【新闻资讯】\n"
            for i, news in enumerate(news_items, 1):
                news_text += f"{i}. 标题: {news.get('title', '')}\n"
                news_text += f"   链接: {news.get('url', '')}\n"
                news_text += f"   摘要: {news.get('content', '')[:250]}...\n\n"

        if forum_items:
            news_text += "【论坛讨论（雪球/股吧）】\n"
            for i, post in enumerate(forum_items, 1):
                news_text += f"{i}. 标题: {post.get('title', '')}\n"
                news_text += f"   链接: {post.get('url', '')}\n"
                news_text += f"   摘要: {post.get('content', '')[:250]}...\n\n"

        # 构建提示词
        target_desc = f"{target_name}（个股）" if target_type == "stock" else f"{target_name}（行业）"

        prompt = f"""
你是一位有15年经验的价值投资分析师，精通行为金融学。请基于以下信息对{target_desc}进行深度分析。

投资原则：
- 坚持"他人恐惧我贪婪，他人贪婪我逃避"的逆向投资理念
- 区分"短期情绪"和"长期基本面"
- 重视安全边际

【信息来源】
{news_text}

请按以下格式输出分析报告：

---

## 一、热点事件速览
（列出3-5个最核心的事件，注明来源是新闻还是论坛）

## 二、多空基本面分析
### 利好因素
1. （事件描述）- 影响程度：[高/中/低]
2. ...

### 利空因素
1. （事件描述）- 影响程度：[高/中/低]
2. ...

## 三、市场情绪分析
### 情绪温度计
当前市场情绪：[极度贪婪/贪婪/中性/恐惧/极度恐惧]

### 情绪依据
（从论坛讨论和新闻氛围中提炼，说明为什么得出这个结论）

### 逆向投资思考
（站在价值投资者角度，当前情绪是否提供了反向操作的机会？）

## 四、总结与建议
### 核心结论
（1-2句话总结）

### 操作建议
- 建议态度：[乐观/中性/谨慎]
- 建议仓位：[观望/试探性买入/持有/减仓/清仓]
- 关注要点：...

---

【注意事项】
1. 区分"事实"和"观点"，不确定的信息要说明
2. 引用信息要简短，不要大段复制
3. 语言专业、精炼，适合价值投资者阅读
4. 如果信息不足，请说明"信息有限，有待进一步验证"
"""

        logger.info(f"调用 LLM 分析: {target_name}")
        messages = [{"role": "user", "content": prompt}]
        result = self.llm.chat(messages, temperature=0.6, max_tokens=2500)

        if result is None:
            return "分析失败"

        return result

    def generate_summary(self, news_list: List[Dict]) -> Optional[str]:
        """
        生成新闻简明摘要

        Args:
            news_list: 新闻列表

        Returns:
            摘要字符串
        """
        if not news_list:
            return "无新闻"

        titles = [n.get("title", "") for n in news_list[:10]]
        joined = " | ".join(titles)

        prompt = f"""
请为以下新闻标题生成一个200字以内的简明摘要，用一句话概括主要内容：

{joined}
"""
        messages = [{"role": "user", "content": prompt}]
        result = self.llm.chat(messages, temperature=0.3, max_tokens=300)

        if result is None:
            return "摘要生成失败"

        return result


# ========== 兼容旧代码的类名 ==========
class DeepSeekLLM(StockAnalyzer):
    """兼容旧代码的包装类"""

    def __init__(self, api_key: str, api_base: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat", timeout: int = 90, max_retries: int = 2):
        provider = DeepSeekLLMProvider(api_key, api_base, model, timeout, max_retries)
        super().__init__(provider)

    def analyze_news_with_sentiment(self, news_list: List[Dict],
                                    target_name: str,
                                    target_type: str = "stock") -> Optional[str]:
        return super().analyze_news_with_sentiment(news_list, target_name, target_type)

    def generate_summary(self, news_list: List[Dict]) -> Optional[str]:
        return super().generate_summary(news_list)

    def analyze_news(self, news_list: List[Dict]) -> Optional[str]:
        return self.analyze_news_with_sentiment(news_list, "目标", "stock")
