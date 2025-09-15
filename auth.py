import sqlite3
import logging
from config import ALLOWED_USERS, ADMIN_USER_ID

logger = logging.getLogger(__name__)

def init_auth_db():
    """Инициализация таблицы пользователей"""
    conn = sqlite3.connect('parts.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Добавляем администратора по умолчанию
    for user_id, username in ALLOWED_USERS.items():
        role = 'admin' if user_id == ADMIN_USER_ID else 'user'
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, role) VALUES (?, ?, ?)',
            (user_id, username, role)
        )
    
    conn.commit()
    return conn

def is_user_allowed(user_id: int) -> bool:
    """Проверяет, есть ли пользователь в списке разрешенных"""
    return user_id in ALLOWED_USERS

def get_user_role(user_id: int) -> str:
    """Возвращает роль пользователя"""
    return "admin" if user_id == ADMIN_USER_ID else "user"

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id == ADMIN_USER_ID

# Инициализируем базу при импорте
init_auth_db()
