"""
配置文件
"""
import os


class Config:
    """默认配置"""
    SECRET_KEY = os.environ.get("SECRET_KEY", "yt-vdl-secret-2026")
    DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/app/downloads")
    MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", "3"))
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/subscriptions.db")
    SUBSCRIPTION_INTERVAL = int(os.environ.get("SUBSCRIPTION_INTERVAL_MINUTES", "60"))

    # 抖音 Cookie（可选，不填也能下载部分内容）
    DOUYIN_MS_TOKEN = os.environ.get("DOUYIN_MS_TOKEN", "")
    DOUYIN_TTWID = os.environ.get("DOUYIN_TTWID", "")
    DOUYIN_ODIN_TT = os.environ.get("DOUYIN_ODIN_TT", "")
    DOUYIN_CSrf = os.environ.get("DOUYIN_CSRF_TOKEN", "")

    # OpenAI API（视频转写用，可选）
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    # 代理（可选）
    HTTP_PROXY = os.environ.get("HTTP_PROXY", "")
