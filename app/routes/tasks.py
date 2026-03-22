"""
任务管理 API 路由
"""

from flask import Blueprint, jsonify, request, send_file
from app.downloader import (
    parse_video, create_task, get_tasks, get_task, cancel_task, delete_task
)

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/parse", methods=["POST"])
def api_parse():
    """解析视频 URL"""
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "请输入视频链接"}), 400

    result = parse_video(url)

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify(result)


@tasks_bp.route("/download", methods=["POST"])
def api_download():
    """开始下载"""
    data = request.get_json()
    url = data.get("url", "").strip()
    format_id = data.get("format_id", "best")
    title = data.get("title", "")

    if not url:
        return jsonify({"error": "请输入视频链接"}), 400

    task_id = create_task(url, format_id, title)
    return jsonify({"task_id": task_id, "status": "pending"})


@tasks_bp.route("/tasks", methods=["GET"])
def api_tasks():
    """获取所有任务"""
    return jsonify({"tasks": get_tasks()})


@tasks_bp.route("/task/<task_id>", methods=["GET"])
def api_task(task_id):
    """获取单个任务"""
    task = get_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task)


@tasks_bp.route("/task/<task_id>/cancel", methods=["POST"])
def api_cancel(task_id):
    """取消任务"""
    if cancel_task(task_id):
        return jsonify({"status": "cancelled"})
    return jsonify({"error": "任务不存在"}), 404


@tasks_bp.route("/task/<task_id>", methods=["DELETE"])
def api_delete(task_id):
    """删除任务"""
    if delete_task(task_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "任务不存在"}), 404


@tasks_bp.route("/task/<task_id>/file", methods=["GET"])
def api_download_file(task_id):
    """下载文件"""
    task = get_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    file_path = task.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "文件不存在"}), 404

    return send_file(file_path, as_attachment=True)


@tasks_bp.route("/tasks/clear-completed", methods=["POST"])
def api_clear_completed():
    """清除已完成任务"""
    from app.downloader.engine import tasks, tasks_lock

    with tasks_lock:
        to_delete = [
            tid for tid, t in tasks.items()
            if t["status"] in ("completed", "error", "cancelled")
        ]
        for tid in to_delete:
            del tasks[tid]

    return jsonify({"status": "ok", "deleted": len(to_delete)})


# 需要 import os
import os
