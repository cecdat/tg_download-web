from flask import Blueprint, jsonify, request, render_template, shutil
import os
import time
import datetime
import psutil
import logging
from database import db_manager
from api.common import login_required
from version import VERSION

system_bp = Blueprint('system', __name__)
logger = logging.getLogger('tg_download_web.system')

@system_bp.route('/api/ping')
def ping():
    return jsonify({'code': 200, 'version': VERSION, 'status': 'running'})

@system_bp.route('/docs')
@login_required
def docs():
    return render_template('docs.html')

@system_bp.route('/api/swagger.json')
@login_required
def swagger_spec():
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "TG-Downloader API",
            "description": "TG-Downloader 的交互式 API 调试文档。所有接口均需要 Session 认证。",
            "version": VERSION
        },
        "tags": [
            {"name": "系统", "description": "状态监控与基础设置"},
            {"name": "账号", "description": "Telegram 账号与频道管理"},
            {"name": "任务", "description": "下载任务与历史记录"},
            {"name": "通知", "description": "推送通知配置"}
        ],
        "paths": {
            "/api/ping": {
                "get": {
                    "tags": ["系统"],
                    "summary": "服务存活检查",
                    "responses": {"200": {"description": "成功"}}
                }
            },
            "/api/status": {
                "get": {
                    "tags": ["系统"],
                    "summary": "获取实时系统状态",
                    "responses": {"200": {"description": "成功"}}
                }
            },
            "/api/accounts": {
                "get": {
                    "tags": ["账号"],
                    "summary": "获取所有账号",
                    "responses": {"200": {"description": "成功"}}
                },
                "post": {
                    "tags": ["账号"],
                    "summary": "添加或更新账号",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "integer"},
                                        "name": {"type": "string"},
                                        "api_id": {"type": "integer"},
                                        "api_hash": {"type": "string"},
                                        "bot_token": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "成功"}}
                }
            },
            "/api/channels": {
                "get": {
                    "tags": ["账号"],
                    "summary": "获取频道列表",
                    "parameters": [{"name": "account_id", "in": "query", "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}}
                },
                "post": {
                    "tags": ["账号"],
                    "summary": "保存频道配置",
                    "requestBody": {
                        "content": {"application/json": {"schema": {"type": "object"}}}
                    },
                    "responses": {"200": {"description": "成功"}}
                }
            },
            "/api/tasks": {
                "get": {
                    "tags": ["任务"],
                    "summary": "获取任务历史",
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}}
                    ],
                    "responses": {"200": {"description": "成功"}}
                }
            },
            "/api/tasks/clear": {
                "post": {
                    "tags": ["任务"],
                    "summary": "清空历史记录",
                    "responses": {"200": {"description": "成功"}}
                }
            },
            "/api/notifications": {
                "get": {
                    "tags": ["通知"],
                    "summary": "获取通知配置",
                    "responses": {"200": {"description": "成功"}}
                },
                "post": {
                    "tags": ["通知"],
                    "summary": "保存通知配置",
                    "requestBody": {
                        "content": {"application/json": {"schema": {"type": "object"}}}
                    },
                    "responses": {"200": {"description": "成功"}}
                }
            },
            "/api/settings": {
                "get": {
                    "tags": ["系统"],
                    "summary": "获取全局设置",
                    "responses": {"200": {"description": "成功"}}
                },
                "post": {
                    "tags": ["系统"],
                    "summary": "保存全局设置",
                    "requestBody": {
                        "content": {"application/json": {"schema": {"type": "object"}}}
                    },
                    "responses": {"200": {"description": "成功"}}
                }
            }
        }
    }
    return jsonify(spec)

@system_bp.route('/api/status')
@login_required
def status():
    try:
        from telegram_downloader import progress_status, bot_active_status
        active_downloads = []
        db_active_tasks = db_manager.get_active_tasks()
        
        for t in db_active_tasks:
            acc_id = t['account_id']
            msg_id = t['message_id']
            progress_data = progress_status.get(acc_id, {}).get(msg_id, {})
            
            active_downloads.append({
                'id': t['id'],
                'acc_id': str(acc_id),
                'channel_name': t['channel_name'] or t['account_name'] or '未知频道',
                'name': t['file_name'],
                'status': t['status'],
                'percentage': progress_data.get('percentage', 0),
                'downloaded': progress_data.get('downloaded_mb', 0),
                'total': progress_data.get('total_mb', 0),
                'speed': progress_data.get('speed', '0 MB/s')
            })
        
        download_dir = db_manager.get_setting('DOWNLOAD_DIR', '/app/downloads')
        if not os.path.exists(download_dir):
            try: os.makedirs(download_dir, exist_ok=True)
            except: download_dir = "."
        
        download_total, download_used, download_free = shutil.disk_usage(download_dir)
        total, used, free = shutil.disk_usage('/')
        memory = psutil.virtual_memory()
        
        boot_time = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_time)
        try: load = list(psutil.getloadavg())
        except AttributeError: load = [psutil.cpu_percent(), 0, 0]
            
        acc_status = {}
        for acc_id, status_text in bot_active_status.items():
            acc_status[acc_id] = status_text
            
        return jsonify({
            'code': 200,
            'data': {
                'active_count': len(active_downloads),
                'active_downloads': active_downloads,
                'bot_status': acc_status,
                'uptime': uptime_seconds,
                'load': load,
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

@system_bp.route('/api/settings', methods=['GET', 'POST'])
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

@system_bp.route('/api/settings/password', methods=['POST'])
@login_required
def change_password():
    from flask import session
    from api.common import verify_password, hash_password
    data = request.get_json()
    old_pwd = data.get('old_password')
    new_pwd = data.get('new_password')
    
    user = db_manager.get_user(session['user_id'])
    if not user or not verify_password(old_pwd, user['password']):
        return jsonify({'code': 400, 'message': '旧密码错误'})
    
    db_manager.update_password(session['user_id'], hash_password(new_pwd))
    return jsonify({'code': 200, 'message': '密码修改成功'})
