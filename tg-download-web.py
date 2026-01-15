from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import logging
import os
import json
import hashlib
import datetime
import time
import asyncio
import threading
from functools import wraps
from typing import Dict, List, Optional, Any
from logging.handlers import TimedRotatingFileHandler
import shutil
import re

from database import db_manager
# 动态导入 telegram_downloader 中的逻辑（稍微修改后集成）
# 或者直接在这里实现集成逻辑

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tg-download-secret-key-fixed')
VERSION = "1.0.1-api-fix" # 增加版本标识用于验证代码是否更新

# 配置日志
LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)
# 设置根日志配置，确保所有模块输出都能被捕获
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        TimedRotatingFileHandler(os.path.join(LOG_DIR, 'web.log'), when='midnight', interval=1, backupCount=3, encoding='utf-8'),
        logging.StreamHandler() # 输出到控制台，方便 docker logs 查看
    ]
)
logger = logging.getLogger('tg_download_web')

# ... (existing functions) ...


# 密码哈希
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hash: str) -> bool:
    return hash_password(password) == hash

# 确保数据库初始化
db_manager._init_db()

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # 强化检测：只要是 /api/ 路径，或者显式要求 JSON，都返回 401
            is_api = (
                request.path.startswith('/api/') or 
                request.is_json or 
                'application/json' in request.headers.get('Accept', '')
            )
            if is_api:
                return jsonify({'code': 401, 'message': '请先登录', 'version': VERSION}), 200
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/ping')
def ping():
    return jsonify({'code': 200, 'version': VERSION, 'status': 'running'})

