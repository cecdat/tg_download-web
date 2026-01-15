from flask import Flask, render_template
import logging
import os
import threading
from logging.handlers import TimedRotatingFileHandler

from database import db_manager
from version import VERSION
from api.common import login_required
from bot_manager import start_account_bot, stop_all_bots

# 导入蓝图
from api.auth import auth_bp
from api.system import system_bp
from api.accounts import accounts_bp
from api.tasks import tasks_bp
from api.notifications import notifications_bp

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tg-download-secret-key-fixed')

# 配置日志
LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        TimedRotatingFileHandler(os.path.join(LOG_DIR, 'web.log'), when='midnight', interval=1, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('tg_download_web')

# 注册蓝图 (按功能划分)
app.register_blueprint(auth_bp)
app.register_blueprint(system_bp)
app.register_blueprint(accounts_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(notifications_bp)

# 确保数据库初始化
db_manager._init_db()

@app.route('/')
@login_required
def index():
    return render_template('index.html')

def cleanup_job():
    """后台清理任务：清理过期文件和日志"""
    import time
    import datetime
    import shutil
    while True:
        try:
            # 1. 清理过期下载文件
            retention_val = db_manager.get_setting('FILE_RETENTION_DAYS', '3')
            try: retention_days = int(retention_val)
            except: retention_days = 3
                
            if retention_days > 0:
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
                cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
                expired_tasks = db_manager.get_expired_tasks(cutoff_str)
                for task in expired_tasks:
                    file_path = task['file_path']
                    if file_path and os.path.exists(file_path):
                        try: os.remove(file_path)
                        except: pass
                    if task['status'] != 'file_expired':
                        db_manager.update_task_status(task['id'], 'file_expired', error_msg='File cleaned up by retention policy')
            
            # 2. 清理过期日志 (保留3天)
            now = time.time()
            for f in os.listdir(LOG_DIR):
                f_path = os.path.join(LOG_DIR, f)
                if os.path.isfile(f_path) and os.stat(f_path).st_mtime < (now - 3 * 86400):
                    try: os.remove(f_path)
                    except: pass
        except Exception as e:
            logger.error(f"Error in cleanup job: {e}")
        time.sleep(3600)

if __name__ == '__main__':
    # 初始化默认设置
    if not db_manager.get_setting('DOWNLOAD_DIR'):
        db_manager.set_setting('DOWNLOAD_DIR', '/app/downloads')
    
    # 初始化 admin 账号
    from api.common import hash_password
    if not db_manager.get_user('admin'):
        db_manager.add_user('admin', hash_password('admin123'))

    # 启动后台清理
    threading.Thread(target=cleanup_job, daemon=True).start()

    # 启动所有账号 Bot
    all_accounts = db_manager.get_accounts()
    for acc in all_accounts:
        chs = db_manager.get_channels(acc['id'])
        if any(c['enabled'] == 1 for c in chs):
            start_account_bot(acc['id'])

    app.run(host='0.0.0.0', port=5001, debug=False)
