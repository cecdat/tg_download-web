from flask import session, jsonify, request, redirect, url_for
from functools import wraps
import hashlib
from version import VERSION

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hash: str) -> bool:
    return hash_password(password) == hash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            is_api = (
                request.path.startswith('/api/') or 
                request.is_json or 
                'application/json' in request.headers.get('Accept', '')
            )
            if is_api:
                return jsonify({'code': 401, 'message': '请先登录', 'version': VERSION}), 200
            return redirect(url_for('auth.login')) # 这里跳转到auth蓝图的登录页
        return f(*args, **kwargs)
    return decorated_function
