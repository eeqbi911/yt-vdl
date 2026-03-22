"""
订阅管理 API 路由
"""

import uuid
from flask import Blueprint, jsonify, request
from app.storage.database import (
    add_subscription, get_subscriptions, get_subscription,
    update_subscription, delete_subscription,
    get_download_history as db_get_history,
)
from app.downloader import parse_video

subscriptions_bp = Blueprint("subscriptions", __name__)


@subscriptions_bp.route("/subscriptions", methods=["GET"])
def api_subscriptions():
    """获取所有订阅"""
    subs = get_subscriptions()
    return jsonify({"subscriptions": [dict(s) for s in subs]})


@subscriptions_bp.route("/subscriptions", methods=["POST"])
def api_add_subscription():
    """添加订阅"""
    data = request.get_json()
    url = data.get("url", "").strip()
    name = data.get("name", url[:30])
    platform = data.get("platform", "通用")
    format_id = data.get("format_id", "best")
    check_interval = int(data.get("check_interval", 60))

    if not url:
        return jsonify({"error": "请输入订阅链接"}), 400

    # 检测平台
    from app.downloader import detect_platform
    platform = detect_platform(url)

    sub_id = str(uuid.uuid4())[:8]
    if add_subscription(sub_id, name, url, platform, format_id, check_interval):
        return jsonify({"id": sub_id, "status": "added"})
    return jsonify({"error": "添加失败或已存在"}), 400


@subscriptions_bp.route("/subscription/<sub_id>", methods=["GET"])
def api_get_subscription(sub_id):
    """获取单个订阅"""
    sub = get_subscription(sub_id)
    if not sub:
        return jsonify({"error": "订阅不存在"}), 404
    return jsonify(dict(sub))


@subscriptions_bp.route("/subscription/<sub_id>", methods=["PUT"])
def api_update_subscription(sub_id):
    """更新订阅"""
    data = request.get_json()
    if update_subscription(sub_id, **data):
        return jsonify({"status": "updated"})
    return jsonify({"error": "更新失败"}), 400


@subscriptions_bp.route("/subscription/<sub_id>", methods=["DELETE"])
def api_delete_subscription(sub_id):
    """删除订阅"""
    if delete_subscription(sub_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "订阅不存在"}), 404


@subscriptions_bp.route("/subscription/<sub_id>/check", methods=["POST"])
def api_check_subscription(sub_id):
    """检查订阅更新"""
    sub = get_subscription(sub_id)
    if not sub:
        return jsonify({"error": "订阅不存在"}), 404

    url = sub["url"]
    result = parse_video(url)

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify({
        "title": result.get("title", ""),
        "thumbnail": result.get("thumbnail", ""),
        "platform": result.get("platform", "通用"),
    })


@subscriptions_bp.route("/download-history", methods=["GET"])
def api_download_history():
    """获取下载历史"""
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    offset = (page - 1) * limit

    total, history = db_get_history(limit, offset)
    return jsonify({
        "history": [dict(h) for h in history],
        "total": total,
        "page": page,
        "limit": limit,
    })
