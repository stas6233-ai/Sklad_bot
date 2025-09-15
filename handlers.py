import logging
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters
from database import get_db_connection, backup_database
from keyboards import get_cancel_keyboard, get_main_keyboard, get_navigation_keyboard, get_users_management_keyboard, get_backup_keyboard
from auth import is_user_allowed, get_user_role, is_admin
from config import ALLOWED_USERS, ADMIN_USER_ID, ITEMS_PER_PAGE

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(ADD_PART_NAME, ADD_PART_NUMBER, ADD_PART_QUANTITY, ADD_PART_UNIT, 
 ADD_PART_MIN_STOCK, EDIT_PART_SELECT, EDIT_PART_FIELD, EDIT_PART_VALUE, 
 DELETE_PART_SELECT, DELETE_PART_CONFIRM, INCOMING, OUTGOING, SEARCH,
 ADD_USER, REMOVE_USER) = range(15)

async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Промежуточный обработчик для проверки прав"""
    user_id = update.effective_user.id
    
    if not is_user_allowed(user_id):
        logger.warning(f"Неавторизованный доступ: {user_id}")
        if update.message:
            await update.message.reply_text(
                "⛔ Доступ запрещен!\n\n"
                "У вас нет прав для использования этого бота.\n"
                "Обратитесь к администратору."
            )
        return False
    
    context.user_data['role'] = get_user_role(user_id)
    return True

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return
    
    await update.message.reply_text(
        '🏭 Бот учета запасных частей\n\n'
        'Выберите действие:',
        reply_markup=get_main_keyboard()
    )

# Команда помощи
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return
        
    help_text = """
🤖 Команды бота:

📦 Приход - оформить поступление запчастей
📤 Расход - оформить выдачу запчастей
📊 Остатки - посмотреть текущие остатки
🔍 Поиск - найти запчасть по названию/номеру
➕ Добавить запчасть - добавить новую позицию
✏️ Редактировать запчасть - изменить данные запчасти
🗑️ Удалить запчасть - удалить позицию из системы
📋 Отчет - получить отчет по складу
👑 Управление пользователями - управление доступом
💾 Бэкапы - управление резервными копиями

❌ Отмена - отменить текущее действие

📝 Форматы ввода:
• Приход/расход: "Код детали | Количество"
• Поиск: "Номер или название"
"""
    await update.message.reply_text(help_text)

# Управление бэкапами
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для создания резервной копии вручную"""
    if not await auth_middleware(update, context):
        return
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только администратор может создавать резервные копии.")
        return
    
    await update.message.reply_text("🔄 Создание резервной копии...")
    
    backup_file = backup_database()
    
    if backup_file:
        file_size = os.path.getsize(backup_file) / 1024
        await update.message.reply_text(
            f"✅ Резервная копия успешно создана!\n\n"
            f"📁 Файл: {os.path.basename(backup_file)}\n"
            f"💾 Размер: {file_size:.1f} КБ\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            reply_markup=get_backup_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при создании резервной копии.",
            reply_markup=get_backup_keyboard()
        )

