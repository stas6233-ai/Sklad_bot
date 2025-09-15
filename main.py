import logging
from datetime import datetime
from telegram.ext import Application, ConversationHandler, MessageHandler, CommandHandler, filters
from telegram.error import TelegramError
from config import BOT_TOKEN
from database import init_db, close_db, start_auto_backup, stop_auto_backup
from handlers import *
from keyboards import get_main_keyboard

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальная переменная для отслеживания состояния
bot_start_time = None

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    try:
        logger.error(f"Ошибка в обработчике: {context.error}", exc_info=context.error)
        
        # Если ошибка связана с конкретным сообщением
        if update and hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "⚠️ Произошла ошибка. Попробуйте еще раз или обратитесь к администратору."
            )
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}")

async def post_init(application: Application):
    """Функция, вызываемая после инициализации бота"""
    global bot_start_time
    bot_start_time = datetime.now()
    logger.info(f"Бот успешно запущен в {bot_start_time}")

async def post_stop(application: Application):
    """Функция, вызываемая при остановке бота"""
    logger.info("Бот остановлен")
    close_db()

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для проверки статуса бота"""
    if not await auth_middleware(update, context):
        return
        
    global bot_start_time
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем статистику
    cursor.execute('SELECT COUNT(*) FROM parts')
    parts_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM transactions')
    transactions_count = cursor.fetchone()[0]
    
    uptime = datetime.now() - bot_start_time if bot_start_time else "неизвестно"
    
    status_message = (
        "🤖 Статус бота:\n\n"
        f"• Запущен: {bot_start_time}\n"
        f"• Аптайм: {uptime}\n"
        f"• Запчастей в базе: {parts_count}\n"
        f"• Операций в истории: {transactions_count}\n"
        f"• Пользователей: {len(ALLOWED_USERS)}\n"
        f"• Версия: 2.0\n"
        "• Статус: ✅ Работает нормально"
    )
    
    await update.message.reply_text(status_message)

def main():
    """Главная функция запуска бота"""
    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        init_db()
        logger.info("База данных готова")
        
        # Запуск автоматического резервного копирования (раз в 24 часа)
        start_auto_backup(interval_hours=24)
        
        # Создание приложения
        logger.info("Создание приложения бота...")
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики ошибок
        application.add_error_handler(error_handler)
        
        # Conversation Handlers
        logger.info("Регистрация обработчиков...")
        
        conv_handler_add = ConversationHandler(
            entry_points=[MessageHandler(filters.Text(['➕ Добавить запчасть']), add_part_start)],
            states={
                ADD_PART_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_part_name)],
                ADD_PART_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_part_number)],
                ADD_PART_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_part_quantity)],
                ADD_PART_UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_part_unit)],
                ADD_PART_MIN_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_part_min_stock)],
            },
            fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Text(['❌ Отмена']), cancel)],
            name="add_part_conversation"
        )
        
        conv_handler_edit = ConversationHandler(
            entry_points=[MessageHandler(filters.Text(['✏️ Редактировать запчасть']), edit_part_start)],
            states={
                EDIT_PART_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_part_select)],
                EDIT_PART_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_part_field)],
                EDIT_PART_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_part_value)],
            },
            fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Text(['❌ Отмена']), cancel)],
            name="edit_part_conversation"
        )
        
        conv_handler_delete = ConversationHandler(
            entry_points=[MessageHandler(filters.Text(['🗑️ Удалить запчасть']), delete_part_start)],
            states={
                DELETE_PART_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_part_select)],
                DELETE_PART_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_part_confirm)],
            },
            fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Text(['❌ Отмена']), cancel)],
            name="delete_part_conversation"
        )
        
        conv_handler_incoming = ConversationHandler(
            entry_points=[MessageHandler(filters.Text(['📦 Приход']), incoming_start)],
            states={
                INCOMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, incoming_process)],
            },
            fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Text(['❌ Отмена']), cancel)],
            name="incoming_conversation"
        )
        
        conv_handler_outgoing = ConversationHandler(
            entry_points=[MessageHandler(filters.Text(['📤 Расход']), outgoing_start)],
            states={
                OUTGOING: [MessageHandler(filters.TEXT & ~filters.COMMAND, outgoing_process)],
            },
            fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Text(['❌ Отмена']), cancel)],
            name="outgoing_conversation"
        )
        
        conv_handler_search = ConversationHandler(
            entry_points=[MessageHandler(filters.Text(['🔍 Поиск']), search_start)],
            states={
                SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_process)],
            },
            fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Text(['❌ Отмена']), cancel)],
            name="search_conversation"
        )
        
        # Новые обработчики для управления пользователями
        conv_handler_add_user = ConversationHandler(
            entry_points=[MessageHandler(filters.Text(['➕ Добавить пользователя']), add_user_start)],
            states={
                ADD_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_process)],
            },
            fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Text(['❌ Отмена']), cancel)],
            name="add_user_conversation"
        )
        
        conv_handler_remove_user = ConversationHandler(
            entry_points=[MessageHandler(filters.Text(['➖ Удалить пользователя']), remove_user_start)],
            states={
                REMOVE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_user_process)],
            },
            fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Text(['❌ Отмена']), cancel)],
            name="remove_user_conversation"
        )
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("cancel", cancel))
        application.add_handler(CommandHandler("status", status_command))
        
        application.add_handler(conv_handler_add)
        application.add_handler(conv_handler_edit)
        application.add_handler(conv_handler_delete)
        application.add_handler(conv_handler_incoming)
        application.add_handler(conv_handler_outgoing)
        application.add_handler(conv_handler_search)
        application.add_handler(conv_handler_add_user)
        application.add_handler(conv_handler_remove_user)
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Добавляем обработчики событий
        application.post_init = post_init
        application.post_stop = post_stop
        
        # Запуск бота
        logger.info("Запуск бота...")
        print("🤖 Бот запущен...")
        print("ℹ️  Для проверки статуса используйте /status")
        print("💾 Автоматическое резервное копирование запущено")
        print("⚠️  Для остановки нажмите Ctrl+C")
        
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        print(f"❌ Критическая ошибка: {e}")
    finally:
        # Останавливаем автоматическое копирование при выходе
        stop_auto_backup()
        close_db()
        logger.info("Работа бота завершена")

if __name__ == '__main__':
    main()
