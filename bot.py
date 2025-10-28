import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import sqlite3
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора
MAIN_MENU, CAMPAIGN_CREATOR, RADIO_SELECTION, TIME_SLOTS, BRANDED_SECTIONS, CONTACT_INFO = range(6)

# Токен бота
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('campaigns.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            campaign_number TEXT,
            radio_stations TEXT,
            time_slots TEXT,
            branded_section TEXT,
            campaign_text TEXT,
            contact_name TEXT,
            company TEXT,
            phone TEXT,
            email TEXT,
            position TEXT,
            requisites TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🚀 СОЗДАТЬ КАМПАНИЮ", callback_data="create_campaign")],
        [InlineKeyboardButton("📊 СТАТИСТИКА ОХВАТА", callback_data="statistics")],
        [InlineKeyboardButton("📋 МОИ ЗАКАЗЫ", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ О НАС", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🔴 РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
        "📍 Ялуторовск • Заводоуковск\n\n"
        "📊 18,500+ в день\n👥 156,000+ в месяц\n\n"
        "🎯 52% доля рынка\n💰 4₽/сек базовая цена"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    
    return MAIN_MENU

# Конструктор ролика
async def campaign_creator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 ВВЕСТИ ТЕКСТ РОЛИКА", callback_data="enter_text")],
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_radio_selection")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "◀️ Назад     Конструктор ролика\n\n"
        "📎 ПРИКРЕПИТЕ ГОТОВЫЙ РОЛИК:\n"
        "[ 📁 Загрузить аудиофайл ]\n"
        "MP3, WAV до 10 МБ\n\n"
        "ИЛИ\n\n"
        "📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n"
        "┌─────────────────────────────────────┐\n"
        "│ Автомобили в Тюмени!               │\n"
        "│ Новые модели в наличии. Выгодный   │\n"
        "│ трейд-ин и кредит 0%. Тест-драйв   │\n"
        "│ в день обращения!                  │\n"
        "└─────────────────────────────────────┘\n"
        "○ 98 знаков из 500\n\n"
        "⏱️ Примерная длительность: 18 секунд\n"
        "[ ПРОСЛУШАТЬ ПРЕВЬЮ ] [ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return CAMPAIGN_CREATOR

# Ввод текста ролика
async def enter_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📝 Введите текст для радиоролика (до 500 знаков):\n\n"
        "Пример:\n"
        "Автомобили в Тюмени! Новые модели в наличии. Выгодный трейд-ин и кредит 0%. "
        "Тест-драйв в день обращения!"
    )
    
    return "WAITING_TEXT"

# Обработка текста ролика
async def process_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if len(text) > 500:
        await update.message.reply_text("❌ Текст превышает 500 знаков. Сократите текст.")
        return "WAITING_TEXT"
    
    context.user_data['campaign_text'] = text
    char_count = len(text)
    
    keyboard = [[InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_radio_selection")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text_display = (
        f"◀️ Назад     Конструктор ролика\n\n"
        f"📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n"
        f"┌─────────────────────────────────────┐\n"
        f"│ {text:<37} │\n"
        f"└─────────────────────────────────────┘\n"
        f"○ {char_count} знаков из 500\n\n"
        f"⏱️ Примерная длительность: {max(15, char_count // 7)} секунд\n"
        f"[ ПРОСЛУШАТЬ ПРЕВЬЮ ] [ ДАЛЕЕ ]"
    )
    
    await update.message.reply_text(text_display, reply_markup=reply_markup)
    return CAMPAIGN_CREATOR

# Выбор радиостанций
async def radio_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_radios = context.user_data.get('selected_radios', [])
    total_listeners = sum({
        'LOVE RADIO': 3200,
        'АВТОРАДИО': 2800,
        'РАДИО ДАЧА': 3500,
        'РАДИО ШАНСОН': 2600,
        'РЕТРО FM': 2900,
        'ЮМОР FM': 2100
    }.get(radio, 0) for radio in selected_radios)
    
    # Создаем клавиатуру с выбранными станциями
    keyboard = []
    radio_stations = [
        ("LOVE RADIO", "radio_love"),
        ("АВТОРАДИО", "radio_auto"),
        ("РАДИО ДАЧА", "radio_dacha"), 
        ("РАДИО ШАНСОН", "radio_chanson"),
        ("РЕТРО FM", "radio_retro"),
        ("ЮМОР FM", "radio_humor")
    ]
    
    for name, callback in radio_stations:
        emoji = "🔘" if name in selected_radios else "⚪"
        button_text = f"{emoji} {name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])
    
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_time_slots")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"◀️ Назад     Выбор радиостанций\n\n"
        f"{'🔘' if 'LOVE RADIO' in selected_radios else '⚪'} LOVE RADIO [📖 Подробнее]\n"
        f"👥 3,200 слушателей/день\n👩 Молодёжь 18-35 лет\n\n"
        f"{'🔘' if 'АВТОРАДИО' in selected_radios else '⚪'} АВТОРАДИО [📖 Подробнее]\n"
        f"👥 2,800 слушателей/день\n👨 Автомобилисты 25-50 лет\n\n"
        f"{'🔘' if 'РАДИО ДАЧА' in selected_radios else '⚪'} РАДИО ДАЧА [📖 Подробнее]\n"
        f"👥 3,500 слушателей/день\n👨👩 Семья 35-65 лет\n\n"
        f"{'🔘' if 'РАДИО ШАНСОН' in selected_radios else '⚪'} РАДИО ШАНСОН [📖 Подробнее]\n"
        f"👥 2,600 слушателей/день\n👨 Мужчины 30-60 лет\n\n"
        f"{'🔘' if 'РЕТРО FM' in selected_radios else '⚪'} РЕТРО FM [📖 Подробнее]\n"
        f"👥 2,900 слушателей/день\n👴👵 Ценители хитов 30-55 лет\n\n"
        f"{'🔘' if 'ЮМОР FM' in selected_radios else '⚪'} ЮМОР FM [📖 Подробнее]\n"
        f"👥 2,100 слушателей/день\n👦👧 Слушатели 25-45 лет\n\n"
        f"Выбрано: {len(selected_radios)} станции • {total_listeners} слушателей\n"
        f"[ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return RADIO_SELECTION

# Обработка выбора радиостанций
async def handle_radio_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    radio_data = {
        'radio_love': 'LOVE RADIO',
        'radio_auto': 'АВТОРАДИО', 
        'radio_dacha': 'РАДИО ДАЧА',
        'radio_chanson': 'РАДИО ШАНСОН',
        'radio_retro': 'РЕТРО FM',
        'radio_humor': 'ЮМОР FM'
    }
    
    if query.data in radio_data:
        radio_name = radio_data[query.data]
        selected_radios = context.user_data.get('selected_radios', [])
        
        if radio_name in selected_radios:
            selected_radios.remove(radio_name)
        else:
            selected_radios.append(radio_name)
        
        context.user_data['selected_radios'] = selected_radios
        return await radio_selection(update, context)
    
    elif query.data == "to_time_slots":
        if not context.user_data.get('selected_radios'):
            await query.answer("❌ Выберите хотя бы одну радиостанцию!", show_alert=True)
            return RADIO_SELECTION
        return await time_slots(update, context)
    
    return RADIO_SELECTION

# Временные слоты
async def time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_branded_sections")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "◀️ Назад     Временные слоты\n\n"
        "🕒 ВЫБЕРИТЕ ВРЕМЯ ВЫХОДА РОЛИКОВ\n\n"
        "🌅 УТРЕННИЕ СЛОТЫ (+25%)\n"
        "[▢] 06:00-07:00 • Подъем, сборы\n"
        "[▢] 07:00-08:00 • Утренние поездки\n"
        "[▢] 08:00-09:00 • Пик трафика 🚀\n"
        "[▢] 09:00-10:00 • Начало работы\n\n"
        "☀️ ДНЕВНЫЕ СЛОТЫ\n"
        "[▢] 10:00-11:00 • Рабочий процесс\n"
        "[▢] 11:00-12:00 • Предобеденное время\n"
        "[▢] 12:00-13:00 • Обеденный перерыв\n"
        "[▢] 13:00-14:00 • После обеда\n"
        "[▢] 14:00-15:00 • Вторая половина дня\n"
        "[▢] 15:00-16:00 • Рабочий финиш\n\n"
        "🌇 ВЕЧЕРНИЕ СЛОТЫ (+20%)\n"
        "[▢] 16:00-17:00 • Конец рабочего дня\n"
        "[▢] 17:00-18:00 • Вечерние поездки\n"
        "[▢] 18:00-19:00 • Пик трафика 🚀\n"
        "[▢] 19:00-20:00 • Домашний вечер\n"
        "[▢] 20:00-21:00 • Вечерний отдых\n\n"
        "📊 Статистика выбора:\n"
        "• Выбрано слотов: 4\n"
        "• Роликов в день: 5\n"
        "• Доплата за премиум-время: 680₽\n\n"
        "🎯 Рекомендации для вашего бизнеса\n"
        "[ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return TIME_SLOTS

# Брендированные рубрики
async def branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_contact_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "◀️ Назад     Брендированные рубрики\n\n"
        "🎙️ ВЫБЕРИТЕ ТИП РУБРИКИ:\n\n"
        "[⚪] АВТОРУБРИКИ\n"
        "Готовые сценарии для автосалонов\n"
        "\"30 секунд о китайских автомобилях\"\n"
        "\"30 секунд об АвтоВАЗе\"\n"
        "+20% к стоимости кампании\n\n"
        "[⚪] НЕДВИЖИМОСТЬ\n"
        "Рубрики для агентств недвижимости\n"
        "\"Совет по недвижимости\"\n"
        "\"Полезно знать при покупке квартиры\"\n"
        "+15% к стоимости кампании\n\n"
        "[⚪] МЕДИЦИНСКИЕ РУБРИКИ\n"
        "Экспертные форматы для клиник\n"
        "\"Здоровое сердце\"\n"
        "\"Совет врача\"\n"
        "+25% к стоимости кампании\n\n"
        "[⚪] ИНДИВИДУАЛЬНАЯ РУБРИКА\n"
        "Разработка под ваш бизнес\n"
        "Уникальный контент и сценарий\n"
        "+30% к стоимости кампании\n\n"
        "[ ПРОСЛУШАТЬ ПРИМЕР ] [ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return BRANDED_SECTIONS

# Контактная информация
async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "◀️ Назад     Контактные данные\n\n"
        "👤 КОНТАКТЫ ДЛЯ СВЯЗИ\n\n"
        "📞 ВАШ ТЕЛЕФОН:\n"
        "┌─────────────────────────────────────┐\n"
        "│ +7 ___ ___ __ __                    │\n"
        "└─────────────────────────────────────┘\n\n"
        "📧 EMAIL:\n"
        "┌─────────────────────────────────────┐\n"
        "│ _____@____.___                      │\n"
        "└─────────────────────────────────────┘\n\n"
        "🏢 НАЗВАНИЕ КОМПАНИИ:\n"
        "┌─────────────────────────────────────┐\n"
        "│ ________________________________     │\n"
        "└─────────────────────────────────────┘\n\n"
        "👨‍💼 КОНТАКТНОЕ ЛИЦО:\n"
        "┌─────────────────────────────────────┐\n"
        "│ ________________________________     │\n"
        "└─────────────────────────────────────┘\n\n"
        "💼 ДОЛЖНОСТЬ:\n"
        "┌─────────────────────────────────────┐\n"
        "│ ________________________________     │\n"
        "└─────────────────────────────────────┘\n\n"
        "📑 ПРИКРЕПИТЕ РЕКВИЗИТЫ:\n"
        "[📎 Загрузить файл с реквизитами]\n"
        "PDF, JPG, PNG до 5 МБ\n"
        "или\n"
        "[📝 Ввести реквизиты вручную]\n\n"
        "[ НАЗАД ] [ ОТПРАВИТЬ ЗАЯВКУ ]\n\n"
        "Пожалуйста, введите ваше имя:"
    )
    
    return CONTACT_INFO

# Обработка контактной информации
async def process_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'contact_name' not in context.user_data:
        context.user_data['contact_name'] = text
        await update.message.reply_text("📞 Введите ваш телефон:")
        return CONTACT_INFO
    
    elif 'phone' not in context.user_data:
        context.user_data['phone'] = text
        await update.message.reply_text("📧 Введите ваш email:")
        return CONTACT_INFO
    
    elif 'email' not in context.user_data:
        context.user_data['email'] = text
        await update.message.reply_text("🏢 Введите название компании:")
        return CONTACT_INFO
    
    elif 'company' not in context.user_data:
        context.user_data['company'] = text
        await update.message.reply_text("💼 Введите вашу должность:")
        return CONTACT_INFO
    
    elif 'position' not in context.user_data:
        context.user_data['position'] = text
        
        # Сохраняем заявку в БД
        campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
        conn = sqlite3.connect('campaigns.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO campaigns 
            (user_id, campaign_number, radio_stations, time_slots, branded_section, campaign_text, contact_name, company, phone, email, position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            update.message.from_user.id,
            campaign_number,
            ','.join(context.user_data.get('selected_radios', [])),
            ','.join(context.user_data.get('time_slots', [])),
            context.user_data.get('branded_section', ''),
            context.user_data.get('campaign_text', ''),
            context.user_data.get('contact_name', ''),
            context.user_data.get('company', ''),
            context.user_data.get('phone', ''),
            context.user_data.get('email', ''),
            context.user_data.get('position', '')
        ))
        
        conn.commit()
        conn.close()
        
        # Отправляем подтверждение
        keyboard = [
            [InlineKeyboardButton("📋 В ЛИЧНЫЙ КАБИНЕТ", callback_data="personal_cabinet")],
            [InlineKeyboardButton("🚀 НОВЫЙ ЗАКАЗ", callback_data="new_order")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ ЗАЯВКА ПРИНЯТА!\n\n"
            f"📋 № заявки: {campaign_number}\n"
            f"📅 Старт: 01.01.2025\n"
            f"💰 Сумма: 14,515₽\n\n"
            f"📧 PDF-предложение отправлено на:\n"
            f"aa@ya-radio.ru\n\n"
            f"👤 Ваш менеджер Надежда свяжется\n"
            f"в течение 1 часа для уточнения деталей\n\n"
            f"📞 +7 (34535) 5-01-51\n"
            f"✉️ aa@ya-radio.ru\n\n"
            f"🚀 ЧТО ДАЛЬШЕ:\n"
            f"• Сегодня: согласование деталей\n"
            f"• Завтра: подготовка роликов\n"
            f"• 01.01.2025: запуск рекламы",
            reply_markup=reply_markup
        )
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        return ConversationHandler.END

# Обработка других кнопок главного меню
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "statistics":
        await query.edit_message_text(
            "📊 СТАТИСТИКА ОХВАТА\n\n"
            "• Ежедневный охват: 18,500+\n"
            "• Месячный охват: 156,000+\n"
            "• Доля рынка: 52%\n"
            "• Базовая цена: 4₽/сек"
        )
    elif query.data == "my_orders":
        await query.edit_message_text(
            "📋 МОИ ЗАКАЗЫ\n\n"
            "Здесь будут отображаться ваши заказы"
        )
    elif query.data == "about":
        await query.edit_message_text(
            "ℹ️ О НАС\n\n"
            "РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
            "📍 Ялуторовск • Заводоуковск\n\n"
            "Ведущий радиовещатель в регионе"
        )
    elif query.data == "new_order":
        return await campaign_creator(update, context)
    elif query.data == "personal_cabinet":
        await query.edit_message_text(
            "📋 ЛИЧНЫЙ КАБИНЕТ\n\n"
            "Здесь будет отображаться информация о ваших заказах"
        )
    
    return MAIN_MENU

# Главная функция
def main():
    # Инициализация БД
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики разговоров
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(campaign_creator, pattern='^create_campaign$'),
                CallbackQueryHandler(handle_main_menu, pattern='^statistics$|^my_orders$|^about$|^new_order$|^personal_cabinet$')
            ],
            CAMPAIGN_CREATOR: [
                CallbackQueryHandler(enter_campaign_text, pattern='^enter_text$'),
                CallbackQueryHandler(radio_selection, pattern='^to_radio_selection$')
            ],
            "WAITING_TEXT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_campaign_text)
            ],
            RADIO_SELECTION: [
                CallbackQueryHandler(handle_radio_selection, pattern='^radio_'),
                CallbackQueryHandler(time_slots, pattern='^to_time_slots$')
            ],
            TIME_SLOTS: [
                CallbackQueryHandler(branded_sections, pattern='^to_branded_sections$')
            ],
            BRANDED_SECTIONS: [
                CallbackQueryHandler(contact_info, pattern='^to_contact_info$')
            ],
            CONTACT_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_contact_info)
            ]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    
    # Запускаем бота
    if 'RENDER' in os.environ:
        # На Render.com используем вебхук
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8443)),
            url_path=TOKEN,
            webhook_url=f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-bot')}.onrender.com/{TOKEN}"
        )
    else:
        # Локально используем polling
        application.run_polling()

if __name__ == '__main__':
    main()
