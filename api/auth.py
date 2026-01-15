from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from database import db_manager
from api.common import hash_password, verify_password
from version import VERSION

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form.to_dict() if request.form else request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = db_manager.get_user(username)
        if user and verify_password(password, user['password']):
            session['user_id'] = user['username']
            session.permanent = True
            is_api = request.path.startswith('/api/') or request.is_json or 'application/json' in request.headers.get('Accept', '')
            if is_api:
                return jsonify({'code': 200, 'message': '登录成功', 'version': VERSION})
            return redirect(url_for('index'))
            
        is_api = request.path.startswith('/api/') or request.is_json or 'application/json' in request.headers.get('Accept', '')
        if is_api:
            return jsonify({'code': 400, 'message': '用户名或密码错误'})
        return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
