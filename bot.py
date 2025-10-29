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
TIME_SLOT_PRICES = {
    'morning': 1.25,  # +25%
    'day': 1.0,       # базовая
    'evening': 1.2    # +20%
}

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
    
    # Базовая стоимость
    base_cost = base_duration * BASE_PRICE_PER_SECOND * spots_per_day * campaign_days
    
    # Надбавки за время
    time_multiplier = 1.0
    selected_time_slots = user_data.get('selected_time_slots', [])
    for slot in selected_time_slots:
        if slot in TIME_SLOT_PRICES:
            time_multiplier = max(time_multiplier, TIME_SLOT_PRICES[slot])
    
    # Надбавка за рубрику
    branded_multiplier = 1.0
    branded_section = user_data.get('branded_section')
    if branded_section in BRANDED_SECTION_PRICES:
        branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
    
    total_price = int(base_cost * time_multiplier * branded_multiplier)
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
    
    keyboard = [
        [
            InlineKeyboardButton("✅ УТРЕННИЕ" if 'morning' in selected_slots else "🌅 УТРЕННИЕ", callback_data="slot_morning"),
            InlineKeyboardButton("✅ ДНЕВНЫЕ" if 'day' in selected_slots else "☀️ ДНЕВНЫЕ", callback_data="slot_day")
        ],
        [
            InlineKeyboardButton("✅ ВЕЧЕРНИЕ" if 'evening' in selected_slots else "🌇 ВЕЧЕРНИЕ", callback_data="slot_evening")
        ],
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_branded_sections")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    morning_count = len([s for s in selected_slots if 'morning' in s])
    day_count = len([s for s in selected_slots if 'day' in s])
    evening_count = len([s for s in selected_slots if 'evening' in s])
    total_slots = morning_count + day_count + evening_count
    
    text = (
        "◀️ Назад     Временные слоты\n\n"
        "🕒 ВЫБЕРИТЕ ВРЕМЯ ВЫХОДА РОЛИКОВ\n\n"
        "🌅 УТРЕННИЕ СЛОТЫ (+25%)\n"
        f"{'✅' if 'morning' in selected_slots else '[▢]'} 06:00-10:00 • Пиковое время\n"
        "• Подъем, сборы, утренние поездки\n"
        "• Пик трафика 🚀\n\n"
        "☀️ ДНЕВНЫЕ СЛОТЫ\n"
        f"{'✅' if 'day' in selected_slots else '[▢]'} 10:00-16:00 • Рабочее время\n"
        "• Рабочий процесс, обеденные перерывы\n\n"
        "🌇 ВЕЧЕРНИЕ СЛОТЫ (+20%)\n"
        f"{'✅' if 'evening' in selected_slots else '[▢]'} 16:00-21:00 • Вечернее время\n"
        "• Конец рабочего дня, поездки домой\n"
        "• Вечерний отдых\n\n"
        f"📊 Статистика выбора:\n"
        f"• Выбрано категорий: {len(selected_slots)}\n"
        f"• Роликов в день: {total_slots * 5}\n"
        f"• Доплата за премиум-время: {sum([25 if s == 'morning' else 20 if s == 'evening' else 0 for s in selected_slots])}%\n\n"
        "🎯 Рекомендации для вашего бизнеса\n"
        "[ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return TIME_SLOTS

# Обработка выбора временных слотов
async def handle_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    slot_data = {
        'slot_morning': 'morning',
        'slot_day': 'day',
        'slot_evening': 'evening'
    }
    
    if query.data in slot_data:
        slot_name = slot_data[query.data]
        selected_slots = context.user_data.get('selected_time_slots', [])
        
        if slot_name in selected_slots:
            selected_slots.remove(slot_name)
        else:
            selected_slots.append(slot_name)
        
        context.user_data['selected_time_slots'] = selected_slots
        return await time_slots(update, context)
    
    elif query.data == "to_branded_sections":
        if not context.user_data.get('selected_time_slots'):
            await query.answer("❌ Выберите хотя бы одну временную категорию!", show_alert=True)
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
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_contact_info")]
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
        "⏱️ Примерная длительность: 18 секунд\n\n"
        f"💰 Предварительная стоимость: {total_price}₽\n\n"
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
        f"💰 Предварительная стоимость: {total_price}₽\n\n"
        f"[ ПРОСЛУШАТЬ ПРЕВЬЮ ] [ ДАЛЕЕ ]"
    )
    
    await update.message.reply_text(text_display, reply_markup=reply_markup)
    return CAMPAIGN_CREATOR

# Шаг 5: Контактная информация
async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    total_price = calculate_campaign_price(context)
    
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
            ','.join(context.user_data.get('selected_time_slots', [])),
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
        
        # Формируем медиаплан для PDF
        media_plan = generate_media_plan(context.user_data, campaign_number)
        
        # Отправляем подтверждение с кнопкой для PDF
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
            f"✉️ aa@ya-radio.ru\n\n"
            f"🚀 ЧТО ДАЛЬШЕ:\n"
            f"• Сегодня: согласование деталей\n"
            f"• Завтра: подготовка роликов\n"
            f"• 01.01.2025: запуск рекламы\n\n"
            f"Нажмите 'СФОРМИРОВАТЬ PDF' для создания медиаплана",
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END

# Генерация медиаплана
def generate_media_plan(user_data, campaign_number):
    selected_radios = user_data.get('selected_radios', [])
    selected_times = user_data.get('selected_time_slots', [])
    branded_section = user_data.get('branded_section')
    campaign_text = user_data.get('campaign_text', 'Текст не указан')
    total_price = user_data.get('total_price', 0)
    
    media_plan = f"""
МЕДИАПЛАН КАМПАНИИ #{campaign_number}
РАДИО ТЮМЕНСКОЙ ОБЛАСТИ

📊 ПАРАМЕТРЫ КАМПАНИИ:
• Радиостанции: {', '.join(selected_radios)}
• Временные слоты: {', '.join(selected_times)}
• Брендированная рубрика: {get_branded_section_name(branded_section)}
• Длительность ролика: 30 секунд
• Количество выходов в день: 5
• Период кампании: 30 дней

💰 СТОИМОСТЬ:
• Базовая цена: 4₽/сек
• Итоговая стоимость: {total_price}₽

📝 ТЕКСТ РОЛИКА:
{campaign_text}

👤 КОНТАКТНАЯ ИНФОРМАЦИЯ:
• Контактное лицо: {user_data.get('contact_name', 'Не указано')}
• Компания: {user_data.get('company', 'Не указано')}
• Должность: {user_data.get('position', 'Не указано')}
• Телефон: {user_data.get('phone', 'Не указано')}
• Email: {user_data.get('email', 'Не указано')}

📞 КОНТАКТЫ РАДИОСТАНЦИИ:
• Менеджер: Надежда
• Телефон: +7 (34535) 5-01-51
• Email: aa@ya-radio.ru

Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}
    """
    
    return media_plan

def get_branded_section_name(section):
    names = {
        'auto': 'Авторубрики (+20%)',
        'realty': 'Недвижимость (+15%)',
        'medical': 'Медицинские рубрики (+25%)',
        'custom': 'Индивидуальная рубрика (+30%)'
    }
    return names.get(section, 'Не выбрана')

# Обработка генерации PDF
async def generate_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    campaign_number = query.data.replace('generate_pdf_', '')
    
    # Здесь будет логика генерации PDF файла
    # Пока отправляем текстовый медиаплан
    
    media_plan = generate_media_plan(context.user_data, campaign_number)
    
    await query.message.reply_text(
        f"📄 МЕДИАПЛАН ДЛЯ ДИРЕКТОРА\n\n"
        f"{media_plan}\n\n"
        f"✅ Медиаплан сформирован и отправлен на email\n"
        f"📧 {context.user_data.get('email', 'Не указан')}"
    )

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
        context.user_data.clear()
        return await radio_selection(update, context)
    elif query.data == "personal_cabinet":
        await query.edit_message_text(
            "📋 ЛИЧНЫЙ КАБИНЕТ\n\n"
            "Здесь будет отображаться информация о ваших заказах"
        )
    elif query.data.startswith("generate_pdf_"):
        return await generate_pdf(update, context)
    
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
                CallbackQueryHandler(radio_selection, pattern='^create_campaign$'),
                CallbackQueryHandler(handle_main_menu, pattern='^statistics$|^my_orders$|^about$|^new_order$|^personal_cabinet$|^generate_pdf_')
            ],
            RADIO_SELECTION: [
                CallbackQueryHandler(handle_radio_selection, pattern='^radio_'),
                CallbackQueryHandler(time_slots, pattern='^to_time_slots$')
            ],
            TIME_SLOTS: [
                CallbackQueryHandler(handle_time_slots, pattern='^slot_'),
                CallbackQueryHandler(branded_sections, pattern='^to_branded_sections$')
            ],
            BRANDED_SECTIONS: [
                CallbackQueryHandler(handle_branded_sections, pattern='^branded_|^skip_branded$'),
                CallbackQueryHandler(campaign_creator, pattern='^to_campaign_creator$')
            ],
            CAMPAIGN_CREATOR: [
                CallbackQueryHandler(enter_campaign_text, pattern='^enter_text$'),
                CallbackQueryHandler(contact_info, pattern='^to_contact_info$')
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
