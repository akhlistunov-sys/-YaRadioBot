import os
import logging
import json
import sqlite3
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from flask import Flask, request

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"
ADMIN_TELEGRAM_ID = 174046571

# Создаем бота и Flask приложение
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

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

@bot.message_handler(commands=['start'])
def start(message):
    """ГЛАВНОЕ МЕНЮ С WEBAPP"""
    
    # Получаем URL WebApp из переменных окружения
    webapp_url = f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-webapp')}.onrender.com"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(
        "🚀 ОТКРЫТЬ RADIOPLANNER APP", 
        web_app=WebAppInfo(url=webapp_url)
    ))
    
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
    
    try:
        bot.send_message(message.chat.id, caption, reply_markup=keyboard)
        logger.info(f"✅ Отправлено меню пользователю {message.chat.id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки меню: {e}")

@bot.message_handler(content_types=['web_app_data'])
def handle_webapp_data(message):
    """Обработка данных из WebApp"""
    try:
        data = json.loads(message.web_app_data.data)
        
        logger.info(f"📱 Данные из WebApp от пользователя {message.chat.id}: {data}")
        
        # Сохраняем кампанию в БД
        campaign_number = save_campaign_to_db(data)
        
        if campaign_number:
            # Отправляем уведомление админу
            send_admin_notification(data, campaign_number)
            
            bot.send_message(
                message.chat.id,
                f"✅ **Заявка #{campaign_number} принята!**\n\n"
                f"📊 Охват: {data.get('actual_reach', 0):,} человек\n"
                f"💰 Стоимость: {data.get('final_price', 0):,}₽\n"
                f"🎯 Радиостанции: {len(data.get('radio_stations', []))} шт\n\n"
                "📞 Менеджер свяжется с вами в течение 15 минут!"
            )
            logger.info(f"✅ Заявка {campaign_number} обработана")
        else:
            bot.send_message(
                message.chat.id,
                "❌ Ошибка сохранения заявки. Пожалуйста, попробуйте еще раз."
            )
            logger.error("❌ Ошибка сохранения заявки в БД")
        
    except Exception as e:
        logger.error(f"❌ WebApp data error: {e}")
        bot.send_message(
            message.chat.id,
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
        
        logger.info(f"✅ Кампания {campaign_number} сохранена в БД")
        return campaign_number
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения кампании: {e}")
        return None

def send_admin_notification(data, campaign_number):
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

🎯 ОХВАТ: {data.get('actual_reach', 0):,} человек
        """
        
        bot.send_message(ADMIN_TELEGRAM_ID, notification_text)
        logger.info(f"✅ Уведомление админу отправлено для #{campaign_number}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки админу: {e}")

@app.route('/')
def index():
    """Главная страница для проверки работы"""
    return '🤖 RadioPlanner Bot is running! 🚀'

@app.route('/health')
def health():
    """Эндпоинт для проверки здоровья"""
    return {'status': 'healthy', 'service': 'telegram-bot'}

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик вебхука от Telegram"""
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK'
        except Exception as e:
            logger.error(f"❌ Ошибка обработки вебхука: {e}")
            return 'Error', 500
    return 'Invalid content-type', 400

def set_webhook():
    """Установка вебхука"""
    try:
        webhook_url = f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-bot')}.onrender.com/webhook"
        logger.info(f"🌐 Устанавливаем вебхук: {webhook_url}")
        
        # Удаляем старый вебхук
        bot.remove_webhook()
        
        # Устанавливаем новый вебхук
        bot.set_webhook(url=webhook_url)
        
        logger.info("✅ Вебхук успешно установлен")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка установки вебхука: {e}")
        return False

if __name__ == "__main__":
    # Инициализация БД
    if init_db():
        logger.info("✅ База данных готова")
    
    # Всегда используем вебхук на Render
    logger.info("🚀 Настраиваем вебхук для Render...")
    
    if set_webhook():
        logger.info("🌈 Запускаем Flask сервер...")
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        logger.error("💥 Не удалось установить вебхук")
