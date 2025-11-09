import os
import logging
import json
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"
ADMIN_TELEGRAM_ID = 174046571

# Инициализация базы данных
def init_db():
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
                campaign_text TEXT,
                production_option TEXT,
                contact_name TEXT,
                company TEXT,
                phone TEXT,
                email TEXT,
                duration INTEGER,
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ГЛАВНОЕ МЕНЮ С WEBAPP"""
    
    # Получаем URL WebApp из переменных окружения
    webapp_url = f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-webapp')}.onrender.com"
    
    keyboard = [
        [InlineKeyboardButton(
            "🚀 ОТКРЫТЬ RADIOPLANNER APP", 
            web_app=WebAppInfo(url=webapp_url)
        )],
        [InlineKeyboardButton("📊 ВОЗРАСТНАЯ СТРУКТУРА", callback_data="statistics")],
        [InlineKeyboardButton("🏆 О НАС", callback_data="about")],
        [InlineKeyboardButton("📋 ЛИЧНЫЙ КАБИНЕТ", callback_data="personal_cabinet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = (
        "🎙️ РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
        "📍 Ялуторовск • Заводоуковск\n\n"
        "✨ **НОВЫЙ ИНТЕРАКТИВНЫЙ КОНСТРУКТОР!**\n\n"
        "📱 • Визуальный подбор времени и станций\n"
        "⚡ • Мгновенный расчет охвата и стоимости\n"
        "💾 • Сохранение всех медиапланов\n"
        "🎯 • Персональные рекомендации\n\n"
        "🚀 Нажмите кнопку ниже чтобы открыть приложение 👇"
    )
    
    if update.message:
        await update.message.reply_text(caption, reply_markup=reply_markup)
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(caption, reply_markup=reply_markup)

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных из WebApp"""
    try:
        webapp_data = update.effective_message.web_app_data
        data = json.loads(webapp_data.data)
        
        logger.info(f"📱 Данные из WebApp: {data}")
        
        # Сохраняем кампанию в БД
        campaign_number = save_campaign_to_db(data)
        
        if campaign_number:
            # Отправляем уведомление админу
            await send_admin_notification(context, data, campaign_number)
            
            await update.message.reply_text(
                f"✅ **Заявка #{campaign_number} принята!**\n\n"
                f"📊 Охват: {data.get('actual_reach', 0):,} человек\n"
                f"💰 Стоимость: {data.get('final_price', 0):,}₽\n"
                f"🎯 Радиостанции: {len(data.get('radio_stations', []))} шт\n\n"
                "📞 Менеджер свяжется с вами в течение 15 минут!"
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка сохранения заявки. Пожалуйста, попробуйте еще раз или свяжитесь с менеджером: @AlexeyKhlistunov"
            )
        
    except Exception as e:
        logger.error(f"❌ WebApp data error: {e}")
        await update.message.reply_text(
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
             company, phone, email, base_price, discount, final_price, actual_reach, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get('actual_reach', 0),
            "webapp"
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Кампания {campaign_number} сохранена")
        return campaign_number
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения кампании: {e}")
        return None

async def send_admin_notification(context, data, campaign_number):
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
Слотов: {len(data.get('time_slots', []))}

💰 ФИНАНСЫ:
Базовая: {data.get('base_price', 0):,}₽
Скидка: {data.get('discount', 0):,}₽
Итоговая: {data.get('final_price', 0):,}₽

🎯 ОХВАТ: {data.get('actual_reach', 0):,} человек
        """
        
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=notification_text
        )
        logger.info(f"✅ Уведомление админу отправлено для #{campaign_number}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки админу: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "statistics":
        await query.edit_message_text(
            "📊 ВОЗРАСТНАЯ СТРУКТУРА\n\n"
            "Откройте WebApp для просмотра детальной статистики "
            "и аналитики аудитории по городам Ялуторовск и Заводоуковск.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 ОТКРЫТЬ APP", 
                    web_app=WebAppInfo(url=f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-webapp')}.onrender.com"))
            ]])
        )
    elif query.data == "about":
        await query.edit_message_text(
            "🏆 О НАС\n\n"
            "10 лет мы помогаем бизнесу достигать своей аудитории "
            "через силу радиоволн.\n\n"
            "📻 6 федеральных станций\n"
            "📍 Ялуторовск • Заводоуковск\n"  
            "🎯 40 000+ слушателей\n\n"
            "Откройте WebApp для полной информации.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 ОТКРЫТЬ APP", 
                    web_app=WebAppInfo(url=f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-webapp')}.onrender.com"))
            ]])
        )
    elif query.data == "personal_cabinet":
        await query.edit_message_text(
            "📋 ЛИЧНЫЙ КАБИНЕТ\n\n"
            "Просматривайте историе заявок, статистику кампаний "
            "и управляйте своими медиапланами в WebApp.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 ОТКРЫТЬ APP", 
                    web_app=WebAppInfo(url=f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-webapp')}.onrender.com"))
            ]])
        )

def main():
    """ЗАПУСК БОТА С WEBAPP"""
    if init_db():
        logger.info("✅ Бот с WebApp запущен успешно")
    
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.StatusUpdate.WEB_APP_DATA, 
        handle_webapp_data
    ))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Запуск на Render
    if "RENDER" in os.environ:
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8443)),
            url_path=TOKEN,
            webhook_url=f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-bot')}.onrender.com/{TOKEN}"
        )
        logger.info("🌐 Бот запущен в режиме Webhook на Render")
    else:
        application.run_polling()
        logger.info("🔍 Бот запущен в режиме Polling")

if __name__ == "__main__":
    main()
