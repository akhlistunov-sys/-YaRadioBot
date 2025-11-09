import os
import logging
import json
import sqlite3
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from flask import Flask, request
from database import init_db, save_campaign_to_db, calculate_campaign_price_and_reach, STATION_COVERAGE, TIME_SLOTS_DATA, BRANDED_SECTION_PRICES, PRODUCTION_OPTIONS, format_number, get_branded_section_name, get_production_option_name

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

@bot.message_handler(commands=['start'])
def start(message):
    """ГЛАВНОЕ МЕНЮ С WEBAPP"""
    
    webapp_url = "https://telegram-radio-webapp.onrender.com"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(
        "🚀 ОТКРЫТЬ RADIOPLANNER APP", 
        web_app=WebAppInfo(url=webapp_url)
    ))
    
    caption = (
        "🎙️ РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
        "📍 Ялуторовск • Заводоуковск\n\n"
        "✨ **ПОЛНЫЙ КОНСТРУКТОР РАДИОРЕКЛАМЫ!**\n\n"
        "📱 • 6 радиостанций с реальным охватом\n"
        "⚡ • Расчет стоимости и охвата онлайн\n"
        "💾 • Брендированные рубрики\n"
        "🎯 • Производство роликов\n\n"
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
        
        logger.info(f"📱 Данные из WebApp от пользователя {message.chat.id}")
        
        # Сохраняем кампанию в БД
        campaign_number = save_campaign_to_db(data)
        
        if campaign_number:
            # Отправляем уведомление админу
            send_admin_notification(data, campaign_number)
            
            # Отправляем подтверждение пользователю
            send_user_confirmation(message.chat.id, data, campaign_number)
            
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

def send_admin_notification(data, campaign_number):
    """Отправка уведомления админу"""
    try:
        # Расчет стоимости для уведомления
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent = calculate_campaign_price_and_reach(data)
        
        stations_text = ""
        for radio in data.get('radio_stations', []):
            listeners = STATION_COVERAGE.get(radio, 0)
            stations_text += f"• {radio}: ~{format_number(listeners)} слушателей\n"
        
        # Текст временных слотов
        slots_text = ""
        for slot_index in data.get('time_slots', []):
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                slots_text += f"• {slot['time']} - {slot['label']}: {slot['coverage_percent']}%\n"
        
        notification_text = f"""
🔔 НОВАЯ ЗАЯВКА ИЗ WEBAPP #{campaign_number}

👤 КЛИЕНТ:
Имя: {data.get('contact_name', 'Не указано')}
Телефон: {data.get('phone', 'Не указан')}
Email: {data.get('email', 'Не указан')}
Компания: {data.get('company', 'Не указана')}

📊 ПАРАМЕТРЫ КАМПАНИИ:

📻 РАДИОСТАНЦИИ:
{stations_text}
📅 ПЕРИОД: {data.get('start_date')} - {data.get('end_date')} ({data.get('campaign_days')} дней)

🕒 ВЫБРАННЫЕ СЛОТЫ:
{slots_text}
• Суммарный охват слотов: {total_coverage_percent}%

🎙️ РУБРИКА: {get_branded_section_name(data.get('branded_section'))}
⏱️ РОЛИК: {get_production_option_name(data.get('production_option'))}
📏 ХРОНОМЕТРАЖ: {data.get('duration', 20)} сек

🎯 РАСЧЕТНЫЙ ОХВАТ:
• Выходов в день: {spots_per_day}
• Всего выходов: {spots_per_day * data.get('campaign_days', 30)}
• Уникальных слушателей в день: ~{format_number(daily_coverage)} чел.
• Общий охват за период: ~{format_number(total_reach)} чел.

💰 СТОИМОСТЬ:
Базовая: {format_number(base_price)}₽
Скидка 50%: -{format_number(discount)}₽
Итоговая: {format_number(final_price)}₽
        """
        
        bot.send_message(ADMIN_TELEGRAM_ID, notification_text)
        logger.info(f"✅ Уведомление админу отправлено для #{campaign_number}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки админу: {e}")

def send_user_confirmation(chat_id, data, campaign_number):
    """Отправка подтверждения пользователю"""
    try:
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent = calculate_campaign_price_and_reach(data)
        
        confirmation_text = f"""
✅ **ВАША ЗАЯВКА #{campaign_number} ПРИНЯТА!**

📊 **ПАРАМЕТРЫ КАМПАНИИ:**
• Радиостанции: {len(data.get('radio_stations', []))} шт
• Период: {data.get('start_date')} - {data.get('end_date')} ({data.get('campaign_days')} дней)
• Выходов в день: {spots_per_day}
• Всего выходов: {spots_per_day * data.get('campaign_days', 30)}

🎯 **ОЖИДАЕМЫЙ ОХВАТ:**
• Ежедневно: ~{format_number(daily_coverage)} чел.
• За весь период: ~{format_number(total_reach)} чел.

💰 **СТОИМОСТЬ:**
• Итоговая: {format_number(final_price)}₽ (скидка 50%)

📞 **ДАЛЬНЕЙШИЕ ДЕЙСТВИЯ:**
Менеджер свяжется с вами в течение 15 минут для подтверждения деталей и запуска кампании.

💎 **Спасибо, что выбрали нас!**
        """
        
        bot.send_message(chat_id, confirmation_text)
        logger.info(f"✅ Подтверждение отправлено пользователю {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки подтверждения: {e}")

@app.route('/')
def index():
    return '🤖 RadioPlanner Bot is running! 🚀'

@app.route('/health')
def health():
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
        
        bot.remove_webhook()
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
    
    # Вебхук для Render
    logger.info("🚀 Настраиваем вебхук для Render...")
    
    if set_webhook():
        logger.info("🌈 Запускаем Flask сервер...")
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        logger.error("💥 Не удалось установить вебхук")
