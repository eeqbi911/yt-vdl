"""
下载引擎 - 支持多平台
整合 yt-dlp 和抖音原生 API
"""

import os
import re
import uuid
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# 全局任务状态
tasks: Dict[str, Dict[str, Any]] = {}
tasks_lock = threading.Lock()
active_downloads = 0


def get_ytdlp_version() -> str:
    """获取 yt-dlp 版本"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def detect_platform(url: str) -> str:
    """检测视频平台"""
    if "douyin.com" in url or "v.douyin.com" in url:
        return "douyin"
    elif "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    elif "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "kuaishou.com" in url:
        return "kuaishou"
    elif "weibo.com" in url or "video.weibo.com" in url:
        return "weibo"
    elif "xiaohongshu.com" in url or "xhslink.com" in url:
        return "xiaohongshu"
    elif "zhihu.com" in url:
        return "zhihu"
    elif "v.qq.com" in url:
        return "qqvideo"
    elif "iqiyi.com" in url:
        return "iqiyi"
    elif "youku.com" in url:
        return "youku"
    else:
        return "unknown"


def format_size(bytes_size: Any) -> str:
    """格式化文件大小"""
    if bytes_size is None or bytes_size <= 0:
        return "未知"
    try:
        bytes_size = float(bytes_size)
    except (ValueError, TypeError):
        return "未知"
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f}TB"


def format_duration(seconds: Any) -> str:
    """格式化时长"""
    if not seconds:
        return "00:00"
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        return "00:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def resolution_rank(res: str) -> int:
    """分辨率排序（越高越高清）"""
    rank_map = {
        "8k": 80, "4k": 70, "2160p": 60, "1440p": 50,
        "1080p": 40, "720p": 30, "480p": 20, "360p": 10, "240p": 5,
    }
    res_lower = res.lower() if res else ""
    for key, rank in rank_map.items():
        if key in res_lower:
            return rank
    return 0


def parse_video(url: str) -> Dict[str, Any]:
    """
    解析视频信息
    优先使用平台原生 API，yt-dlp 作为备选
    """
    from app.downloader.douyin import DouyinClient, parse_douyin_url

    platform = detect_platform(url)

    # 抖音：优先使用原生 API
    if platform == "douyin":
        aweme_id = parse_douyin_url(url)
        if aweme_id and not aweme_id.startswith("/"):
            client = DouyinClient()
            info = _parse_douyin_sync(client, aweme_id)
            if info:
                return info

    # 使用 yt-dlp 解析（通用方案）
    return _parse_with_ytdlp(url, platform)


def _parse_douyin_sync(client, aweme_id: str) -> Optional[Dict[str, Any]]:
    """同步解析抖音视频"""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        info = loop.run_until_complete(client.get_video_info(aweme_id))
        loop.close()
        if info:
            return _build_douyin_response(info)
    except Exception as e:
        print(f"抖音原生 API 解析失败: {e}")
    return None


def _build_douyin_response(info: Dict[str, Any]) -> Dict[str, Any]:
    """构建抖音解析响应"""
    video_url = info.get("video_url", "")
    duration = info.get("duration", 0)

    # 构造格式选项
    formats = []
    for res in ["1080p", "720p", "480p", "360p"]:
        formats.append({
            "format_id": res,
            "label": f"{res} (mp4)",
            "ext": "mp4",
            "resolution": res,
            "filesize": 0,
        })

    return {
        "title": info.get("title", "未知标题"),
        "thumbnail": info.get("cover_url", ""),
        "duration": duration,
        "duration_str": format_duration(duration),
        "uploader": info.get("author", {}).get("nickname", ""),
        "platform": "douyin",
        "webpage_url": info.get("video_url", ""),
        "video_url": video_url,
        "formats": formats,
    }


def _parse_with_ytdlp(url: str, platform: str) -> Dict[str, Any]:
    """使用 yt-dlp 解析视频"""
    cmd = ["yt-dlp", "--dump-json", "--no-warnings", "--no-playlist", url]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": f"解析失败: {result.stderr[:200]}"}

        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return {"error": "解析失败：无返回数据"}

        import json
        data = json.loads(lines[0])

        # 解析格式
        formats = []
        seen = set()
        for f in data.get("formats", []):
            vcodec = f.get("vcodec", "none")
            if vcodec == "none":
                continue
            res = f.get("resolution", "") or ""
            ext = f.get("ext", "")
            fs = f.get("filesize") or f.get("filesize_approx") or 0
            fid = f.get("format_id", "")

            if res and res not in seen:
                seen.add(res)
                label = f"{res} ({ext})"
                if fs:
                    label += f" - {format_size(fs)}"
                formats.append({
                    "format_id": fid,
                    "label": label,
                    "ext": ext,
                    "resolution": res,
                    "filesize": fs,
                })

        # 按清晰度排序
        formats.sort(key=lambda x: resolution_rank(x["resolution"]), reverse=True)
        formats = formats[:12]

        return {
            "title": data.get("title", "未知标题"),
            "thumbnail": data.get("thumbnail") or "",
            "duration": data.get("duration", 0),
            "duration_str": format_duration(data.get("duration", 0)),
            "uploader": data.get("uploader") or "",
            "platform": platform,
            "webpage_url": data.get("webpage_url", url),
            "formats": formats,
        }

    except subprocess.TimeoutExpired:
        return {"error": "解析超时，请检查URL或网络"}
    except json.JSONDecodeError:
        return {"error": "解析失败，无法获取视频信息"}
    except Exception as e:
        return {"error": str(e)}


# ===== 下载任务管理 =====

def create_task(url: str, format_id: str = "best", title: str = "") -> str:
    """创建下载任务"""
    global active_downloads

    task_id = str(uuid.uuid4())[:8]

    with tasks_lock:
        tasks[task_id] = {
            "id": task_id,
            "url": url,
            "title": title or "下载任务",
            "format_id": format_id,
            "status": "pending",
            "progress": 0,
            "progress_text": "",
            "created_at": datetime.now().isoformat(),
            "file_path": None,
            "error": None,
            "process": None,
            "created_ts": datetime.now().timestamp(),
        }

    _start_download_thread(task_id)
    return task_id


def _start_download_thread(task_id: str):
    """启动下载线程"""
    global active_downloads

    thread = threading.Thread(target=_download_worker, args=(task_id,), daemon=True)
    thread.start()


def _download_worker(task_id: str):
    """下载工作线程"""
    global active_downloads

    with tasks_lock:
        if task_id not in tasks:
            return
        task = tasks[task_id]
        task["status"] = "downloading"
        active_downloads += 1

    url = task["url"]
    format_id = task.get("format_id", "best")
    output_dir = os.environ.get("DOWNLOAD_DIR", "/app/downloads")
    output_template = os.path.join(output_dir, "%(title>.80)s.%(ext)s")

    cmd = [
        "yt-dlp", "--newline", "-f", format_id,
        "-o", output_template, "--no-playlist", url,
    ]

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )

        with tasks_lock:
            tasks[task_id]["process"] = process

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            # 解析进度
            if "[download]" in line and "%" in line:
                try:
                    pct = float(line.split("%")[0].split()[-1])
                    with tasks_lock:
                        if task_id in tasks:
                            tasks[task_id]["progress"] = pct
                except (ValueError, IndexError):
                    pass

            # 更新状态
            with tasks_lock:
                if task_id not in tasks:
                    process.terminate()
                    return
                if tasks[task_id]["status"] == "cancelled":
                    process.terminate()
                    return

        process.wait()

        with tasks_lock:
            if task_id not in tasks:
                return

            if process.returncode == 0:
                # 找下载的文件
                files = sorted(Path(output_dir).glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
                task_title = tasks[task_id].get("title", "")[:20]
                for f in files:
                    if task_title and task_title in f.name:
                        tasks[task_id]["status"] = "completed"
                        tasks[task_id]["progress"] = 100
                        tasks[task_id]["file_path"] = str(f)
                        break
                else:
                    tasks[task_id]["status"] = "completed"
                    tasks[task_id]["progress"] = 100
            else:
                tasks[task_id]["status"] = "error"
                tasks[task_id]["error"] = f"下载失败 (code {process.returncode})"

            tasks[task_id]["process"] = None
            active_downloads = max(0, active_downloads - 1)

    except Exception as e:
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["status"] = "error"
                tasks[task_id]["error"] = str(e)
                tasks[task_id]["process"] = None
                active_downloads = max(0, active_downloads - 1)


def get_tasks() -> list:
    """获取所有任务"""
    with tasks_lock:
        return list(tasks.values())


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取单个任务"""
    with tasks_lock:
        return tasks.get(task_id)


def cancel_task(task_id: str) -> bool:
    """取消任务"""
    with tasks_lock:
        if task_id not in tasks:
            return False
        task = tasks[task_id]
        if task["status"] == "downloading" and task.get("process"):
            task["process"].terminate()
        task["status"] = "cancelled"
        return True


def delete_task(task_id: str) -> bool:
    """删除任务"""
    with tasks_lock:
        if task_id in tasks:
            cancel_task(task_id)
            del tasks[task_id]
            return True
        return False
