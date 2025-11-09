import os
import logging
import json
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"
ADMIN_TELEGRAM_ID = 174046571

def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                campaign_number TEXT,
                radio_stations TEXT,
                start_date TEXT,
                end_date TEXT,
                campaign_days INTEGER,
                time_slots TEXT,
                branded_section TEXT,
                contact_name TEXT,
                company TEXT,
                phone TEXT,
                email TEXT,
                base_price INTEGER,
                discount INTEGER,
                final_price INTEGER,
                actual_reach INTEGER,
                status TEXT DEFAULT "active",
                source TEXT DEFAULT "webapp",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")
        return False

def start(update, context):
    """ГЛАВНОЕ МЕНЮ С WEBAPP"""
    
    # Получаем URL WebApp из переменных окружения
    webapp_url = f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-webapp')}.onrender.com"
    
    keyboard = [
        [InlineKeyboardButton(
            "🚀 ОТКРЫТЬ RADIOPLANNER APP", 
            web_app=WebAppInfo(url=webapp_url)
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = (
        "🎙️ РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
        "📍 Ялуторовск • Заводоуковск\n\n"
        "✨ **НОВЫЙ ИНТЕРАКТИВНЫЙ КОНСТРУКТОР!**\n\n"
        "🚀 Нажмите кнопку ниже чтобы открыть приложение 👇"
    )
    
    update.message.reply_text(caption, reply_markup=reply_markup)

def handle_webapp_data(update, context):
    """Обработка данных из WebApp"""
    try:
        webapp_data = update.effective_message.web_app_data
        data = json.loads(webapp_data.data)
        
        logger.info(f"📱 Данные из WebApp: {data}")
        
        # Сохраняем кампанию в БД
        campaign_number = save_campaign_to_db(data)
        
        if campaign_number:
            # Отправляем уведомление админу
            send_admin_notification(context, data, campaign_number)
            
            update.message.reply_text(
                f"✅ **Заявка #{campaign_number} принята!**\n\n"
                f"📊 Охват: {data.get('actual_reach', 0):,} человек\n"
                f"💰 Стоимость: {data.get('final_price', 0):,}₽\n\n"
                "📞 Менеджер свяжется с вами в течение 15 минут!"
            )
        else:
            update.message.reply_text(
                "❌ Ошибка сохранения заявки. Пожалуйста, попробуйте еще раз."
            )
        
    except Exception as e:
        logger.error(f"❌ WebApp data error: {e}")
        update.message.reply_text(
            "❌ Ошибка обработки данных. Пожалуйста, попробуйте еще раз."
        )

def save_campaign_to_db(data):
    """Сохранение кампании в базу данных"""
    try:
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        campaign_number = f"WA-{datetime.now().strftime('%H%M%S')}"
        
        cursor.execute("""
            INSERT INTO campaigns 
            (user_id, campaign_number, radio_stations, start_date, end_date, 
             campaign_days, time_slots, branded_section, contact_name,
             company, phone, email, base_price, discount, final_price, actual_reach)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('user_id'),
            campaign_number,
            ",".join(data.get('radio_stations', [])),
            data.get('start_date'),
            data.get('end_date'),
            data.get('campaign_days'),
            ",".join(map(str, data.get('time_slots', []))),
            data.get('branded_section'),
            data.get('contact_name'),
            data.get('company'),
            data.get('phone'),
            data.get('email'),
            data.get('base_price', 0),
            data.get('discount', 0),
            data.get('final_price', 0),
            data.get('actual_reach', 0)
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Кампания {campaign_number} сохранена")
        return campaign_number
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения кампании: {e}")
        return None

def send_admin_notification(context, data, campaign_number):
    """Отправка уведомления админу"""
    try:
        notification_text = f"""
🔔 НОВАЯ ЗАЯВКА ИЗ WEBAPP #{campaign_number}

👤 КЛИЕНТ:
Имя: {data.get('contact_name', 'Не указано')}
Телефон: {data.get('phone', 'Не указан')}
Email: {data.get('email', 'Не указан')}
Компания: {data.get('company', 'Не указана')}

📊 ПАРАМЕТРЫ:
Радиостанции: {', '.join(data.get('radio_stations', []))}
Период: {data.get('start_date')} - {data.get('end_date')} ({data.get('campaign_days')} дней)

💰 ФИНАНСЫ:
Итоговая стоимость: {data.get('final_price', 0):,}₽
        """
        
        context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=notification_text
        )
        logger.info(f"✅ Уведомление админу отправлено для #{campaign_number}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки админу: {e}")

def error_handler(update, context):
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления: {context.error}")

def main():
    """ЗАПУСК БОТА С WEBAPP"""
    if init_db():
        logger.info("✅ Бот с WebApp запущен успешно")
    
    # Создаем Updater
    updater = Updater(TOKEN, use_context=True)
    
    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher
    
    # Обработчики
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.status_update.web_app_data, handle_webapp_data))
    
    # Обработчик ошибок
    dp.add_error_handler(error_handler)
    
    # Запуск на Render
    if "RENDER" in os.environ:
        # Webhook режим для Render
        PORT = int(os.environ.get("PORT", 8443))
        updater.start_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-bot')}.onrender.com/{TOKEN}"
        )
        logger.info(f"🌐 Бот запущен в режиме Webhook на порту {PORT}")
    else:
        # Polling режим для локальной разработки
        updater.start_polling()
        logger.info("🔍 Бот запущен в режиме Polling")
    
    # Запускаем бота
    updater.idle()

if __name__ == "__main__":
    main()
