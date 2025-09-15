import sqlite3
import logging
import shutil
import os
from datetime import datetime
from threading import local
from threading import Timer
import threading

logger = logging.getLogger(__name__)

# Используем ThreadLocal для безопасного доступа к БД в многопоточности
thread_local = local()

# Глобальная переменная для таймера бэкапов
backup_timer = None

def get_db_connection():
    """Возвращает соединение с БД для текущего потока"""
    if not hasattr(thread_local, 'conn'):
        thread_local.conn = sqlite3.connect('parts.db', check_same_thread=False)
        thread_local.conn.row_factory = sqlite3.Row
    return thread_local.conn

def init_db():
    """Инициализация базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Таблица запчастей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        part_number TEXT NOT NULL UNIQUE,
        quantity INTEGER DEFAULT 0,
        unit TEXT DEFAULT 'шт.',
        price REAL DEFAULT 0.0,
        location TEXT DEFAULT 'склад',
        min_stock INTEGER DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица транзакций
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        document_number TEXT,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (part_id) REFERENCES parts (id)
    )
    ''')
    
    conn.commit()
    logger.info("База данных успешно инициализирована")
    return conn

def backup_database():
    """Создание резервной копии базы данных"""
    try:
        # Создаем папку для бэкапов если нет
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            logger.info(f"Создана папка для бэкапов: {backup_dir}")
        
        # Формируем имя файла с датой
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f'parts_backup_{timestamp}.db')
        
        # Закрываем соединение перед копированием
        close_db()
        
        # Копируем файл базы данных
        shutil.copy2('parts.db', backup_file)
        
        # Восстанавливаем соединение
        get_db_connection()
        
        logger.info(f"Резервная копия создана: {backup_file}")
        
        # Очищаем старые бэкапы (оставляем последние 10)
        cleanup_old_backups(backup_dir, keep=10)
        
        return backup_file
        
    except Exception as e:
        logger.error(f"Ошибка при создании резервной копии: {e}")
        # Восстанавливаем соединение в случае ошибки
        try:
            get_db_connection()
        except:
            pass
        return None

def cleanup_old_backups(backup_dir, keep=10):
    """Очистка старых резервных копий"""
    try:
        if not os.path.exists(backup_dir):
            return
            
        backup_files = [f for f in os.listdir(backup_dir) if f.startswith('parts_backup_') and f.endswith('.db')]
        backup_files.sort(reverse=True)
        
        # Удаляем старые файлы
        for old_file in backup_files[keep:]:
            file_path = os.path.join(backup_dir, old_file)
            os.remove(file_path)
            logger.info(f"Удален старый бэкап: {old_file}")
            
    except Exception as e:
        logger.error(f"Ошибка при очистке старых бэкапов: {e}")

def start_auto_backup(interval_hours=24):
    """Запуск автоматического резервного копирования"""
    global backup_timer
    
    def backup_wrapper():
        try:
            backup_database()
        finally:
            # Перезапускаем таймер
            start_auto_backup(interval_hours)
    
    # Отменяем предыдущий таймер если есть
    if backup_timer:
        backup_timer.cancel()
    
    # Запускаем новый таймер
    backup_timer = Timer(interval_hours * 3600, backup_wrapper)
    backup_timer.daemon = True
    backup_timer.start()
    
    logger.info(f"Автоматическое резервное копирование запущено (интервал: {interval_hours} часов)")

def stop_auto_backup():
    """Остановка автоматического резервного копирования"""
    global backup_timer
    if backup_timer:
        backup_timer.cancel()
        backup_timer = None
        logger.info("Автоматическое резервное копирование остановлено")

def close_db():
    """Закрывает соединение с БД для текущего потока"""
    if hasattr(thread_local, 'conn'):
        thread_local.conn.close()
        del thread_local.conn
