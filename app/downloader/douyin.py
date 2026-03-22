"""
抖音 API 客户端
支持无需登录 Cookie 即可获取视频信息和无水印下载链接
"""

import json
import random
import time
import httpx
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, urlencode

from app.auth.xbogus import XBogus


class DouyinClient:
    """抖音 API 客户端"""

    BASE_URL = "https://www.douyin.com"
    UA_LIST = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    ]

    def __init__(
        self,
        ms_token: str = "",
        ttwid: str = "",
        odin_tt: str = "",
        csrf_token: str = "",
        proxy: str = "",
    ):
        self.ms_token = ms_token
        self.ttwid = ttwid
        self.odin_tt = odin_tt
        self.csrf_token = csrf_token
        self.proxy = proxy
        self.ua = random.choice(self.UA_LIST)

    def _get_cookies(self) -> Dict[str, str]:
        """构造 Cookie 字典"""
        cookies = {}
        if self.ms_token:
            cookies["msToken"] = self.ms_token
        if self.ttwid:
            cookies["ttwid"] = self.ttwid
        if self.odin_tt:
            cookies["odin_tt"] = self.odin_tt
        if self.csrf_token:
            cookies["passport_csrf_token"] = self.csrf_token
        return cookies

    def _get_headers(self) -> Dict[str, str]:
        """构造请求头"""
        return {
            "User-Agent": self.ua,
            "Referer": "https://www.douyin.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def _sign_url(self, url: str) -> str:
        """对 URL 进行 X-Bogus 签名"""
        parsed = urlparse(url)
        # 只需要对 path + query 签名
        path_query = f"{parsed.path}?{parsed.query}"
        signer = XBogus(user_agent=self.ua)
        signed_path, _, _ = signer.build(path_query)
        # 重新构造完整 URL
        return f"{self.BASE_URL}{signed_path}"

    async def get_video_info(self, aweme_id: str) -> Optional[Dict[str, Any]]:
        """
        获取视频详情

        Args:
            aweme_id: 视频 ID (如 7619257181032887899)

        Returns:
            视频信息字典，包含标题、封面、时长、无水印链接等
        """
        url = f"{self.BASE_URL}/aweme/v1/aweme/detail/?aweme_id={aweme_id}"
        signed_url = self._sign_url(url)

        cookies = self._get_cookies()
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(signed_url, headers=headers, cookies=cookies)
                data = resp.json()

                aweme_detail = data.get("aweme_detail", {})
                if not aweme_detail:
                    return None

                return self._parse_aweme(aweme_detail)
        except Exception as e:
            print(f"获取视频信息失败: {e}")
            return None

    def _parse_aweme(self, aweme: Dict[str, Any]) -> Dict[str, Any]:
        """解析视频数据"""
        video = aweme.get("video", {})
        author = aweme.get("author", {})
        music = aweme.get("music", {})

        # 获取无水印视频链接
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        no_watermark_url = None

        for url in url_list:
            if "watermark=0" in url or "watermark=1" not in url:
                no_watermark_url = url
                break

        # 如果没有找到无水印链接，尝试构造
        if not no_watermark_url:
            video_uri = play_addr.get("uri") or video.get("vid")
            if video_uri:
                no_watermark_url = self._build_no_watermark_url(video_uri)

        # 封面图
        thumbnails = video.get("thumbnails", [])
        cover_url = thumbnails[0].get("url_list", [None])[0] if thumbnails else None
        if not cover_url:
            cover_url = video.get("cover", {}).get("url_list", [None])[0]

        return {
            "aweme_id": aweme.get("aweme_id", ""),
            "title": aweme.get("desc", "未知标题"),
            "description": aweme.get("desc", ""),
            "create_time": aweme.get("create_time", 0),
            "duration": video.get("duration", 0) // 1000,  # 毫秒转秒
            "cover_url": cover_url,
            "video_url": no_watermark_url,
            "width": video.get("width", 0),
            "height": video.get("height", 0),
            "author": {
                "uid": author.get("uid", ""),
                "nickname": author.get("nickname", ""),
                "unique_id": author.get("unique_id", ""),
                "avatar_url": author.get("avatar_url", {}).get("url_list", [None])[0],
            },
            "music": {
                "id": music.get("id", ""),
                "title": music.get("title", ""),
                "author": music.get("author", ""),
                "url": music.get("play_url", {}).get("url_list", [None])[0],
            },
            "platform": "douyin",
        }

    def _build_no_watermark_url(self, video_uri: str) -> str:
        """构造无水印视频 URL"""
        params = {
            "video_id": video_uri,
            "ratio": "1080p",
            "line": "0",
            "is_play_url": "1",
            "watermark": "0",
            "source": "PackSourceEnum_PUBLISH",
        }
        path = "/aweme/v1/play/"
        query = urlencode(params)
        unsigned_url = f"{self.BASE_URL}{path}?{query}"
        signed_url, _, _ = XBogus(user_agent=self.ua).build(unsigned_url)
        return signed_url

    async def get_user_videos(
        self,
        sec_uid: str,
        mode: str = "post",
        max_count: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        获取用户视频列表

        Args:
            sec_uid: 用户 sec_uid
            mode: post/like/mix/music
            max_count: 最大获取数量

        Returns:
            视频列表
        """
        endpoint_map = {
            "post": "/aweme/v1/aweme/post/",
            "like": "/aweme/v1/like/list/",
            "mix": "/aweme/v1/mix/list/",
            "music": "/aweme/v1/music/list/",
        }

        endpoint = endpoint_map.get(mode, endpoint_map["post"])
        cursor = 0
        videos = []
        has_more = True

        while len(videos) < max_count and has_more:
            url = f"{self.BASE_URL}{endpoint}?sec_user_id={sec_uid}&max_cursor={cursor}&count=20"
            signed_url = self._sign_url(url)

            cookies = self._get_cookies()
            headers = self._get_headers()

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(signed_url, headers=headers, cookies=cookies)
                    data = resp.json()

                    aweme_list = data.get("aweme_list", [])
                    for aweme in aweme_list:
                        videos.append(self._parse_aweme(aweme))
                        if len(videos) >= max_count:
                            break

                    has_more = data.get("has_more", False)
                    cursor = data.get("max_cursor", 0)

            except Exception as e:
                print(f"获取用户视频失败: {e}")
                break

        return videos[:max_count]


def parse_douyin_url(url: str) -> Optional[str]:
    """
    从各种抖音 URL 格式中提取 aweme_id 或 sec_uid

    支持格式:
    - https://www.douyin.com/video/7619257181032887899
    - https://v.douyin.com/SV3hPwuY8b8/
    - https://www.douyin.com/note/7341234567890123456
    """
    parsed = urlparse(url)

    # 短链接 (v.douyin.com)
    if "v.douyin.com" in parsed.netloc:
        return url  # 需要重定向获取真实 URL

    # 视频链接
    if "/video/" in parsed.path:
        video_id = parsed.path.split("/video/")[-1].split("/")[0].split("?")[0]
        return video_id

    # 图文链接
    if "/note/" in parsed.path:
        note_id = parsed.path.split("/note/")[-1].split("/")[0].split("?")[0]
        return note_id

    # 用户主页
    if "/user/" in parsed.path:
        return parsed.path  # 返回完整路径，后续处理

    return None
