"""
下载引擎 - 支持多平台
整合 yt-dlp 和抖音原生 API
"""

import os
import re
import time
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


def _normalize_url(url: str) -> str:
    """从完整分享链接中提取纯净的视频URL"""
    from urllib.parse import urlparse, parse_qs, unquote
    try:
        parsed = urlparse(url)
        # 微博长链接清理
        if "weibo.com" in parsed.netloc and "video/" in parsed.path:
            vid = parsed.path.split("video/")[-1].split("/")[0].split("?")[0]
            return f"https://weibo.com/video/{vid}"
        # 知乎链接清理
        if "zhihu.com" in parsed.netloc:
            from re import search as re_search
            m = re_search(r'/(answer|pin|p)/(\d+)', parsed.path)
            if m:
                return f"https://www.zhihu.com/{m.group(1)}/{m.group(2)}"
        # 保留原始URL
        return url
    except Exception:
        return url


def parse_video(raw_url: str) -> Dict[str, Any]:
    """
    解析视频信息
    优先使用平台原生 API，yt-dlp 作为备选，抖音额外使用 Playwright 降级
    """
    from app.downloader.douyin import DouyinClient, parse_douyin_url

    # 去除多余字段，只保留纯净URL
    url = _normalize_url(raw_url.strip())
    platform = detect_platform(url)

    # 抖音：三层降级
    if platform == "douyin":
        aweme_id = parse_douyin_url(url)
        if aweme_id and not aweme_id.startswith("/"):
            # 第1层：原生 API（需要 cookie）
            try:
                client = DouyinClient()
                info = _parse_douyin_sync(client, aweme_id)
                if info and info.get("video_url"):
                    return info
            except Exception as e:
                print(f"抖音API解析失败: {e}")

            # 第2层：yt-dlp（也需要 cookie）
            info = _parse_douyin_ytdlp(url)
            if info and not info.get("error"):
                return info

            # 第3层：Playwright 浏览器抓取（无需 cookie！）
            info = _scrape_douyin_playwright(url)
            if info and not info.get("error"):
                return info

            return info or {"error": "抖音解析失败，请稍后重试"}

    # 其他平台：yt-dlp
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


def _parse_douyin_ytdlp(url: str) -> Optional[Dict[str, Any]]:
    """第2层：尝试用 yt-dlp 解析抖音"""
    try:
        info = _parse_with_ytdlp(url, "douyin")
        if info and not info.get("error"):
            return info
    except Exception as e:
        print(f"抖音yt-dlp解析失败: {e}")
    return None


