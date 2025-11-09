from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import logging
from shared.database import init_db, save_campaign  # Выносим общую логику

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"
WEBAPP_URL = f"https://{os.environ.get('RENDER_SERVICE_NAME')}.onrender.com"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ГЛАВНОЕ МЕНЮ С WEBAPP КНОПКОЙ"""
    
    # Основная кнопка WebApp
    keyboard = [
        [InlineKeyboardButton(
            "🚀 ОТКРЫТЬ RADIOPLANNER APP", 
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html")
        )],
        [InlineKeyboardButton("📊 ВОЗРАСТНАЯ СТРУКТУРА", callback_data="statistics")],
        [InlineKeyboardButton("🏆 О НАС", callback_data="about")],
        [InlineKeyboardButton("📋 ЛИЧНЫЙ КАБИНЕТ", callback_data="personal_cabinet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = (
        "🎙️ РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n\n"
        "✨ **НОВЫЙ СПОСОБ РАСЧЕТА РЕКЛАМЫ!**\n\n"
        "• 📱 **Интерактивный конструктор** в WebApp\n"
        "• 🎯 **Визуальный подбор** времени и станций\n"
        "• ⚡ **Мгновенный просчет** охвата и стоимости\n"
        "• 💾 **Сохранение** всех ваших медиапланов\n\n"
        "Нажмите кнопку ниже чтобы открыть приложение 👇"
    )
    
    await update.message.reply_text(caption, reply_markup=reply_markup)

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных из WebApp"""
    try:
        webapp_data = update.effective_message.web_app_data
        data = json.loads(webapp_data.data)
        
        campaign_number = save_campaign(data)
        
        await update.message.reply_text(
            f"✅ Заявка #{campaign_number} принята через WebApp!\n"
            f"📊 Охват: {data['reach']} человек\n"
            f"💰 Стоимость: {data['price']}₽\n\n"
            "Менеджер свяжется с вами в течение 15 минут!"
        )
        
    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await update.message.reply_text("❌ Ошибка обработки данных")

def main():
    """ЗАПУСК БОТА"""
    if init_db():
        logger.info("Бот с WebApp запущен успешно")
    
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.StatusUpdate.WEB_APP_DATA, 
        handle_webapp_data
    ))
    
    # Запуск на Render
    if "RENDER" in os.environ:
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8443)),
            url_path=TOKEN,
            webhook_url=f"https://{os.environ.get('RENDER_SERVICE_NAME')}.onrender.com/{TOKEN}"
        )
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
