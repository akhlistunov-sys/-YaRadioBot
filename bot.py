import os
import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import io
import re
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора
MAIN_MENU, RADIO_SELECTION, CAMPAIGN_DATES, TIME_SLOTS, BRANDED_SECTIONS, CAMPAIGN_CREATOR, PRODUCTION_OPTION, CONTACT_INFO, CONFIRMATION, FINAL_ACTIONS = range(10)

# Токен бота
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

# Ваш Telegram ID для уведомлений
ADMIN_TELEGRAM_ID = 174046571

# Цены и параметры
BASE_PRICE_PER_SECOND = 2
MIN_PRODUCTION_COST = 2000
MIN_BUDGET = 7000

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

# Обновленные данные охвата (усредненные)
STATION_COVERAGE = {
    'LOVE RADIO': 540,
    'АВТОРАДИО': 3250,
    'РАДИО ДАЧА': 3250,
    'РАДИО ШАНСОН': 2900,
    'РЕТРО FM': 3600,
    'ЮМОР FM': 1260
}

BRANDED_SECTION_PRICES = {
    'auto': 1.2,
    'realty': 1.15,
    'medical': 1.25,
    'custom': 1.3
}

PRODUCTION_OPTIONS = {
    'standard': {'price': 2000, 'name': 'СТАНДАРТНЫЙ РОЛИК', 'desc': 'Профессиональная озвучка, музыкальное оформление, 2 правки, срок: 2-3 дня'},
    'premium': {'price': 4000, 'name': 'ПРЕМИУМ РОЛИК', 'desc': 'Озвучка 2-мя голосами, индивидуальная музыка, 5 правки, срочное производство 1 день'},
    'ready': {'price': 0, 'name': 'ГОТОВЫЙ РОЛИК', 'desc': 'У меня есть свой ролик, пришлю файлом'}
}

