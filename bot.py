import os
import logging
import sqlite3
from datetime import datetime
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
MAIN_MENU, RADIO_SELECTION, CAMPAIGN_PERIOD, TIME_SLOTS, BRANDED_SECTIONS, CAMPAIGN_CREATOR, PRODUCTION_OPTION, CONTACT_INFO, CONFIRMATION, FINAL_ACTIONS = range(10)

# Токен бота
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

# Ваш Telegram ID для уведомлений
ADMIN_TELEGRAM_ID = 174046571  # Твой числовой ID

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

BRANDED_SECTION_PRICES = {
    'auto': 1.2,      # +20%
    'realty': 1.15,   # +15%
    'medical': 1.25,  # +25%
    'custom': 1.3     # +30%
}

PRODUCTION_OPTIONS = {
    'standard': {'price': 2000, 'name': 'СТАНДАРТНЫЙ РОЛИК', 'desc': 'Профессиональная озвучка, музыкальное оформление, 2 правки, срок: 2-3 дня'},
    'premium': {'price': 4000, 'name': 'ПРЕМИУМ РОЛИК', 'desc': 'Озвучка 2-мя голосами, индивидуальная музыка, 5 правки, срочное производство 1 день'},
    'ready': {'price': 0, 'name': 'ГОТОВЫЙ РОЛИК', 'desc': 'У меня есть свой ролик, пришлю файлом'}
}

