import os
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Получаем токен из переменных окружения Render
BOT_TOKEN = os.getenv('8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU')

if not BOT_TOKEN:
    logging.error("❌ BOT_TOKEN не установлен. Убедитесь, что вы добавили переменную BOT_TOKEN в настройки Render.")
    exit(1)

# Данные радиостанций
stations = [
    {"id": 1, "name": "Love Radio", "listeners": 3200, "price": 280, "emoji": "❤️"},
    {"id": 2, "name": "Авторадио", "listeners": 2800, "price": 260, "emoji": "🚗"},
    {"id": 3, "name": "Радио Дача", "listeners": 3500, "price": 240, "emoji": "🏡"},
    {"id": 4, "name": "Радио Шансон", "listeners": 2600, "price": 250, "emoji": "🎵"},
    {"id": 5, "name": "Ретро FM", "listeners": 2900, "price": 230, "emoji": "📻"},
    {"id": 6, "name": "Юмор FM", "listeners": 2100, "price": 270, "emoji": "😊"}
]

# Хранилище пользовательских данных
user_sessions = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_sessions[user_id] = {
        'selected_stations': [],
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

# Показать выбор станций
async def show_stations_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_session = user_sessions.get(user_id, {})
    user_session['step'] = 'selecting_stations'
    user_sessions[user_id] = user_session
    
    selected_count = len(user_session.get('selected_stations', []))
    selected_text = f"\n✅ Выбрано: {selected_count} станций" if selected_count > 0 else ""
    
    keyboard = []
    for station in stations:
        is_selected = station['id'] in user_session.get('selected_stations', [])
        emoji = "✅ " if is_selected else ""
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji}{station['emoji']} {station['name']}",
                callback_data=f"station_{station['id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("📞 Связаться с менеджером", callback_data="contact_manager")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    stations_text = "\n".join([
        f"{s['emoji']} *{s['name']}*\n"
        f"👥 {s['listeners']} слушателей/день\n"
        f"💰 {s['price']}₽ за ролик\n"
        for s in stations
    ])
    
    message = f"*YA\\-RADIO \\- Выбор радиостанций*{selected_text}\n\n{stations_text}"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message, 
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

# Обработка выбора станций
async def handle_station_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_session = user_sessions.get(user_id, {'selected_stations': []})
    
    station_id = int(query.data.split('_')[1])
    
    if station_id in user_session['selected_stations']:
        user_session['selected_stations'].remove(station_id)
    else:
        user_session['selected_stations'].append(station_id)
    
    user_sessions[user_id] = user_session
    await show_stations_selection(update, context)

