import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from aiohttp import web
import threading

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', '8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU')

# Данные радиостанций
stations = [
    {"id": 1, "name": "Love Radio", "listeners": 3200, "price": 280, "emoji": "❤️"},
    {"id": 2, "name": "Авторадио", "listeners": 2800, "price": 260, "emoji": "🚗"},
    {"id": 3, "name": "Радио Дача", "listeners": 3500, "price": 240, "emoji": "🏡"},
    {"id": 4, "name": "Радио Шансон", "listeners": 2600, "price": 250, "emoji": "🎵"},
    {"id": 5, "name": "Ретро FM", "listeners": 2900, "price": 230, "emoji": "📻"},
    {"id": 6, "name": "Юмор FM", "listeners": 2100, "price": 270, "emoji": "😊"}
]

# Временные слоты
time_slots = [
    "06:00-07:00 🌅 Утро", "07:00-08:00 🚀 Пик", "08:00-09:00 📈 Трафик",
    "09:00-10:00 ☕ Работа", "10:00-11:00 📊 День", "11:00-12:00 ⏰ Обед",
    "12:00-13:00 🍽️ Перерыв", "13:00-14:00 📋 После обеда", "14:00-15:00 🔄 Работа",
    "15:00-16:00 📝 Вечер", "16:00-17:00 🏃 Выход", "17:00-18:00 🚀 Пик",
    "18:00-19:00 📈 Трафик", "19:00-20:00 🏠 Дом", "20:00-21:00 🌙 Отдых"
]

# Хранилище пользовательских данных
user_sessions = {}

# Простой HTTP сервер для здоровья
async def handle_health(request):
    return web.Response(text="✅ YA-RADIO Bot is running!")

async def handle_root(request):
    return web.Response(text="🤖 YA-RADIO Telegram Bot\n\nVisit https://ya-radio.ru")

def run_health_server():
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    
    port = int(os.getenv('PORT', 10000))
    web.run_app(app, host='0.0.0.0', port=port, print=None)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_sessions[user_id] = {
        'selected_stations': [],
        'selected_slots': [],
        'campaign_days': 30,
        'spots_per_day': 5,
        'step': 'main'
    }
    
    keyboard = [
        ['🎯 Выбрать станции', '📊 Статистика'],
        ['💰 Калькулятор', '📞 Контакты'],
        ['ℹ️ О нас']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    message = (
        "🎧 *Добро пожаловать в YA-RADIO\\!*\n\n"
        "*Радио Тюменской области* \\- официальный вещатель в Ялуторовске и Заводоуковске\n\n"
        "Я помогу вам заказать рекламу на наших радиостанциях:\n"
        "• Love Radio ❤️\n• Авторадио 🚗\n• Радио Дача 🏡\n"
        "• Радио Шансон 🎵\n• Ретро FM 📻\n• Юмор FM 😊\n\n"
        "*Ключевые показатели:*\n"
        "📊 18,500\\+ слушателей в день\n"
        "👥 156,000\\+ контактов в месяц\n"
        "🎯 52% доля рынка\n"
        "💰 4₽/сек базовая цена\n"
        "📍 Ялуторовск • Заводоуковск"
    )
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )

# [ВСТАВЬТЕ СЮДА ВСЕ ФУНКЦИИ ИЗ ПРЕДЫДУЩЕГО КОДА]
# show_stations_selection, handle_station_selection, reset_stations, next_to_slots,
# show_time_slots, handle_slot_selection, reset_slots, calculate_price,
# show_price_calculation, calculate_total_cost, contact_manager, show_statistics,
# show_calculator, show_contacts, show_about, goto_stations, new_calculation, handle_text
# (скопируйте их из предыдущего сообщения без изменений)

# Функция для запуска Telegram бота
def run_bot():
    # Создаем Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_station_selection, pattern="^station_"))
    application.add_handler(CallbackQueryHandler(handle_slot_selection, pattern="^slot_"))
    application.add_handler(CallbackQueryHandler(reset_stations, pattern="^reset_stations$"))
    application.add_handler(CallbackQueryHandler(reset_slots, pattern="^reset_slots$"))
    application.add_handler(CallbackQueryHandler(next_to_slots, pattern="^next_to_slots$"))
    application.add_handler(CallbackQueryHandler(calculate_price, pattern="^calculate_price$"))
    application.add_handler(CallbackQueryHandler(contact_manager, pattern="^contact_manager$"))
    application.add_handler(CallbackQueryHandler(goto_stations, pattern="^goto_stations$"))
    application.add_handler(CallbackQueryHandler(new_calculation, pattern="^new_calculation$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запускаем бота
    print("🤖 Бот YA-RADIO запущен!")
    print("🌐 Сайт: http://ya-radio.ru")
    print("📞 Телефон: +7 (34535) 5-01-51")
    print("📧 Email: a.khlistunov@gmail.com")
    
    application.run_polling()

# Основная функция
def main():
    # Запускаем health server в отдельном потоке
    health_thread = threading.Thread(target=run_health_server)
    health_thread.daemon = True
    health_thread.start()
    
    # Запускаем бота в основном потоке
    run_bot()

if __name__ == '__main__':
    main()
