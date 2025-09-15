import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID администратора (замените на ваш реальный ID)
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '123456789'))

# Получаем список разрешенных пользователей
allowed_users_str = os.getenv('ALLOWED_USER_IDS', '')
ALLOWED_USER_IDS = [int(uid.strip()) for uid in allowed_users_str.split(',') if uid.strip()]

# Создаем словарь пользователей
ALLOWED_USERS = {uid: f"Пользователь_{uid}" for uid in ALLOWED_USER_IDS}
if ADMIN_USER_ID:
    ALLOWED_USERS[ADMIN_USER_ID] = "Администратор"

# Настройки пагинации
ITEMS_PER_PAGE = 10

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в переменных окружения")
