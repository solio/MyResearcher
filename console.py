"""
终端彩色输出模块
用于高亮显示错误信息
"""


class Colors:
    """颜色常量"""
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"


def print_error(message: str):
    """打印红色错误信息"""
    print(f"{Colors.RED}{Colors.BOLD}{message}{Colors.RESET}")


def print_warning(message: str):
    """打印黄色警告信息"""
    print(f"{Colors.YELLOW}{message}{Colors.RESET}")


def print_success(message: str):
    """打印绿色成功信息"""
    print(f"{Colors.GREEN}{message}{Colors.RESET}")


def print_info(message: str):
    """打印蓝色信息"""
    print(f"{Colors.CYAN}{message}{Colors.RESET}")


def highlight_deepseek_error(error_msg: str) -> str:
    """
    高亮显示 DeepSeek 错误信息

    Args:
        error_msg: 错误信息

    Returns:
        友好的错误描述
    """
    error_lower = str(error_msg).lower()

    if "payment required" in error_lower or "402" in str(error_msg):
        return f"{Colors.RED}{Colors.BOLD}【需要付费】DeepSeek API 额度不足或账户余额不足{Colors.RESET}"
    elif "unauthorized" in error_lower or "401" in str(error_msg):
        return f"{Colors.RED}{Colors.BOLD}【认证失败】DeepSeek API Key 无效或已过期{Colors.RESET}"
    elif "rate limit" in error_lower or "429" in str(error_msg):
        return f"{Colors.YELLOW}{Colors.BOLD}【频率超限】DeepSeek API 请求过于频繁，请稍后再试{Colors.RESET}"
    elif "timeout" in error_lower:
        return f"{Colors.YELLOW}{Colors.BOLD}【请求超时】DeepSeek API 响应超时{Colors.RESET}"
    elif "context window" in error_lower or "maximum context" in error_lower:
        return f"{Colors.RED}{Colors.BOLD}【上下文超限】输入内容超过模型最大长度{Colors.RESET}"
    else:
        return f"{Colors.RED}{Colors.BOLD}【LLM 错误】{error_msg}{Colors.RESET}"


def highlight_search_error(error_msg: str) -> str:
    """
    高亮显示搜索 API 错误信息

    Args:
        error_msg: 错误信息

    Returns:
        友好的错误描述
    """
    error_lower = str(error_msg).lower()

    if "payment required" in error_lower or "402" in str(error_msg):
        return f"{Colors.RED}{Colors.BOLD}【需要付费】Tavily API 额度不足{Colors.RESET}"
    elif "unauthorized" in error_lower or "401" in str(error_msg):
        return f"{Colors.RED}{Colors.BOLD}【认证失败】Tavily API Key 无效{Colors.RESET}"
    elif "rate limit" in error_lower or "429" in str(error_msg):
        return f"{Colors.YELLOW}{Colors.BOLD}【频率超限】Tavily API 请求过于频繁{Colors.RESET}"
    elif "timeout" in error_lower:
        return f"{Colors.YELLOW}{Colors.BOLD}【请求超时】搜索请求超时{Colors.RESET}"
    else:
        return f"{Colors.RED}{Colors.BOLD}【搜索错误】{error_msg}{Colors.RESET}"
