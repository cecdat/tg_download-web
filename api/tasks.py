from flask import Blueprint, jsonify, request
import os
import logging
from database import db_manager
from api.common import login_required

tasks_bp = Blueprint('tasks', __name__)
logger = logging.getLogger('tg_download_web.tasks')

@tasks_bp.route('/api/tasks')
@login_required
def tasks():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    result = db_manager.get_tasks(page, limit)
    return jsonify({'code': 200, 'data': result['list'], 'count': result['total']})

@tasks_bp.route('/api/tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    db_manager.delete_task(task_id)
    return jsonify({'code': 200, 'message': '记录已删除'})

@tasks_bp.route('/api/tasks/rename', methods=['POST'])
@login_required
def rename_task():
    data = request.get_json()
    task_id = data.get('id')
    new_name = data.get('new_name')
    if not task_id or not new_name: return jsonify({'code': 400, 'message': '参数缺失'})
    if '/' in new_name or '\\' in new_name or '..' in new_name:
        return jsonify({'code': 400, 'message': '文件名包含非法字符'})

    conn = db_manager._get_connection()
    try:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task: return jsonify({'code': 404, 'message': '任务不存在'})
        old_path = task['file_path']
        if not old_path or not os.path.exists(old_path):
            return jsonify({'code': 404, 'message': '原文件不存在或已被移动'})
        
        dir_name = os.path.dirname(old_path)
        _, ext = os.path.splitext(old_path)
        if not os.path.splitext(new_name)[1]: new_name += ext
        new_path = os.path.join(dir_name, new_name)
        if os.path.exists(new_path): return jsonify({'code': 400, 'message': '目标文件名已存在'})
             
        os.rename(old_path, new_path)
        with conn:
            conn.execute("UPDATE tasks SET file_name = ?, file_path = ? WHERE id = ?", (new_name, new_path, task_id))
        return jsonify({'code': 200, 'message': '重命名成功'})
    except Exception as e:
        logger.error(f"Rename Error: {e}")
        return jsonify({'code': 500, 'message': str(e)})
    finally: conn.close()

@tasks_bp.route('/api/tasks/clear', methods=['POST'])
@login_required
def clear_tasks():
    db_manager.clear_tasks()
    return jsonify({'code': 200, 'message': '已清空非活跃任务记录'})
