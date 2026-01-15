import sqlite3
import json
import os
import hashlib
import threading
from typing import Any, Dict, List, Optional

class DatabaseManager:
    def __init__(self, db_path: str = "data/tg_download.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=60, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.lock:
            conn = self._get_connection()
            try:
                # 启用 WAL 模式提高并发性能
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                with conn:
                    # 设置表 (全局通用)
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS settings (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        )
                    ''')
                    # 用户表
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            username TEXT PRIMARY KEY,
                            password TEXT
                        )
                    ''')
                    # Telegram 账号表（仅存储认证信息）
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS accounts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT,
                            api_id INTEGER,
                            api_hash TEXT,
                            bot_token TEXT,
                            session_name TEXT,
                            created_at TEXT
                        )
                    ''')
                    
                    # 频道监听表（每个频道一条记录）
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS channels (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            account_id INTEGER,
                            channel_id TEXT,
                            channel_name TEXT,
                            enabled INTEGER DEFAULT 1,
                            status TEXT DEFAULT 'stopped',
                            FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE
                        )
                    ''')
                    # 通知配置表
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS notifications (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT,
                            type TEXT, -- e.g. 'bark'
                            config TEXT, -- JSON string
                            enabled INTEGER DEFAULT 1
                        )
                    ''')
                    # 下载任务历史表
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS tasks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            account_id INTEGER,
                            message_id INTEGER,
                            file_name TEXT,
                            file_size REAL,
                            status TEXT,
                            start_time TEXT,
                            end_time TEXT,
                            error_msg TEXT
                        )
                    ''')
                    
                    # 自动迁移：检查 tasks 表是否存在 account_id 和 file_path 列
                    try:
                        cursor = conn.execute("PRAGMA table_info(tasks)")
                        columns = [column[1] for column in cursor.fetchall()]
                        if 'account_id' not in columns:
                            conn.execute("ALTER TABLE tasks ADD COLUMN account_id INTEGER")
                        if 'file_path' not in columns:
                            conn.execute("ALTER TABLE tasks ADD COLUMN file_path TEXT")
                        if 'channel_id' not in columns:
                             conn.execute("ALTER TABLE tasks ADD COLUMN channel_id INTEGER")
                        if 'source_message_id' not in columns:
                             conn.execute("ALTER TABLE tasks ADD COLUMN source_message_id INTEGER")
                        if 'source_channel_id' not in columns:
                             conn.execute("ALTER TABLE tasks ADD COLUMN source_channel_id INTEGER")
                    except Exception as e:
                        print(f"Migration error (tasks columns): {e}")

                    # 自动迁移：检查 channels 表是否存在 custom_path 列
                    try:
                        cursor = conn.execute("PRAGMA table_info(channels)")
                        columns = [column[1] for column in cursor.fetchall()]
                        if 'custom_path' not in columns:
                            conn.execute("ALTER TABLE channels ADD COLUMN custom_path TEXT")
                    except Exception as e:
                        print(f"Migration error (channels.custom_path): {e}")

                    # 自动迁移：从旧的accounts表迁移数据到新结构
                    try:
                        cursor = conn.execute("PRAGMA table_info(accounts)")
                        old_columns = [column[1] for column in cursor.fetchall()]
                        if 'channel_id' in old_columns and 'created_at' not in old_columns:
                            # 旧结构，需要迁移
                            old_accounts = conn.execute("SELECT * FROM accounts").fetchall()
                            # 重命名旧表
                            conn.execute("ALTER TABLE accounts RENAME TO accounts_old")
                            # 创建新表结构
                            conn.execute('''
                                CREATE TABLE accounts (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT,
                                    api_id INTEGER,
                                    api_hash TEXT,
                                    bot_token TEXT,
                                    session_name TEXT,
                                    created_at TEXT
                                )
                            ''')
                            # 迁移账号数据
                            for old_acc in old_accounts:
                                conn.execute('''
                                    INSERT INTO accounts (id, name, api_id, api_hash, bot_token, session_name, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                                ''', (old_acc[0], old_acc[1], old_acc[2], old_acc[3], old_acc[4], old_acc[6]))
                                
                                # 迁移频道数据（拆分逗号分隔的频道）
                                if old_acc[5]:  # channel_id字段
                                    for ch_id in str(old_acc[5]).split(','):
                                        ch_id = ch_id.strip()
                                        if ch_id:
                                            conn.execute('''
                                                INSERT INTO channels (account_id, channel_id, channel_name, enabled, status)
                                                VALUES (?, ?, ?, ?, ?)
                                            ''', (old_acc[0], ch_id, ch_id, old_acc[7] if len(old_acc) > 7 else 1, 'stopped'))
                            # 删除旧表
                            conn.execute("DROP TABLE accounts_old")
                            print("Successfully migrated accounts to new structure")
                    except Exception as e:
                        print(f"Migration error (accounts structure): {e}")
            finally:
                conn.close()

    # --- 账号管理 ---
    def get_accounts(self) -> List[Dict]:
        conn = self._get_connection()
        try:
            rows = conn.execute("SELECT * FROM accounts").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_account(self, data: Dict) -> int:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute('''
                    INSERT INTO accounts (name, api_id, api_hash, bot_token, session_name, created_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                ''', (data['name'], data['api_id'], data['api_hash'], data['bot_token'], data['session_name']))
                return cursor.lastrowid
        finally:
            conn.close()

    def update_account(self, acc_id: int, data: Dict):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute('''
                    UPDATE accounts SET name=?, api_id=?, api_hash=?, bot_token=?
                    WHERE id=?
                ''', (data['name'], data['api_id'], data['api_hash'], data['bot_token'], acc_id))
        finally:
            conn.close()

    def delete_account(self, acc_id: int):
        conn = self._get_connection()
        try:
            with conn:
                # 由于设置了外键级联删除，删除账号会自动删除关联的频道
                conn.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
        finally:
            conn.close()

    # --- 频道管理 ---
    def get_channels(self, account_id: int = None) -> List[Dict]:
        """获取频道列表，可选按账号ID筛选"""
        conn = self._get_connection()
        try:
            if account_id:
                rows = conn.execute("SELECT * FROM channels WHERE account_id = ?", (account_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM channels").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_channel_with_account(self, channel_id: int) -> Optional[Dict]:
        """获取频道信息及关联的账号信息"""
        conn = self._get_connection()
        try:
            row = conn.execute('''
                SELECT c.*, a.name as account_name, a.api_id, a.api_hash, a.bot_token, a.session_name
                FROM channels c
                JOIN accounts a ON c.account_id = a.id
                WHERE c.id = ?
            ''', (channel_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def add_channel(self, data: Dict) -> int:
        """添加频道"""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute('''
                    INSERT INTO channels (account_id, channel_id, channel_name, enabled, custom_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (data['account_id'], data['channel_id'], data.get('channel_name', data['channel_id']), data.get('enabled', 1), data.get('custom_path', '')))
                return cursor.lastrowid
        finally:
            conn.close()

    def update_channel(self, ch_id: int, data: Dict):
        """更新频道信息"""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute('''
                    UPDATE channels SET channel_id=?, channel_name=?, enabled=?, custom_path=?
                    WHERE id=?
                ''', (data['channel_id'], data.get('channel_name', data['channel_id']), data.get('enabled', 1), data.get('custom_path', ''), ch_id))
        finally:
            conn.close()

    def delete_channel(self, ch_id: int):
        """删除频道"""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM channels WHERE id=?", (ch_id,))
        finally:
            conn.close()

    def toggle_channel(self, ch_id: int) -> int:
        """切换频道启用状态"""
        conn = self._get_connection()
        try:
            with conn:
                row = conn.execute("SELECT enabled FROM channels WHERE id=?", (ch_id,)).fetchone()
                if row:
                    new_status = 0 if row[0] else 1
                    conn.execute("UPDATE channels SET enabled=? WHERE id=?", (new_status, ch_id))
                    return new_status
                return 0
        finally:
            conn.close()

    # --- 通知管理 ---
    def get_notifications(self) -> List[Dict]:
        conn = self._get_connection()
        try:
            rows = conn.execute("SELECT * FROM notifications").fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item['config'] = json.loads(item['config'])
                result.append(item)
            return result
        finally:
            conn.close()

    def add_notification(self, data: Dict):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute('''
                    INSERT INTO notifications (name, type, config, enabled)
                    VALUES (?, ?, ?, ?)
                ''', (data['name'], data['type'], json.dumps(data['config']), data.get('enabled', 1)))
        finally:
            conn.close()

    def update_notification(self, n_id: int, data: Dict):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute('''
                    UPDATE notifications SET name=?, type=?, config=?, enabled=?
                    WHERE id=?
                ''', (data['name'], data['type'], json.dumps(data['config']), data.get('enabled', 1), n_id))
        finally:
            conn.close()

    def delete_notification(self, n_id: int):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM notifications WHERE id=?", (n_id,))
        finally:
            conn.close()

    # --- 基础设置 ---
    def get_setting(self, key: str, default: Any = None) -> Any:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                try:
                    return json.loads(row['value'])
                except:
                    return row['value']
            return default
        finally:
            conn.close()

    def set_setting(self, key: str, value: Any):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, json.dumps(value, ensure_ascii=False))
                )
        finally:
            conn.close()

    # --- 用户管理 ---
    def get_user(self, username: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def add_user(self, username: str, password_hash: str):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO users (username, password) VALUES (?, ?)",
                    (username, password_hash)
                )
        finally:
            conn.close()

    def update_password(self, username: str, new_password_hash: str):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE users SET password = ? WHERE username = ?",
                    (new_password_hash, username)
                )
        finally:
            conn.close()

    # --- 任务管理 ---
    def get_tasks(self, page: int = 1, limit: int = 20) -> Dict:
        conn = self._get_connection()
        try:
            offset = (page - 1) * limit
            
            # 获取总数
            total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            
            # 获取数据 (关联查询以获取账号名称和频道名称)
            # channel_id 在 tasks 表中可能为空（旧数据），或者对应 channels 表中的数据库ID
            rows = conn.execute(f'''
                SELECT t.*, a.name as account_name, c.channel_name 
                FROM tasks t
                LEFT JOIN accounts a ON t.account_id = a.id
                LEFT JOIN channels c ON t.channel_id = c.id
                ORDER BY t.id DESC LIMIT ? OFFSET ?
            ''', (limit, offset)).fetchall()
            
            return {
                'total': total,
                'page': page,
                'limit': limit,
                'list': [dict(row) for row in rows]
            }
        finally:
            conn.close()

    def add_task(self, task_data: Dict) -> int:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute('''
                    INSERT INTO tasks (account_id, message_id, file_name, file_size, status, start_time, file_path, channel_id, source_message_id, source_channel_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_data.get('account_id'),
                    task_data.get('message_id'),
                    task_data.get('file_name'),
                    task_data.get('file_size'),
                    task_data.get('status', 'downloading'),
                    task_data.get('start_time'),
                    task_data.get('file_path'),
                    task_data.get('channel_id'),
                    task_data.get('source_message_id'),
                    task_data.get('source_channel_id')
                ))
                return cursor.lastrowid
        finally:
            conn.close()

    def get_unfinished_tasks_by_account(self, account_id: int) -> List[Dict]:
        """获取某个账号下所有未完成（正在下载或等待中）的任务"""
        conn = self._get_connection()
        try:
            rows = conn.execute('''
                SELECT * FROM tasks 
                WHERE account_id = ? AND status IN ('downloading', 'waiting')
                ORDER BY id ASC
            ''', (account_id,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def update_task_status(self, task_id: int, status: str, end_time: str = None, error_msg: str = None, start_time: str = None):
        conn = self._get_connection()
        try:
            with conn:
                if end_time:
                    conn.execute(
                        "UPDATE tasks SET status = ?, end_time = ?, error_msg = ? WHERE id = ?",
                        (status, end_time, error_msg, task_id)
                    )
                elif start_time:
                    conn.execute(
                        "UPDATE tasks SET status = ?, start_time = ? WHERE id = ?",
                        (status, start_time, task_id)
                    )
                else:
                    conn.execute(
                        "UPDATE tasks SET status = ? WHERE id = ?",
                        (status, task_id)
                    )
        finally:
            conn.close()

    def delete_task(self, task_id: int):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        finally:
            conn.close()

    def get_expired_tasks(self, cutoff_time: str) -> List[Dict]:
        """获取早于 cutoff_time 且状态为 completed 的任务"""
        conn = self._get_connection()
        try:
            rows = conn.execute('''
                SELECT * FROM tasks 
                WHERE status = 'completed' 
                AND end_time IS NOT NULL 
                AND end_time < ?
            ''', (cutoff_time,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def clear_tasks(self):
        conn = self._get_connection()
        try:
            with conn:
                # 只清除已完成、失败或停止的任务，保留下载中和等待中的
                conn.execute("DELETE FROM tasks WHERE status NOT IN ('downloading', 'waiting')")
        finally:
            conn.close()

    def get_active_task_count(self) -> int:
        """获取当前正在下载的任务数（不含等待中）用于并发控制"""
        conn = self._get_connection()
        try:
            return conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'downloading'").fetchone()[0]
        finally:
            conn.close()
            
    def get_active_tasks(self) -> List[Dict]:
        """获取所有活跃任务（包含正在下载和排队等待的）"""
        conn = self._get_connection()
        try:
            rows = conn.execute('''
                SELECT t.*, a.name as account_name, c.channel_name
                FROM tasks t
                LEFT JOIN accounts a ON t.account_id = a.id
                LEFT JOIN channels c ON t.channel_id = c.id
                WHERE t.status IN ('downloading', 'waiting')
                ORDER BY CASE WHEN t.status = 'downloading' THEN 0 ELSE 1 END, t.id ASC
            ''').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

db_manager = DatabaseManager()
