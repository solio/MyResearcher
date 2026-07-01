"""
一次性数据迁移脚本：将 output/ 下所有 JSON 文件导入 SQLite
幂等：同一天的数据不会重复导入
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime

from database import (
    init_db, get_db, insert_run, insert_result,
    seed_stocks_industries, get_db_stats,
)
from config import get_config
from logger import get_logger

logger = get_logger()


def extract_stock_code(target_name: str) -> str:
    """从 '隆基绿能(601012)' 提取 '601012'"""
    m = re.search(r'\((\d{6})\)', target_name)
    return m.group(1) if m else ""


def get_already_imported_dates(db) -> set:
    """获取已导入的日期集合"""
    rows = db.execute("SELECT DISTINCT date FROM research_runs").fetchall()
    return {r["date"] for r in rows}


def find_data_files(output_dir: str):
    """扫描所有 YYYYMMDD/*数据.json 文件"""
    data_dir = Path(output_dir)
    files = []
    for date_dir in sorted(data_dir.iterdir()):
        if not date_dir.is_dir() or not re.match(r'^\d{8}$', date_dir.name):
            continue
        for f in sorted(date_dir.iterdir()):
            if f.name.endswith("数据.json") and not f.name.endswith("搜索数据.json"):
                files.append(f)
    return files


def migrate():
    config = get_config()
    init_db()
    db = get_db()

    # 种子数据
    seed_stocks_industries(config.STOCK_LIST, config.INDUSTRY_LIST)
    logger.info("已写入 stocks + industries")

    # 跳过已导入的日期
    imported = get_already_imported_dates(db)
    if imported:
        logger.info(f"已有 {len(imported)} 个日期已导入: {sorted(imported)}")

    # 扫描数据文件
    data_files = find_data_files(config.OUTPUT_DIR)
    logger.info(f"找到 {len(data_files)} 个数据文件")

    new_count = 0
    skip_count = 0
    total_news = 0

    for fpath in data_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"读取失败: {fpath} — {e}")
            continue

        date_str = data.get("date", "")
        if not date_str:
            date_str = fpath.parent.name  # fallback: 目录名即日期

        if date_str in imported:
            skip_count += 1
            continue

        is_backfill = data.get("backfill", False)
        search_provider = data.get("search_provider", "tavily")
        timestamp = data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        try:
            run_id = insert_run(date_str, search_provider, is_backfill)
            # 覆盖 timestamp（insert_run 用的是当前时间）
            db.execute("UPDATE research_runs SET timestamp=? WHERE id=?",
                       (timestamp, run_id))
        except Exception as e:
            logger.error(f"创建 run 失败 ({date_str}): {e}")
            continue

        for result in data.get("results", []):
            try:
                insert_result(run_id, result)
            except Exception as e:
                logger.warning(f"  插入结果失败 {result.get('target_name', '?')}: {e}")

        db.commit()
        imported.add(date_str)
        new_count += 1

        # 统计
        news_count = sum(
            len(r.get("news_list", [])) for r in data.get("results", [])
        )
        total_news += news_count

        if new_count % 10 == 0:
            logger.info(f"  进度: {new_count} 天已导入...")

    logger.info(f"迁移完成: 新增 {new_count} 天, 跳过 {skip_count} 天, 共 ~{total_news} 条新闻/帖子")
    logger.info(f"数据库统计: {get_db_stats()}")


def migrate_emotion_params():
    """导入 emotion_params.json（如果存在）"""
    from database import save_emotion_params
    config = get_config()
    params_path = os.path.join(config.OUTPUT_DIR, "emotion_params.json")
    if not os.path.exists(params_path):
        logger.warning(f"情绪参数文件不存在: {params_path}")
        return

    with open(params_path, "r", encoding="utf-8") as f:
        params = json.load(f)

    save_emotion_params(params)
    logger.info(f"情绪参数已导入: {len(params.get('stocks', {}))} 只股票")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    migrate()
    migrate_emotion_params()

    stats = get_db_stats()
    print(f"\n数据库: output/data.db ({stats['db_size_kb']} KB)")
    for k, v in stats.items():
        if k != "db_size_kb":
            print(f"  {k}: {v}")
