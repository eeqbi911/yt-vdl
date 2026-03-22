"""
订阅定时调度器 - 后台线程自动检查并下载UP主新视频
"""
import threading
import queue
import time
import sqlite3
import os
from datetime import datetime
from app.downloader import parse_video, detect_platform

DB_PATH = "/app/data/subscriptions.db"
_running = False
_scheduler_thread = None
_worker_threads = []
_check_queue = queue.Queue()


def _get_subs():
    """获取所有订阅（独立线程用）"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM subscriptions ORDER BY created_at DESC")
        rows = c.fetchall()
        return rows
    finally:
        conn.close()


def _update_time(sub_id: str):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("UPDATE subscriptions SET last_check = ? WHERE id = ?",
                    (datetime.now().isoformat(), sub_id))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _update_last_video(sub_id: str, video_url: str, title: str):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("""
            UPDATE subscriptions
            SET last_video_url = ?, last_video_title = ?, last_check = ?
            WHERE id = ?
        """, (video_url, title, datetime.now().isoformat(), sub_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[订阅] 更新失败: {e}")


def _record_history(task_id: str, url: str, title: str, status: str, sub_id: str):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("""
            INSERT INTO download_history (task_id, url, title, status, subscription_id)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, url, title, status, sub_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[订阅] 记录历史失败: {e}")


def _check_and_download(sub_id: str):
    """检查单个订阅，发现新视频则创建下载任务"""
    try:
        subs = _get_subs()
        sub = next((dict(s) for s in subs if dict(s)["id"] == sub_id), None)
        if not sub or not sub.get("enabled"):
            return

        url = sub["url"]
        fmt = sub.get("format_id") or "best"
        last_url = sub.get("last_video_url")
        sub_name = sub.get("name", "")

        result = parse_video(url)
        if "error" in result:
            _update_time(sub_id)
            return

        new_title = result.get("title", "无标题")
        new_url = result.get("webpage_url") or url

        if last_url and new_url == last_url:
            _update_time(sub_id)
            return

        print(f"[订阅] {sub_name} 发现新视频: {new_title}")

        # 创建下载任务
        from app.downloader.engine import create_task
        page_url = url if "video/" in url or "user/" in url else url
        task_id = create_task(page_url, fmt, new_title)
        _update_last_video(sub_id, new_url, new_title)
        _record_history(task_id, new_url, new_title, "pending", sub_id)

    except Exception as e:
        print(f"[订阅] 检查失败 {sub_id}: {e}")


def _scheduler_loop():
    """主循环 - 每30秒检查哪些订阅该触发"""
    while _running:
        try:
            subs = _get_subs()
            now = datetime.now()
            for sub in [dict(s) for s in subs]:
                if not sub.get("enabled"):
                    continue
                interval = sub.get("check_interval", 60)
                last_check = sub.get("last_check", "")
                if last_check:
                    try:
                        last = datetime.fromisoformat(last_check[:19])
                        if (now - last).total_seconds() < interval * 60:
                            continue
                    except Exception:
                        pass
                # 需要检查
                _check_queue.put(sub["id"])
        except Exception as e:
            print(f"[调度] 轮询失败: {e}")
        time.sleep(30)


def _worker_loop():
    """工作线程 - 处理队列中的订阅检查"""
    while _running:
        try:
            sub_id = _check_queue.get(timeout=5)
            _check_and_download(sub_id)
            _check_queue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[工作] 处理失败: {e}")


def start_scheduler():
    """启动订阅调度器"""
    global _running, _scheduler_thread, _worker_threads
    if _running:
        return
    _running = True

    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="SubScheduler")
    _scheduler_thread.start()

    for i in range(2):
        t = threading.Thread(target=_worker_loop, daemon=True, name=f"SubWorker-{i}")
        t.start()
        _worker_threads.append(t)

    print("[订阅调度] 已启动，每30秒检查订阅")


def stop_scheduler():
    global _running
    _running = False
    print("[订阅调度] 已停止")
