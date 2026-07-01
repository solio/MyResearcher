"""
SQLite 数据库模块 —— 替代 JSON 文件存储
无外部依赖，Python 内置 sqlite3。
"""
import sqlite3
import json
import threading
from typing import List, Dict, Optional
from datetime import datetime


DATA_DIR = "./output"
DB_PATH = f"{DATA_DIR}/db/data.db"

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """获取线程本地数据库连接（单例）"""
    import os as _os
    _os.makedirs(_os.path.dirname(DB_PATH), exist_ok=True)
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    """建表，幂等执行"""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT DEFAULT '',
            market_cap REAL DEFAULT 100.0
        );

        CREATE TABLE IF NOT EXISTS industries (
            name TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS research_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            search_provider TEXT DEFAULT 'tavily',
            is_backfill INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_runs_date ON research_runs(date);

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES research_runs(id),
            target_type TEXT NOT NULL,
            target_name TEXT NOT NULL,
            stock_code TEXT DEFAULT '',
            emotion_score REAL DEFAULT 0,
            analysis TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            failure_reason TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
        CREATE INDEX IF NOT EXISTS idx_results_stock ON results(stock_code, target_type);

        CREATE TABLE IF NOT EXISTS emotion_v3 (
            result_id INTEGER PRIMARY KEY REFERENCES results(id),
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            market_cap REAL DEFAULT 100.0,
            analysis_time TEXT DEFAULT '',
            news_score REAL DEFAULT 0,
            forum_score REAL DEFAULT 0,
            trading_score REAL DEFAULT 0,
            final_score REAL DEFAULT 0,
            rating_level TEXT DEFAULT '',
            rating_emoji TEXT DEFAULT '',
            confidence REAL DEFAULT 0,
            news_metrics_json TEXT DEFAULT '{}',
            forum_metrics_json TEXT DEFAULT '{}',
            trading_metrics_json TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            source TEXT DEFAULT '',
            source_type TEXT DEFAULT '',
            published_date TEXT DEFAULT '',
            post_time TEXT DEFAULT '',
            reply_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            read_count INTEGER DEFAULT 0,
            is_warning INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_news_url ON news_items(url);

        CREATE TABLE IF NOT EXISTS result_news (
            result_id INTEGER NOT NULL REFERENCES results(id),
            news_id INTEGER NOT NULL REFERENCES news_items(id),
            PRIMARY KEY (result_id, news_id)
        );

        CREATE TABLE IF NOT EXISTS emotion_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            date TEXT NOT NULL,
            hot_post_count INTEGER DEFAULT 0,
            explosive_post_count INTEGER DEFAULT 0,
            avg_reply_count REAL DEFAULT 0,
            avg_like_count REAL DEFAULT 0,
            guba_hot_reply_threshold REAL,
            guba_hot_like_threshold REAL,
            UNIQUE(stock_code, date)
        );
        CREATE INDEX IF NOT EXISTS idx_emotion_params_stock ON emotion_params(stock_code, date);
    """)
    db.commit()


# ========== 写入操作 ==========

def insert_run(date_str: str, search_provider: str = "tavily",
               is_backfill: bool = False) -> int:
    """创建一条 research_run，返回 run_id"""
    db = get_db()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = db.execute(
        "INSERT INTO research_runs (date, timestamp, search_provider, is_backfill) VALUES (?,?,?,?)",
        (date_str, ts, search_provider, 1 if is_backfill else 0)
    )
    db.commit()
    return cur.lastrowid


def insert_result(run_id: int, result: dict) -> int:
    """插入一条 result，同时写入 emotion_v3 和 news_items 关联。返回 result_id"""
    db = get_db()

    target_name = result.get("target_name", "")
    target_type = result.get("target_type", "stock")
    stock_code = ""
    if target_type == "stock" and "(" in target_name:
        # 从 "隆基绿能(601012)" 提取代码
        import re
        m = re.search(r'\((\d{6})\)', target_name)
        if m:
            stock_code = m.group(1)

    cur = db.execute(
        """INSERT INTO results (run_id, target_type, target_name, stock_code,
           emotion_score, analysis, summary, failure_reason, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (run_id, target_type, target_name, stock_code,
         result.get("emotion_score", 0),
         result.get("analysis", ""),
         result.get("summary", ""),
         result.get("failure_reason", ""),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    result_id = cur.lastrowid

    # emotion_v3
    ev3 = result.get("emotion_v3")
    if ev3 and isinstance(ev3, dict):
        db.execute(
            """INSERT INTO emotion_v3 (result_id, stock_code, stock_name, market_cap,
               analysis_time, news_score, forum_score, trading_score, final_score,
               rating_level, rating_emoji, confidence,
               news_metrics_json, forum_metrics_json, trading_metrics_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (result_id,
             ev3.get("stock_code", stock_code),
             ev3.get("stock_name", target_name.split("(")[0] if "(" in target_name else target_name),
             ev3.get("market_cap", 100.0),
             ev3.get("analysis_time", ""),
             ev3.get("news_score", 0),
             ev3.get("forum_score", 0),
             ev3.get("trading_score", 0),
             ev3.get("final_score", 0),
             ev3.get("rating_level", ""),
             ev3.get("rating_emoji", ""),
             ev3.get("confidence", 0),
             json.dumps(ev3.get("news_metrics") or {}, ensure_ascii=False),
             json.dumps(ev3.get("forum_metrics") or {}, ensure_ascii=False),
             json.dumps(ev3.get("trading_metrics") or {}, ensure_ascii=False))
        )

    # news_items + result_news
    news_list = result.get("news_list", [])
    if news_list:
        news_ids = upsert_news_items(news_list)
        for nid in news_ids:
            db.execute(
                "INSERT OR IGNORE INTO result_news (result_id, news_id) VALUES (?,?)",
                (result_id, nid)
            )

    db.commit()
    return result_id


def upsert_news_items(news_list: List[Dict]) -> List[int]:
    """批量去重插入新闻/帖子，返回 id 列表"""
    db = get_db()
    ids = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in news_list:
        url = item.get("url", "")
        if not url:
            continue

        # 先查是否存在（ON CONFLICT DO UPDATE 的 lastrowid 在无变更时返回 0）
        existing = db.execute(
            "SELECT id FROM news_items WHERE url = ?", (url,)
        ).fetchone()
        if existing:
            ids.append(existing["id"])
            continue

        title = (item.get("title") or "")[:500]
        content = (item.get("content") or "")[:5000]
        source = item.get("source", "")
        source_type = item.get("source_type", "")
        published_date = item.get("published_date", "")
        post_time = item.get("post_time", "")
        reply_count = item.get("reply_count", 0) or 0
        like_count = item.get("like_count", 0) or 0
        read_count = item.get("read_count", 0) or 0
        is_warning = 1 if item.get("is_warning") else 0

        cur = db.execute(
            """INSERT INTO news_items (url, title, content, source, source_type,
               published_date, post_time, reply_count, like_count, read_count,
               is_warning, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (url, title, content, source, source_type,
             published_date, post_time, reply_count, like_count, read_count,
             is_warning, now_str)
        )
        ids.append(cur.lastrowid)
    db.commit()
    return ids


def check_backfilled(date_str: str, stock_code: str) -> bool:
    """检查某日某股票是否已回填"""
    db = get_db()
    row = db.execute(
        """SELECT 1 FROM results r
           JOIN research_runs ru ON r.run_id = ru.id
           WHERE ru.date = ? AND r.stock_code = ? AND ru.is_backfill = 1
           LIMIT 1""",
        (date_str, stock_code)
    ).fetchone()
    return row is not None


# ========== 读取操作 ==========

def get_or_create_run(date_str: str, search_provider: str = "tavily") -> int:
    """获取已有 run_id 或创建新 run。用于增量保存场景"""
    db = get_db()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 查找今天非 backfill 的 run
    row = db.execute(
        "SELECT id FROM research_runs WHERE date=? AND is_backfill=0 ORDER BY id DESC LIMIT 1",
        (date_str,)
    ).fetchone()
    if row:
        return row[0]
    return insert_run(date_str, search_provider)


def get_yesterday_summary(target_name: str, yesterday_str: str) -> str:
    """获取前一日的分析摘要（供去重对比）"""
    db = get_db()
    row = db.execute(
        """SELECT r.summary FROM results r
           JOIN research_runs ru ON r.run_id = ru.id
           WHERE ru.date = ? AND r.target_name = ?
           LIMIT 1""",
        (yesterday_str, target_name)
    ).fetchone()
    return row["summary"] if row else ""


def get_latest_date() -> Optional[str]:
    """获取数据库中最新的投研日期"""
    db = get_db()
    row = db.execute(
        "SELECT date FROM research_runs WHERE is_backfill=0 ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return row["date"] if row else None


def get_stock_history(stock_code: str) -> List[Dict]:
    """获取某股票的历史情绪时间序列（供看板）"""
    db = get_db()
    rows = db.execute(
        """SELECT ru.date, r.emotion_score,
                  ev.final_score, ev.news_score, ev.forum_score, ev.trading_score,
                  ev.confidence, ev.rating_level, ev.rating_emoji,
                  ev.news_metrics_json, ev.forum_metrics_json, ev.trading_metrics_json,
                  ru.is_backfill
           FROM results r
           JOIN research_runs ru ON r.run_id = ru.id
           LEFT JOIN emotion_v3 ev ON ev.result_id = r.id
           WHERE r.stock_code = ? AND r.target_type = 'stock'
           ORDER BY ru.date ASC""",
        (stock_code,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_dates() -> List[str]:
    """获取所有投研日期"""
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT date FROM research_runs ORDER BY date ASC"
    ).fetchall()
    return [r["date"] for r in rows]


def get_stocks() -> List[Dict]:
    """获取股票列表"""
    db = get_db()
    return [dict(r) for r in db.execute("SELECT * FROM stocks").fetchall()]


def get_results_by_date(date_str: str) -> List[Dict]:
    """获取某日所有结果（含 emotion_v3 和 news_list）"""
    db = get_db()
    rows = db.execute(
        """SELECT r.*, ru.date as run_date, ru.timestamp as run_timestamp,
                  ru.search_provider
           FROM results r
           JOIN research_runs ru ON r.run_id = ru.id
           WHERE ru.date = ?
           ORDER BY r.id""",
        (date_str,)
    ).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        # 补 emotion_v3
        ev3_row = db.execute(
            "SELECT * FROM emotion_v3 WHERE result_id = ?", (r["id"],)
        ).fetchone()
        if ev3_row:
            ev3 = dict(ev3_row)
            ev3["news_metrics"] = json.loads(ev3.pop("news_metrics_json", "{}"))
            ev3["forum_metrics"] = json.loads(ev3.pop("forum_metrics_json", "{}"))
            ev3["trading_metrics"] = json.loads(ev3.pop("trading_metrics_json", "{}"))
            r["emotion_v3"] = ev3

        # 补 news_list
        news_rows = db.execute(
            """SELECT n.* FROM news_items n
               JOIN result_news rn ON n.id = rn.news_id
               WHERE rn.result_id = ?""",
            (r["id"],)
        ).fetchall()
        r["news_list"] = [dict(n) for n in news_rows]

        results.append(r)
    return results


def get_posts_by_stock_month(stock_code: str, year_month: str) -> dict:
    """获取某只股票某个月的所有帖子，按日期分组，供看板帖子列表。

    Args:
        stock_code: 股票代码如 '601012'
        year_month: 年月如 '202606'

    Returns:
        {"stock_code": "601012", "year_month": "202606",
         "available_months": [...], "dates": {"20260601": [posts], ...}}
    """
    db = get_db()

    # 获取有帖子的所有月份
    month_rows = db.execute(
        """SELECT DISTINCT substr(ru.date, 1, 6) as ym
           FROM research_runs ru
           JOIN results r ON r.run_id = ru.id
           JOIN result_news rn ON rn.result_id = r.id
           WHERE r.stock_code = ?
           ORDER BY ym DESC""",
        (stock_code,)
    ).fetchall()
    available_months = [m["ym"] for m in month_rows]

    # 获取指定月份的帖子
    rows = db.execute(
        """SELECT ru.date, ni.id, ni.url, ni.title, ni.content, ni.source,
                  ni.source_type, ni.post_time, ni.reply_count, ni.like_count,
                  ni.read_count
           FROM research_runs ru
           JOIN results r ON r.run_id = ru.id
           JOIN result_news rn ON rn.result_id = r.id
           JOIN news_items ni ON ni.id = rn.news_id
           WHERE r.stock_code = ? AND ru.date LIKE ?
           ORDER BY ru.date ASC, ni.read_count DESC""",
        (stock_code, year_month + "%")
    ).fetchall()

    dates: Dict[str, list] = {}
    for row in rows:
        d = dict(row)
        date_str = d.pop("date")
        dates.setdefault(date_str, []).append(d)

    return {
        "stock_code": stock_code,
        "year_month": year_month,
        "available_months": available_months,
        "dates": dates,
    }


def get_all_stock_results() -> List[Dict]:
    """获取所有股票结果（含 emotion_v3，供看板初始化）"""
    db = get_db()
    rows = db.execute(
        """SELECT r.id as result_id, r.target_name, r.stock_code, r.emotion_score,
                  ru.date, ru.is_backfill,
                  ev.final_score, ev.news_score, ev.forum_score, ev.trading_score,
                  ev.confidence, ev.rating_level,
                  ev.news_metrics_json, ev.forum_metrics_json, ev.trading_metrics_json
           FROM results r
           JOIN research_runs ru ON r.run_id = ru.id
           LEFT JOIN emotion_v3 ev ON ev.result_id = r.id
           WHERE r.target_type = 'stock' AND r.failure_reason = ''
           ORDER BY ru.date ASC, r.id ASC""",
    ).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        for key in ["news_metrics_json", "forum_metrics_json", "trading_metrics_json"]:
            if d.get(key):
                d[key.replace("_json", "")] = json.loads(d.pop(key))
            else:
                d.pop(key, None)
        results.append(d)
    return results


# ========== 情绪参数 ==========

def save_emotion_params(params: dict):
    """保存情绪参数历史（覆盖 emotion_params.json）"""
    db = get_db()
    stocks_data = params.get("stocks", {})
    updated_at = params.get("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    for code, sp in stocks_data.items():
        history = sp.get("history", [])
        if history:
            latest = history[-1]
            db.execute(
                """INSERT OR REPLACE INTO emotion_params
                   (stock_code, date, hot_post_count, explosive_post_count,
                    avg_reply_count, avg_like_count,
                    guba_hot_reply_threshold, guba_hot_like_threshold)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (code, updated_at[:10],
                 latest.get("hot_post_count", 0),
                 latest.get("explosive_post_count", 0),
                 latest.get("avg_reply_count", 0),
                 latest.get("avg_like_count", 0),
                 sp.get("guba_hot_reply_threshold"),
                 sp.get("guba_hot_like_threshold"))
            )
    db.commit()


def load_emotion_params() -> dict:
    """加载每个股票最新的情绪参数（对应原 emotion_params.json）"""
    db = get_db()
    rows = db.execute(
        """SELECT stock_code, guba_hot_reply_threshold, guba_hot_like_threshold,
                  date, hot_post_count, explosive_post_count, avg_reply_count, avg_like_count
           FROM emotion_params
           WHERE (stock_code, date) IN (
               SELECT stock_code, MAX(date) FROM emotion_params GROUP BY stock_code
           )"""
    ).fetchall()

    stocks = {}
    for r in rows:
        stocks[r["stock_code"]] = {
            "stock_code": r["stock_code"],
            "guba_hot_reply_threshold": r["guba_hot_reply_threshold"],
            "guba_hot_like_threshold": r["guba_hot_like_threshold"],
            "history": [{
                "date": r["date"],
                "hot_post_count": r["hot_post_count"],
                "explosive_post_count": r["explosive_post_count"],
                "avg_reply_count": r["avg_reply_count"],
                "avg_like_count": r["avg_like_count"],
            }]
        }
    return {"stocks": stocks, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def load_emotion_thresholds(stock_codes: List[str]) -> Dict[str, Dict]:
    """获取股票情绪阈值（供看板）"""
    db = get_db()
    if not stock_codes:
        return {}
    placeholders = ",".join("?" for _ in stock_codes)
    rows = db.execute(
        f"""SELECT stock_code, guba_hot_reply_threshold, guba_hot_like_threshold
            FROM emotion_params
            WHERE (stock_code, date) IN (
                SELECT stock_code, MAX(date) FROM emotion_params
                WHERE stock_code IN ({placeholders})
                GROUP BY stock_code
            )""",
        stock_codes
    ).fetchall()
    return {r["stock_code"]: {"hot_reply_threshold": r["guba_hot_reply_threshold"],
                               "hot_like_threshold": r["guba_hot_like_threshold"]}
            for r in rows}


# ========== 辅助 ==========

def seed_stocks_industries(stocks: List[Dict], industries: List[str]):
    """初始化股票和行业静态数据"""
    db = get_db()
    for s in stocks:
        db.execute(
            "INSERT OR REPLACE INTO stocks (code, name, industry, market_cap) VALUES (?,?,?,?)",
            (s["code"], s["name"], s.get("industry", ""), s.get("market_cap", 100.0))
        )
    for ind in industries:
        db.execute("INSERT OR IGNORE INTO industries (name) VALUES (?)", (ind,))
    db.commit()


def update_result(result_id: int, result: dict):
    """更新已有 result 的 emotion_v3 和分析，追加 news_items 关联"""
    db = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.execute(
        """UPDATE results SET emotion_score=?, analysis=?, summary=?,
           failure_reason=?, created_at=? WHERE id=?""",
        (result.get("emotion_score", 0),
         result.get("analysis", ""),
         result.get("summary", ""),
         result.get("failure_reason", ""),
         now_str,
         result_id)
    )

    # emotion_v3: delete old + insert new
    ev3 = result.get("emotion_v3")
    if ev3 and isinstance(ev3, dict):
        db.execute("DELETE FROM emotion_v3 WHERE result_id=?", (result_id,))
        target_name = result.get("target_name", "")
        import re
        stock_code = ""
        m = re.search(r'\((\d{6})\)', target_name)
        if m:
            stock_code = m.group(1)
        db.execute(
            """INSERT INTO emotion_v3 (result_id, stock_code, stock_name, market_cap,
               analysis_time, news_score, forum_score, trading_score, final_score,
               rating_level, rating_emoji, confidence,
               news_metrics_json, forum_metrics_json, trading_metrics_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (result_id,
             ev3.get("stock_code", stock_code),
             ev3.get("stock_name", target_name.split("(")[0] if "(" in target_name else target_name),
             ev3.get("market_cap", 100.0),
             ev3.get("analysis_time", ""),
             ev3.get("news_score", 0),
             ev3.get("forum_score", 0),
             ev3.get("trading_score", 0),
             ev3.get("final_score", 0),
             ev3.get("rating_level", ""),
             ev3.get("rating_emoji", ""),
             ev3.get("confidence", 0),
             json.dumps(ev3.get("news_metrics") or {}, ensure_ascii=False),
             json.dumps(ev3.get("forum_metrics") or {}, ensure_ascii=False),
             json.dumps(ev3.get("trading_metrics") or {}, ensure_ascii=False))
        )

    # 追加新 news_items 关联
    news_list = result.get("news_list", [])
    if news_list:
        news_ids = upsert_news_items(news_list)
        for nid in news_ids:
            db.execute(
                "INSERT OR IGNORE INTO result_news (result_id, news_id) VALUES (?,?)",
                (result_id, nid)
            )

    db.commit()


def get_active_tavily_key_index(default: int = 0) -> int:
    """获取上次使用的 Tavily Key 索引（持久化状态）"""
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT)"
    )
    row = db.execute(
        "SELECT value FROM app_state WHERE key='tavily_key_index'"
    ).fetchone()
    return int(row["value"]) if row else default


def set_active_tavily_key_index(index: int):
    """保存当前使用的 Tavily Key 索引"""
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT)"
    )
    db.execute(
        "INSERT OR REPLACE INTO app_state (key, value) VALUES ('tavily_key_index', ?)",
        (str(index),)
    )
    db.commit()


def get_db_stats() -> dict:
    """数据库统计信息"""
    db = get_db()
    tables = ["stocks", "industries", "research_runs", "results",
              "emotion_v3", "news_items", "result_news", "emotion_params"]
    stats = {}
    for t in tables:
        stats[t] = db.execute(f"SELECT COUNT(*) as n FROM {t}").fetchone()["n"]
    stats["db_size_kb"] = __import__("os").path.getsize(DB_PATH) // 1024
    return stats
