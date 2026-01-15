from flask import Blueprint, jsonify, request
from database import db_manager
from api.common import login_required

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/api/notifications', methods=['GET', 'POST'])
@login_required
def notifications():
    if request.method == 'POST':
        data = request.get_json()
        if 'id' in data:
            db_manager.update_notification(data['id'], data)
        else:
            db_manager.add_notification(data)
        return jsonify({'code': 200, 'message': '通知配置已保存'})
    return jsonify({'code': 200, 'data': db_manager.get_notifications()})
