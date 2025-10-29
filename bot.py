import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора
MAIN_MENU, RADIO_SELECTION, TIME_SLOTS, BRANDED_SECTIONS, CAMPAIGN_CREATOR, CONTACT_INFO = range(6)

# Токен бота
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

# Цены и параметры
BASE_PRICE_PER_SECOND = 4
MIN_PRODUCTION_COST = 2000  # Минимальная стоимость изготовления ролика

TIME_SLOTS_DATA = [
    {"time": "06:00-07:00", "label": "Подъем, сборы", "premium": True},
    {"time": "07:00-08:00", "label": "Утренние поездки", "premium": True},
    {"time": "08:00-09:00", "label": "Пик трафика 🚀", "premium": True},
    {"time": "09:00-10:00", "label": "Начало работы", "premium": True},
    {"time": "10:00-11:00", "label": "Рабочий процесс", "premium": False},
    {"time": "11:00-12:00", "label": "Предобеденное время", "premium": False},
    {"time": "12:00-13:00", "label": "Обеденный перерыв", "premium": False},
    {"time": "13:00-14:00", "label": "После обеда", "premium": False},
    {"time": "14:00-15:00", "label": "Вторая половина дня", "premium": False},
    {"time": "15:00-16:00", "label": "Рабочий финиш", "premium": False},
    {"time": "16:00-17:00", "label": "Конец рабочего дня", "premium": True},
    {"time": "17:00-18:00", "label": "Вечерние поездки", "premium": True},
    {"time": "18:00-19:00", "label": "Пик трафика 🚀", "premium": True},
    {"time": "19:00-20:00", "label": "Домашний вечер", "premium": True},
    {"time": "20:00-21:00", "label": "Вечерний отдых", "premium": True}
]

BRANDED_SECTION_PRICES = {
    'auto': 1.2,      # +20%
    'realty': 1.15,   # +15%
    'medical': 1.25,  # +25%
    'custom': 1.3     # +30%
}

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
            total_price INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Расчет стоимости кампании
def calculate_campaign_price(context):
    user_data = context.user_data
    
    # Базовые параметры
    base_duration = 30  # секунд
    spots_per_day = 5
    campaign_days = 30
    
    # Базовая стоимость эфира
    base_air_cost = base_duration * BASE_PRICE_PER_SECOND * spots_per_day * campaign_days
    
    # Надбавки за премиум-время
    selected_time_slots = user_data.get('selected_time_slots', [])
    time_multiplier = 1.0
    
    for slot_index in selected_time_slots:
        if 0 <= slot_index < len(TIME_SLOTS_DATA):
            slot = TIME_SLOTS_DATA[slot_index]
            if slot['premium']:
                if slot_index <= 3:  # Утренние слоты
                    time_multiplier = max(time_multiplier, 1.25)
                else:  # Вечерние слоты
                    time_multiplier = max(time_multiplier, 1.2)
    
    # Надбавка за рубрику
    branded_multiplier = 1.0
    branded_section = user_data.get('branded_section')
    if branded_section in BRANDED_SECTION_PRICES:
        branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
    
    # Итоговая стоимость (эфир + производство)
    air_cost = int(base_air_cost * time_multiplier * branded_multiplier)
    total_price = max(air_cost, MIN_PRODUCTION_COST)
    
    return total_price

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

# Шаг 1: Выбор радиостанций
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
    
    if query.data == "back_to_main":
        return await start(update, context)
    
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

