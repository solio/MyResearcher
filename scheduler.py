"""
定时任务调度模块
负责定时执行投研任务
"""
import os
import time
import schedule
from datetime import datetime
from typing import Optional

from config import Config, get_config
from researcher import StockResearcher
from logger import get_logger, setup_logger

logger = get_logger()


class ResearchScheduler:
    """投研任务调度器"""

    def __init__(self, config: Optional[Config] = None):
        """
        初始化调度器

        Args:
            config: 配置对象，为 None 时自动加载
        """
        self.config = config or get_config()

        # 设置日志
        setup_logger(log_dir=os.path.join(self.config.OUTPUT_DIR, "logs"),
                     log_level=self.config.LOG_LEVEL)

        self.researcher = StockResearcher(self.config)
        self.is_running = False

    def run_once(self):
        """执行一次投研任务"""
        logger.info("=" * 60)
        logger.info(f"执行投研任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        try:
            # 运行所有研究
            results = self.researcher.run_all()

            # 保存结果
            if results:
                self.researcher.save_results(results)

            logger.info(f"任务完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            logger.error(f"任务执行出错: {e}", exc_info=True)

    def start(self):
        """启动定时任务"""
        # 验证配置
        if not self.config.validate():
            logger.error("配置验证失败，无法启动")
            return

        interval = self.config.CHECK_INTERVAL_MINUTES
        logger.info(f"投研助手已启动")
        logger.info(f"检查间隔: {interval} 分钟")
        logger.info(f"按 Ctrl+C 停止\n")

        # 先执行一次
        self.run_once()

        # 设置定时任务
        schedule.every(interval).minutes.do(self.run_once)

        self.is_running = True

        # 运行调度循环
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            logger.info("\n\n收到停止信号，正在退出...")
            self.is_running = False

    def stop(self):
        """停止定时任务"""
        self.is_running = False


def main():
    """主函数"""
    scheduler = ResearchScheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
