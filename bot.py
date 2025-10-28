import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask
import os
import asyncio
import threading

# 🔐 Твой токен от BotFather
BOT_TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

logging.basicConfig(level=logging.INFO)

# Веб-сервер для Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "🎧 YA-RADIO Bot is running!"

@web_app.route('/health')
def health():
    return "✅ OK"

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    web_app.run(host='0.0.0.0', port=port, debug=False)

# Данные бота
stations = ["Радио Тюмень", "Радио Ишим", "Радио Ялуторовск"]
user_sessions = {}

# Функции бота (остаются без изменений)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📻 Выбрать станции", callback_data="stations")],
        [InlineKeyboardButton("📊 Рассчитать стоимость", callback_data="calc")],
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")]
    ]
    await update.message.reply_text(
        "👋 Добро пожаловать в Радио Тюменской области!\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "stations":
        keyboard = [[InlineKeyboardButton(s, callback_data=f"st:{s}")] for s in stations]
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="done_stations")])
        await query.edit_message_text("Выберите станции:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("st:"):
        station = data.split(":")[1]
        user_sessions.setdefault(user_id, {"stations": []})
        if station in user_sessions[user_id]["stations"]:
            user_sessions[user_id]["stations"].remove(station)
        else:
            user_sessions[user_id]["stations"].append(station)
        await query.answer(f"Выбрано: {station}")

    elif data == "done_stations":
        chosen = ", ".join(user_sessions.get(user_id, {}).get("stations", [])) or "ничего"
        await query.edit_message_text(f"Вы выбрали: {chosen}")

    elif data == "calc":
        total = len(user_sessions.get(user_id, {}).get("stations", [])) * 1000
        await query.edit_message_text(f"💰 Примерная стоимость размещения: {total} ₽")

    elif data == "contacts":
        await query.edit_message_text("📞 Контакт: +7 (34535) 5-01-51\n🌐 http://ya-radio.ru/")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Используйте меню через /start 😊")

def run_bot():
    """Запускает Telegram бота"""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("✅ Бот YA-RADIO запущен...")
    app.run_polling()

if __name__ == "__main__":
    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Запускаем бота в основном потоке
    run_bot()