# Связь с менеджером
async def contact_manager(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_session = user_sessions.get(user_id, {})
    
    selected_stations = [
        s for s in stations 
        if s['id'] in user_session.get('selected_stations', [])
    ]
    
    selected_text = ""
    if selected_stations:
        selected_text = f"\n📻 *Выбранные станции:* {', '.join([s['name'] for s in selected_stations])}"
    
    message = (
        f"📞 *YA\\-RADIO \\- Контакты менеджера*{selected_text}\n\n"
        "*Ваш персональный менеджер:*\n"
        "👩 Надежда\n\n"
        "*Контактные данные:*\n"
        "📱 Телефон: \\+7 \\(34535\\) 5\\-01\\-51\n"
        "📧 Email: a\\.khlistunov@gmail\\.com\n"
        "🌐 Сайт: ya\\-radio\\.ru\n\n"
        "*График работы:*\n"
        "🕘 Пн\\-Пт: 9:00\\-18:00\n"
        "🕙 Сб: 10:00\\-16:00\n"
        "🚫 Вс: выходной"
    )
    
    keyboard = [
        [InlineKeyboardButton("📞 Позвонить", url="tel:+73453550151")],
        [InlineKeyboardButton("📧 Написать", url="mailto:a.khlistunov@gmail.com")],
        [InlineKeyboardButton("🌐 Сайт YA-RADIO", url="http://ya-radio.ru")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )

# Показать статистику
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "📊 *YA\\-RADIO \\- Статистика охвата*\n\n"
        "*География вещания:*\n"
        "📍 Ялуторовск и район \\(~52,000 чел\\.\\)\n"
        "📍 Заводоуковск и район \\(~46,500 чел\\.\\)\n\n"
        "*Общие показатели:*\n"
        "📊 Суточный охват: 18,500\\+ чел\\.\n"
        "👥 Месячный охват: 156,000\\+ контактов\n"
        "🎯 Доля рынка: 52%\n"
        "💰 Базовая цена: 4₽/сек\n\n"
        "*Возрастная структура:*\n"
        "👨‍💼 35\\-45 лет: 36%\n"
        "👨‍🔧 46\\-55 лет: 30%\n"
        "👴 56\\-65 лет: 22%\n"
        "👦 18\\-34 лет: 12%"
    )
    
    if update.callback_query:
        await update.callback_query.message.reply_text(message, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(message, parse_mode='MarkdownV2')

# Показать калькулятор
async def show_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "💰 *YA\\-RADIO \\- Калькулятор стоимости*\n\n"
        "*Базовая цена:* 4₽ за секунду\n"
        "*Стандартный ролик 30 сек:* 120₽\n\n"
        "*Система скидок:*\n"
        "🥉 50\\-99 роликов: \\-20%\n"
        "🥈 100\\-199 роликов: \\-40%\n"
        "🥇 200\\-299 роликов: \\-50%\n"
        "💎 300\\+ роликов: \\-60%\n\n"
        "*Дополнительные бонусы:*\n"
        "📻 \\+5% за каждую доп\\. станцию\n"
        "📅 \\+10% за размещение от 3 месяцев\n\n"
        "Для точного расчета нажмите \"🎯 Выбрать станции\""
    )
    
    keyboard = [[InlineKeyboardButton("🎯 Выбрать станции", callback_data="goto_stations")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

# Показать контакты
async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "📞 *YA\\-RADIO \\- Контакты*\n\n"
        "*Радио Тюменской области*\n"
        "Официальный вещатель в Ялуторовске и Заводоуковске\n\n"
        "*Контактные данные:*\n"
        "📱 Телефон: \\+7 \\(34535\\) 5\\-01\\-51\n"
        "📧 Email: a\\.khlistunov@gmail\\.com\n"
        "🌐 Сайт: ya\\-radio\\.ru\n\n"
        "*Рекламный отдел:*\n"
        "👩 Менеджер: Надежда\n"
        "🕘 График: Пн\\-Пт 9:00\\-18:00"
    )
    
    keyboard = [
        [InlineKeyboardButton("📞 Позвонить", url="tel:+73453550151")],
        [InlineKeyboardButton("📧 Написать", url="mailto:a.khlistunov@gmail.com")],
        [InlineKeyboardButton("🌐 Сайт YA-RADIO", url="http://ya-radio.ru")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

# Показать информацию о нас
async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "ℹ️ *YA\\-RADIO \\- О нас*\n\n"
        "*Радио Тюменской области* \\- ведущий радио\\-холдинг в Ялуторовске и Заводоуковске\n\n"
        "*Наши радиостанции:*\n"
        "❤️ Love Radio \\- музыка и настроение\n"
        "🚗 Авторадио \\- для тех, кто в пути\n"
        "🏡 Радио Дача \\- уют и домашняя атмосфера\n"
        "🎵 Радио Шансон \\- честные истории\n"
        "📻 Ретро FM \\- хиты прошлых лет\n"
        "😊 Юмор FM \\- позитив и смех\n\n"
        "*Почему выбирают нас:*\n"
        "✅ Максимальный охват аудитории\n"
        "✅ Профессиональный подход\n"
        "✅ Гибкая система скидок\n"
        "✅ Индивидуальные решения\n\n"
        "*Наша миссия:*\n"
        "Создавать эффективные рекламные кампании, которые работают на результат\\!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎯 Начать заказ", callback_data="goto_stations")],
        [InlineKeyboardButton("🌐 Сайт YA-RADIO", url="http://ya-radio.ru")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

# Переход к выбору станций
async def goto_stations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await show_stations_selection(update, context)

# Обработка текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    
    if text == '🎯 Выбрать станции':
        await show_stations_selection(update, context)
    elif text == '📊 Статистика':
        await show_statistics(update, context)
    elif text == '💰 Калькулятор':
        await show_calculator(update, context)
    elif text == '📞 Контакты':
        await show_contacts(update, context)
    elif text == 'ℹ️ О нас':
        await show_about(update, context)
    else:
        message = (
            "*YA\\-RADIO \\- Главное меню*\n\n"
            "Используйте кнопки ниже для навигации:\n\n"
            "🎯 *Выбрать станции* \\- подбор радиостанций и расчет\n"
            "💰 *Калькулятор* \\- быстрый расчет стоимости\n"
            "📊 *Статистика* \\- данные по охвату аудитории\n"
            "📞 *Контакты* \\- связь с нашим менеджером\n"
            "ℹ️ *О нас* \\- информация о наших радиостанциях"
        )
        
        keyboard = [
            ['🎯 Выбрать станции', '📊 Статистика'],
            ['💰 Калькулятор', '📞 Контакты'],
            ['ℹ️ О нас']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

def main():
    # Создаем Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_station_selection, pattern="^station_"))
    application.add_handler(CallbackQueryHandler(contact_manager, pattern="^contact_manager$"))
    application.add_handler(CallbackQueryHandler(goto_stations, pattern="^goto_stations$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запускаем бота
    logging.info("🤖 Бот YA-RADIO запущен!")
    logging.info("🌐 Сайт: http://ya-radio.ru")
    logging.info("📞 Телефон: +7 (34535) 5-01-51")
    logging.info("📧 Email: a.khlistunov@gmail.com")
    
    # Для Render используем polling с обработкой остановки
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()