async def backup_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра статуса бэкапов"""
    if not await auth_middleware(update, context):
        return
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только администратор может просматривать статус бэкапов.")
        return
    
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        await update.message.reply_text(
            "📭 Резервные копии отсутствуют.",
            reply_markup=get_backup_keyboard()
        )
        return
    
    backup_files = [f for f in os.listdir(backup_dir) if f.startswith('parts_backup_') and f.endswith('.db')]
    backup_files.sort(reverse=True)
    
    if not backup_files:
        await update.message.reply_text(
            "📭 Резервные копии отсутствуют.",
            reply_markup=get_backup_keyboard()
        )
        return
    
    total_size = sum(os.path.getsize(os.path.join(backup_dir, f)) for f in backup_files) / 1024 / 1024
    
    # Получаем информацию о последнем бэкапе
    last_backup = backup_files[0]
    last_backup_size = os.path.getsize(os.path.join(backup_dir, last_backup)) / 1024
    last_backup_time = " ".join(last_backup.split('_')[2:4]).replace('.db', '')
    
    message = (
        f"📊 Статус резервного копирования:\n\n"
        f"• Всего копий: {len(backup_files)}\n"
        f"• Общий размер: {total_size:.1f} МБ\n"
        f"• Последняя копия: {last_backup_time}\n"
        f"• Размер: {last_backup_size:.1f} КБ\n\n"
        f"Для создания новой копии нажмите '💾 Создать бэкап'"
    )
    
    await update.message.reply_text(message, reply_markup=get_backup_keyboard())

# Обработка навигации
async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return
        
    text = update.message.text
    
    if text == '◀️ Предыдущая страница':
        context.user_data['stock_page'] = context.user_data.get('stock_page', 2) - 1
        await show_stock(update, context)
    elif text == '▶️ Следующая страница':
        context.user_data['stock_page'] = context.user_data.get('stock_page', 0) + 1
        await show_stock(update, context)
    elif text == '📋 Главное меню':
        await start(update, context)
    else:
        await handle_message(update, context)

# Управление пользователями
async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только администратор может управлять пользователями.")
        return
    
    await update.message.reply_text(
        "👑 Управление пользователями:\n\n"
        "Выберите действие:",
        reply_markup=get_users_management_keyboard()
    )

# Показать список пользователей
async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только администратор может просматривать пользователей.")
        return
    
    message = "👥 Список пользователей:\n\n"
    for uid, username in ALLOWED_USERS.items():
        role = "👑 Админ" if uid == ADMIN_USER_ID else "👤 Пользователь"
        message += f"{role}: {username} (ID: {uid})\n"
    
    message += f"\nВсего пользователей: {len(ALLOWED_USERS)}"
    await update.message.reply_text(message, reply_markup=get_users_management_keyboard())

# Добавление пользователя - начало
async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только администратор может добавлять пользователей.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Введите ID пользователя для добавления:\n\n"
        "Чтобы получить ID пользователя, попросите его написать боту @userinfobot\n\n"
        "❌ Отмена - отменить добавление",
        reply_markup=get_cancel_keyboard()
    )
    return ADD_USER

async def add_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    try:
        new_user_id = int(update.message.text.strip())
        
        if new_user_id in ALLOWED_USERS:
            await update.message.reply_text("❌ Этот пользователь уже есть в списке.")
            return ADD_USER
        
        # Добавляем пользователя
        ALLOWED_USERS[new_user_id] = f"Пользователь_{new_user_id}"
        
        # Обновляем .env файл
        update_env_file(new_user_id, None)
        
        await update.message.reply_text(
            f"✅ Пользователь {new_user_id} успешно добавлен!\n\n"
            f"Теперь у него есть доступ к боту.",
            reply_markup=get_users_management_keyboard()
        )
        
    except ValueError:
        await update.message.reply_text("❌ ID пользователя должен быть числом! Введите снова:")
        return ADD_USER
    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении пользователя.")
    
    return ConversationHandler.END

# Удаление пользователя - начало
async def remove_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только администратор может удалять пользователей.")
        return ConversationHandler.END
    
    # Показываем список пользователей для удаления
    message = "Выберите пользователя для удаления:\n\n"
    users_list = []
    
    for uid, username in ALLOWED_USERS.items():
        if uid != ADMIN_USER_ID:  # Нельзя удалить админа
            users_list.append([f"➖ {username} (ID: {uid})"])
            message += f"👤 {username} (ID: {uid})\n"
    
    if not users_list:
        await update.message.reply_text("❌ Нет пользователей для удаления.", reply_markup=get_users_management_keyboard())
        return ConversationHandler.END
    
    users_list.append(['❌ Отмена'])
    reply_markup = ReplyKeyboardMarkup(users_list, resize_keyboard=True)
    
    await update.message.reply_text(
        message + "\nВыберите пользователя для удаления:",
        reply_markup=reply_markup
    )
    return REMOVE_USER

async def remove_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    try:
        # Извлекаем ID из текста (формат: "➖ Username (ID: 123456789)")
        text = update.message.text
        if '(ID:' in text:
            user_id_str = text.split('(ID:')[1].split(')')[0].strip()
            user_id_to_remove = int(user_id_str)
        else:
            await update.message.reply_text("❌ Неверный формат. Выберите пользователя из списка.")
            return REMOVE_USER
        
        if user_id_to_remove == ADMIN_USER_ID:
            await update.message.reply_text("❌ Нельзя удалить администратора!")
            return REMOVE_USER
        
        if user_id_to_remove not in ALLOWED_USERS:
            await update.message.reply_text("❌ Пользователь не найден в списке.")
            return REMOVE_USER
        
        # Удаляем пользователя
        removed_username = ALLOWED_USERS.pop(user_id_to_remove)
        
        # Обновляем .env файл
        update_env_file(None, user_id_to_remove)
        
        await update.message.reply_text(
            f"✅ Пользователь {removed_username} (ID: {user_id_to_remove}) удален!\n\n"
            f"Теперь у него нет доступа к боту.",
            reply_markup=get_users_management_keyboard()
        )
        
    except ValueError:
        await update.message.reply_text("❌ Ошибка формата. Выберите пользователя из списка:")
        return REMOVE_USER
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}")
        await update.message.reply_text("❌ Ошибка при удалении пользователя.")
    
    return ConversationHandler.END

# Функция для обновления .env файла
def update_env_file(add_user_id: int = None, remove_user_id: int = None):
    """Обновляет файл .env с новым списком пользователей"""
    try:
        # Читаем текущий файл
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Обновляем список пользователей
        current_ids = set()
        for line in lines:
            if line.startswith('ALLOWED_USER_IDS='):
                current_ids = set(int(uid.strip()) for uid in line.split('=', 1)[1].split(',') if uid.strip())
                break
        
        if add_user_id:
            current_ids.add(add_user_id)
        if remove_user_id and remove_user_id in current_ids:
            current_ids.remove(remove_user_id)
        
        # Формируем новую строку
        new_users_str = ','.join(str(uid) for uid in current_ids)
        
        # Обновляем файл
        new_lines = []
        users_line_found = False
        
        for line in lines:
            if line.startswith('ALLOWED_USER_IDS='):
                new_lines.append(f'ALLOWED_USER_IDS={new_users_str}\n')
                users_line_found = True
            else:
                new_lines.append(line)
        
        # Если строка не найдена, добавляем ее
        if not users_line_found:
            new_lines.append(f'ALLOWED_USER_IDS={new_users_str}\n')
        
        # Записываем обратно
        with open('.env', 'w') as f:
            f.writelines(new_lines)
            
        logger.info(f"Обновлен .env файл. Текущие пользователи: {new_users_str}")
            
    except Exception as e:
        logger.error(f"Ошибка обновления .env файла: {e}")

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return
        
    text = update.message.text
    
    # Навигация
    if text in ['◀️ Предыдущая страница', '▶️ Следующая страница', '📋 Главное меню']:
        await handle_navigation(update, context)
    # Управление бэкапами
    elif text == '💾 Бэкапы':
        await update.message.reply_text(
            "💾 Управление резервными копиями:\n\n"
            "Выберите действие:",
            reply_markup=get_backup_keyboard()
        )
    elif text == '💾 Создать бэкап':
        await backup_command(update, context)
    elif text == '📊 Статус бэкапов':
        await backup_status(update, context)
    # Управление пользователями
    elif text == '👑 Управление пользователями':
        await manage_users(update, context)
    elif text == '👥 Список пользователей':
        await show_users(update, context)
    elif text == '➕ Добавить пользователя':
        await add_user_start(update, context)
    elif text == '➖ Удалить пользователя':
        await remove_user_start(update, context)
    # Основные команды
    elif text == '📦 Приход':
        await incoming_start(update, context)
    elif text == '📤 Расход':
        await outgoing_start(update, context)
    elif text == '📊 Остатки':
        await show_stock(update, context)
    elif text == '🔍 Поиск':
        await search_start(update, context)
    elif text == '➕ Добавить запчасть':
        await add_part_start(update, context)
    elif text == '✏️ Редактировать запчасть':
        await edit_part_start(update, context)
    elif text == '🗑️ Удалить запчасть':
        await delete_part_start(update, context)
    elif text == '📋 Отчет':
        await generate_report(update, context)
    elif text == '❓ Помощь':
        await help_command(update, context)
    elif text == '❌ Отмена':
        await cancel(update, context)
    else:
        await update.message.reply_text("Не понимаю команду. Используйте кнопки меню.")

# Добавление запчасти - начало
async def add_part_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        'Введите наименование детали:\n\n'
        'Пример: Подшипник шариковый 6305\n\n'
        '❌ Отмена - отменить добавление',
        reply_markup=get_cancel_keyboard()
    )
    return ADD_PART_NAME

async def add_part_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    context.user_data['new_part'] = {'name': update.message.text.strip()}
    await update.message.reply_text(
        'Введите код детали (артикул):\n\n'
        'Пример: 6305-2RS\n\n'
        '❌ Отмена - отменить добавление'
    )
    return ADD_PART_NUMBER

async def add_part_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    part_number = update.message.text.strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM parts WHERE part_number = ?', (part_number,))
    existing_part = cursor.fetchone()
    
    if existing_part:
        await update.message.reply_text('❌ Запчасть с таким кодом уже существует! Введите другой код:')
        return ADD_PART_NUMBER
    
    context.user_data['new_part']['part_number'] = part_number
    await update.message.reply_text(
        'Введите начальное количество:\n\n'
        'Пример: 10\n\n'
        '❌ Отмена - отменить добавление'
    )
    return ADD_PART_QUANTITY

async def add_part_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    try:
        quantity = int(update.message.text.strip())
        context.user_data['new_part']['quantity'] = quantity
        
        keyboard = [['шт.', 'м', 'кг', 'уп.'], ['❌ Отмена']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            'Выберите или введите единицу измерения:\n\n'
            'Пример: шт., м, кг, уп.\n\n'
            '❌ Отмена - отменить добавление',
            reply_markup=reply_markup
        )
        return ADD_PART_UNIT
    except ValueError:
        await update.message.reply_text('❌ Количество должно быть числом! Введите снова:')
        return ADD_PART_QUANTITY

async def add_part_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    unit = update.message.text.strip()
    context.user_data['new_part']['unit'] = unit
    await update.message.reply_text(
        'Введите минимальный запас (пороговое значение для оповещения):\n\n'
        'Пример: 5\n\n'
        '❌ Отмена - отменить добавление',
        reply_markup=get_cancel_keyboard()
    )
    return ADD_PART_MIN_STOCK

async def add_part_min_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    try:
        min_stock = int(update.message.text.strip())
        part_data = context.user_data['new_part']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO parts (name, part_number, quantity, unit, min_stock) VALUES (?, ?, ?, ?, ?)',
            (part_data['name'], part_data['part_number'], part_data['quantity'], 
             part_data['unit'], min_stock)
        )
        
        if part_data['quantity'] > 0:
            part_id = cursor.lastrowid
            cursor.execute(
                'INSERT INTO transactions (part_id, type, quantity) VALUES (?, ?, ?)',
                (part_id, 'incoming', part_data['quantity'])
            )
        
        conn.commit()
        
        await update.message.reply_text(
            f'✅ Запчасть успешно добавлена:\n\n'
            f'🏷️ Наименование: {part_data["name"]}\n'
            f'🔢 Код: {part_data["part_number"]}\n'
            f'📦 Количество: {part_data["quantity"]} {part_data["unit"]}\n'
            f'⚠️ Мин. запас: {min_stock} {part_data["unit"]}',
            reply_markup=get_main_keyboard()
        )
        
        context.user_data.pop('new_part', None)
        
    except ValueError:
        await update.message.reply_text('❌ Минимальный запас должен быть числом! Введите снова:')
        return ADD_PART_MIN_STOCK
    except Exception as e:
        logger.error(f"Ошибка при добавлении запчасти: {e}")
        await update.message.reply_text('❌ Ошибка при добавлении запчасти. Попробуйте снова.')
    
    return ConversationHandler.END

# Удаление запчасти - начало
async def delete_part_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        'Введите код детали для удаления:\n\n'
        'Пример: 6305-2RS\n\n'
        '❌ Отмена - отменить удаление',
        reply_markup=get_cancel_keyboard()
    )
    return DELETE_PART_SELECT

async def delete_part_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    part_number = update.message.text.strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM parts WHERE part_number = ?', (part_number,))
    part = cursor.fetchone()
    
    if not part:
        await update.message.reply_text('❌ Запчасть не найдена! Введите другой код:')
        return DELETE_PART_SELECT
    
    context.user_data['delete_part'] = {
        'id': part[0],
        'name': part[1],
        'part_number': part[2],
        'quantity': part[3],
        'unit': part[4]
    }
    
    keyboard = [['✅ Да, удалить', '❌ Нет, отменить']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f'⚠️ Вы уверены, что хотите удалить запчасть?\n\n'
        f'🏷️ Наименование: {part[1]}\n'
        f'🔢 Код: {part[2]}\n'
        f'📦 Количество: {part[3]} {part[4]}\n\n'
        'Это действие нельзя отменить!',
        reply_markup=reply_markup
    )
    return DELETE_PART_CONFIRM

async def delete_part_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Нет, отменить':
        await update.message.reply_text(
            '✅ Удаление отменено.',
            reply_markup=get_main_keyboard()
        )
        context.user_data.pop('delete_part', None)
        return ConversationHandler.END
        
    if update.message.text != '✅ Да, удалить':
        await update.message.reply_text('❌ Пожалуйста, выберите вариант из клавиатуры:')
        return DELETE_PART_CONFIRM
        
    part_data = context.user_data.get('delete_part')
    if not part_data:
        await update.message.reply_text('❌ Ошибка: данные о запчасти не найдены.')
        return ConversationHandler.END
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Сначала удаляем связанные транзакции
        cursor.execute('DELETE FROM transactions WHERE part_id = ?', (part_data['id'],))
        # Затем удаляем саму запчасть
        cursor.execute('DELETE FROM parts WHERE id = ?', (part_data['id'],))
        
        conn.commit()
        
        await update.message.reply_text(
            f'✅ Запчасть успешно удалена:\n\n'
            f'🏷️ Наименование: {part_data["name"]}\n'
            f'🔢 Код: {part_data["part_number"]}\n'
            f'📦 Было на складе: {part_data["quantity"]} {part_data["unit"]}',
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при удалении запчасти: {e}")
        await update.message.reply_text(
            '❌ Ошибка при удалении запчасти.',
            reply_markup=get_main_keyboard()
        )
    
    context.user_data.pop('delete_part', None)
    return ConversationHandler.END

# Редактирование запчасти - начало
async def edit_part_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        'Введите код детали для редактирования:\n\n'
        'Пример: 6305-2RS\n\n'
        '❌ Отмена - отменить редактирование',
        reply_markup=get_cancel_keyboard()
    )
    return EDIT_PART_SELECT

async def edit_part_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    part_number = update.message.text.strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM parts WHERE part_number = ?', (part_number,))
    part = cursor.fetchone()
    
    if not part:
        await update.message.reply_text('❌ Запчасть не найдена! Введите другой код:')
        return EDIT_PART_SELECT
    
    context.user_data['edit_part'] = {
        'id': part[0],
        'name': part[1],
        'part_number': part[2],
        'quantity': part[3],
        'unit': part[4],
        'min_stock': part[7]
    }
    
    keyboard = [
        ['✏️ Наименование', '✏️ Код'],
        ['✏️ Количество', '✏️ Единица измерения'],
        ['✏️ Мин. запас', '❌ Отмена']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f'📝 Редактирование запчасти:\n\n'
        f'🏷️ Наименование: {part[1]}\n'
        f'🔢 Код: {part[2]}\n'
        f'📦 Количество: {part[3]} {part[4]}\n'
        f'⚠️ Мин. запас: {part[7]} {part[4]}\n\n'
        'Выберите что редактировать:',
        reply_markup=reply_markup
    )
    return EDIT_PART_FIELD

async def edit_part_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    field = update.message.text.strip()
    part_data = context.user_data['edit_part']
    
    field_map = {
        '✏️ Наименование': 'name',
        '✏️ Код': 'part_number',
        '✏️ Количество': 'quantity',
        '✏️ Единица измерения': 'unit',
        '✏️ Мин. запас': 'min_stock'
    }
    
    if field not in field_map:
        await update.message.reply_text('❌ Неверный выбор! Выберите поле для редактирования:')
        return EDIT_PART_FIELD
    
    context.user_data['edit_field'] = field_map[field]
    
    current_value = part_data[field_map[field]]
    await update.message.reply_text(
        f'Текущее значение: {current_value}\n\n'
        f'Введите новое значение:\n\n'
        f'❌ Отмена - отменить редактирование',
        reply_markup=get_cancel_keyboard()
    )
    return EDIT_PART_VALUE

async def edit_part_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    try:
        field = context.user_data['edit_field']
        new_value = update.message.text.strip()
        part_data = context.user_data['edit_part']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if field in ['quantity', 'min_stock']:
            new_value = int(new_value)
        
        if field == 'part_number' and new_value != part_data['part_number']:
            cursor.execute('SELECT * FROM parts WHERE part_number = ?', (new_value,))
            if cursor.fetchone():
                await update.message.reply_text('❌ Запчасть с таким кодом уже существует! Введите другой код:')
                return EDIT_PART_VALUE
        
        # БЕЗОПАСНОЕ обновление с использованием словаря
        allowed_fields = {
            'name': 'name',
            'part_number': 'part_number', 
            'quantity': 'quantity',
            'unit': 'unit',
            'min_stock': 'min_stock'
        }
        
        if field not in allowed_fields:
            await update.message.reply_text('❌ Неверное поле для редактирования!')
            return ConversationHandler.END
        
        # Безопасное выполнение запроса
        sql = f'UPDATE parts SET {allowed_fields[field]} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
        cursor.execute(sql, (new_value, part_data['id']))
        
        if field == 'quantity':
            quantity_diff = new_value - part_data['quantity']
            if quantity_diff != 0:
                transaction_type = 'incoming' if quantity_diff > 0 else 'outgoing'
                cursor.execute(
                    'INSERT INTO transactions (part_id, type, quantity) VALUES (?, ?, ?)',
                    (part_data['id'], transaction_type, abs(quantity_diff))
                )
        
        conn.commit()
        
        await update.message.reply_text(
            f'✅ Запчасть успешно обновлена!\n\n'
            f'Поле "{field}" изменено на: {new_value}',
            reply_markup=get_main_keyboard()
        )
        
        context.user_data.pop('edit_part', None)
        context.user_data.pop('edit_field', None)
        
    except ValueError:
        await update.message.reply_text('❌ Неверный формат! Введите числовое значение:')
        return EDIT_PART_VALUE
    except Exception as e:
        logger.error(f"Ошибка при редактировании запчасти: {e}")
        await update.message.reply_text('❌ Ошибка при обновлении.')
    
    return ConversationHandler.END

# Приход запчастей
async def incoming_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        'Введите данные прихода:\n'
        'Код детали | Количество\n\n'
        'Пример: 6305-2RS | 10\n\n'
        '❌ Отмена - отменить приход',
        reply_markup=get_cancel_keyboard()
    )
    return INCOMING

async def incoming_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    try:
        data = update.message.text.split('|')
        if len(data) < 2:
            await update.message.reply_text('❌ Неверный формат. Используйте: Код детали | Количество')
            return INCOMING
        
        part_number = data[0].strip()
        quantity = int(data[1].strip())
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM parts WHERE part_number = ?', (part_number,))
        part = cursor.fetchone()
        
        if not part:
            await update.message.reply_text('❌ Запчасть не найдена!')
            return INCOMING
        
        new_quantity = part[3] + quantity
        cursor.execute(
            'UPDATE parts SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (new_quantity, part[0])
        )
        
        cursor.execute(
            'INSERT INTO transactions (part_id, type, quantity) VALUES (?, ?, ?)',
            (part[0], 'incoming', quantity)
        )
        
        conn.commit()
        
        await update.message.reply_text(
            f'✅ Приход оформлен:\n'
            f'Запчасть: {part[1]}\n'
            f'Код: {part[2]}\n'
            f'Количество: +{quantity} {part[4]}\n'
            f'Новый остаток: {new_quantity} {part[4]}',
            reply_markup=get_main_keyboard()
        )
        
    except ValueError:
        await update.message.reply_text('❌ Ошибка: количество должно быть числом!')
        return INCOMING
    except Exception as e:
        logger.error(f"Ошибка при приходе: {e}")
        await update.message.reply_text('❌ Ошибка при обработке прихода.')
    
    return ConversationHandler.END

# Расход запчастей
async def outgoing_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        'Введите данные расхода:\n'
        'Код детали | Количество\n\n'
        'Пример: 6305-2RS | 2\n\n'
        '❌ Отмена - отменить расход',
        reply_markup=get_cancel_keyboard()
    )
    return OUTGOING

async def outgoing_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    try:
        data = update.message.text.split('|')
        if len(data) < 2:
            await update.message.reply_text('❌ Неверный формат. Используйте: Код детали | Количество')
            return OUTGOING
        
        part_number = data[0].strip()
        quantity = int(data[1].strip())
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM parts WHERE part_number = ?', (part_number,))
        part = cursor.fetchone()
        
        if not part:
            await update.message.reply_text('❌ Запчасть не найдена!')
            return OUTGOING
        
        if part[3] < quantity:
            await update.message.reply_text(
                f'❌ Недостаточно на складе!\n'
                f'Запчасть: {part[1]}\n'
                f'Доступно: {part[3]} {part[4]}\n'
                f'Требуется: {quantity} {part[4]}'
            )
            return OUTGOING
        
        new_quantity = part[3] - quantity
        cursor.execute(
            'UPDATE parts SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (new_quantity, part[0])
        )
        
        cursor.execute(
            'INSERT INTO transactions (part_id, type, quantity) VALUES (?, ?, ?)',
            (part[0], 'outgoing', quantity)
        )
        
        conn.commit()
        
        await update.message.reply_text(
            f'✅ Расход оформлен:\n'
            f'Запчасть: {part[1]}\n'
            f'Код: {part[2]}\n'
            f'Количество: -{quantity} {part[4]}\n'
            f'Новый остаток: {new_quantity} {part[4]}',
            reply_markup=get_main_keyboard()
        )
        
    except ValueError:
        await update.message.reply_text('❌ Ошибка: количество должно быть числом!')
        return OUTGOING
    except Exception as e:
        logger.error(f"Ошибка при расходе: {e}")
        await update.message.reply_text('❌ Ошибка при обработке расхода.')
    
    return ConversationHandler.END

# Поиск запчастей
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return ConversationHandler.END
        
    await update.message.reply_text(
        'Введите номер или название запчасти для поиска:\n\n'
        '❌ Отмена - отменить поиск',
        reply_markup=get_cancel_keyboard()
    )
    return SEARCH

async def search_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '❌ Отмена':
        await cancel(update, context)
        return ConversationHandler.END
        
    search_term = update.message.text.strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT * FROM parts WHERE name LIKE ? OR part_number LIKE ?',
        (f'%{search_term}%', f'%{search_term}%')
    )
    parts = cursor.fetchall()
    
    if not parts:
        await update.message.reply_text('🔍 Запчасти не найдены.', reply_markup=get_main_keyboard())
    else:
        message = "🔍 Результаты поиска:\n\n"
        for part in parts:
            status = "⚠️ " if part[3] <= part[7] else "✅ "
            message += f"{status}{part[1]} ({part[2]}): {part[3]} {part[4]}\n"
        
        await update.message.reply_text(message, reply_markup=get_main_keyboard())
    
    return ConversationHandler.END

# Показать остатки
async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM parts')
    total_count = cursor.fetchone()[0]
    
    if total_count == 0:
        await update.message.reply_text('📭 Нет запчастей в базе данных.')
        return
    
    # Получаем страницу из контекста или устанавливаем первую
    page = context.user_data.get('stock_page', 1)
    offset = (page - 1) * ITEMS_PER_PAGE
    
    cursor.execute('SELECT * FROM parts ORDER BY name LIMIT ? OFFSET ?', (ITEMS_PER_PAGE, offset))
    parts = cursor.fetchall()
    
    total_pages = (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    message = f"📊 Остатки на складе (стр. {page}/{total_pages})\n\n"
    
    for part in parts:
        status = "⚠️ " if part[3] <= part[7] else "✅ "
        message += f"{status}{part[1]} ({part[2]}): {part[3]} {part[4]}\n"
    
    # Добавляем кнопки навигации если нужно
    if total_count > ITEMS_PER_PAGE:
        has_prev = page > 1
        has_next = page < total_pages
        
        reply_markup = get_navigation_keyboard(has_prev, has_next)
        await update.message.reply_text(message, reply_markup=reply_markup)
        
        # Сохраняем текущую страницу
        context.user_data['stock_page'] = page
    else:
        await update.message.reply_text(message, reply_markup=get_main_keyboard())

# Генерация отчета
async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_middleware(update, context):
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM parts WHERE quantity <= min_stock ORDER BY quantity')
    low_stock = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*), SUM(quantity) FROM parts')
    total_parts, total_quantity = cursor.fetchone()
    
    message = "📋 Отчет по складу\n\n"
    message += f"Всего позиций: {total_parts}\n"
    message += f"Общее количество: {total_quantity or 0} шт.\n\n"
    
    if low_stock:
        message += "⚠️ Критический остаток:\n"
        for part in low_stock:
            message += f"{part[1]} ({part[2]}): {part[3]}/{part[7]} {part[4]}\n"
    else:
        message += "✅ Все позиции в норме"
    
    await update.message.reply_text(message)

# Отмена действия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        '❌ Действие отменено.',
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END