PERIOD_OPTIONS = {
    '15_days': {'days': 15, 'name': '15 ДНЕЙ (минимум)'},
    '30_days': {'days': 30, 'name': '30 ДНЕЙ (рекомендуем)'},
    '60_days': {'days': 60, 'name': '60 ДНЕЙ'}
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
                campaign_period TEXT,
                time_slots TEXT,
                branded_section TEXT,
                campaign_text TEXT,
                production_option TEXT,
                contact_name TEXT,
                company TEXT,
                phone TEXT,
                email TEXT,
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

# Валидация телефона
def validate_phone(phone: str) -> bool:
    pattern = r'^(\+7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
    return bool(re.match(pattern, phone))

# Форматирование чисел
def format_number(num):
    return f"{num:,}".replace(',', ' ')

# Расчет стоимости кампании и охвата
def calculate_campaign_price_and_reach(user_data):
    try:
        # Базовые параметры
        base_duration = user_data.get('duration', 20)  # секунд
        period_days = user_data.get('campaign_period_days', 30)
        num_stations = len(user_data.get('selected_radios', []))
        selected_time_slots = user_data.get('selected_time_slots', [])
        
        # Количество выходов в день
        spots_per_day = len(selected_time_slots) * num_stations
        
        # Базовая стоимость эфира
        base_air_cost = base_duration * BASE_PRICE_PER_SECOND * spots_per_day * period_days
        
        # Надбавки за премиум-время (10% за утренние и вечерние)
        time_multiplier = 1.0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                if slot['premium']:
                    time_multiplier = max(time_multiplier, 1.1)  # 10% наценка
        
        # Надбавка за рубрику
        branded_multiplier = 1.0
        branded_section = user_data.get('branded_section')
        if branded_section in BRANDED_SECTION_PRICES:
            branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
        
        # Стоимость производства
        production_cost = user_data.get('production_cost', 0)
        
        # Итоговая стоимость (эфир + производство)
        air_cost = int(base_air_cost * time_multiplier * branded_multiplier)
        base_price = air_cost + production_cost
        
        # Применяем скидку 50%
        discount = int(base_price * 0.5)
        discounted_price = base_price - discount
        
        # Проверяем минимальный бюджет
        final_price = max(discounted_price, MIN_BUDGET)
        
        # Расчет охвата
        daily_listeners = sum({
            'LOVE RADIO': 1600,
            'АВТОРАДИО': 1400,
            'РАДИО ДАЧА': 1800,
            'РАДИО ШАНСОН': 1200,
            'РЕТРО FM': 1500,
            'ЮМОР FM': 1100
        }.get(radio, 0) for radio in user_data.get('selected_radios', []))
        
        # Учитываем пересечение аудитории (примерно 30% уникальности)
        unique_daily_reach = int(daily_listeners * 0.7)
        total_reach = unique_daily_reach * period_days
        
        return base_price, discount, final_price, total_reach, daily_listeners, spots_per_day
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

# Создание Excel файла
def create_excel_file(user_data, campaign_number):
    try:
        base_price, discount, final_price, total_reach, daily_listeners, spots_per_day = calculate_campaign_price_and_reach(user_data)
        
        # Создаем новую книгу Excel
        wb = Workbook()
        ws = wb.active
        ws.title = f"Медиаплан {campaign_number}"
        
        # Стили
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        title_font = Font(bold=True, size=12)
        border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                       top=Side(style='thin'), bottom=Side(style='thin'))
        
        # Заголовок
        ws.merge_cells('A1:F1')
        ws['A1'] = f"МЕДИАПЛАН КАМПАНИИ #{campaign_number}"
        ws['A1'].font = header_font
        ws['A1'].fill = header_fill
        ws['A1'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('A2:F2')
        ws['A2'] = "РАДИО ТЮМЕНСКОЙ ОБЛАСТИ"
        ws['A2'].font = Font(bold=True, size=12, color="366092")
        ws['A2'].alignment = Alignment(horizontal='center')
        
        # Статус заявки
        ws.merge_cells('A4:F4')
        ws['A4'] = "✅ Ваша заявка принята! Спасибо за доверие!"
        ws['A4'].font = Font(bold=True, size=11)
        
        # Параметры кампании
        ws['A6'] = "📊 ПАРАМЕТРЫ КАМПАНИИ:"
        ws['A6'].font = title_font
        
        params = [
            f"Радиостанции: {', '.join(user_data.get('selected_radios', []))}",
            f"Период: {user_data.get('campaign_period_days', 30)} дней",
            f"Выходов в день: {spots_per_day}",
            f"Всего выходов за период: {spots_per_day * user_data.get('campaign_period_days', 30)}",
            f"Хронометраж ролика: {user_data.get('duration', 20)} сек",
            f"Брендированная рубрика: {get_branded_section_name(user_data.get('branded_section'))}",
            f"Производство: {PRODUCTION_OPTIONS.get(user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}"
        ]
        
        for i, param in enumerate(params, 7):
            ws[f'A{i}'] = f"• {param}"
        
        # Детализация по радиостанциям
        ws['A15'] = "📻 ВЫБРАННЫЕ РАДИОСТАНЦИИ:"
        ws['A15'].font = title_font
        
        station_listeners = {
            'LOVE RADIO': 1600,
            'АВТОРАДИО': 1400,
            'РАДИО ДАЧА': 1800,
            'РАДИО ШАНСОН': 1200,
            'РЕТРО FM': 1500,
            'ЮМОР FM': 1100
        }
        
        row = 16
        total_listeners = 0
        for radio in user_data.get('selected_radios', []):
            listeners = station_listeners.get(radio, 0)
            total_listeners += listeners
            ws[f'A{row}'] = f"• {radio}: {format_number(listeners)} слушателей/день"
            row += 1
        
        ws[f'A{row}'] = f"• ИТОГО: {format_number(total_listeners)} слушателей/день"
        ws[f'A{row}'].font = Font(bold=True)
        
        # Детализация по временным слотам
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
        
        # Охват кампании
        row += 1
        ws[f'A{row}'] = "🎯 РАСЧЕТНЫЙ ОХВАТ:"
        ws[f'A{row}'].font = title_font
        
        row += 1
        ws[f'A{row}'] = f"• Ежедневный охват: ~{format_number(daily_listeners)} человек"
        row += 1
        ws[f'A{row}'] = f"• Уникальный охват в день: ~{format_number(int(daily_listeners * 0.7))} человек"
        row += 1
        ws[f'A{row}'] = f"• Общий охват за период: ~{format_number(total_reach)} человек"
        
        # Финансовая информация
        row += 2
        ws[f'A{row}'] = "💰 ФИНАНСОВАЯ ИНФОРМАЦИЯ:"
        ws[f'A{row}'].font = title_font
        
        # Таблица стоимости
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
        
        # Контактные данные клиента
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
        
        # Контакты компании
        row = i + 2
        ws[f'A{row}'] = "📞 НАШИ КОНТАКТЫ:"
        ws[f'A{row}'].font = title_font
        ws[f'A{row + 1}'] = "• Email: a.khlistunov@gmail.com"
        ws[f'A{row + 2}'] = "• Telegram: t.me/AlexeyKhlistunov"
        
        # Дополнительная информация
        row = row + 4
        ws[f'A{row}'] = "🎯 СТАРТ КАМПАНИИ:"
        ws[f'A{row}'].font = title_font
        ws[f'A{row + 1}'] = "В течение 3 рабочих дней после подтверждения"
        
        # Дата формирования
        row = row + 3
        ws[f'A{row}'] = f"📅 Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        # Настройка ширины колонок
        ws.column_dimensions['A'].width = 45
        ws.column_dimensions['B'].width = 15
        
        # Применяем границы к таблице стоимости
        table_start = financial_start = row - len(financial_data) - 1
        table_end = table_start + len(financial_data) - 1
        for row_num in range(table_start, table_end + 1):
            for col in ['A', 'B']:
                ws[f'{col}{row_num}'].border = border
        
        # Сохраняем в буфер
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        logger.info(f"Excel файл успешно создан для кампании #{campaign_number}")
        return buffer
        
    except Exception as e:
        logger.error(f"Ошибка при создании Excel: {e}")
        return None

# Отправка Excel файла
async def send_excel_file(update: Update, context: ContextTypes.DEFAULT_TYPE, campaign_number: str):
    try:
        # Создаем Excel файл
        excel_buffer = create_excel_file(context.user_data, campaign_number)
        
        if not excel_buffer:
            return False
            
        # Отправляем Excel файл
        if hasattr(update, 'message') and update.message:
            await update.message.reply_document(
                document=excel_buffer,
                filename=f"mediaplan_{campaign_number}.xlsx",
                caption=f"📊 Ваш медиаплан кампании #{campaign_number}"
            )
        else:
            # Если это callback query
            await update.callback_query.message.reply_document(
                document=excel_buffer,
                filename=f"mediaplan_{campaign_number}.xlsx",
                caption=f"📊 Ваш медиаплан кампании #{campaign_number}"
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке Excel: {e}")
        return False

# Отправка уведомления админу
async def send_admin_notification(context, user_data, campaign_number):
    """Отправка уведомления админу о новой заявке"""
    try:
        base_price, discount, final_price, total_reach, daily_listeners, spots_per_day = calculate_campaign_price_and_reach(user_data)
        
        # Детализация по радиостанциям
        stations_text = ""
        station_listeners = {
            'LOVE RADIO': 1600,
            'АВТОРАДИО': 1400,
            'РАДИО ДАЧА': 1800,
            'РАДИО ШАНСОН': 1200,
            'РЕТРО FM': 1500,
            'ЮМОР FM': 1100
        }
        
        for radio in user_data.get('selected_radios', []):
            listeners = station_listeners.get(radio, 0)
            stations_text += f"• {radio}: {format_number(listeners)}/день\n"
        
        # Детализация по слотам
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
📅 ПЕРИОД: {user_data.get('campaign_period_days', 30)} дней
🕒 СЛОТЫ ({len(user_data.get('selected_time_slots', []))} выбрано):
{slots_text}
🎙️ РУБРИКА: {get_branded_section_name(user_data.get('branded_section'))}
⏱️ РОЛИК: {PRODUCTION_OPTIONS.get(user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}
📏 ХРОНОМЕТРАЖ: {user_data.get('duration', 20)} сек

💰 СТОИМОСТЬ:
Базовая: {format_number(base_price)}₽
Скидка 50%: -{format_number(discount)}₽
Итоговая: {format_number(final_price)}₽

🎯 ОХВАТ:
• Выходов в день: {spots_per_day}
• Всего выходов: {spots_per_day * user_data.get('campaign_period_days', 30)}
• Ежедневно: ~{format_number(daily_listeners)} чел.
• За период: ~{format_number(total_reach)} чел.
"""
        
        # Создаем клавиатуру с кнопками действий
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
        
        # Отправляем уведомление админу
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
        "🎙️ РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
        "📍 Ялуторовск • Заводоуковск\n"
        "📍 Территория +35 км вокруг городов\n\n"
        "📊 Охват: 9,200+ в день\n"
        "👥 Охват: 68,000+ в месяц\n\n"
        "🎯 52% доля местного радиорынка\n"
        "💰 2₽/сек базовая цена"
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
        'LOVE RADIO': 1600,
        'АВТОРАДИО': 1400,
        'РАДИО ДАЧА': 1800,
        'РАДИО ШАНСОН': 1200,
        'РЕТРО FM': 1500,
        'ЮМОР FM': 1100
    }.get(radio, 0) for radio in selected_radios)
    
    # Создаем клавиатуру с выбранными станциями
    keyboard = []
    radio_stations = [
        ("LOVE RADIO", "radio_love", 1600),
        ("АВТОРАДИО", "radio_auto", 1400),
        ("РАДИО ДАЧА", "radio_dacha", 1800), 
        ("РАДИО ШАНСОН", "radio_chanson", 1200),
        ("РЕТРО FM", "radio_retro", 1500),
        ("ЮМОР FM", "radio_humor", 1100)
    ]
    
    for name, callback, listeners in radio_stations:
        emoji = "✅" if name in selected_radios else "⚪"
        button_text = f"{emoji} {name} ({format_number(listeners)} ч/день)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])
        keyboard.append([InlineKeyboardButton("📖 Подробнее", callback_data=f"details_{callback}")])
    
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_campaign_period")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"Выбор радиостанций\n\n"
        f"{'✅' if 'LOVE RADIO' in selected_radios else '⚪'} LOVE RADIO\n"
        f"👥 1,600 слушателей/день\n👩 Молодёжь 18-35 лет\n\n"
        f"{'✅' if 'АВТОРАДИО' in selected_radios else '⚪'} АВТОРАДИО\n"
        f"👥 1,400 слушателей/день\n👨 Автомобилисты 25-50 лет\n\n"
        f"{'✅' if 'РАДИО ДАЧА' in selected_radios else '⚪'} РАДИО ДАЧА\n"
        f"👥 1,800 слушателей/день\n👨👩 Семья 35-65 лет\n\n"
        f"{'✅' if 'РАДИО ШАНСОН' in selected_radios else '⚪'} РАДИО ШАНСОН\n"
        f"👥 1,200 слушателей/день\n👨 Мужчины 30-60 лет\n\n"
        f"{'✅' if 'РЕТРО FM' in selected_radios else '⚪'} РЕТРО FM\n"
        f"👥 1,500 слушателей/день\n👴👵 Ценители хитов 30-55 лет\n\n"
        f"{'✅' if 'ЮМОР FM' in selected_radios else '⚪'} ЮМОР FM\n"
        f"👥 1,100 слушателей/день\n👦👧 Слушатели 25-45 лет\n\n"
        f"Выбрано: {len(selected_radios)} станции • {format_number(total_listeners)} слушателей\n"
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
    
    elif query.data.startswith("details_"):
        station_data = {
            'details_radio_love': "LOVE RADIO - 1,600 слушателей/день\n• Молодёжь 18-35 лет (65%)\n• Активные, следят за трендами\n• Музыка: современные хиты\n• Особенности: интерактивные конкурсы",
            'details_radio_auto': "АВТОРАДИО - 1,400 слушателей/день\n• Автомобилисты 25-50 лет (70%)\n• Дорожные новости, пробки\n• Музыка: российские и зарубежные хиты\n• Особенности: дорожная информация каждые 15 минут",
            'details_radio_dacha': "РАДИО ДАЧА - 1,800 слушателей/день\n• Семья 35-65 лет (60% женщины)\n• Семейные ценности, дачные советы\n• Музыка: российская эстрада, ретро\n• Особенности: утренние шоу, полезные советы",
            'details_radio_chanson': "РАДИО ШАНСОН - 1,200 слушателей/день\n• Мужчины 30-60 лет (75%)\n• Драйв и душевность\n• Музыка: шансон, авторская песня\n• Особенности: истории песен, гостевые эфиры",
            'details_radio_retro': "РЕТРО FM - 1,500 слушателей/день\n• Ценители хитов 30-55 лет\n• Ностальгия по 80-90-м\n• Музыка: хиты 80-90-х годов\n• Особенности: тематические подборки",
            'details_radio_humor': "ЮМОР FM - 1,100 слушателей/день\n• Слушатели 25-45 лет\n• Лёгкий юмор и позитив\n• Музыка: развлекательные шоу, комедии\n• Особенности: юмористические программы"
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
    
    elif query.data == "to_campaign_period":
        if not context.user_data.get('selected_radios'):
            await query.answer("❌ Выберите хотя бы одну радиостанцию!", show_alert=True)
            return RADIO_SELECTION
        return await campaign_period(update, context)
    
    elif query.data == "back_to_radio":
        return await radio_selection(update, context)
    
    return RADIO_SELECTION

# Шаг 2: Период кампании
async def campaign_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_period = context.user_data.get('campaign_period')
    selected_radios = context.user_data.get('selected_radios', [])
    
    # Информация о выбранных станциях
    stations_info = "📻 ВЫБРАНЫ СТАНЦИИ:\n"
    station_listeners = {
        'LOVE RADIO': 1600,
        'АВТОРАДИО': 1400,
        'РАДИО ДАЧА': 1800,
        'РАДИО ШАНСОН': 1200,
        'РЕТРО FM': 1500,
        'ЮМОР FM': 1100
    }
    
    for radio in selected_radios:
        listeners = station_listeners.get(radio, 0)
        stations_info += f"• {radio} ({format_number(listeners)} ч/день)\n"
    
    keyboard = []
    for key, option in PERIOD_OPTIONS.items():
        is_selected = "✅" if selected_period == key else "⚪"
        # Расчет стоимости для каждого периода
        base_cost = 750 * option['days'] * len(selected_radios)
        discounted_cost = base_cost * 0.5
        keyboard.append([
            InlineKeyboardButton(
                f"{is_selected} {option['name']} - {format_number(int(discounted_cost))}₽", 
                callback_data=f"period_{key}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_radio")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_time_slots")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"Период кампании\n\n"
        f"{stations_info}\n"
        f"📅 ВЫБЕРИТЕ ПЕРИОД КАМПАНИИ:\n\n"
        f"🎯 Старт кампании: в течение 3 дней после подтверждения\n"
        f"⏱️ Минимальный период: 15 дней\n\n"
        f"Цены указаны со скидкой 50%"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return CAMPAIGN_PERIOD

# Обработка выбора периода
async def handle_campaign_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_radio":
        return await radio_selection(update, context)
    
    elif query.data.startswith("period_"):
        period_key = query.data.replace("period_", "")
        if period_key in PERIOD_OPTIONS:
            context.user_data['campaign_period'] = period_key
            context.user_data['campaign_period_days'] = PERIOD_OPTIONS[period_key]['days']
            return await campaign_period(update, context)
    
    elif query.data == "to_time_slots":
        if not context.user_data.get('campaign_period'):
            await query.answer("❌ Выберите период кампании!", show_alert=True)
            return CAMPAIGN_PERIOD
        return await time_slots(update, context)
    
    return CAMPAIGN_PERIOD

# Шаг 3: Временные слоты
async def time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_slots = context.user_data.get('selected_time_slots', [])
    selected_radios = context.user_data.get('selected_radios', [])
    period_days = context.user_data.get('campaign_period_days', 30)
    
    # Создаем клавиатуру с временными слотами
    keyboard = []
    
    # Кнопка "Выбрать все"
    keyboard.append([InlineKeyboardButton("✅ ВЫБРАТЬ ВСЕ СЛОТЫ", callback_data="select_all_slots")])
    
    # Утренние слоты
    keyboard.append([InlineKeyboardButton("🌅 УТРЕННИЕ СЛОТЫ (+10%)", callback_data="header_morning")])
    for i in range(4):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "⚪"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    # Дневные слоты
    keyboard.append([InlineKeyboardButton("☀️ ДНЕВНЫЕ СЛОТЫ", callback_data="header_day")])
    for i in range(4, 10):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "⚪"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    # Вечерние слоты
    keyboard.append([InlineKeyboardButton("🌇 ВЕЧЕРНИЕ СЛОТЫ (+10%)", callback_data="header_evening")])
    for i in range(10, 15):
        slot = TIME_SLOTS_DATA[i]
        emoji = "✅" if i in selected_slots else "⚪"
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_period")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_branded_sections")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    total_slots = len(selected_slots)
    total_outputs_per_day = total_slots * len(selected_radios)
    total_outputs_period = total_outputs_per_day * period_days
    
    # Информация о выбранных параметрах
    stations_text = "📻 ВЫБРАНЫ СТАНЦИИ:\n" + "\n".join([f"• {radio}" for radio in selected_radios])
    
    text = (
        f"Временные слоты\n\n"
        f"{stations_text}\n"
        f"📅 ПЕРИОД КАМПАНИИ: {period_days} дней\n\n"
        f"🕒 ВЫБЕРИТЕ ВРЕМЯ ВЫХОДА РОЛИКОВ\n\n"
        f"📊 Статистика выбора:\n"
        f"• Выбрано слотов: {total_slots}\n"
        f"• Выходов в день на всех радио: {total_outputs_per_day}\n"
        f"• Всего выходов за период: {format_number(total_outputs_period)}\n\n"
        f"🎯 Выберите подходящие временные интервалы\n"
        f"[ ДАЛЕЕ ]"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return TIME_SLOTS

# Обработка выбора временных слотов
async def handle_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_period":
        return await campaign_period(update, context)
    
    elif query.data == "select_all_slots":
        # Выбираем все 15 слотов
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

# Шаг 4: Брендированные рубрики
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

# Обработка выбора рубрик
async def handle_branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_time":
        return await time_slots(update, context)
    
    elif query.data == "show_example":
        example_text = (
            "Комплексные рекламные решения для продвижения услуг Тюменского кардиологического научного центра на радиостанциях Тюмени.\n\n"
            "Задача: Продвижение услуг кардиологического центра, информирование жителей региона о важности профилактики сердечно-сосудистых заболеваний.\n\n"
            "Форматы размещения:\n• Рекламные ролики (15–30 сек.)\n• Брендированные рубрики — «Здоровое сердце», «Совет врача»\n\n"
            "Пример рубрики (30 сек.):\n«❤️ Знаете ли вы, что регулярное обследование сердца помогает предупредить серьёзные заболевания? В Тюменском кардиологическом научном центре вы можете пройти диагностику и получить консультацию специалистов. Заботьтесь о себе и своих близких — здоровье сердца в надёжных руках!»\n\n"
            "Преимущества:\n• Доступ к широкой аудитории\n• Высокий уровень доверия к радио\n• Интеграция бренда в полезный контент\n• Формирование имиджа экспертного медицинского центра"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ НАЗАД К ВЫБОРУ РУБРИК", callback_data="back_to_branded")]]
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

# Шаг 5: Конструктор ролика - ИСПРАВЛЕННАЯ ВЕРСИЯ
async def campaign_creator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Рассчитываем предварительную стоимость и охват
    base_price, discount, final_price, total_reach, daily_listeners, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
    context.user_data['base_price'] = base_price
    context.user_data['discount'] = discount
    context.user_data['final_price'] = final_price
    
    provide_own = context.user_data.get('provide_own_audio', False)
    campaign_text = context.user_data.get('campaign_text', '')
    char_count = len(campaign_text) if campaign_text else 0
    duration = context.user_data.get('duration', 20)
    
    # Формируем клавиатуру в зависимости от выбора "Пришлю свой ролик"
    keyboard = []
    
    if provide_own:
        # Если выбран "Пришлю свой ролик" - показываем кнопку указания хронометража
        keyboard.append([InlineKeyboardButton("⏱️ Указать хронометраж", callback_data="enter_duration")])
        keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
    else:
        # Если НЕ выбран "Пришлю свой ролик" - показываем кнопку ввода текста
        keyboard.append([InlineKeyboardButton("📝 ВВЕСТИ ТЕКСТ РОЛИКА", callback_data="enter_text")])
        keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
        keyboard.append([InlineKeyboardButton("⏱️ Указать хронометраж", callback_data="enter_duration")])
    
    keyboard.append([InlineKeyboardButton("⏩ ПРОПУСТИТЬ", callback_data="skip_text")])
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_branded")])
    keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_production_option")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "Конструктор ролика\n\n"
        "📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n\n"
        f"{campaign_text if campaign_text else '[Ваш текст появится здесь]'}\n\n"
        f"○ {char_count} знаков из 500\n\n"
        f"⏱️ Длительность ролика: {duration} секунд\n"
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

# Ввод текста ролика - ИСПРАВЛЕННАЯ ВЕРСИЯ
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

# Обработка текста ролика - ИСПРАВЛЕННАЯ ВЕРСИЯ
async def process_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        if len(text) > 500:
            await update.message.reply_text("❌ Текст превышает 500 знаков. Сократите текст и отправьте снова:")
            return "WAITING_TEXT"
        
        context.user_data['campaign_text'] = text
        context.user_data['provide_own_audio'] = False
        
        # Автоматически возвращаем в конструктор ролика
        base_price, discount, final_price, total_reach, daily_listeners, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
        
        char_count = len(text)
        duration = context.user_data.get('duration', 20)
        
        # Формируем клавиатуру для конструктора
        keyboard = []
        provide_own = context.user_data.get('provide_own_audio', False)
        
        if provide_own:
            keyboard.append([InlineKeyboardButton("⏱️ Указать хронометраж", callback_data="enter_duration")])
            keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
        else:
            keyboard.append([InlineKeyboardButton("📝 ВВЕСТИ ТЕКСТ РОЛИКА", callback_data="enter_text")])
            keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
            keyboard.append([InlineKeyboardButton("⏱️ Указать хронометраж", callback_data="enter_duration")])
        
        keyboard.append([InlineKeyboardButton("⏩ ПРОПУСТИТЬ", callback_data="skip_text")])
        keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_branded")])
        keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_production_option")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text_display = (
            f"Конструктор ролика\n\n"
            f"📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n\n"
            f"{text}\n\n"
            f"○ {char_count} знаков из 500\n\n"
            f"⏱️ Длительность ролика: {duration} секунд\n"
            f"📊 Выходов в день: {spots_per_day}\n\n"
            f"💰 Предварительная стоимость:\n"
            f"   Базовая: {format_number(base_price)}₽\n"
            f"   Скидка 50%: -{format_number(discount)}₽\n"
            f"   Итоговая: {format_number(final_price)}₽\n\n"
            f"📊 Примерный охват кампании:\n"
            f"   ~{format_number(total_reach)} человек за период\n\n"
            f"{'✅' if provide_own else '⚪'} Пришлю свой ролик"
        )
        
        await update.message.reply_text(text_display, reply_markup=reply_markup)
        return CAMPAIGN_CREATOR
        
    except Exception as e:
        logger.error(f"Ошибка в process_campaign_text: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте еще раз: /start")
        return ConversationHandler.END

# Ввод хронометража
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

# Обработка хронометража - ИСПРАВЛЕННАЯ ВЕРСИЯ (автоматический возврат)
async def process_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        duration_text = update.message.text.strip()
        duration = int(duration_text)
        
        if duration < 10 or duration > 30:
            await update.message.reply_text("❌ Длительность должна быть от 10 до 30 секунд. Попробуйте еще раз:")
            return "WAITING_DURATION"
        
        context.user_data['duration'] = duration
        
        # Автоматически возвращаем в конструктор ролика
        base_price, discount, final_price, total_reach, daily_listeners, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
        
        campaign_text = context.user_data.get('campaign_text', '')
        char_count = len(campaign_text) if campaign_text else 0
        provide_own = context.user_data.get('provide_own_audio', False)
        
        # Формируем клавиатуру для конструктора
        keyboard = []
        
        if provide_own:
            keyboard.append([InlineKeyboardButton("⏱️ Указать хронометраж", callback_data="enter_duration")])
            keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
        else:
            keyboard.append([InlineKeyboardButton("📝 ВВЕСТИ ТЕКСТ РОЛИКА", callback_data="enter_text")])
            keyboard.append([InlineKeyboardButton("✅ Пришлю свой ролик" if provide_own else "⚪ Пришлю свой ролик", callback_data="provide_own_audio")])
            keyboard.append([InlineKeyboardButton("⏱️ Указать хронометраж", callback_data="enter_duration")])
        
        keyboard.append([InlineKeyboardButton("⏩ ПРОПУСТИТЬ", callback_data="skip_text")])
        keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_branded")])
        keyboard.append([InlineKeyboardButton("➡️ ДАЛЕЕ", callback_data="to_production_option")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text_display = (
            f"Конструктор ролика\n\n"
            f"📝 ВАШ ТЕКСТ ДЛЯ РОЛИКА (до 500 знаков):\n\n"
            f"{campaign_text if campaign_text else '[Ваш текст появится здесь]'}\n\n"
            f"○ {char_count} знаков из 500\n\n"
            f"⏱️ Длительность ролика: {duration} секунд\n"
            f"📊 Выходов в день: {spots_per_day}\n\n"
            f"💰 Предварительная стоимость:\n"
            f"   Базовая: {format_number(base_price)}₽\n"
            f"   Скидка 50%: -{format_number(discount)}₽\n"
            f"   Итоговая: {format_number(final_price)}₽\n\n"
            f"📊 Примерный охват кампании:\n"
            f"   ~{format_number(total_reach)} человек за период\n\n"
            f"{'✅' if provide_own else '⚪'} Пришлю свой ролик"
        )
        
        await update.message.reply_text(text_display, reply_markup=reply_markup)
        return CAMPAIGN_CREATOR
        
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите число от 10 до 30:")
        return "WAITING_DURATION"

# Шаг 6: Производство ролика
async def production_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Если клиент выбрал "Пришлю свой ролик", пропускаем этот шаг
    if context.user_data.get('provide_own_audio'):
        context.user_data['production_option'] = 'ready'
        context.user_data['production_cost'] = 0
        return await contact_info(update, context)
    
    selected_production = context.user_data.get('production_option')
    
    keyboard = []
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
        "🎙️ ВЫБЕРИТЕ ВАРИАНТ РОЛИКА:\n\n"
        "⚪ СТАНДАРТНЫЙ РОЛИК - от 2,000₽\n"
        "• Профессиональная озвучка\n• Музыкальное оформление\n• 2 правки\n• Срок: 2-3 дня\n\n"
        "⚪ ПРЕМИУМ РОЛИК - от 4,000₽\n"
        "• Озвучка 2-мя голосами\n• Индивидуальная музыка\n• 5 правок\n• Срочное производство 1 день\n\n"
        "💰 Влияние на итоговую стоимость"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return PRODUCTION_OPTION

# Обработка выбора производства
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

# Шаг 7: Контактные данные
async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    base_price, discount, final_price, total_reach, daily_listeners, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
    
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

# Обработка контактной информации
async def process_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        
        if 'contact_name' not in context.user_data:
            context.user_data['contact_name'] = text
            await update.message.reply_text(
                "📞 Введите ваш телефон:\n\n"
                "Формат: +79XXXXXXXXX\n"
                "Пример: +79123456789"
            )
            return CONTACT_INFO
        
        elif 'phone' not in context.user_data:
            if not validate_phone(text):
                await update.message.reply_text("❌ Неверный формат телефона. Используйте формат: +79XXXXXXXXX")
                return CONTACT_INFO
            context.user_data['phone'] = text
            await update.message.reply_text("📧 Введите ваш email:")
            return CONTACT_INFO
        
        elif 'email' not in context.user_data:
            context.user_data['email'] = text
            await update.message.reply_text("🏢 Введите название компании:")
            return CONTACT_INFO
        
        elif 'company' not in context.user_data:
            context.user_data['company'] = text
            return await show_confirmation(update, context)
            
    except Exception as e:
        logger.error(f"Ошибка в process_contact_info: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Пожалуйста, начните заново: /start"
        )
        return ConversationHandler.END

# Показать подтверждение заявки - ИСПРАВЛЕННАЯ ВЕРСИЯ (новая кнопка)
async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    base_price, discount, final_price, total_reach, daily_listeners, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
    
    # Детализация по радиостанциям
    stations_text = ""
    station_listeners = {
        'LOVE RADIO': 1600,
        'АВТОРАДИО': 1400,
        'РАДИО ДАЧА': 1800,
        'РАДИО ШАНСОН': 1200,
        'РЕТРО FM': 1500,
        'ЮМОР FM': 1100
    }
    
    for radio in context.user_data.get('selected_radios', []):
        listeners = station_listeners.get(radio, 0)
        stations_text += f"• {radio}: {format_number(listeners)}/день\n"
    
    # Детализация по слотам
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
📅 ПЕРИОД: {context.user_data.get('campaign_period_days', 30)} дней
🕒 ВЫБРАНО СЛОТОВ: {len(context.user_data.get('selected_time_slots', []))}
{slots_text}
🎙️ РУБРИКА: {get_branded_section_name(context.user_data.get('branded_section'))}
⏱️ РОЛИК: {PRODUCTION_OPTIONS.get(context.user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}
📏 ХРОНОМЕТРАЖ: {context.user_data.get('duration', 20)} сек

💰 СТОИМОСТЬ:
Базовая: {format_number(base_price)}₽
Скидка 50%: -{format_number(discount)}₽
Итоговая: {format_number(final_price)}₽

🎯 ОХВАТ:
• Выходов в день: {spots_per_day}
• Всего выходов: {spots_per_day * context.user_data.get('campaign_period_days', 30)}
• Ежедневно: ~{format_number(daily_listeners)} чел.
• За период: ~{format_number(total_reach)} чел.
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 ОТПРАВИТЬ ЗАЯВКУ", callback_data="submit_campaign")],
        [InlineKeyboardButton("◀️ ВЕРНУТЬСЯ К ВЫБОРУ РАДИО", callback_data="back_to_radio_from_confirmation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
    return CONFIRMATION

# Обработка подтверждения заявки - ИСПРАВЛЕННАЯ ВЕРСИЯ
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_radio_from_confirmation":
        # Возвращаем к выбору радиостанций, сохраняя все данные
        return await radio_selection(update, context)
    
    elif query.data == "submit_campaign":
        try:
            # Рассчитываем финальную стоимость и охват
            base_price, discount, final_price, total_reach, daily_listeners, spots_per_day = calculate_campaign_price_and_reach(context.user_data)
            context.user_data['base_price'] = base_price
            context.user_data['discount'] = discount
            context.user_data['final_price'] = final_price
            
            # Сохраняем заявку в БД
            campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
            conn = sqlite3.connect('campaigns.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO campaigns 
                (user_id, campaign_number, radio_stations, campaign_period, time_slots, branded_section, campaign_text, production_option, contact_name, company, phone, email, base_price, discount, final_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                query.from_user.id,
                campaign_number,
                ','.join(context.user_data.get('selected_radios', [])),
                context.user_data.get('campaign_period', ''),
                ','.join(map(str, context.user_data.get('selected_time_slots', []))),
                context.user_data.get('branded_section', ''),
                context.user_data.get('campaign_text', ''),
                context.user_data.get('production_option', ''),
                context.user_data.get('contact_name', ''),
                context.user_data.get('company', ''),
                context.user_data.get('phone', ''),
                context.user_data.get('email', ''),
                base_price,
                discount,
                final_price
            ))
            
            conn.commit()
            conn.close()
            
            # Отправляем уведомление админу
            await send_admin_notification(context, context.user_data, campaign_number)
            
            # Показываем подтверждение клиенту
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

# Обработка финальных действий
async def handle_final_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "generate_excel":
            campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
            try:
                # Создаем и отправляем Excel
                success = await send_excel_file(update, context, campaign_number)
                if not success:
                    await query.message.reply_text("❌ Ошибка при создании Excel. Попробуйте еще раз.")
            except Exception as e:
                logger.error(f"Ошибка Excel: {e}")
                await query.message.reply_text("❌ Ошибка при создании Excel. Попробуйте еще раз.")
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

# Личный кабинет
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

# Статистика охвата
async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📊 СТАТИСТИКА ОХВАТА\n\n"
        "• Ежедневный охват: 9,200+\n"
        "• Месячный охват: 68,000+\n"
        "• Радиус вещания: 35 км вокруг городов\n"
        "• Доля рынка: 52%\n"
        "• Базовая цена: 2₽/сек\n\n"
        "По станциям (в день):\n"
        "• LOVE RADIO: 1,600\n"
        "• АВТОРАДИО: 1,400\n"  
        "• РАДИО ДАЧА: 1,800\n"
        "• РАДИО ШАНСОН: 1,200\n"
        "• РЕТРО FM: 1,500\n"
        "• ЮМОР FM: 1,100\n\n"
        "🎯 Охватываем:\n"
        "📍 Ялуторовск\n"
        "📍 Заводоуковск\n"  
        "📍 Территория +35 км вокруг городов\n\n"
        "📈 Источники исследований:\n"
        "• RADIOPORTAL.RU - Радио в малых городах\n"
        "• Mediascope - Российский радиорынок\n"  
        "• ВЦИОМ - Популярность радио в региона\n\n"
        "🔗 radioportal.ru/radio-audience-research\n"
        "🔗 mediascope.net/services/media/radio/\n"
        "🔗 wciom.ru/analytical-reviews/radio-audience\n\n"
        "🎧 В малых городах слушают 2.5 часа/день\n"
        "🚗 65% аудитории - автомобилисты\n"
        "🏘️ +35% охват за счет сельской местности",
        reply_markup=reply_markup
    )
    return MAIN_MENU

# О нас
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎙️ РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
        "📍 Ялуторовск • Заводоуковск\n\n"
        "ℹ️ О НАС\n\n"
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

# Улучшенный обработчик главного меню - добавим обработку новой кнопки
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Обработка основных действий
    if query.data == "create_campaign":
        context.user_data.clear()
        return await radio_selection(update, context)
    
    elif query.data == "statistics":
        return await statistics(update, context)
    
    elif query.data == "my_orders":
        return await personal_cabinet(update, context)
    
    elif query.data == "about":
        return await about(update, context)
    
    # ОБРАБОТКА АДМИНСКИХ КНОПОК
    elif query.data.startswith("generate_excel_"):
        campaign_number = query.data.replace("generate_excel_", "")
        try:
            excel_buffer = create_excel_file(context.user_data, campaign_number)
            if excel_buffer:
                await query.message.reply_document(
                    document=excel_buffer,
                    filename=f"mediaplan_{campaign_number}.xlsx",
                    caption=f"📊 Excel для клиента #{campaign_number}"
                )
            else:
                await query.message.reply_text(f"❌ Ошибка при создании Excel")
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка при создании Excel: {e}")
    
    elif query.data.startswith("get_excel_"):
        campaign_number = query.data.replace("get_excel_", "")
        try:
            excel_buffer = create_excel_file(context.user_data, campaign_number)
            if excel_buffer:
                await query.message.reply_document(
                    document=excel_buffer,
                    filename=f"mediaplan_{campaign_number}.xlsx",
                    caption=f"📊 Excel для клиента #{campaign_number}"
                )
            else:
                await query.message.reply_text(f"❌ Ошибка при создании Excel")
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка при создании Excel: {e}")
    
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
    
    elif query.data == "back_to_period":
        return await campaign_period(update, context)
    
    elif query.data == "back_to_time":
        return await time_slots(update, context)
    
    elif query.data == "back_to_branded":
        return await branded_sections(update, context)
    
    elif query.data == "back_to_creator":
        return await campaign_creator(update, context)
    
    elif query.data == "back_to_production":
        return await production_option(update, context)
    
    elif query.data == "back_to_company":
        await query.message.reply_text("🏢 Введите название компании:")
        return CONTACT_INFO
    
    elif query.data == "back_to_final":
        # Возврат к финальным действиям после личного кабинета
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
    
    elif query.data == "provide_own_audio":
        # Переключатель "Пришлю свой ролик"
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

# Главная функция
def main():
    # Инициализация БД
    if init_db():
        logger.info("Бот запущен успешно")
    else:
        logger.error("Ошибка инициализации БД")
    
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
            CAMPAIGN_PERIOD: [
                CallbackQueryHandler(handle_campaign_period, pattern='^.*$')
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
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_production$')
            ],
            CONFIRMATION: [
                CallbackQueryHandler(handle_confirmation, pattern='^.*$')
            ],
            FINAL_ACTIONS: [
                CallbackQueryHandler(handle_final_actions, pattern='^.*$')
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    
    # Добавляем отдельный обработчик для админских кнопок
    application.add_handler(CallbackQueryHandler(
        handle_main_menu, 
        pattern='^(generate_excel_|get_excel_|call_|email_)'
    ))
    
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