def _scrape_douyin_playwright(url: str) -> Optional[Dict[str, Any]]:
    """第3层：Playwright 浏览器抓取（无需 cookie）"""
    import re, json

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"error": "Playwright 未安装，无法解析抖音"}

    video_data = {"title": None, "video_url": None, "cover": None, "author": None, "duration": 0, "error": None}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            # 拦截 API 响应
            api_results = []

            def handle_response(response):
                url_path = response.url
                if ("douyin" in url_path or "byted" in url_path or "tiktok" in url_path) and "html" not in url_path:
                    api_results.append(response)

            page.on("response", handle_response)

            try:
                page.goto(url, timeout=45000, wait_until="commit")
            except Exception as e:
                print(f"Playwright goto: {e}")

            deadline = time.time() + 55
            while time.time() < deadline and not (video_data.get("video_url") and video_data.get("title")):
                page.wait_for_timeout(2000)
                for resp in api_results:
                    try:
                        body_bytes = resp.body()
                        body = body_bytes.decode("utf-8", errors="ignore") if isinstance(body_bytes, bytes) else str(body_bytes)
                        if not video_data.get("title"):
                            tm = re.search(r'"desc"\s*:\s*"([^"]{2,300})"', body)
                            if tm and len(tm.group(1)) > 5:
                                video_data["title"] = tm.group(1)
                        if not video_data.get("video_url"):
                            for pat in [
                                r"https?://[^\s\"\'\\]+\.douyinvod\.com[^\s\"\'\\]*",
                                r"https?://v\d+-[^\s\"\'\\]*\.douyin\.com[^\s\"\'\\]*",
                                r"https?://[^\s\"\'\\]+\.bytedvdal\.com[^\s\"\'\\]*",
                            ]:
                                mv = re.search(pat, body)
                                if mv and len(mv.group(0)) > 50:
                                    video_data["video_url"] = mv.group(0)
                                    break
                        if not video_data.get("duration"):
                            dm = re.search(r'"duration"\s*:\s*(\d{2,10})', body)
                            if dm:
                                d = int(dm.group(1))
                                if 5 < d < 7200:
                                    video_data["duration"] = d
                    except Exception:
                        pass
                if video_data.get("video_url") and video_data.get("title"):
                    break

            browser.close()
    except Exception as e:
        video_data["error"] = f"Playwright解析失败: {e}"
        import traceback
        traceback.print_exc()

    if not video_data["video_url"]:
        return {"error": video_data.get("error") or "未能获取视频地址"}

    # 构造格式
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
        "title": video_data.get("title", "未知标题"),
        "thumbnail": video_data.get("cover", ""),
        "duration": video_data.get("duration", 0),
        "duration_str": format_duration(video_data.get("duration", 0)),
        "uploader": video_data.get("author", ""),
        "platform": "douyin",
        "webpage_url": url,
        "video_url": video_data["video_url"],
        "formats": formats,
    }


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

    # 检查是否抖音视频直链（需要用浏览器下载）
    is_douyin_direct = bool(
        re.search(r"douyinvod\.com|bytedvdal\.com|aweme\.vod", url or "")
    )

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
            "is_douyin_direct": is_douyin_direct,
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
    is_douyin_direct = task.get("is_douyin_direct", False)
    format_id = task.get("format_id", "best")
    output_dir = os.environ.get("DOWNLOAD_DIR", "/app/downloads")
    task_title = task.get("title", "") or "video"
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_title)[:60]
    output_path = os.path.join(output_dir, f"{safe_title}.mp4")

    # 抖音直链：必须用Playwright下载（直链有签名时效）
    if is_douyin_direct:
        _download_douyin_playwright(task_id, url, output_path)
        with tasks_lock:
            active_downloads = max(0, active_downloads - 1)
        return

    # 其他平台：用yt-dlp
    cmd = [
        "yt-dlp", "--newline", "-f", format_id,
        "-o", os.path.join(output_dir, "%(title>.80)s.%(ext)s"),
        "--no-playlist", url,
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

            if "[download]" in line and "%" in line:
                try:
                    pct = float(line.split("%")[0].split()[-1])
                    with tasks_lock:
                        if task_id in tasks:
                            tasks[task_id]["progress"] = pct
                except (ValueError, IndexError):
                    pass

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
                files = sorted(Path(output_dir).glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
                for f in files:
                    if safe_title in f.name or task_title[:20] in f.name:
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


def _download_douyin_playwright(task_id: str, video_url: str, output_path: str):
    """用Playwright从页面提取视频直链后下载"""
    import time, re
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["status"] = "error"
                tasks[task_id]["error"] = "Playwright未安装"
        return

    with tasks_lock:
        tasks[task_id]["progress"] = 5

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            # 先访问主页建立session
            try:
                page.goto("https://www.douyin.com/", timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
            except Exception:
                pass

            # 提取视频ID
            vid = str(video_url)
            for pattern in ["/video/(\d+)", "(\d{17,19})"]:
                m = re.search(pattern, vid)
                if m:
                    vid = m.group(1)
                    break

            # 访问视频页面
            try:
                page.goto(f"https://www.douyin.com/video/{vid}", timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(6000)
            except Exception:
                pass

            # 从页面提取视频直链
            video_src = page.evaluate("""
                () => {
                    const v = document.querySelector("video");
                    if (v && v.src && v.src.length > 20) return v.src;
                    const all = document.querySelectorAll("*");
                    for (const el of all) {
                        const src = el.src || el.href || "";
                        if ((src.includes("douyinvod") || src.includes("aweme.vod")) && src.length > 50) {
                            return decodeURIComponent(src);
                        }
                    }
                    return null;
                }
            """)

            browser.close()

        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["progress"] = 40

        if not video_src:
            import subprocess
            result = subprocess.run(
                ["yt-dlp", "-f", "best", "--no-warnings", "-o", output_path, f"https://www.douyin.com/video/{vid}"],
                capture_output=True, text=True, timeout=60
            )
            with tasks_lock:
                if task_id in tasks:
                    if result.returncode == 0:
                        tasks[task_id]["status"] = "completed"
                        tasks[task_id]["progress"] = 100
                        tasks[task_id]["file_path"] = output_path
                    else:
                        tasks[task_id]["status"] = "error"
                        tasks[task_id]["error"] = f"下载失败: {result.stderr[:80]}"
            return

        # 用httpx下载视频
        import httpx
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
        }

        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["progress"] = 50

        response = httpx.get(video_src, headers=headers, follow_redirects=True, timeout=60)
        total = int(response.headers.get("content-length", 0))

        with open(output_path, "wb") as f:
            downloaded = 0
            for chunk in response.iter_bytes(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = min(50 + int(45 * downloaded / total), 95)
                        with tasks_lock:
                            if task_id in tasks:
                                tasks[task_id]["progress"] = pct

        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["progress"] = 100
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["file_path"] = output_path

    except Exception as e:
        import traceback
        traceback.print_exc()
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]["status"] = "error"
                tasks[task_id]["error"] = f"下载失败: {e}"

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
