"""
配置管理模块
负责加载和管理所有配置项
"""
import os
from dotenv import load_dotenv
from typing import List, Dict


class Config:
    """配置管理类"""

    def __init__(self, env_file: str = ".env"):
        """
        初始化配置

        Args:
            env_file: 环境变量文件路径
        """
        # 加载环境变量
        if os.path.exists(env_file):
            load_dotenv(env_file)
        else:
            print(f"警告: 配置文件 {env_file} 不存在，使用默认配置")

        # ========== API 配置 ==========
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-0a3f7ffc68eb4f84b9a906085d9842e3")
        self.DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        self.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

        self.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")

        # ========== 定时任务配置 ==========
        self.CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "180"))

        # ========== 股票列表配置 ==========
        self.STOCK_LIST = self._parse_stock_list(os.getenv("STOCK_LIST", "601012|隆基绿能,002407|多氟多,603039|泛微,003000|劲仔"))

        # ========== 行业列表配置 ==========
        self.INDUSTRY_LIST = self._parse_industry_list(os.getenv("INDUSTRY_LIST", "光伏行业|玻璃行业|锂电行业|it软件开发行业|休闲零食"))

        # ========== 搜索配置 ==========
        self.SEARCH_RESULT_COUNT = int(os.getenv("SEARCH_RESULT_COUNT", "5"))
        self.SEARCH_SCOPES = os.getenv("SEARCH_SCOPES", "news,blogs,forums").split(",")
        self.ENABLE_FORUM_SEARCH = os.getenv("ENABLE_FORUM_SEARCH", "true").lower() == "true"

        # ========== 搜索API配置 ==========
        self.SEARCH_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT", "40"))  # 搜索超时时间（秒）
        self.SEARCH_MAX_RETRIES = int(os.getenv("SEARCH_MAX_RETRIES", "3"))  # 搜索最大重试次数
        self.LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "90"))  # LLM超时时间（秒）
        self.LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))  # LLM最大重试次数

        # ========== 搜索过滤配置 ==========
        self.SEARCH_TIME_RANGE_DAYS = int(os.getenv("SEARCH_TIME_RANGE_DAYS", "60"))  # 搜索时间范围：默认2个月
        self.SEARCH_MIN_CONTENT_LENGTH = int(os.getenv("SEARCH_MIN_CONTENT_LENGTH", "50"))  # 内容最小长度
        self.SEARCH_MAX_PAGES = int(os.getenv("SEARCH_MAX_PAGES", "3"))  # 最大翻页次数
        self.ENABLE_CONTENT_CLEANUP = os.getenv("ENABLE_CONTENT_CLEANUP", "true").lower() == "true"  # 是否清理模板内容

        # ========== 情绪分析配置 ==========
        self.EMOTION_XUEQIU_WEIGHT = float(os.getenv("EMOTION_XUEQIU_WEIGHT", "0.5"))  # 雪球权重
        self.EMOTION_GUBA_HOT_WEIGHT = float(os.getenv("EMOTION_GUBA_HOT_WEIGHT", "0.2"))  # 股吧热度权重
        self.EMOTION_GUBA_EXPLOSIVE_WEIGHT = float(os.getenv("EMOTION_GUBA_EXPLOSIVE_WEIGHT", "0.2"))  # 股吧爆值权重
        self.EMOTION_GUBA_NORMAL_WEIGHT = float(os.getenv("EMOTION_GUBA_NORMAL_WEIGHT", "0.1"))  # 股吧普值权重

        self.EMOTION_GUBA_HOT_REPLY_BASE = int(os.getenv("EMOTION_GUBA_HOT_REPLY_BASE", "2"))  # 股吧热度回帖数基数
        self.EMOTION_GUBA_HOT_LIKE_BASE = int(os.getenv("EMOTION_GUBA_HOT_LIKE_BASE", "2"))  # 股吧热度点赞数基数
        self.EMOTION_GUBA_EXPLOSIVE_REPLY = int(os.getenv("EMOTION_GUBA_EXPLOSIVE_REPLY", "10"))  # 股吧爆值回帖数
        self.EMOTION_GUBA_EXPLOSIVE_LIKE = int(os.getenv("EMOTION_GUBA_EXPLOSIVE_LIKE", "10"))  # 股吧爆值点赞数
        self.EMOTION_XUEQIU_EXPLOSIVE_REPLY = int(os.getenv("EMOTION_XUEQIU_EXPLOSIVE_REPLY", "100"))  # 雪球爆值回帖数
        self.EMOTION_XUEQIU_EXPLOSIVE_LIKE = int(os.getenv("EMOTION_XUEQIU_EXPLOSIVE_LIKE", "100"))  # 雪球爆值点赞数

        self.EMOTION_PARAM_UPDATE_DAYS = int(os.getenv("EMOTION_PARAM_UPDATE_DAYS", "5"))  # 参数更新天数
        self.EMOTION_PARAM_CHANGE_THRESHOLD = float(os.getenv("EMOTION_PARAM_CHANGE_THRESHOLD", "0.5"))  # 参数更新阈值
        self.EMOTION_PARAM_MIN = int(os.getenv("EMOTION_PARAM_MIN", "1"))  # 参数最小值

        self.EMOTION_DATA_FILE = os.getenv("EMOTION_DATA_FILE", "./output/emotion_params.json")  # 情绪参数文件

        # ========== 输出配置 ==========
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # 确保输出目录存在
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    def _parse_stock_list(self, stock_str: str) -> List[Dict]:
        """
        解析股票列表字符串

        兼容两种格式：
        - 代码|名称
        - 代码|名称|行业|市值（可选，单位亿）

        Args:
            stock_str: 股票列表字符串

        Returns:
            股票字典列表
        """
        stocks = []
        if not stock_str:
            return stocks

        for item in stock_str.split(","):
            item = item.strip()
            if not item:
                continue

            parts = item.split("|")
            if len(parts) >= 2:
                stocks.append({
                    "code": parts[0].strip(),
                    "name": parts[1].strip(),
                    "industry": parts[2].strip() if len(parts) >= 3 else "",
                    "market_cap": float(parts[3].strip()) if len(parts) >= 4 else 100.0  # 默认100亿
                })

        return stocks

    def _parse_industry_list(self, industry_str: str) -> List[str]:
        """
        解析行业列表字符串

        Args:
            industry_str: 逗号或|分隔的行业名称

        Returns:
            行业名称列表
        """
        if not industry_str:
            return []
        # 兼容逗号和|分隔
        if "|" in industry_str:
            return [ind.strip() for ind in industry_str.split("|") if ind.strip()]
        return [ind.strip() for ind in industry_str.split(",") if ind.strip()]

    def get_output_dir_for_date(self, date_str: str) -> str:
        """
        获取指定日期的输出目录

        Args:
            date_str: 日期字符串，格式 YYYYMMDD

        Returns:
            目录路径
        """
        dir_path = os.path.join(self.OUTPUT_DIR, date_str)
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    def validate(self) -> bool:
        """
        验证配置是否完整

        Returns:
            是否验证通过
        """
        errors = []

        if not self.DEEPSEEK_API_KEY:
            errors.append("DEEPSEEK_API_KEY 未配置")

        if not self.TAVILY_API_KEY:
            errors.append("TAVILY_API_KEY 未配置")

        if not self.STOCK_LIST:
            errors.append("STOCK_LIST 未配置")

        if not self.INDUSTRY_LIST:
            errors.append("INDUSTRY_LIST 未配置")

        if errors:
            print("配置验证失败:")
            for error in errors:
                print(f"  - {error}")
            return False

        return True


# 全局配置实例
_config = None


def get_config(env_file: str = ".env") -> Config:
    """
    获取全局配置实例（单例模式）

    Args:
        env_file: 环境变量文件路径

    Returns:
        Config 实例
    """
    global _config
    if _config is None:
        _config = Config(env_file)
    return _config