# Инициализация базы данных
def init_db():
    try:
        conn = sqlite3.connect('campaigns.db')
        cursor = conn.cursor()
        cursor.execute('''
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
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        return False

def validate_phone(phone: str) -> bool:
    pattern = r'^(\+7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
    return bool(re.match(pattern, phone))

def format_number(num):
    return f"{num:,}".replace(',', ' ')

def calculate_campaign_price_and_reach(user_data):
    try:
        base_duration = user_data.get('duration', 20)
        campaign_days = user_data.get('campaign_days', 30)
        num_stations = len(user_data.get('selected_radios', []))
        selected_time_slots = user_data.get('selected_time_slots', [])
        
        spots_per_day = len(selected_time_slots) * num_stations
        base_air_cost = base_duration * BASE_PRICE_PER_SECOND * spots_per_day * campaign_days
        
        time_multiplier = 1.0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                if slot['premium']:
                    time_multiplier = max(time_multiplier, 1.1)
        
        branded_multiplier = 1.0
        branded_section = user_data.get('branded_section')
        if branded_section in BRANDED_SECTION_PRICES:
            branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
        
        production_cost = user_data.get('production_cost', 0)
        air_cost = int(base_air_cost * time_multiplier * branded_multiplier)
        base_price = air_cost + production_cost
        
        discount = int(base_price * 0.5)
        discounted_price = base_price - discount
        final_price = max(discounted_price, MIN_BUDGET)
        
        # Новый расчет охвата по спотам
        coverage_per_spot = 0.15  # 15% охват за один спот
        daily_coverage = 0
        for radio in user_data.get('selected_radios', []):
            station_coverage = STATION_COVERAGE.get(radio, 0)
            daily_coverage += station_coverage * coverage_per_spot * len(selected_time_slots)
        
        total_reach = int(daily_coverage * campaign_days * 0.7 * 0.5)  # Учет уникальности и повторяемости
        
        return base_price, discount, final_price, total_reach, int(daily_coverage), spots_per_day
    except Exception as e:
        logger.error(f"Ошибка расчета стоимости: {e}")
        return 0, 0, 0, 0, 0, 0

def get_branded_section_name(section):
    names = {
        'auto': 'Авторубрики (+20%)',
        'realty': 'Недвижимость (+15%)',
        'medical': 'Медицинские рубрики (+25%)',
        'custom': 'Индивидуальная рубрика (+30%)'
    }
    return names.get(section, 'Не выбрана')

def create_excel_file_from_db(campaign_number):
    try:
        conn = sqlite3.connect('campaigns.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM campaigns WHERE campaign_number = ?', (campaign_number,))
        campaign_data = cursor.fetchone()
        conn.close()
        
        if not campaign_data:
            return None
            
        # Создаем user_data из данных БД
        user_data = {
            'selected_radios': campaign_data[3].split(','),
            'start_date': campaign_data[4],
            'end_date': campaign_data[5],
            'campaign_days': campaign_data[6],
            'selected_time_slots': list(map(int, campaign_data[7].split(','))) if campaign_data[7] else [],
            'branded_section': campaign_data[8],
            'campaign_text': campaign_data[9],
            'production_option': campaign_data[10],
            'contact_name': campaign_data[11],
            'company': campaign_data[12],
            'phone': campaign_data[13],
            'email': campaign_data[14],
            'duration': campaign_data[15],
            'production_cost': PRODUCTION_OPTIONS.get(campaign_data[10], {}).get('price', 0)
        }
        
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day = calculate_campaign_price_and_reach(user_data)
        
        wb = Workbook()
        ws = wb.active
        ws.title = f"Медиаплан {campaign_number}"
        
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        title_font = Font(bold=True, size=12)
        border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                       top=Side(style='thin'), bottom=Side(style='thin'))
        
        ws.merge_cells('A1:F1')
        ws['A1'] = f"МЕДИАПЛАН КАМПАНИИ #{campaign_number}"
        ws['A1'].font = header_font
        ws['A1'].fill = header_fill
        ws['A1'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('A2:F2')
        ws['A2'] = "РАДИО ТЮМЕНСКОЙ ОБЛАСТИ"
        ws['A2'].font = Font(bold=True, size=12, color="366092")
        ws['A2'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('A4:F4')
        ws['A4'] = "✅ Ваша заявка принята! Спасибо за доверие!"
        ws['A4'].font = Font(bold=True, size=11)
        
        ws['A6'] = "📊 ПАРАМЕТРЫ КАМПАНИИ:"
        ws['A6'].font = title_font
        
        params = [
            f"Радиостанции: {', '.join(user_data.get('selected_radios', []))}",
            f"Период: {user_data.get('start_date')} - {user_data.get('end_date')} ({user_data.get('campaign_days')} дней)",
            f"Выходов в день: {spots_per_day}",
            f"Всего выходов за период: {spots_per_day * user_data.get('campaign_days', 30)}",
            f"Хронометраж ролика: {user_data.get('duration', 20)} сек",
            f"Брендированная рубрика: {get_branded_section_name(user_data.get('branded_section'))}",
            f"Производство: {PRODUCTION_OPTIONS.get(user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}"
        ]
        
        for i, param in enumerate(params, 7):
            ws[f'A{i}'] = f"• {param}"
        
        ws['A15'] = "📻 ВЫБРАННЫЕ РАДИОСТАНЦИИ:"
        ws['A15'].font = title_font
        
        row = 16
        total_listeners = 0
        for radio in user_data.get('selected_radios', []):
            listeners = STATION_COVERAGE.get(radio, 0)
            total_listeners += listeners
            ws[f'A{row}'] = f"• {radio}: {format_number(listeners)} слушателей/день"
            row += 1
        
        ws[f'A{row}'] = f"• ИТОГО: {format_number(total_listeners)} слушателей/день"
        ws[f'A{row}'].font = Font(bold=True)
        
        row += 2
        ws[f'A{row}'] = "🕒 ВЫБРАННЫЕ ВРЕМЕННЫЕ СЛОТЫ:"
        ws[f'A{row}'].font = title_font
        
        row += 1
        for slot_index in user_data.get('selected_time_slots', []):
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                premium = "✅" if slot['premium'] else "❌"
                ws[f'A{row}'] = f"• {slot['time']} - {slot['label']} (Премиум: {premium})"
                row += 1
        
        row += 1
        ws[f'A{row}'] = "🎯 РАСЧЕТНЫЙ ОХВАТ (по выбранным спотам):"
        ws[f'A{row}'].font = title_font
        
        row += 1
        coverage_per_spot = int(total_listeners * 0.15 / len(user_data.get('selected_time_slots', [1])))
        ws[f'A{row}'] = f"• Выходов в день: {spots_per_day}"
        row += 1
        ws[f'A{row}'] = f"• Охват за 1 выход: ~{format_number(coverage_per_spot)} чел. (15% от аудитории)"
        row += 1
        ws[f'A{row}'] = f"• Ежедневный охват: ~{format_number(daily_coverage)} чел."
        row += 1
        ws[f'A{row}'] = f"• Общий охват за период: ~{format_number(total_reach)} чел."
        
        row += 2
        ws[f'A{row}'] = "💰 ФИНАНСОВАЯ ИНФОРМАЦИЯ:"
        ws[f'A{row}'].font = title_font
        
        financial_data = [
            ['Позиция', 'Сумма (₽)'],
            ['Эфирное время', base_price - user_data.get('production_cost', 0)],
            ['Производство ролика', user_data.get('production_cost', 0)],
            ['', ''],
            ['Базовая стоимость', base_price],
            ['Скидка 50%', -discount],
            ['', ''],
            ['ИТОГО', final_price]
        ]
        
        for i, (item, value) in enumerate(financial_data, row + 1):
            ws[f'A{i}'] = item
            if isinstance(value, int):
                ws[f'B{i}'] = value
                if item == 'ИТОГО':
                    ws[f'B{i}'].font = Font(bold=True, color="FF0000")
                elif item == 'Скидка 50%':
                    ws[f'B{i}'].font = Font(color="00FF00")
            else:
                ws[f'B{i}'] = value
        
        row = i + 3
        ws[f'A{row}'] = "👤 ВАШИ КОНТАКТЫ:"
        ws[f'A{row}'].font = title_font
        
        contacts = [
            f"Имя: {user_data.get('contact_name', 'Не указано')}",
            f"Телефон: {user_data.get('phone', 'Не указан')}",
            f"Email: {user_data.get('email', 'Не указан')}",
            f"Компания: {user_data.get('company', 'Не указана')}"
        ]
        
        for i, contact in enumerate(contacts, row + 1):
            ws[f'A{i}'] = f"• {contact}"
        
        row = i + 2
        ws[f'A{row}'] = "📞 НАШИ КОНТАКТЫ:"
        ws[f'A{row}'].font = title_font
        ws[f'A{row + 1}'] = "• Email: a.khlistunov@gmail.com"
        ws[f'A{row + 2}'] = "• Telegram: t.me/AlexeyKhlistunov"
        
        row = row + 4
        ws[f'A{row}'] = "🎯 СТАРТ КАМПАНИИ:"
        ws[f'A{row}'].font = title_font
        ws[f'A{row + 1}'] = "В течение 3 рабочих дней после подтверждения"
        
        row = row + 3
        ws[f'A{row}'] = f"📅 Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        ws.column_dimensions['A'].width = 45
        ws.column_dimensions['B'].width = 15
        
        table_start = row - len(financial_data) - 1
        table_end = table_start + len(financial_data) - 1
        for row_num in range(table_start, table_end + 1):
            for col in ['A', 'B']:
                ws[f'{col}{row_num}'].border = border
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        logger.info(f"Excel файл успешно создан для кампании #{campaign_number}")
        return buffer
        
    except Exception as e:
        logger.error(f"Ошибка при создании Excel: {e}")
        return None

async def send_excel_file_to_admin(context, campaign_number):
    try:
        excel_buffer = create_excel_file_from_db(campaign_number)
        if not excel_buffer:
            return False
            
        await context.bot.send_document(
            chat_id=ADMIN_TELEGRAM_ID,
            document=excel_buffer,
            filename=f"mediaplan_{campaign_number}.xlsx",
            caption=f"📊 Медиаплан кампании #{campaign_number}"
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке Excel админу: {e}")
        return False

async def send_admin_notification(context, user_data, campaign_number):
    try:
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day = calculate_campaign_price_and_reach(user_data)
        
        stations_text = ""
        for radio in user_data.get('selected_radios', []):
            listeners = STATION_COVERAGE.get(radio, 0)
            stations_text += f"• {radio}: {format_number(listeners)}/день\n"
        
        slots_text = ""
        for slot_index in user_data.get('selected_time_slots', []):
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                premium = "✅" if slot['premium'] else "❌"
                slots_text += f"• {slot['time']} - {slot['label']} (Премиум: {premium})\n"
        
        notification_text = f"""
🔔 НОВАЯ ЗАЯВКА #{campaign_number}

👤 КЛИЕНТ:
Имя: {user_data.get('contact_name', 'Не указано')}
Телефон: {user_data.get('phone', 'Не указан')}
Email: {user_data.get('email', 'Не указан')}
Компания: {user_data.get('company', 'Не указана')}

📊 РАДИОСТАНЦИИ:
{stations_text}
📅 ПЕРИОД: {user_data.get('start_date')} - {user_data.get('end_date')} ({user_data.get('campaign_days')} дней)
🕒 СЛОТЫ ({len(user_data.get('selected_time_slots', []))} выбрано):
{slots_text}
🎙️ РУБРИКА: {get_branded_section_name(user_data.get('branded_section'))}
⏱️ РОЛИК: {PRODUCTION_OPTIONS.get(user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}
📏 ХРОНОМЕТРАЖ: {user_data.get('duration', 20)} сек

💰 СТОИМОСТЬ:
Базовая: {format_number(base_price)}₽
Скидка 50%: -{format_number(discount)}₽
Итоговая: {format_number(final_price)}₽

🎯 РАСЧЕТНЫЙ ОХВАТ (по выбранным спотам):
• Выходов в день: {spots_per_day}
• Всего выходов: {spots_per_day * user_data.get('campaign_days', 30)}
• Ежедневно: ~{format_number(daily_coverage)} чел.
• За период: ~{format_number(total_reach)} чел.
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📊 СФОРМИРОВАТЬ EXCEL", callback_data=f"generate_excel_{campaign_number}"),
            ],
            [
                InlineKeyboardButton(f"📞 {user_data.get('phone', 'Телефон')}", callback_data=f"call_{user_data.get('phone', '')}"),
                InlineKeyboardButton(f"✉️ Написать", callback_data=f"email_{user_data.get('email', '')}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=notification_text,
            reply_markup=reply_markup
        )
        logger.info(f"Уведомление админу отправлено для кампании #{campaign_number}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🚀 СОЗДАТЬ КАМПАНИЮ", callback_data="create_campaign")],
        [InlineKeyboardButton("📊 СТАТИСТИКА ОХВАТА", callback_data="statistics")],
        [InlineKeyboardButton("📋 МОИ ЗАКАЗЫ", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ О НАС", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = (
        "📍 Ялуторовск • Заводоуковск\n"
        "📍 Территория +35 км вокруг городов\n\n"
        "📊 Потенциальных контактов: от 3,000+ в день\n"
        "👥 Уникальных слушателей: от 35,000+ в месяц\n\n"
        "🎯 52% доля местного радиорынка\n"
        "💰 2₽/сек базовая цена"
    )
    
    # Если это сообщение от команды /start
    if update.message:
        await update.message.reply_text(
            caption,
            reply_markup=reply_markup
        )
    else:
        # Если это callback query (возврат из другого раздела)
        query = update.callback_query
        await query.answer()
        
        # Редактируем существующее сообщение вместо создания нового
        await query.edit_message_text(
            caption,
            reply_markup=reply_markup
        )
    
    return MAIN_MENU

async def radio_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_radios = context.user_data.get('selected_radios', [])
    total_listeners = sum(STATION_COVERAGE.get(radio, 0) for radio in selected_radios)
    
    keyboard = []
    
    # Новая кнопка - ВЫБРАТЬ ВСЕ 6 РАДИОСТАНЦИЙ
    all_selected = len(selected_radios) == 6
    keyboard.append([InlineKeyboardButton(
        "✅ ВЫБРАТЬ ВСЕ 6 РАДИОСТАНЦИЙ" if all_selected else "⚪ ВЫБРАТЬ ВСЕ 6 РАДИОСТАНЦИЙ", 
        callback_data="select_all_radios"
    )])
    
    radio_stations = [
        ("LOVE RADIO", "radio_love", 540),
        ("АВТОРАДИО", "radio_auto", 3250),
        ("РАДИО ДАЧА", "radio_dacha", 3250), 
        ("РАДИО ШАНСОН", "radio_chanson", 2900),
        ("РЕТРО FM", "radio_retro", 3600),
        ("ЮМОР FM", "radio_humor", 1260)
    ]
    
    for name, callback, listeners in radio_stations:
        emoji = "✅" if name in selected_radios else "⚪"
        button_text = f"{emoji} {name} ({format_number(listeners)} ч/день)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])
        keyboard.append([InlineKeyboardButton("📖 Подробнее", callback_data=f"details_{callback}")])
    
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_campaign_dates")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"Выбор радиостанций\n\n"
        f"{'✅' if 'LOVE RADIO' in selected_radios else '⚪'} LOVE RADIO\n"
        f"👥 540 слушателей/день\n👩 Молодёжь 16-35 лет\n\n"
        f"{'✅' if 'АВТОРАДИО' in selected_radios else '⚪'} АВТОРАДИО\n"
        f"👥 3,250 слушателей/день\n👨 Автомобилисты 25-55 лет\n\n"
        f"{'✅' if 'РАДИО ДАЧА' in selected_radios else '⚪'} РАДИО ДАЧА\n"
        f"👥 3,250 слушателей/день\n👨👩 Семья 35-60 лет\n\n"
        f"{'✅' if 'РАДИО ШАНСОН' in selected_radios else '⚪'} РАДИО ШАНСОН\n"
        f"👥 2,900 слушателей/день\n👨 Мужчины 30-60+ лет\n\n"
        f"{'✅' if 'РЕТРО FM' in selected_radios else '⚪'} РЕТРО FM\n"
        f"👥 3,600 слушателей/день\n👴👵 Взрослые 35-65 лет\n\n"
        f"{'✅' if 'ЮМОР FM' in selected_radios else '⚪'} ЮМОР FM\n"
        f"👥 1,260 слушателей/день\n👦👧 Молодежь 12-19 и взрослые 25-45 лет\n\n"
        f"Выбрано: {len(selected_radios)} станции • {format_number(total_listeners)} слушателей\n"
        f"[ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return RADIO_SELECTION

async def handle_radio_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_main":
        return await start(update, context)
    
    elif query.data == "select_all_radios":
        # Выбираем все 6 радиостанций
        all_radios = ['LOVE RADIO', 'АВТОРАДИО', 'РАДИО ДАЧА', 'РАДИО ШАНСОН', 'РЕТРО FM', 'ЮМОР FM']
        context.user_data['selected_radios'] = all_radios
        return await radio_selection(update, context)
    
    elif query.data.startswith("details_"):
        station_data = {
            'details_radio_love': "LOVE RADIO - 540 слушателей/день\n• Молодёжь 16-35 лет\n• Охват снижен на 40-50% из-за возрастной структуры\n• Музыка: современные хиты",
            'details_radio_auto': "АВТОРАДИО - 3,250 слушателей/день\n• Автомобилисты 25-55 лет\n• Универсальный формат для широкой аудитории\n• Дорожные новости, пробки",
            'details_radio_dacha': "РАДИО ДАЧА - 3,250 слушателей/день\n• Семья 35-60 лет\n• Высокий охват среди пенсионеров\n• Семейные ценности, дачные советы",
            'details_radio_chanson': "РАДИО ШАНСОН - 2,900 слушателей/день\n• Мужчины 30-60+ лет\n• Популярно среди старшей аудитории\n• Музыка: шансон, авторская песня",
            'details_radio_retro': "РЕТРО FM - 3,600 слушателей/день\n• Взрослые 35-65 лет\n• Идеально подходит для возрастной структуры\n• Музыка: хиты 80-90-х годов",
            'details_radio_humor': "ЮМОР FM - 1,260 слушателей/день\n• Молодежь 12-19 и взрослые 25-45 лет\n• Стабильный охват\n• Юмористические программы"
        }
        
        station_info = station_data.get(query.data, "Информация о станции")
        keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_radio")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(station_info, reply_markup=reply_markup)
        return RADIO_SELECTION
    
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
    
    elif query.data == "to_campaign_dates":
        if not context.user_data.get('selected_radios'):
            await query.answer("❌ Выберите хотя бы одну радиостанцию!", show_alert=True)
            return RADIO_SELECTION
        return await campaign_dates(update, context)
    
    elif query.data == "back_to_radio":
        return await radio_selection(update, context)
    
    return RADIO_SELECTION

async def campaign_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    start_date = context.user_data.get('start_date')
    end_date = context.user_data.get('end_date')
    campaign_days = context.user_data.get('campaign_days', 0)
    
    selected_radios = context.user_data.get('selected_radios', [])
    stations_info = "📻 ВЫБРАНЫ СТАНЦИИ:\n"
    for radio in selected_radios:
        listeners = STATION_COVERAGE.get(radio, 0)
        stations_info += f"• {radio} ({format_number(listeners)} ч/день)\n"
    
    # Определяем текст кнопки в зависимости от состояния
    dates_button_text = "✅ ПЕРИОД ВЫБРАН" if start_date and end_date else "🗓️ ВЫБРАТЬ ПЕРИОД"
    
    keyboard = [
        [InlineKeyboardButton(dates_button_text, callback_data="select_period")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_radio")],
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_time_slots")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    dates_info = ""
    if start_date and end_date:
        dates_info = f"🗓️ Начало: {start_date} ✅\n🗓️ Окончание: {end_date} ✅\n"
    else:
        dates_info = "🗓️ Период не выбран\n"
    
    text = (
        f"📅 ВЫБЕРИТЕ ДАТЫ КАМПАНИИ\n\n"
        f"{stations_info}\n"
        f"{dates_info}\n"
        f"─────────────────\n"
        f"✅ Период: {campaign_days} дней\n"
        f"⚠️ Минимальный период: 15 дней\n\n"
        f"🎯 Старт кампании: в течение 3 дней после подтверждения"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return CAMPAIGN_DATES

async def handle_campaign_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_radio":
        return await radio_selection(update, context)
    
    elif query.data == "select_period":
        keyboard = [[InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_period")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📅 Введите дату начала кампании в формате ДД.ММ.ГГГГ:\n\n"
            "Пример: 15.12.2024\n\n"
            "Отправьте дату сообщением:",
            reply_markup=reply_markup
        )
        return "WAITING_START_DATE"
    
    elif query.data == "to_time_slots":
        if not context.user_data.get('start_date') or not context.user_data.get('end_date'):
            await query.answer("❌ Выберите период кампании!", show_alert=True)
            return CAMPAIGN_DATES
        
        campaign_days = context.user_data.get('campaign_days', 0)
        if campaign_days < 15:
            await query.answer("❌ Минимальный период кампании - 15 дней!", show_alert=True)
            return CAMPAIGN_DATES
            
        return await time_slots(update, context)
    
    elif query.data == "cancel_period":
        return await campaign_dates(update, context)
    
    return CAMPAIGN_DATES

async def process_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date_text = update.message.text.strip()
        start_date = datetime.strptime(date_text, '%d.%m.%Y')
        
        if start_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            await update.message.reply_text(
                "❌ Дата начала не может быть в прошлом. Введите корректную дату:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_period")]])
            )
            return "WAITING_START_DATE"
        
        context.user_data['start_date'] = date_text
        
        # Переходим к запросу даты окончания
        keyboard = [[InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_period")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📅 Введите дату окончания кампании в формате ДД.ММ.ГГГГ:\n\n"
            "Пример: 30.12.2024\n\n"
            "Отправьте дату сообщением:",
            reply_markup=reply_markup
        )
        return "WAITING_END_DATE"
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:\n\n"
            "Пример: 15.12.2024",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_period")]])
        )
        return "WAITING_START_DATE"

async def process_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date_text = update.message.text.strip()
        end_date = datetime.strptime(date_text, '%d.%m.%Y')
        
        if not context.user_data.get('start_date'):
            await update.message.reply_text(
                "❌ Сначала выберите дату начала. Введите дату окончания снова:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_period")]])
            )
            return "WAITING_END_DATE"
        
        start_date = datetime.strptime(context.user_data['start_date'], '%d.%m.%Y')
        
        if end_date <= start_date:
            await update.message.reply_text(
                "❌ Дата окончания должна быть после даты начала. Введите корректную дату:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_period")]])
            )
            return "WAITING_END_DATE"
        
        campaign_days = (end_date - start_date).days + 1
        
        if campaign_days < 15:
            await update.message.reply_text(
                "❌ Минимальный период кампании - 15 дней. Введите дату окончания снова:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_period")]])
            )
            return "WAITING_END_DATE"
        
        context.user_data['end_date'] = date_text
        context.user_data['campaign_days'] = campaign_days
        
        # Возвращаемся в меню дат с обновленной информацией
        return await campaign_dates_from_message(update, context)
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:\n\n"
            "Пример: 30.12.2024",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_period")]])
        )
        return "WAITING_END_DATE"

async def campaign_dates_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия campaign_dates для вызова из message handler"""
    start_date = context.user_data.get('start_date')
    end_date = context.user_data.get('end_date')
    campaign_days = context.user_data.get('campaign_days', 0)
    
    selected_radios = context.user_data.get('selected_radios', [])
    stations_info = "📻 ВЫБРАНЫ СТАНЦИИ:\n"
    for radio in selected_radios:
        listeners = STATION_COVERAGE.get(radio, 0)
        stations_info += f"• {radio} ({format_number(listeners)} ч/день)\n"
    
    dates_button_text = "✅ ПЕРИОД ВЫБРАН" if start_date and end_date else "🗓️ ВЫБРАТЬ ПЕРИОД"
    
    keyboard = [
        [InlineKeyboardButton(dates_button_text, callback_data="select_period")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_radio")],
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_time_slots")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    dates_info = ""
    if start_date and end_date:
        dates_info = f"🗓️ Начало: {start_date} ✅\n🗓️ Окончание: {end_date} ✅\n"
    else:
        dates_info = "🗓️ Период не выбран\n"
    
    text = (
        f"📅 ВЫБЕРИТЕ ДАТЫ КАМПАНИИ\n\n"
        f"{stations_info}\n"
        f"{dates_info}\n"
        f"─────────────────\n"
        f"✅ Период: {campaign_days} дней\n"
        f"⚠️ Минимальный период: 15 дней\n\n"
        f"🎯 Старт кампании: в течение 3 дней после подтверждения"
    )
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    return CAMPAIGN_DATES

async def time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_slots = context.user_data.get('selected_time_slots', [])
    selected_radios = context.user_data.get('selected_radios', [])
    campaign_days = context.user_data.get('campaign_days', 30)
    
    keyboard = []
    keyboard.append([InlineKeyboardButton("✅ ВЫБРАТЬ ВСЕ СЛОТЫ", callback_data="select_all_slots")])
    keyboard.append([InlineKeyboardButton("🌅 УТРЕННИЕ СЛОТЫ (+10%)", callback_data="header_morning")])
    
    for i in range(4):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "⚪"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    keyboard.append([InlineKeyboardButton("☀️ ДНЕВНЫЕ СЛОТЫ", callback_data="header_day")])
    for i in range(4, 10):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "⚪"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    keyboard.append([InlineKeyboardButton("🌇 ВЕЧЕРНИЕ СЛОТЫ (+10%)", callback_data="header_evening")])
    for i in range(10, 15):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "⚪"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_dates")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_branded_sections")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    total_slots = len(selected_slots)
    total_outputs_per_day = total_slots * len(selected_radios)
    total_outputs_period = total_outputs_per_day * campaign_days
    
    stations_text = "📻 ВЫБРАНЫ СТАНЦИИ:\n" + "\n".join([f"• {radio}" for radio in selected_radios])
    
    text = (
        f"Временные слоты\n\n"
        f"{stations_text}\n"
        f"📅 ПЕРИОД: {context.user_data.get('start_date')} - {context.user_data.get('end_date')} ({campaign_days} дней)\n\n"
        f"🕒 ВЫБЕРИТЕ ВРЕМЯ ВЫХОДА РОЛИКОВ\n\n"
        f"📊 Статистика выбора:\n"
        f"• Выбрано слots: {total_slots}\n"
        f"• Выходов в день на всех радио: {total_outputs_per_day}\n"
        f"• Всего выходов за период: {format_number(total_outputs_period)}\n\n"
        f"🎯 Выберите подходящие временные интервалы\n"
        f"[ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return TIME_SLOTS

async def handle_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_dates":
        return await campaign_dates(update, context)
    
    elif query.data == "select_all_slots":
        context.user_data['selected_time_slots'] = list(range(15))
        return await time_slots(update, context)
    
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

async def branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_branded = context.user_data.get('branded_section')
    
    keyboard = [
        [InlineKeyboardButton("✅ АВТОРУБРИКИ" if selected_branded == 'auto' else "⚪ АВТОРУБРИКИ", callback_data="branded_auto")],
        [InlineKeyboardButton("✅ НЕДВИЖИМОСТЬ" if selected_branded == 'realty' else "⚪ НЕДВИЖИМОСТЬ", callback_data="branded_realty")],
        [InlineKeyboardButton("✅ МЕДИЦИНСКИЕ" if selected_branded == 'medical' else "⚪ МЕДИЦИНСКИЕ", callback_data="branded_medical")],
        [InlineKeyboardButton("✅ ИНДИВИДУАЛЬНАЯ" if selected_branded == 'custom' else "⚪ ИНДИВИДУАЛЬНАЯ", callback_data="branded_custom")],
        [InlineKeyboardButton("📋 Посмотреть пример", callback_data="show_example")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_time")],
        [InlineKeyboardButton("⏩ ПРОПУСТИТЬ", callback_data="skip_branded")],
        [InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_campaign_creator")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "Брендированные рубрики\n\n"
        "🎙️ ВЫБЕРИТЕ ТИП РУБРИКИ:\n\n"
        f"{'✅' if selected_branded == 'auto' else '⚪'} АВТОРУБРИКИ\n"
        "Готовые сценарии для автосалонов\n"
        "\"30 секунд о китайских автомобилях\"\n"
        "\"30 секунд об АвтоВАЗе\"\n"
        "+20% к стоимости кампании\n\n"
        f"{'✅' if selected_branded == 'realty' else '⚪'} НЕДВИЖИМОСТЬ\n"
        "Рубрики для агентств недвижимости\n"
        "\"Совет по недвижимости\"\n"
        "\"Полезно знать при покупке квартиры\"\n"
        "+15% к стоимости кампании\n\n"
        f"{'✅' if selected_branded == 'medical' else '⚪'} МЕДИЦИНСКИЕ РУБРИКИ\n"
        "Экспертные форматы для клиник\n"
        "\"Здоровое серде\"\n"
        "\"Совет врача\"\n"
        "+25% к стоимости кампании\n\n"
        f"{'✅' if selected_branded == 'custom' else '⚪'} ИНДИВИДУАЛЬНАЯ РУБРИКА\n"
        "Разработка под ваш бизнес\n"
        "Уникальный контент и сценарий\n"
        "+30% к стоимости кампании"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return BRANDED_SECTIONS

async def handle_branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_time":
        return await time_slots(update, context)
    
    elif query.data == "show_example":
        example_text = (
            "Рубрики «30 секунд об АвтоВАЗе» \n"
            "Готовый комплект рубрик для АвтоВАЗа (понедельник–воскресенье). \n\n"
            "Понедельник — Интересный факт\n"
            "ВАЗ-2106, знаменитая «шестёрка», стала одной из самых массовых моделей АвтоВАЗа. За 30 лет выпуска было произведено более 4 миллионов автомобилей — рекорд для отечественного автопрома!\n\n"
            "Вторник — Интересный факт\n"
            "LADA Kalina, появившаяся в 2004 году, стала первой моделью АвтоВАЗа, оснащённой системой ABS и подушками безопасности. Именно с неё начался новый этап в развитии безопасности российских автомобилей.\n\n"
            "Среда — Интересный факт\n"
            "LADA Priora долгое время была выбором молодых водителей. За время выпуска с 2007 по 2018 год с конвейера сошло более 1 миллиона машин, а многие до сих пор на дорогах.\n\n"
            "Четверг — Интересный факт\n"
            "В 2018 году АвтоВАЗ начал экспорт LADA Vesta и LADA Largus в Европу. Эти модели хорошо зарекомендовали себя благодаря надёжности и доступной цене.\n\n"
            "Пятница — Интересный факт\n"
            "На заводе АвтоВАЗа в Тольятти работает более 30 тысяч сотрудников. Это один из крупнейших работодателей Самарской области, а сам завод называют «городом в городе».\n\n"
            "Суббота — Интересный факт\n"
            "LADA Niva не раз участвовала в ралли «Париж — Дакар». В 1980-х эта модель удивляла мир своей проходимостью и выносливостью, соревнуясь с лучшими внедорожниками мира.\n\n"
            "Воскресенье — Интересный факт\n"
            "В 2021 году LADA стала маркой №1 на российском рынке: её доля составила более 20% всех проданных автомобилей в стране. Это подтверждает доверие миллионов водителей."
        )
        
        keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_branded")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(example_text, reply_markup=reply_markup)
        return BRANDED_SECTIONS
    
    elif query.data == "back_to_branded":
        return await branded_sections(update, context)
    
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

async def campaign_creator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    base_price, discount, final_price, total_reach, daily_coverage, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
    context.user_data['base_price'] = base_price
    context.user_data['discount'] = discount
    context.user_data['final_price'] = final_price
    
    provide_own = context.user_data.get('provide_own_audio', False)
    campaign_text = context.user_data.get('campaign_text', '')
    char_count = len(campaign_text) if campaign_text else 0
    
    keyboard = []
    
    if provide_own:
        keyboard.append([InlineKeyboardButton("⏱️ Указать хронометраж", callback_data="enter_duration")])
        keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
    else:
        keyboard.append([InlineKeyboardButton("📝 ВВЕСТИ ТЕКСТ РОЛИКА", callback_data="enter_text")])
        keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
    
    keyboard.append([InlineKeyboardButton("⏩ ПРОПУСТИТЬ", callback_data="skip_text")])
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_branded")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_production_option")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "Конструктор ролика\n\n"
        "📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n\n"
        f"{campaign_text if campaign_text else '[Ваш текст появится здесь]'}\n\n"
        f"○ {char_count} знаков из 500\n\n"
        f"⏱️ Длительность ролика: {context.user_data.get('duration', 20)} секунд\n"
        f"📊 Выходов в день: {spots_per_day}\n\n"
        f"💰 Предварительная стоимость:\n"
        f"   Базовая: {format_number(base_price)}₽\n"
        f"   Скидка 50%: -{format_number(discount)}₽\n"
        f"   Итоговая: {format_number(final_price)}₽\n\n"
        f"📊 Примерный охват кампании:\n"
        f"   ~{format_number(total_reach)} человек за период\n\n"
        f"{'✅' if provide_own else '⚪'} Пришлю свой ролик"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return CAMPAIGN_CREATOR

async def enter_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_creator")],
        [InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_text")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📝 Введите текст для радиоролика (до 500 знаков):\n\n"
        "Пример:\n"
        "\"Автомобили в Тюмени! Новые модели в наличии. Выгодный трейд-ин и кредит 0%. "
        "Тест-драйв в день обращения!\"\n\n"
        "Отправьте текст сообщением:",
        reply_markup=reply_markup
    )
    
    return "WAITING_TEXT"

async def process_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        if len(text) > 500:
            await update.message.reply_text(
                "❌ Текст превышает 500 знаков. Сократите текст и отправьте снова:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_text")]
                ])
            )
            return "WAITING_TEXT"
        
        context.user_data['campaign_text'] = text
        context.user_data['provide_own_audio'] = False
        
        # Возвращаемся в конструктор ролика с обновленным текстом
        return await campaign_creator_from_message(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка в process_campaign_text: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте еще раз: /start")
        return ConversationHandler.END

async def campaign_creator_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия campaign_creator для вызова из message handler"""
    base_price, discount, final_price, total_reach, daily_coverage, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
    context.user_data['base_price'] = base_price
    context.user_data['discount'] = discount
    context.user_data['final_price'] = final_price
    
    provide_own = context.user_data.get('provide_own_audio', False)
    campaign_text = context.user_data.get('campaign_text', '')
    char_count = len(campaign_text) if campaign_text else 0
    
    keyboard = []
    
    if provide_own:
        keyboard.append([InlineKeyboardButton("⏱️ Указать хронометраж", callback_data="enter_duration")])
        keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
    else:
        keyboard.append([InlineKeyboardButton("📝 ВВЕСТИ ТЕКСТ РОЛИКА", callback_data="enter_text")])
        keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
    
    keyboard.append([InlineKeyboardButton("⏩ ПРОПУСТИТЬ", callback_data="skip_text")])
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_branded")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_production_option")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "Конструктор ролика\n\n"
        "📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n\n"
        f"{campaign_text if campaign_text else '[Ваш текст появится здесь]'}\n\n"
        f"○ {char_count} знаков из 500\n\n"
        f"⏱️ Длительность ролика: {context.user_data.get('duration', 20)} секунд\n"
        f"📊 Выходов в день: {spots_per_day}\n\n"
        f"💰 Предварительная стоимость:\n"
        f"   Базовая: {format_number(base_price)}₽\n"
        f"   Скидка 50%: -{format_number(discount)}₽\n"
        f"   Итоговая: {format_number(final_price)}₽\n\n"
        f"📊 Примерный охват кампании:\n"
        f"   ~{format_number(total_reach)} человек за период\n\n"
        f"{'✅' if provide_own else '⚪'} Пришлю свой ролик"
    )
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    return CAMPAIGN_CREATOR

async def enter_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_creator")],
        [InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_duration")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⏱️ Введите длительность ролика в секундах (10-30):\n\n"
        "Рекомендуем:\n"
        "• 15 секунд - краткое сообщение\n"
        "• 20 секунд - стандартный ролик\n"
        "• 30 секунд - подробное описание\n\n"
        "Отправьте число от 10 до 30:",
        reply_markup=reply_markup
    )
    
    return "WAITING_DURATION"

async def process_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        duration_text = update.message.text.strip()
        duration = int(duration_text)
        
        if duration < 10 or duration > 30:
            await update.message.reply_text(
                "❌ Длительность должна быть от 10 до 30 секунд. Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_duration")]
                ])
            )
            return "WAITING_DURATION"
        
        context.user_data['duration'] = duration
        
        # Возвращаемся в конструктор ролика с обновленным хронометражом
        return await campaign_creator_from_message(update, context)
        
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите число от 10 до 30:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_duration")]
            ])
        )
        return "WAITING_DURATION"

async def production_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if hasattr(update, 'callback_query') else None
    
    if query:
        await query.answer()
    
    # Если клиент выбрал "Пришлю свой ролик", автоматически выбираем готовый ролик
    if context.user_data.get('provide_own_audio'):
        context.user_data['production_option'] = 'ready'
        context.user_data['production_cost'] = 0
    
    selected_production = context.user_data.get('production_option')
    campaign_text = context.user_data.get('campaign_text', '')
    
    # Автоматический расчет хронометража по тексту, если не указан
    if not context.user_data.get('duration'):
        char_count = len(campaign_text)
        if char_count <= 75:
            estimated_duration = 15
        elif char_count <= 100:
            estimated_duration = 20
        else:
            estimated_duration = 30
        context.user_data['duration'] = estimated_duration
    
    keyboard = []
    
    # Если выбран "свой ролик", показываем только готовый вариант
    if context.user_data.get('provide_own_audio'):
        keyboard.append([
            InlineKeyboardButton(
                f"✅ {PRODUCTION_OPTIONS['ready']['name']}", 
                callback_data="production_ready"
            )
        ])
    else:
        for key, option in PRODUCTION_OPTIONS.items():
            is_selected = "✅" if selected_production == key else "⚪"
            keyboard.append([
                InlineKeyboardButton(
                    f"{is_selected} {option['name']} - от {format_number(option['price'])}₽", 
                    callback_data=f"production_{key}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_creator")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_contact_info")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "Производство ролика\n\n"
        f"📝 ВАШ ТЕКСТ:\n\"{campaign_text[:100]}{'...' if len(campaign_text) > 100 else ''}\"\n\n"
        f"⏱️ Длительность: {context.user_data.get('duration', 20)} секунд\n\n"
        "🎙️ ВЫБЕРИТЕ ВАРИАНТ РОЛИКА:\n\n"
    )
    
    if context.user_data.get('provide_own_audio'):
        text += "✅ ГОТОВЫЙ РОЛИК\n• Вы пришлете свой ролик файлом\n"
    else:
        text += (
            "⚪ СТАНДАРТНЫЙ РОЛИК - от 2,000₽\n"
            "• Профессиональная озвучка\n• Музыкальное оформление\n• 2 правки\n• Срок: 2-3 дня\n\n"
            "⚪ ПРЕМИУМ РОЛИК - от 4,000₽\n"
            "• Озвучка 2-мя голосами\n• Индивидуальная музыка\n• 5 правок\n• Срочное производство 1 день\n\n"
            "⚪ ГОТОВЫЙ РОЛИК\n"
            "• У меня есть свой ролик\n"
        )
    
    text += "\n💰 Влияние на итоговую стоимость"
    
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    return PRODUCTION_OPTION

async def handle_production_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_creator":
        return await campaign_creator(update, context)
    
    elif query.data.startswith("production_"):
        production_key = query.data.replace("production_", "")
        if production_key in PRODUCTION_OPTIONS:
            context.user_data['production_option'] = production_key
            context.user_data['production_cost'] = PRODUCTION_OPTIONS[production_key]['price']
            return await production_option(update, context)
    
    elif query.data == "to_contact_info":
        if not context.user_data.get('production_option'):
            await query.answer("❌ Выберите вариант производства ролика!", show_alert=True)
            return PRODUCTION_OPTION
        return await contact_info(update, context)
    
    return PRODUCTION_OPTION

async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    base_price, discount, final_price, total_reach, daily_coverage, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
    
    keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_production")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"Контактные данные\n\n"
        f"💰 Стоимость кампании:\n"
        f"   Базовая: {format_number(base_price)}₽\n"
        f"   Скидка 50%: -{format_number(discount)}₽\n"
        f"   Итоговая: {format_number(final_price)}₽\n\n"
        f"📊 Примерный охват: ~{format_number(total_reach)} человек за период\n\n"
        f"─────────────────\n"
        f"📝 ВВЕДИТЕ ВАШЕ ИМЯ\n"
        f"─────────────────\n"
        f"(нажмите Enter для отправки)"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return CONTACT_INFO

async def process_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        
        if 'contact_name' not in context.user_data:
            context.user_data['contact_name'] = text
            await update.message.reply_text(
                "📞 Введите ваш телефон:\n\n"
                "Формат: +79XXXXXXXXX\n"
                "Пример: +79123456789\n\n"
                "❌ ОТМЕНА - /cancel"
            )
            return CONTACT_INFO
        
        elif 'phone' not in context.user_data:
            if not validate_phone(text):
                await update.message.reply_text(
                    "❌ Неверный формат телефона. Используйте формат: +79XXXXXXXXX\n\n"
                    "Пример: +79123456789\n\n"
                    "❌ ОТМЕНА - /cancel"
                )
                return CONTACT_INFO
            context.user_data['phone'] = text
            await update.message.reply_text("📧 Введите ваш email:\n\n❌ ОТМЕНА - /cancel")
            return CONTACT_INFO
        
        elif 'email' not in context.user_data:
            context.user_data['email'] = text
            await update.message.reply_text("🏢 Введите название компании:\n\n❌ ОТМЕНА - /cancel")
            return CONTACT_INFO
        
        elif 'company' not in context.user_data:
            context.user_data['company'] = text
            return await show_confirmation_from_message(update, context)
            
    except Exception as e:
        logger.error(f"Ошибка в process_contact_info: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Пожалуйста, начните заново: /start"
        )
        return ConversationHandler.END

async def show_confirmation_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Версия show_confirmation для вызова из message handler"""
    base_price, discount, final_price, total_reach, daily_coverage, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
    
    stations_text = ""
    for radio in context.user_data.get('selected_radios', []):
        listeners = STATION_COVERAGE.get(radio, 0)
        stations_text += f"• {radio}: {format_number(listeners)}/день\n"
    
    slots_text = ""
    for slot_index in context.user_data.get('selected_time_slots', []):
        if 0 <= slot_index < len(TIME_SLOTS_DATA):
            slot = TIME_SLOTS_DATA[slot_index]
            premium = "✅" if slot['premium'] else "❌"
            slots_text += f"• {slot['time']} - {slot['label']} (Премиум: {premium})\n"
    
    confirmation_text = f"""
📋 ПОДТВЕРЖДЕНИЕ ЗАЯВКИ

👤 ВАШИ ДАННЫЕ:
Имя: {context.user_data.get('contact_name', 'Не указано')}
Телефон: {context.user_data.get('phone', 'Не указан')}
Email: {context.user_data.get('email', 'Не указан')}
Компания: {context.user_data.get('company', 'Не указана')}

📊 ПАРАМЕТРЫ КАМПАНИИ:

📻 РАДИОСТАНЦИИ:
{stations_text}
📅 ПЕРИОД: {context.user_data.get('start_date')} - {context.user_data.get('end_date')} ({context.user_data.get('campaign_days')} дней)
🕒 ВЫБРАНО СЛОТОВ: {len(context.user_data.get('selected_time_slots', []))}
{slots_text}
🎙️ РУБРИКА: {get_branded_section_name(context.user_data.get('branded_section'))}
⏱️ РОЛИК: {PRODUCTION_OPTIONS.get(context.user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}
📏 ХРОНОМЕТРАЖ: {context.user_data.get('duration', 20)} сек

🎯 РАСЧЕТНЫЙ ОХВАТ (по выбранным спотам):
• Выходов в день: {spots_per_day}
• Всего выходов: {spots_per_day * context.user_data.get('campaign_days', 30)}
• Ежедневно: ~{format_number(daily_coverage)} чел.
• За период: ~{format_number(total_reach)} чел.

💰 СТОИМОСТЬ:
Базовая: {format_number(base_price)}₽
Скидка 50%: -{format_number(discount)}₽
Итоговая: {format_number(final_price)}₽
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 ОТПРАВИТЬ ЗАЯВКУ", callback_data="submit_campaign")],
        [InlineKeyboardButton("◀️ ВЕРНУТЬСЯ К ВЫБОРУ РАДИО", callback_data="back_to_radio_from_confirmation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
    return CONFIRMATION

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    base_price, discount, final_price, total_reach, daily_coverage, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
    
    stations_text = ""
    for radio in context.user_data.get('selected_radios', []):
        listeners = STATION_COVERAGE.get(radio, 0)
        stations_text += f"• {radio}: {format_number(listeners)}/день\n"
    
    slots_text = ""
    for slot_index in context.user_data.get('selected_time_slots', []):
        if 0 <= slot_index < len(TIME_SLOTS_DATA):
            slot = TIME_SLOTS_DATA[slot_index]
            premium = "✅" if slot['premium'] else "❌"
            slots_text += f"• {slot['time']} - {slot['label']} (Премиум: {premium})\n"
    
    confirmation_text = f"""
📋 ПОДТВЕРЖДЕНИЕ ЗАЯВКИ

👤 ВАШИ ДАННЫЕ:
Имя: {context.user_data.get('contact_name', 'Не указано')}
Телефон: {context.user_data.get('phone', 'Не указан')}
Email: {context.user_data.get('email', 'Не указан')}
Компания: {context.user_data.get('company', 'Не указана')}

📊 ПАРАМЕТРЫ КАМПАНИИ:

📻 РАДИОСТАНЦИИ:
{stations_text}
📅 ПЕРИОД: {context.user_data.get('start_date')} - {context.user_data.get('end_date')} ({context.user_data.get('campaign_days')} дней)
🕒 ВЫБРАНО СЛОТОВ: {len(context.user_data.get('selected_time_slots', []))}
{slots_text}
🎙️ РУБРИКА: {get_branded_section_name(context.user_data.get('branded_section'))}
⏱️ РОЛИК: {PRODUCTION_OPTIONS.get(context.user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}
📏 ХРОНОМЕТРАЖ: {context.user_data.get('duration', 20)} сек

🎯 РАСЧЕТНЫЙ ОХВАТ (по выбранным спотам):
• Выходов в день: {spots_per_day}
• Всего выходов: {spots_per_day * context.user_data.get('campaign_days', 30)}
• Ежедневно: ~{format_number(daily_coverage)} чел.
• За период: ~{format_number(total_reach)} чел.

💰 СТОИМОСТЬ:
Базовая: {format_number(base_price)}₽
Скидка 50%: -{format_number(discount)}₽
Итоговая: {format_number(final_price)}₽
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 ОТПРАВИТЬ ЗАЯВКУ", callback_data="submit_campaign")],
        [InlineKeyboardButton("◀️ ВЕРНУТЬСЯ К ВЫБОРУ РАДИО", callback_data="back_to_radio_from_confirmation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(confirmation_text, reply_markup=reply_markup)
    return CONFIRMATION

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_radio_from_confirmation":
        return await radio_selection(update, context)
    
    elif query.data == "submit_campaign":
        try:
            base_price, discount, final_price, total_reach, daily_coverage, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
            
            campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
            conn = sqlite3.connect('campaigns.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO campaigns 
                (user_id, campaign_number, radio_stations, start_date, end_date, campaign_days,
                 time_slots, branded_section, campaign_text, production_option, contact_name,
                 company, phone, email, duration, base_price, discount, final_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                query.from_user.id,
                campaign_number,
                ','.join(context.user_data.get('selected_radios', [])),
                context.user_data.get('start_date'),
                context.user_data.get('end_date'),
                context.user_data.get('campaign_days'),
                ','.join(map(str, context.user_data.get('selected_time_slots', []))),
                context.user_data.get('branded_section', ''),
                context.user_data.get('campaign_text', ''),
                context.user_data.get('production_option', ''),
                context.user_data.get('contact_name', ''),
                context.user_data.get('company', ''),
                context.user_data.get('phone', ''),
                context.user_data.get('email', ''),
                context.user_data.get('duration', 20),
                base_price,
                discount,
                final_price
            ))
            
            conn.commit()
            conn.close()
            
            await send_admin_notification(context, context.user_data, campaign_number)
            
            success_text = f"""
✅ ЗАЯВКА ПРИНЯТА!

Спасибо за доверие! 😊
Наш менеджер свяжется с вами в ближайшее время.

📋 № заявки: {campaign_number}
📅 Старт: в течение 3 дней
💰 Сумма со скидкой 50%: {format_number(final_price)}₽
📊 Примерный охват: ~{format_number(total_reach)} человек за период

Выберите дальнейшее действие:
"""
            
            keyboard = [
                [InlineKeyboardButton("📊 СФОРМИРОВАТЬ EXCEL МЕДИАПЛАН", callback_data="generate_excel")],
                [InlineKeyboardButton("📋 ЛИЧНЫЙ КАБИНЕТ", callback_data="personal_cabinet")],
                [InlineKeyboardButton("🚀 НОВЫЙ ЗАКАЗ", callback_data="new_order")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(success_text, reply_markup=reply_markup)
            return FINAL_ACTIONS
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении заявки: {e}")
            await query.message.reply_text(
                "❌ Произошла ошибка при сохранении заявки.\n"
                "Пожалуйста, начните заново: /start\n"
                "Или свяжитесь с поддержкой: t.me/AlexeyKhlistunov"
            )
            return ConversationHandler.END
    
    return CONFIRMATION

async def handle_final_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "generate_excel":
            # Находим последнюю кампанию пользователя
            user_id = query.from_user.id
            conn = sqlite3.connect('campaigns.db')
            cursor = conn.cursor()
            cursor.execute('SELECT campaign_number FROM campaigns WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (user_id,))
            campaign_data = cursor.fetchone()
            conn.close()
            
            if campaign_data:
                campaign_number = campaign_data[0]
                try:
                    excel_buffer = create_excel_file_from_db(campaign_number)
                    if excel_buffer:
                        await query.message.reply_document(
                            document=excel_buffer,
                            filename=f"mediaplan_{campaign_number}.xlsx",
                            caption=f"📊 Ваш медиаплан кампании #{campaign_number}"
                        )
                    else:
                        await query.message.reply_text("❌ Ошибка при создании Excel. Попробуйте еще раз.")
                except Exception as e:
                    logger.error(f"Ошибка Excel: {e}")
                    await query.message.reply_text("❌ Ошибка при создании Excel. Попробуйте еще раз.")
            else:
                await query.message.reply_text("❌ Не найдено данных о кампании.")
            return FINAL_ACTIONS
        
        elif query.data == "personal_cabinet":
            return await personal_cabinet(update, context)
        
        elif query.data == "new_order":
            context.user_data.clear()
            await query.message.reply_text("🚀 Начинаем новую кампанию!")
            return await radio_selection(update, context)
        
        return FINAL_ACTIONS
        
    except Exception as e:
        logger.error(f"Ошибка в handle_final_actions: {e}")
        await query.message.reply_text("❌ Ошибка. Начните заново: /start")
        return ConversationHandler.END

async def personal_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    conn = sqlite3.connect('campaigns.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT campaign_number, status, final_price, created_at FROM campaigns WHERE user_id = ? ORDER BY created_at DESC LIMIT 5', (user_id,))
    orders = cursor.fetchall()
    conn.close()
    
    if orders:
        orders_text = "📋 ПОСЛЕДНИЕ ЗАКАЗЫ:\n\n"
        for order in orders:
            orders_text += f"📋 {order[0]} | {order[1]} | {format_number(order[2])}₽ | {order[3][:10]}\n"
    else:
        orders_text = "📋 У вас пока нет заказов"
    
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_final")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 ЛИЧНЫЙ КАБИНЕТ\n\n"
        f"{orders_text}\n\n"
        f"Здесь отображается история ваших заказов",
        reply_markup=reply_markup
    )
    return FINAL_ACTIONS

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Возрастная структура населения Ялуторовска и Заводоуковска существенно корректирует предполагаемый охват радиостанций — в сторону снижения для молодёжных форматов и роста для «взрослых». \n\n"
        "1. Возрастная структура (ключевые факты)\n"
        "• Ялуторовск: по данным Тюменьстата, заметно выше доля жителей 65+ лет (6 969 человек) по сравнению с Заводоуковском (4 655 человек).\n"
        "• Заводоуковск: считается одним из самых «молодых» городов региона, но всё же старше Тюмени (где средний возраст — 38,1 года) .\n"
        "• Общий тренд: в малых городах Тюменской области средний возраст выше, чем в Тюмени, за счёт:\n"
        "o оттока молодёжи в областной центр;\n"
        "o более высокой доли пенсионеров;\n"
        "o низкой рождаемости.\n\n"
        "2. Как это влияет на радиоохват\n"
        "Каждая станция имеет ядро целевой аудитории по возрасту. В «постаревших» городах:\n"
        "• падает охват станций с молодёжной аудиторией;\n"
        "• растёт охват станций, ориентированных на 35+.\n\n"
        "по станциям:\n\n"
        "1. Love Radio (ядро: 16–35 лет)\n"
        "o В Тюмени/крупных городах: высокий охват за счёт студентов и молодых специалистов.\n"
        "o В Ялуторовске/Заводоуковске: охват снижается на 40–50 % из за меньшей доли молодёжи.\n"
        " Базовый охват = 480–600 чел./день.\n\n"
        "2. Юмор FM (ядро: 12–19 и 25–45 лет)\n"
        "o Потеря молодёжного сегмента (12–19 лет) снижает охват на 20–30 %.\n"
        "o Базовый охват = 1 120–1 400 чел./день \n\n"
        "3. Авторадио (25–55 лет)\n"
        "o Ядро совпадает с наиболее многочисленной возрастной группой в малых городаы.\n"
        "o Базовый охват = 2 900–3 600 чел./день \n\n"
        "4. Ретро FM (35–65 лет)\n"
        "o Идеально попадает в возрастную структуру: высокая доля 45–65-летних.\n"
        "o Базовый охват = 3 200–4 000 чел./день \n\n"
        "5. Радио Дача (35–60 лет)\n"
        "o Сильный охват за счёт семейной аудитории и пенсионеров.\n"
        "o Базовый охват = 2 900–3 600 чел./день\n\n"
        "6. Радио Шансон (30–60+ лет)\n"
        "o Высокая популярность среди мужчин 45+ и пенсионеров.\n"
        "o Базовый охват = 2 600–3 200 чел./день \n\n"
        "3. Итоговый свод с учётом возраста\n"
        "Радиостанция	Охват (чел./день)\n"
        "Love Radio	480–600\n"
        "Юмор FM	1 120–1 400\n"
        "Авторадио	2 900–3 600\n"
        "Ретро FM	3 200–4 000\n"
        "Радио Дача	2 900–3 600\n"
        "Радио Шансон	2 600–3 200\n\n"
        "4. Ключевые выводы\n"
        "1. Самые эффективные станции для Ялуторовска/Заводоуковска:\n"
        "o Ретро FM, Радио Дача, Радио Шансон — их охват выше среднего за счёт совпадения с возрастной структуры.\n"
        "o Авторадио — стабильно высокий охват благодаря универсальности.\n"
        "2. Слабые форматы:\n"
        "o Love Radio — низкий охват из за дефицита молодёжи.\n"
        "o Юмор FM — теряет часть аудитории, но остаётся релевантным для 25–45 лет.\n"
        "3. Рекомендации для рекламы:\n"
        "o Для товаров/услуг для пенсионеров: Ретро FM, Радио Дача.\n"
        "o Для мужского сегмента 40+: Радио Шансон.\n"
        "o Для широкой аудитории: Авторадио.\n"
        "o Для молодёжи 18–30 лет: Love Radio \n\n"
        "5. Важные оговорки\n"
        "• Данные приближённые: точные метрики требуют локальных замеров.\n"
        "• Сезонность: летом охват может расти за счёт приезжих и автовладельцев.",
        reply_markup=reply_markup
    )
    return MAIN_MENU

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📍 Ялуторовск • Заводоуковск\n\n"
        "ℹ️ О НАС\n\n"
        "✅ Опыт работы на местном рынке: 10 лет\n\n"
        "📻 ВЕЩАЕМ НА 6 РАДИОСТАНЦИЯХ:\n"
        "• LOVE RADIO\n"
        "• АВТОРАДИО\n"
        "• РАДИО ДАЧА\n"
        "• РАДИО ШАНСОН\n"
        "• РЕТРО FM\n"
        "• ЮМОР FM\n\n"
        "Ведущий радиовещатель в регионе\n"
        "Охватываем 52% радиорынка\n\n"
        "Юридическая информация:\n"
        "Индивидуальный предприниматель\n"
        "Хлыстунов Алексей Александрович\n"
        "ОГРНИП 315723200067362\n\n"
        "📧 a.khlistunov@gmail.com\n"
        "📱 Telegram: t.me/AlexeyKhlistunov",
        reply_markup=reply_markup
    )
    return MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "create_campaign":
        context.user_data.clear()
        return await radio_selection(update, context)
    
    elif query.data == "statistics":
        return await statistics(update, context)
    
    elif query.data == "my_orders":
        return await personal_cabinet(update, context)
    
    elif query.data == "about":
        return await about(update, context)
    
    # ОБРАБОТКА АДМИНСКИХ КНОПОК EXCEL
    elif query.data.startswith("generate_excel_"):
        campaign_number = query.data.replace("generate_excel_", "")
        try:
            success = await send_excel_file_to_admin(context, campaign_number)
            if success:
                await query.answer("✅ Excel отправлен вам в личные сообщения")
            else:
                await query.answer("❌ Ошибка при создании Excel")
        except Exception as e:
            await query.answer(f"❌ Ошибка: {e}")
    
    elif query.data.startswith("call_"):
        phone = query.data.replace("call_", "")
        await query.answer(f"📞 Наберите: {phone}")
    
    elif query.data.startswith("email_"):
        email = query.data.replace("email_", "")
        await query.answer(f"✉️ Email: {email}")
    
    # НАВИГАЦИЯ
    elif query.data == "back_to_main":
        return await start(update, context)
    
    elif query.data == "back_to_radio":
        return await radio_selection(update, context)
    
    elif query.data == "back_to_radio_from_confirmation":
        return await radio_selection(update, context)
    
    elif query.data == "back_to_dates":
        return await campaign_dates(update, context)
    
    elif query.data == "back_to_time":
        return await time_slots(update, context)
    
    elif query.data == "back_to_branded":
        return await branded_sections(update, context)
    
    elif query.data == "back_to_creator":
        return await campaign_creator(update, context)
    
    elif query.data == "back_to_production":
        return await production_option(update, context)
    
    elif query.data == "back_to_final":
        keyboard = [
            [InlineKeyboardButton("📊 СФОРМИРОВАТЬ EXCEL МЕДИАПЛАН", callback_data="generate_excel")],
            [InlineKeyboardButton("📋 ЛИЧНЫЙ КАБИНЕТ", callback_data="personal_cabinet")],
            [InlineKeyboardButton("🚀 НОВЫЙ ЗАКАЗ", callback_data="new_order")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите дальнейшее действие:",
            reply_markup=reply_markup
        )
        return FINAL_ACTIONS
    
    elif query.data == "skip_text":
        context.user_data['campaign_text'] = ''
        return await production_option(update, context)
    
    elif query.data == "cancel_text":
        return await campaign_creator(update, context)
    
    elif query.data == "cancel_duration":
        return await campaign_creator(update, context)
    
    elif query.data == "cancel_period":
        return await campaign_dates(update, context)
    
    elif query.data == "provide_own_audio":
        current_state = context.user_data.get('provide_own_audio', False)
        context.user_data['provide_own_audio'] = not current_state
        return await campaign_creator(update, context)
    
    elif query.data == "to_production_option":
        return await production_option(update, context)
    
    elif query.data == "enter_duration":
        return await enter_duration(update, context)
    
    elif query.data == "enter_text":
        return await enter_campaign_text(update, context)
    
    elif query.data == "submit_campaign":
        return await handle_confirmation(update, context)
    
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Операция отменена.\n\n"
        "Для начала новой кампании используйте /start"
    )
    return ConversationHandler.END

def main():
    if init_db():
        logger.info("Бот запущен успешно")
    else:
        logger.error("Ошибка инициализации БД")
    
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(handle_main_menu, pattern='^.*$')
            ],
            RADIO_SELECTION: [
                CallbackQueryHandler(handle_radio_selection, pattern='^.*$')
            ],
            CAMPAIGN_DATES: [
                CallbackQueryHandler(handle_campaign_dates, pattern='^.*$')
            ],
            "WAITING_START_DATE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_start_date),
                CallbackQueryHandler(handle_main_menu, pattern='^cancel_period$')
            ],
            "WAITING_END_DATE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_end_date),
                CallbackQueryHandler(handle_main_menu, pattern='^cancel_period$')
            ],
            TIME_SLOTS: [
                CallbackQueryHandler(handle_time_slots, pattern='^.*$')
            ],
            BRANDED_SECTIONS: [
                CallbackQueryHandler(handle_branded_sections, pattern='^.*$')
            ],
            CAMPAIGN_CREATOR: [
                CallbackQueryHandler(handle_main_menu, pattern='^(back_to_|skip_text|cancel_text|to_production_option|provide_own_audio|enter_text|enter_duration)'),
                CallbackQueryHandler(enter_campaign_text, pattern='^enter_text$'),
                CallbackQueryHandler(enter_duration, pattern='^enter_duration$')
            ],
            "WAITING_TEXT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_campaign_text),
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_creator$'),
                CallbackQueryHandler(handle_main_menu, pattern='^cancel_text$')
            ],
            "WAITING_DURATION": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_duration),
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_creator$'),
                CallbackQueryHandler(handle_main_menu, pattern='^cancel_duration$')
            ],
            PRODUCTION_OPTION: [
                CallbackQueryHandler(handle_production_option, pattern='^.*$')
            ],
            CONTACT_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_contact_info),
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_production$'),
                CommandHandler('cancel', cancel)
            ],
            CONFIRMATION: [
                CallbackQueryHandler(handle_confirmation, pattern='^.*$')
            ],
            FINAL_ACTIONS: [
                CallbackQueryHandler(handle_final_actions, pattern='^.*$')
            ]
        },
        fallbacks=[CommandHandler('start', start), CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(
        handle_main_menu, 
        pattern='^(generate_excel_|get_excel_|call_|email_)'
    ))
    
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
