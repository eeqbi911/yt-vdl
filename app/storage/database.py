"""
存储模块 - SQLite 数据库
"""
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

DB_PATH = "data/subscriptions.db"
_db_lock = threading.Lock()


def get_db_path() -> str:
    from flask import current_app
    try:
        return current_app.config.get("DATABASE_PATH", DB_PATH)
    except RuntimeError:
        return DB_PATH


@contextmanager
def get_db():
    """线程安全的数据库连接"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """初始化数据库表"""
    with get_db() as conn:
        c = conn.cursor()
        # 订阅表
        c.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                platform TEXT DEFAULT '通用',
                format_id TEXT DEFAULT 'best',
                enabled INTEGER DEFAULT 1,
                check_interval INTEGER DEFAULT 60,
                last_check TEXT,
                last_video_url TEXT,
                last_video_title TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 已下载视频表
        c.execute("""
            CREATE TABLE IF NOT EXISTS downloaded_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id TEXT,
                url TEXT NOT NULL,
                title TEXT,
                downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
            )
        """)
        # 下载历史表
        c.execute("""
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                url TEXT NOT NULL,
                title TEXT,
                status TEXT,
                downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                subscription_id TEXT
            )
        """)
        # 视频去重表（用于批量下载去重）
        c.execute("""
            CREATE TABLE IF NOT EXISTS aweme (
                aweme_id TEXT PRIMARY KEY,
                title TEXT,
                author_name TEXT,
                download_time INTEGER,
                file_path TEXT,
                status TEXT DEFAULT 'completed'
            )
        """)
        conn.commit()


# ===== 订阅操作 =====

def add_subscription(id: str, name: str, url: str, platform: str = "通用",
                    format_id: str = "best", check_interval: int = 60) -> bool:
    """添加订阅"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO subscriptions (id, name, url, platform, format_id, check_interval)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id, name, url, platform, format_id, check_interval))
            return True
    except sqlite3.IntegrityError:
        return False


def get_subscriptions() -> List[sqlite3.Row]:
    """获取所有订阅"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM subscriptions ORDER BY created_at DESC")
        return c.fetchall()


def get_subscription(sub_id: str) -> Optional[sqlite3.Row]:
    """获取单个订阅"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
        return c.fetchone()


def update_subscription(sub_id: str, **kwargs) -> bool:
    """更新订阅"""
    allowed = ["name", "url", "platform", "format_id", "enabled", "check_interval"]
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [sub_id]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE subscriptions SET {set_clause} WHERE id = ?", values)
        return c.rowcount > 0


def delete_subscription(sub_id: str) -> bool:
    """删除订阅"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        return c.rowcount > 0


# ===== 下载历史 =====

def record_download(task_id: str, url: str, title: str, status: str,
                   subscription_id: str = None):
    """记录下载历史"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO download_history (task_id, url, title, status, subscription_id)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, url, title, status, subscription_id))


def get_download_history(limit: int = 100, offset: int = 0) -> tuple:
    """获取下载历史"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM download_history")
        total = c.fetchone()[0]
        c.execute("""
            SELECT * FROM download_history
            ORDER BY downloaded_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return total, c.fetchall()


# ===== 视频去重（批量下载用）=====

def is_video_downloaded(aweme_id: str) -> bool:
    """检查视频是否已下载"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM aweme WHERE aweme_id = ?", (aweme_id,))
        return c.fetchone() is not None


def add_downloaded_aweme(aweme_id: str, title: str, author_name: str,
                          file_path: str = "", status: str = "completed"):
    """记录已下载视频"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO aweme (aweme_id, title, author_name, download_time, file_path, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (aweme_id, title, author_name, int(datetime.now().timestamp()), file_path, status))