@app.route('/api/login', methods=['POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
            
        username = data.get('username')
        password = data.get('password')
        
        user = db_manager.get_user(username)
        if user and verify_password(password, user['password']):
            session['user_id'] = user['username']
            session.permanent = True
            
            # 只要是以 /api/ 开头或者显式要求 JSON 的，都返回 JSON
            is_api = request.path.startswith('/api/') or request.is_json or 'application/json' in request.headers.get('Accept', '')
            if is_api:
                return jsonify({'code': 200, 'message': '登录成功', 'version': VERSION})
            return redirect(url_for('index'))
            
        if request.is_json or request.path.startswith('/api/') or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({'code': 400, 'message': '用户名或密码错误'})
        return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')



@app.route('/api/accounts', methods=['GET', 'POST'])
@login_required
def accounts():
    if request.method == 'POST':
        data = request.form.to_dict() if request.form else request.get_json()
        # 确保Bot Token字段可选，设置默认值为空字符串
        if 'bot_token' not in data:
            data['bot_token'] = ''
        acc_id = None
        if 'id' in data and data['id']:
            acc_id = data['id']
            db_manager.update_account(acc_id, data)
        else:
            if 'session_name' not in data or not data['session_name']:
                data['session_name'] = f"acc_{int(time.time())}"
            data['api_id'] = int(data['api_id'])
            # 添加/更新账号后，尝试启动(重连)Bot以验证并在有频道时恢复工作
            acc_id = db_manager.add_account(data)
        
        if acc_id:
            start_account_bot(acc_id)
            
        return jsonify({'code': 200, 'message': '账号已保存，正在尝试连接...'})
    return jsonify({'code': 200, 'data': db_manager.get_accounts()})

@app.route('/api/accounts/delete/<int:acc_id>', methods=['POST'])
@login_required
def delete_account(acc_id):
    # 停止关联的账号bot
    stop_account_bot(acc_id)
    db_manager.delete_account(acc_id)
    return jsonify({'code': 200, 'message': '账号已删除'})

@app.route('/api/channels', methods=['GET', 'POST'])
@login_required
def channels():
    if request.method == 'POST':
        data = request.get_json()
        acc_id = None
        if 'id' in data and data['id']:
            db_manager.update_channel(data['id'], data)
            # 获取账号ID以重启Bot
            ch_info = db_manager.get_channel_with_account(data['id'])
            if ch_info:
                acc_id = ch_info['account_id']
        else:
            db_manager.add_channel(data)
            acc_id = data.get('account_id')
            
        if acc_id:
            start_account_bot(acc_id)
            
        return jsonify({'code': 200, 'message': '频道已保存'})
    
    # 获取频道列表，并关联账号信息
    account_id = request.args.get('account_id', type=int)
    channels_list = db_manager.get_channels(account_id)
    
    # 为每个频道添加账号名称
    accounts = {acc['id']: acc for acc in db_manager.get_accounts()}
    for ch in channels_list:
        if ch['account_id'] in accounts:
            ch['account_name'] = accounts[ch['account_id']]['name']
    
    return jsonify({'code': 200, 'data': channels_list})

@app.route('/api/channels/toggle/<int:ch_id>', methods=['POST'])
@login_required
def toggle_channel(ch_id):
    new_status = db_manager.toggle_channel(ch_id)
    ch_info = db_manager.get_channel_with_account(ch_id)
    
    if not ch_info:
        return jsonify({'code': 404, 'message': '频道不存在'})
    
    # 重启账号Bot以更新监听列表
    start_account_bot(ch_info['account_id'])
    
    return jsonify({'code': 200, 'message': '状态已更新', 'enabled': new_status})

@app.route('/api/channels/delete/<int:ch_id>', methods=['POST'])
@login_required
def delete_channel(ch_id):
    ch_info = db_manager.get_channel_with_account(ch_id)
    if ch_info:
        acc_id = ch_info['account_id']
        db_manager.delete_channel(ch_id)
        # 删除后重启Bot刷新列表
        start_account_bot(acc_id)
    else:
        db_manager.delete_channel(ch_id)
    return jsonify({'code': 200, 'message': '频道已删除'})

@app.route('/api/notifications', methods=['GET', 'POST'])
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

@app.route('/api/status')
@login_required
def status():
    try:
        import psutil
        from telegram_downloader import progress_status, bot_active_status
        # 优化：提前加载所有频道映射表 {channel_id_str: channel_name}
        # 因为 progress_status 中的 channel_id_raw 是 Telegram 原始 ID (可能是负数 -100xxx)
        # 而数据库存的 channel_id 可能是简写或全写。
        all_accounts = db_manager.get_accounts()
        channel_map = {}
        for acc in all_accounts:
            chs = db_manager.get_channels(acc['id'])
            for ch in chs:
                # 建立多重索引以提高匹配率
                cid = str(ch['channel_id'])
                cname = ch['channel_name'] or cid
                channel_map[cid] = cname
                if not cid.startswith('-100'):
                    channel_map[f"-100{cid}"] = cname
        
        active_downloads = []
        for acc_id, downloads in progress_status.items():
            for msg_id, p in downloads.items():
                fname = p.get('file_name', '未知')
                raw_cid = str(p.get('channel_id_raw', ''))
                
                # 优先从 map 中取名，取不到则用 ID
                channel_display = channel_map.get(raw_cid, raw_cid) or str(acc_id)

                active_downloads.append({
                    'acc_id': str(acc_id),
                    'channel_name': channel_display,
                    'name': fname,
                    'percentage': p.get('percentage', 0),
                    'downloaded': p.get('downloaded_mb', 0),
                    'total': p.get('total_mb', 0),
                    'speed': p.get('speed', '0 MB/s')
                })
        
        download_dir = db_manager.get_setting('DOWNLOAD_DIR', '/app/downloads')
        # 如果目录不存在，尝试创建或者使用当前文件夹
        if not os.path.exists(download_dir):
            try:
                os.makedirs(download_dir, exist_ok=True)
            except:
                download_dir = "."
        
        # 获取下载目录磁盘空间
        download_total, download_used, download_free = shutil.disk_usage(download_dir)
        # 获取整个服务器磁盘空间（根目录）
        total, used, free = shutil.disk_usage('/')
        memory = psutil.virtual_memory()
        
        # 获取账号运行状态 (直接获取详细状态文本)
        acc_status = {}
        for acc_id, status_text in bot_active_status.items():
            acc_status[acc_id] = status_text
            
        return jsonify({
            'code': 200,
            'data': {
                'active_count': len(active_downloads),
                'active_downloads': active_downloads,
                'bot_status': acc_status,
                'disk': {
                    'total': total // (1024**3),
                    'used': used // (1024**3),
                    'free': free // (1024**3),
                    'percent': int((used/total)*100) if total > 0 else 0,
                    'download_dir_total': download_total // (1024**3),
                    'download_dir_free': download_free // (1024**3)
                },
                'memory': {
                    'total': round(memory.total / (1024**3), 1),
                    'used': round(memory.used / (1024**3), 1),
                    'percent': memory.percent
                }
            }
        })
    except Exception as e:
        logger.error(f"Status API Error: {e}")
        return jsonify({'code': 500, 'message': str(e)})

@app.route('/api/tasks')
@login_required
def tasks():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    result = db_manager.get_tasks(page, limit)
    return jsonify({'code': 200, 'data': result['list'], 'count': result['total']})

@app.route('/api/tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    db_manager.delete_task(task_id)
    return jsonify({'code': 200, 'message': '记录已删除'})

@app.route('/api/tasks/rename', methods=['POST'])
@login_required
def rename_task():
    data = request.get_json()
    task_id = data.get('id')
    new_name = data.get('new_name')
    
    if not task_id or not new_name:
        return jsonify({'code': 400, 'message': '参数缺失'})
    
    # 简单的安全性检查，防止路径穿越
    if '/' in new_name or '\\' in new_name or '..' in new_name:
        return jsonify({'code': 400, 'message': '文件名包含非法字符'})

    conn = db_manager._get_connection()
    try:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'})
            
        old_path = task['file_path']
        if not old_path or not os.path.exists(old_path):
            return jsonify({'code': 404, 'message': '原文件不存在或已被移动'})
            
        # 构建新路径
        dir_name = os.path.dirname(old_path)
        _, ext = os.path.splitext(old_path)
        
        # 如果新名字没有后缀，自动补全原后缀
        if not os.path.splitext(new_name)[1]:
            new_name += ext
            
        new_path = os.path.join(dir_name, new_name)
        
        if os.path.exists(new_path):
             return jsonify({'code': 400, 'message': '目标文件名已存在'})
             
        # 重命名物理文件
        os.rename(old_path, new_path)
        
        # 更新数据库
        with conn:
            conn.execute("UPDATE tasks SET file_name = ?, file_path = ? WHERE id = ?", (new_name, new_path, task_id))
            
        return jsonify({'code': 200, 'message': '重命名成功'})
    except Exception as e:
        logger.error(f"Rename Error: {e}")
        return jsonify({'code': 500, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/tasks/clear', methods=['POST'])
@login_required
def clear_tasks():
    db_manager.clear_tasks()
    return jsonify({'code': 200, 'message': '已清空非活跃任务记录'})

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        data = request.get_json()
        for key, value in data.items():
            db_manager.set_setting(key, value)
        return jsonify({'code': 200, 'message': '设置已保存'})
    return jsonify({'code': 200, 'data': {
        'DOWNLOAD_DIR': db_manager.get_setting('DOWNLOAD_DIR', '/app/downloads'),
        'SEND_CHANNEL_LOGIN_MSG': db_manager.get_setting('SEND_CHANNEL_LOGIN_MSG', 'False'),
        'MAX_CONCURRENT_DOWNLOADS': db_manager.get_setting('MAX_CONCURRENT_DOWNLOADS', '3'),
        'FILE_RETENTION_DAYS': db_manager.get_setting('FILE_RETENTION_DAYS', '3')
    }})

@app.route('/api/settings/password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    old_pwd = data.get('old_password')
    new_pwd = data.get('new_password')
    
    user = db_manager.get_user(session['user_id'])
    if not user or not verify_password(old_pwd, user['password']):
        return jsonify({'code': 400, 'message': '旧密码错误'})
    
    db_manager.update_password(session['user_id'], hash_password(new_pwd))
    return jsonify({'code': 200, 'message': '密码修改成功'})

bot_instances = {} # {account_id: (stop_event, thread)}

def start_account_bot(account_id):
    """为单个账号启动bot (管理该账号下所有频道)"""
    try:
        account_id = int(account_id)
    except (ValueError, TypeError):
        logger.error(f"Cannot start bot: Invalid account_id {account_id}")
        return

    stop_account_bot(account_id)
    
    accounts = db_manager.get_accounts()
    target_acc = next((a for a in accounts if a['id'] == account_id), None)
    
    if not target_acc:
        logger.error(f"Cannot start bot: Account {account_id} not found")
        return
        
    import telegram_downloader
    stop_event = asyncio.Event()
    
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(telegram_downloader.run_account_bot(target_acc, stop_event))
        except Exception as e:
            logger.error(f"Account bot {target_acc['name']} error: {e}")
            
    t = threading.Thread(target=run, daemon=True)
    t.start()
    bot_instances[account_id] = (stop_event, t)

def stop_account_bot(account_id):
    if account_id in bot_instances:
        stop_event, t = bot_instances.pop(account_id)
        try:
            stop_event.set()
            # 必须等待旧线程完全结束，否则 Telethon Session 文件会被锁
            if t.is_alive():
                logger.info(f"Adding wait for thread {account_id} to stop...")
                t.join(timeout=10)
            time.sleep(1) # 给 SQLite 一点时间释放锁
        except Exception as e:
            logger.error(f"Error stopping bot {account_id}: {e}")

def stop_all_bots():
    """停止所有正在运行的 Bot"""
    for acc_id in list(bot_instances.keys()):
        stop_account_bot(acc_id)
    time.sleep(1)

def cleanup_job():
    """后台清理任务：清理过期文件和日志"""
    while True:
        try:
            logger.info("Running cleanup job...")
            
            # 1. 清理过期下载文件
            retention_val = db_manager.get_setting('FILE_RETENTION_DAYS', '3')
            try:
                retention_days = int(retention_val) if retention_val and str(retention_val).strip() else 3
            except:
                retention_days = 3
                
            if retention_days > 0:
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
                cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
                
                expired_tasks = db_manager.get_expired_tasks(cutoff_str)
                logger.info(f"Found {len(expired_tasks)} expired tasks (older than {retention_days} days)")
                
                for task in expired_tasks:
                    file_path = task['file_path']
                    # 删除物理文件
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            logger.info(f"Deleted expired file: {file_path}")
                        except Exception as e:
                            logger.error(f"Failed to delete file {file_path}: {e}")
                    
                    # 更新任务状态 (标记为文件已过期清理)
                    # 保留记录但状态变更为 file_expired
                    if task['status'] != 'file_expired':
                        db_manager.update_task_status(task['id'], 'file_expired', error_msg='File cleaned up by retention policy')
            
            # 2. 清理过期日志 (保留3天)
            log_retention_days = 3
            now = time.time()
            for f in os.listdir(LOG_DIR):
                f_path = os.path.join(LOG_DIR, f)
                if os.path.isfile(f_path):
                    # 如果修改时间超过3天
                    if os.stat(f_path).st_mtime < (now - log_retention_days * 86400):
                        try:
                            os.remove(f_path)
                            logger.info(f"Deleted old log file: {f}")
                        except Exception as e:
                            logger.error(f"Failed to delete log {f}: {e}")

            logger.info("Cleanup job finished.")
        except Exception as e:
            logger.error(f"Error in cleanup job: {e}")
        
        # 每小时检查一次
        time.sleep(3600)

if __name__ == '__main__':
    # 1. 基础环境设置 (仅在为空时设置默认值)
    if not db_manager.get_setting('DOWNLOAD_DIR'):
        db_manager.set_setting('DOWNLOAD_DIR', '/app/downloads')
    
    # 2. 初始化默认用户 (admin/admin123)
    if not db_manager.get_user('admin'):
        db_manager.add_user('admin', hash_password('admin123'))

    # 3. 启动后台清理线程
    cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
    cleanup_thread.start()

    # 4. 启动所有账号 Bot
    # 由于现在Bot是按账号管理的，我们需要遍历账号
    all_accounts = db_manager.get_accounts()
    for acc in all_accounts:
        # 检查该账号下是否有启用的频道
        chs = db_manager.get_channels(acc['id'])
        if any(c['enabled'] == 1 for c in chs):
            start_account_bot(acc['id'])

    app.run(host='0.0.0.0', port=5001, debug=False)
