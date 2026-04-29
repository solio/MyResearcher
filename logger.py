"""
日志模块
负责记录程序运行日志
"""
import logging
import os
from datetime import datetime
from pythonjsonlogger import jsonlogger


def setup_logger(name: str = "researcher", log_dir: str = "./logs",
                 log_level: str = "INFO") -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录
        log_level: 日志级别

    Returns:
        配置好的 Logger 实例
    """
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)

    # 获取 logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（按日期）
    today = datetime.now().strftime("%Y%m%d")
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f"{today}.log"),
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# 全局日志实例
_logger = None


def get_logger() -> logging.Logger:
    """
    获取全局日志实例

    Returns:
        Logger 实例
    """
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger
