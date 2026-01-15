from flask import Blueprint, jsonify, request
from database import db_manager
from api.common import login_required
from bot_manager import start_account_bot, stop_account_bot

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/api/accounts', methods=['GET', 'POST'])
@login_required
def accounts():
    if request.method == 'POST':
        data = request.form.to_dict() if request.form else request.get_json()
        if 'bot_token' not in data: data['bot_token'] = ''
        acc_id = None
        if 'id' in data and data['id']:
            acc_id = data['id']
            db_manager.update_account(acc_id, data)
        else:
            if 'session_name' not in data or not data['session_name']:
                import time
                data['session_name'] = f"acc_{int(time.time())}"
            data['api_id'] = int(data['api_id'])
            acc_id = db_manager.add_account(data)
        
        if acc_id: start_account_bot(acc_id)
        return jsonify({'code': 200, 'message': '账号已保存，正在尝试连接...'})
    return jsonify({'code': 200, 'data': db_manager.get_accounts()})

@accounts_bp.route('/api/accounts/delete/<int:acc_id>', methods=['POST'])
@login_required
def delete_account(acc_id):
    stop_account_bot(acc_id)
    db_manager.delete_account(acc_id)
    return jsonify({'code': 200, 'message': '账号已删除'})

@accounts_bp.route('/api/channels', methods=['GET', 'POST'])
@login_required
def channels():
    if request.method == 'POST':
        data = request.get_json()
        acc_id = None
        if 'id' in data and data['id']:
            db_manager.update_channel(data['id'], data)
            ch_info = db_manager.get_channel_with_account(data['id'])
            if ch_info: acc_id = ch_info['account_id']
        else:
            db_manager.add_channel(data)
            acc_id = data.get('account_id')
        if acc_id: start_account_bot(acc_id)
        return jsonify({'code': 200, 'message': '频道已保存'})
    
    account_id = request.args.get('account_id', type=int)
    channels_list = db_manager.get_channels(account_id)
    accounts = {acc['id']: acc for acc in db_manager.get_accounts()}
    for ch in channels_list:
        if ch['account_id'] in accounts:
            ch['account_name'] = accounts[ch['account_id']]['name']
    return jsonify({'code': 200, 'data': channels_list})

@accounts_bp.route('/api/channels/toggle/<int:ch_id>', methods=['POST'])
@login_required
def toggle_channel(ch_id):
    new_status = db_manager.toggle_channel(ch_id)
    ch_info = db_manager.get_channel_with_account(ch_id)
    if not ch_info: return jsonify({'code': 404, 'message': '频道不存在'})
    start_account_bot(ch_info['account_id'])
    return jsonify({'code': 200, 'message': '状态已更新', 'enabled': new_status})

@accounts_bp.route('/api/channels/delete/<int:ch_id>', methods=['POST'])
@login_required
def delete_channel(ch_id):
    ch_info = db_manager.get_channel_with_account(ch_id)
    if ch_info:
        acc_id = ch_info['account_id']
        db_manager.delete_channel(ch_id)
        start_account_bot(acc_id)
    else:
        db_manager.delete_channel(ch_id)
    return jsonify({'code': 200, 'message': '频道已删除'})
