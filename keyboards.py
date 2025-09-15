from telegram import ReplyKeyboardMarkup

# Утилиты для создания клавиатур
def get_cancel_keyboard():
    return ReplyKeyboardMarkup([['❌ Отмена']], resize_keyboard=True)

def get_main_keyboard():
    keyboard = [
        ['📦 Приход', '📤 Расход'],
        ['📊 Остатки', '🔍 Поиск'],
        ['➕ Добавить запчасть', '✏️ Редактировать запчасть'],
        ['🗑️ Удалить запчасть', '📋 Отчет'],
        ['👑 Управление пользователями', '💾 Бэкапы'],
        ['❓ Помощь']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_navigation_keyboard(has_prev: bool, has_next: bool):
    """Клавиатура для навигации по страницам"""
    keyboard = []
    if has_prev:
        keyboard.append(['◀️ Предыдущая страница'])
    if has_next:
        keyboard.append(['▶️ Следующая страница'])
    keyboard.append(['📋 Главное меню'])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_users_management_keyboard():
    """Клавиатура для управления пользователями"""
    keyboard = [
        ['👥 Список пользователей', '➕ Добавить пользователя'],
        ['➖ Удалить пользователя', '📋 Главное меню']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_backup_keyboard():
    """Клавиатура для управления бэкапами"""
    keyboard = [
        ['💾 Создать бэкап', '📊 Статус бэкапов'],
        ['📋 Главное меню']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
