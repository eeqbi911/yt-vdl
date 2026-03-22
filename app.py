#!/usr/bin/env python3
"""
yt-vdl - 视频下载 Web 管理界面
入口文件
"""

import os
import sys

# 确保 app 目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request

from app.config import Config


def create_app(config_class=Config):
    """应用工厂"""
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")
    app.config.from_object(config_class)

    # 确保数据目录存在
    os.makedirs("data", exist_ok=True)
    os.makedirs(app.config["DOWNLOAD_DIR"], exist_ok=True)

    # 初始化数据库
    from app.storage.database import init_db
    init_db()

    # 注册蓝图
    from app.routes.tasks import tasks_bp
    app.register_blueprint(tasks_bp, url_prefix="/api")

    # 页面路由
    @app.route("/")
    def index():
        return render_template("index.html")

    # API 路由
    @app.route("/api/info")
    def api_info():
        from app.downloader import get_ytdlp_version
        return jsonify({
            "version": get_ytdlp_version(),
            "platform": "Linux",
            "download_dir": app.config["DOWNLOAD_DIR"],
            "max_concurrent": app.config["MAX_CONCURRENT"],
            "douyin_supported": True,
        })

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    @app.route("/api/platforms")
    def api_platforms():
        return jsonify({
            "platforms": [
                {"id": "douyin", "name": "抖音", "icon": "🎵"},
                {"id": "bilibili", "name": "B站", "icon": "📺"},
                {"id": "youtube", "name": "YouTube", "icon": "▶"},
                {"id": "kuaishou", "name": "快手", "icon": "📱"},
                {"id": "weibo", "name": "微博", "icon": "📝"},
                {"id": "xiaohongshu", "name": "小红书", "icon": "📕"},
                {"id": "zhihu", "name": "知乎", "icon": "💬"},
                {"id": "qqvideo", "name": "腾讯视频", "icon": "🐧"},
                {"id": "iqiyi", "name": "爱奇艺", "icon": "🎬"},
                {"id": "youku", "name": "优酷", "icon": "☁️"},
            ]
        })

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