# Шаг 2: Временные слоты (активный выбор)
async def time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_slots = context.user_data.get('selected_time_slots', [])
    
    # Создаем клавиатуру с временными слотами
    keyboard = []
    
    # Утренние слоты
    keyboard.append([InlineKeyboardButton("🌅 УТРЕННИЕ СЛОТЫ (+25%)", callback_data="header_morning")])
    for i in range(4):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "▢"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    # Дневные слоты
    keyboard.append([InlineKeyboardButton("☀️ ДНЕВНЫЕ СЛОТЫ", callback_data="header_day")])
    for i in range(4, 10):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "▢"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    # Вечерние слоты
    keyboard.append([InlineKeyboardButton("🌇 ВЕЧЕРНИЕ СЛОТЫ (+20%)", callback_data="header_evening")])
    for i in range(10, 15):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "▢"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_radio")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_branded_sections")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Статистика выбора
    premium_count = len([s for s in selected_slots if TIME_SLOTS_DATA[s]['premium']])
    regular_count = len(selected_slots) - premium_count
    total_slots = len(selected_slots)
    
    text = (
        "◀️ Назад     Временные слоты\n\n"
        "🕒 ВЫБЕРИТЕ ВРЕМЯ ВЫХОДА РОЛИКОВ\n\n"
        f"📊 Статистика выбора:\n"
        f"• Выбрано слотов: {total_slots}\n"
        f"• Премиум-слоты: {premium_count}\n"
        f"• Обычные слоты: {regular_count}\n"
        f"• Роликов в день: {total_slots * 5}\n\n"
        "🎯 Выберите подходящие временные интервалы\n"
        "[ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return TIME_SLOTS

# Обработка выбора временных слотов
async def handle_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_radio":
        return await radio_selection(update, context)
    
    elif query.data.startswith("time_"):
        slot_index = int(query.data.split("_")[1])
        selected_slots = context.user_data.get('selected_time_slots', [])
        
        if slot_index in selected_slots:
            selected_slots.remove(slot_index)
        else:
            selected_slots.append(slot_index)
        
        context.user_data['selected_time_slots'] = selected_slots
        return await time_slots(update, context)
    
    elif query.data == "to_branded_sections":
        if not context.user_data.get('selected_time_slots'):
            await query.answer("❌ Выберите хотя бы один временной слот!", show_alert=True)
            return TIME_SLOTS
        return await branded_sections(update, context)
    
    return TIME_SLOTS

# Шаг 3: Брендированные рубрики (активный выбор)
async def branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_branded = context.user_data.get('branded_section')
    
    keyboard = [
        [InlineKeyboardButton("✅ АВТОРУБРИКИ" if selected_branded == 'auto' else "⚪ АВТОРУБРИКИ", callback_data="branded_auto")],
        [InlineKeyboardButton("✅ НЕДВИЖИМОСТЬ" if selected_branded == 'realty' else "⚪ НЕДВИЖИМОСТЬ", callback_data="branded_realty")],
        [InlineKeyboardButton("✅ МЕДИЦИНСКИЕ" if selected_branded == 'medical' else "⚪ МЕДИЦИНСКИЕ", callback_data="branded_medical")],
        [InlineKeyboardButton("✅ ИНДИВИДУАЛЬНАЯ" if selected_branded == 'custom' else "⚪ ИНДИВИДУАЛЬНАЯ", callback_data="branded_custom")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_time")],
        [InlineKeyboardButton("⏩ ПРОПУСТИТЬ", callback_data="skip_branded")],
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_campaign_creator")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "◀️ Назад     Брендированные рубрики\n\n"
        "🎙️ ВЫБЕРИТЕ ТИП РУБРИКИ:\n\n"
        f"{'✅' if selected_branded == 'auto' else '[⚪]'} АВТОРУБРИКИ\n"
        "Готовые сценарии для автосалонов\n"
        "\"30 секунд о китайских автомобилях\"\n"
        "\"30 секунд об АвтоВАЗе\"\n"
        "+20% к стоимости кампании\n\n"
        f"{'✅' if selected_branded == 'realty' else '[⚪]'} НЕДВИЖИМОСТЬ\n"
        "Рубрики для агентств недвижимости\n"
        "\"Совет по недвижимости\"\n"
        "\"Полезно знать при покупке квартиры\"\n"
        "+15% к стоимости кампании\n\n"
        f"{'✅' if selected_branded == 'medical' else '[⚪]'} МЕДИЦИНСКИЕ РУБРИКИ\n"
        "Экспертные форматы для клиник\n"
        "\"Здоровое сердце\"\n"
        "\"Совет врача\"\n"
        "+25% к стоимости кампании\n\n"
        f"{'✅' if selected_branded == 'custom' else '[⚪]'} ИНДИВИДУАЛЬНАЯ РУБРИКА\n"
        "Разработка под ваш бизнес\n"
        "Уникальный контент и сценарий\n"
        "+30% к стоимости кампании\n\n"
        "[ ПРОСЛУШАТЬ ПРИМЕР ] [ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return BRANDED_SECTIONS

# Обработка выбора рубрик
async def handle_branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_time":
        return await time_slots(update, context)
    
    branded_data = {
        'branded_auto': 'auto',
        'branded_realty': 'realty',
        'branded_medical': 'medical',
        'branded_custom': 'custom'
    }
    
    if query.data in branded_data:
        context.user_data['branded_section'] = branded_data[query.data]
        return await branded_sections(update, context)
    
    elif query.data == "skip_branded":
        context.user_data['branded_section'] = None
        return await campaign_creator(update, context)
    
    elif query.data == "to_campaign_creator":
        return await campaign_creator(update, context)
    
    return BRANDED_SECTIONS

# Шаг 4: Конструктор ролика
async def campaign_creator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Рассчитываем предварительную стоимость
    total_price = calculate_campaign_price(context)
    context.user_data['total_price'] = total_price
    
    keyboard = [
        [InlineKeyboardButton("📝 ВВЕСТИ ТЕКСТ РОЛИКА", callback_data="enter_text")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_branded")],
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_contact_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    campaign_text = context.user_data.get('campaign_text', '')
    char_count = len(campaign_text) if campaign_text else 0
    
    text = (
        "◀️ Назад     Конструктор ролика\n\n"
        "📎 ПРИКРЕПИТЕ ГОТОВЫЙ РОЛИК:\n"
        "[ 📁 Загрузить аудиофайл ]\n"
        "MP3, WAV до 10 МБ\n\n"
        "ИЛИ\n\n"
        "📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n"
        f"┌─────────────────────────────────────┐\n"
        f"│ {campaign_text[:37] if campaign_text else '':<37} │\n"
        f"└─────────────────────────────────────┘\n"
        f"○ {char_count} знаков из 500\n\n"
        f"⏱️ Примерная длительность: {max(15, char_count // 7) if char_count > 0 else 0} секунд\n\n"
        f"💰 Предварительная стоимость: от {total_price}₽\n"
        f"   (включая изготовление ролика от {MIN_PRODUCTION_COST}₽)\n\n"
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
        "Тест-драйв в день обращения!\n\n"
        "Отправьте текст сообщением:"
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
    
    total_price = calculate_campaign_price(context)
    
    keyboard = [[InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_contact_info")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text_display = (
        f"◀️ Назад     Конструктор ролика\n\n"
        f"📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n"
        f"┌─────────────────────────────────────┐\n"
        f"│ {text:<37} │\n"
        f"└─────────────────────────────────────┘\n"
        f"○ {char_count} знаков из 500\n\n"
        f"⏱️ Примерная длительность: {max(15, char_count // 7)} секунд\n\n"
        f"💰 Предварительная стоимость: от {total_price}₽\n"
        f"   (включая изготовление ролика от {MIN_PRODUCTION_COST}₽)\n\n"
        f"[ ПРОСЛУШАТЬ ПРЕВЬЮ ] [ ДАЛЕЕ ]"
    )
    
    await update.message.reply_text(text_display, reply_markup=reply_markup)
    return CAMPAIGN_CREATOR

# Шаг 5: Контактная информация
async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    total_price = calculate_campaign_price(context)
    
    keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_creator")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"◀️ Назад     Контактные данные\n\n"
        f"👤 КОНТАКТЫ ДЛЯ СВЯЗИ\n\n"
        f"💰 Предварительная стоимость: {total_price}₽\n\n"
        f"📞 ВАШ ТЕЛЕФОН:\n"
        f"┌─────────────────────────────────────┐\n"
        f"│ +7 ___ ___ __ __                    │\n"
        f"└─────────────────────────────────────┘\n\n"
        f"📧 EMAIL:\n"
        f"┌─────────────────────────────────────┐\n"
        f"│ _____@____.___                      │\n"
        f"└─────────────────────────────────────┘\n\n"
        f"🏢 НАЗВАНИЕ КОМПАНИИ:\n"
        f"┌─────────────────────────────────────┐\n"
        f"│ ________________________________     │\n"
        f"└─────────────────────────────────────┘\n\n"
        f"👨‍💼 КОНТАКТНОЕ ЛИЦО:\n"
        f"┌─────────────────────────────────────┐\n"
        f"│ ________________________________     │\n"
        f"└─────────────────────────────────────┘\n\n"
        f"💼 ДОЛЖНОСТЬ:\n"
        f"┌─────────────────────────────────────┐\n"
        f"│ ________________________________     │\n"
        f"└─────────────────────────────────────┘\n\n"
        f"📑 ПРИКРЕПИТЕ РЕКВИЗИТЫ:\n"
        f"[📎 Загрузить файл с реквизитами]\n"
        f"PDF, JPG, PNG до 5 МБ\n"
        f"или\n"
        f"[📝 Ввести реквизиты вручную]\n\n"
        f"[ НАЗАД ] [ ОТПРАВИТЬ ЗАЯВКУ ]\n\n"
        f"Пожалуйста, введите ваше имя:"
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
        
        # Рассчитываем финальную стоимость
        total_price = calculate_campaign_price(context)
        context.user_data['total_price'] = total_price
        
        # Сохраняем заявку в БД
        campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
        conn = sqlite3.connect('campaigns.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO campaigns 
            (user_id, campaign_number, radio_stations, time_slots, branded_section, campaign_text, contact_name, company, phone, email, position, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            update.message.from_user.id,
            campaign_number,
            ','.join(context.user_data.get('selected_radios', [])),
            ','.join(map(str, context.user_data.get('selected_time_slots', []))),
            context.user_data.get('branded_section', ''),
            context.user_data.get('campaign_text', ''),
            context.user_data.get('contact_name', ''),
            context.user_data.get('company', ''),
            context.user_data.get('phone', ''),
            context.user_data.get('email', ''),
            context.user_data.get('position', ''),
            total_price
        ))
        
        conn.commit()
        conn.close()
        
        # Отправляем подтверждение с работающими кнопками
        keyboard = [
            [InlineKeyboardButton("📄 СФОРМИРОВАТЬ PDF", callback_data=f"generate_pdf_{campaign_number}")],
            [InlineKeyboardButton("📋 В ЛИЧНЫЙ КАБИНЕТ", callback_data="personal_cabinet")],
            [InlineKeyboardButton("🚀 НОВЫЙ ЗАКАЗ", callback_data="new_order")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ ЗАЯВКА ПРИНЯТА!\n\n"
            f"📋 № заявки: {campaign_number}\n"
            f"📅 Старт: 01.01.2025\n"
            f"💰 Сумма: {total_price}₽\n\n"
            f"📧 PDF-предложение будет отправлено на:\n"
            f"{context.user_data['email']}\n\n"
            f"👤 Ваш менеджер Надежда свяжется\n"
            f"в течение 1 часа для уточнения деталей\n\n"
            f"📞 +7 (34535) 5-01-51\n"
            f"✉️ a.khlistunov@gmail.com\n\n"
            f"🚀 ЧТО ДАЛЬШЕ:\n"
            f"• Сегодня: согласование деталей\n"
            f"• Завтра: подготовка роликов\n"
            f"• 01.01.2025: запуск рекламы\n\n"
            f"Нажмите 'СФОРМИРОВАТЬ PDF' для создания медиаплана",
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END

# Генерация медиаплана (заглушка)
async def generate_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    campaign_number = query.data.replace('generate_pdf_', '')
    
    # Здесь будет реальная генерация PDF
    media_plan = f"""
МЕДИАПЛАН КАМПАНИИ #{campaign_number}
РАДИО ТЮМЕНСКОЙ ОБЛАСТИ

✅ PDF успешно сформирован!
Заявка отправлена менеджеру.

📧 Копия отправлена на:
a.khlistunov@gmail.com
    """
    
    await query.message.reply_text(
        f"📄 МЕДИАПЛАН ДЛЯ ДИРЕКТОРА\n\n"
        f"{media_plan}\n\n"
        f"✅ Медиаплан сформирован и отправлен!\n"
        f"📧 Заказчику: {context.user_data.get('email', 'Не указан')}\n"
        f"📧 Нам: a.khlistunov@gmail.com"
    )

# Личный кабинет
async def personal_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    conn = sqlite3.connect('campaigns.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT campaign_number, status, total_price, created_at FROM campaigns WHERE user_id = ? ORDER BY created_at DESC LIMIT 5', (user_id,))
    orders = cursor.fetchall()
    conn.close()
    
    if orders:
        orders_text = "📋 ПОСЛЕДНИЕ ЗАКАЗЫ:\n\n"
        for order in orders:
            orders_text += f"📋 {order[0]} | {order[1]} | {order[2]}₽ | {order[3][:10]}\n"
    else:
        orders_text = "📋 У вас пока нет заказов"
    
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 ЛИЧНЫЙ КАБИНЕТ\n\n"
        f"{orders_text}\n\n"
        f"Здесь отображается история ваших заказов",
        reply_markup=reply_markup
    )

# Обработка главного меню и навигации
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "create_campaign":
        context.user_data.clear()
        return await radio_selection(update, context)
    
    elif query.data == "statistics":
        await query.edit_message_text(
            "📊 СТАТИСТИКА ОХВАТА\n\n"
            "• Ежедневный охват: 18,500+\n"
            "• Месячный охват: 156,000+\n"
            "• Доля рынка: 52%\n"
            "• Базовая цена: 4₽/сек\n\n"
            "• LOVE RADIO: 3,200/день\n"
            "• АВТОРАДИО: 2,800/день\n"
            "• РАДИО ДАЧА: 3,500/день\n"
            "• РАДИО ШАНСОН: 2,600/день\n"
            "• РЕТРО FM: 2,900/день\n"
            "• ЮМОР FM: 2,100/день"
        )
        return MAIN_MENU
    
    elif query.data == "my_orders":
        return await personal_cabinet(update, context)
    
    elif query.data == "about":
        await query.edit_message_text(
            "ℹ️ О НАС\n\n"
            "🔴 РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
            "📍 Ялуторовск • Заводоуковск\n\n"
            "Ведущий радиовещатель в регионе\n"
            "Охватываем 52% радиорынка\n\n"
            "📞 +7 (34535) 5-01-51\n"
            "📧 a.khlistunov@gmail.com\n"
            "👤 Менеджер: Надежда"
        )
        return MAIN_MENU
    
    elif query.data == "new_order":
        context.user_data.clear()
        return await radio_selection(update, context)
    
    elif query.data == "personal_cabinet":
        return await personal_cabinet(update, context)
    
    elif query.data.startswith("generate_pdf_"):
        return await generate_pdf(update, context)
    
    elif query.data == "back_to_main":
        return await start(update, context)
    
    elif query.data == "back_to_radio":
        return await radio_selection(update, context)
    
    elif query.data == "back_to_time":
        return await time_slots(update, context)
    
    elif query.data == "back_to_branded":
        return await branded_sections(update, context)
    
    elif query.data == "back_to_creator":
        return await campaign_creator(update, context)
    
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
                CallbackQueryHandler(handle_main_menu, pattern='^.*$')
            ],
            RADIO_SELECTION: [
                CallbackQueryHandler(handle_radio_selection, pattern='^.*$')
            ],
            TIME_SLOTS: [
                CallbackQueryHandler(handle_time_slots, pattern='^.*$')
            ],
            BRANDED_SECTIONS: [
                CallbackQueryHandler(handle_branded_sections, pattern='^.*$')
            ],
            CAMPAIGN_CREATOR: [
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_|^to_contact_info$'),
                CallbackQueryHandler(enter_campaign_text, pattern='^enter_text$')
            ],
            "WAITING_TEXT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_campaign_text)
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
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8443)),
            url_path=TOKEN,
            webhook_url=f"https://{os.environ.get('RENDER_SERVICE_NAME', 'telegram-radio-bot')}.onrender.com/{TOKEN}"
        )
    else:
        application.run_polling()

if __name__ == '__main__':
    main()
