import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# 🔐 Твой токен от BotFather
BOT_TOKEN = "ТОКЕН_ОТ_BOTFATHER"

logging.basicConfig(level=logging.INFO)

# Списки станций и временных слотов
stations = ["Радио Тюмень", "Радио Ишим", "Радио Ялуторовск"]
time_slots = ["Утро (7–10)", "День (10–17)", "Вечер (17–21)"]

user_sessions = {}

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

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("✅ Бот YA-RADIO запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
