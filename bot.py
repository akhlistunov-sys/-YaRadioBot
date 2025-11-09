import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Импорт констант и функций из database.py
from database import (
    TOKEN, init_db
)

# Импорт обработчиков из webapp
from webapp.handlers import (
    start, about_section, radio_selection, handle_radio_selection,
    campaign_dates, handle_campaign_dates, process_start_date, process_end_date,
    time_slots, handle_time_slots,
    branded_sections, handle_branded_sections,
    campaign_creator, enter_campaign_text, process_campaign_text,
    enter_duration, process_duration,
    production_option, handle_production_option,
    contact_info, process_contact_info,
    show_confirmation, handle_confirmation,
    handle_final_actions, personal_cabinet, detailed_statistics,
    statistics, contacts_details, handle_main_menu, cancel
)

async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для Web App - отправляем обычное меню бота"""
    logger.info("Web App opened, sending bot menu")
    
    keyboard = [
        [InlineKeyboardButton("🚀 НАЧАТЬ РАСЧЕТ", callback_data="create_campaign")],
        [InlineKeyboardButton("📊 ВОЗРАСТНАЯ СТРУКТУРА", callback_data="statistics")],
        [InlineKeyboardButton("🏆 О НАС", callback_data="about")],
        [InlineKeyboardButton("📋 ЛИЧНЫЙ КАБИНЕТ", callback_data="personal_cabinet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = (
        "🎙️ РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
        "📍 Ялуторовск • Заводоуковск\n\n"
        "🤖 **Рассчитайте рекламу за 2 минуты**\n"
        "3 простых шага → готовый медиаплан\n\n"
        "• 6 федеральных радиостанций\n"
        "• Скидка 50% на первую кампанию\n"
        "• Старт через 3 дня\n"
        "• Персональный медиаплан\n\n"
        "🏆 70+ кампаний в 2025 году\n"
        "✅ От 7 000₽"
    )
    
    await update.message.reply_text(caption, reply_markup=reply_markup)
    return "MAIN_MENU"

def main():
    """ОСНОВНАЯ ФУНКЦИЯ - обычный Telegram бот"""
    logger.info("Бот запущен")
    
    if init_db():
        logger.info("База данных инициализирована")
    else:
        logger.error("Ошибка инициализации БД")
    
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler)
        ],
        states={
            "MAIN_MENU": [
                CallbackQueryHandler(handle_main_menu, pattern="^.*$")
            ],
            "RADIO_SELECTION": [
                CallbackQueryHandler(handle_radio_selection, pattern="^.*$")
            ],
            "CAMPAIGN_DATES": [
                CallbackQueryHandler(handle_campaign_dates, pattern="^.*$")
            ],
            "WAITING_START_DATE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_start_date),
                CallbackQueryHandler(handle_main_menu, pattern="^back_to_radio$")
            ],
            "WAITING_END_DATE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_end_date),
                CallbackQueryHandler(handle_main_menu, pattern="^back_to_radio$")
            ],
            "TIME_SLOTS": [
                CallbackQueryHandler(handle_time_slots, pattern="^.*$")
            ],
            "BRANDED_SECTIONS": [
                CallbackQueryHandler(handle_branded_sections, pattern="^.*$")
            ],
            "CAMPAIGN_CREATOR": [
                CallbackQueryHandler(handle_main_menu, pattern="^(back_to_|skip_text|cancel_text|to_production_option|enter_text|enter_duration|provide_own_audio)"),
                CallbackQueryHandler(enter_campaign_text, pattern="^enter_text$"),
                CallbackQueryHandler(enter_duration, pattern="^enter_duration$")
            ],
            "WAITING_TEXT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_campaign_text),
                CallbackQueryHandler(handle_main_menu, pattern="^back_to_creator$"),
                CallbackQueryHandler(handle_main_menu, pattern="^cancel_text$")
            ],
            "WAITING_DURATION": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_duration),
                CallbackQueryHandler(handle_main_menu, pattern="^back_to_creator$"),
                CallbackQueryHandler(handle_main_menu, pattern="^cancel_duration$")
            ],
            "PRODUCTION_OPTION": [
                CallbackQueryHandler(handle_production_option, pattern="^.*$")
            ],
            "CONTACT_INFO": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_contact_info),
                CallbackQueryHandler(handle_main_menu, pattern="^(back_to_production|back_to_contact_name|back_to_contact_phone|back_to_contact_email)$"),
                CommandHandler("cancel", cancel)
            ],
            "CONFIRMATION": [
                CallbackQueryHandler(handle_confirmation, pattern="^.*$")
            ],
            "FINAL_ACTIONS": [
                CallbackQueryHandler(handle_final_actions, pattern="^.*$")
            ]
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    
    # Обработчики для кнопок контактов
    application.add_handler(CallbackQueryHandler(
        lambda update, context: update.callback_query.answer(), 
        pattern="^(call_|email_)"
    ))
    
    # Запуск в зависимости от среды
    if "RENDER" in os.environ:
        logger.info("Запуск в режиме webhook на Render")
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8443)),
            url_path=TOKEN,
            webhook_url=f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-bot')}.onrender.com/{TOKEN}"
        )
    else:
        logger.info("Запуск в режиме polling")
        application.run_polling()

if __name__ == "__main__":
    main()
