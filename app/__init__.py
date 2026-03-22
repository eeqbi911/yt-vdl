"""
yt-vdl - 视频下载 Web 管理界面
Flask application factory
"""

from flask import Flask
from app.config import Config


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="../templates", static_folder="../static", static_url_path="/static")
    app.config.from_object(config_class)

    # 注册蓝图
    from app.routes.tasks import tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/api')

    # 页面路由
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

    @app.route('/api/info')
    def api_info():
        from app.downloader import get_ytdlp_version
        from flask import jsonify
        return jsonify({
            "version": get_ytdlp_version(),
            "platform": "Linux",
            "download_dir": app.config["DOWNLOAD_DIR"],
            "max_concurrent": app.config["MAX_CONCURRENT"],
        })

    @app.route('/api/health')
    def api_health():
        from flask import jsonify
        return jsonify({"status": "ok"})

    return app
