import os
import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import io
import re

# НОВЫЕ ИМПОРТЫ ДЛЯ EXCEL
import openpyxl
from openpyxl.styles import Font, Border, Side, Alignment, PatternFill
from openpyxl.utils import get_column_letter

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора (ОБНОВЛЕНО: добавлены WAITING_DURATION, CONFIRM_TEXT)
MAIN_MENU, RADIO_SELECTION, CAMPAIGN_PERIOD, TIME_SLOTS, BRANDED_SECTIONS, CAMPAIGN_CREATOR, PRODUCTION_OPTION, CONTACT_INFO, FINAL_ACTIONS, WAITING_TEXT, WAITING_DURATION, CONFIRM_TEXT = range(12) 

# Токен бота
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

# Ваш Telegram ID для уведомлений
ADMIN_TELEGRAM_ID = 174046571  # Твой числовой ID

# Цены и параметры (ОБНОВЛЕНО)
BASE_PRICE_PER_SECOND = 2
DEFAULT_DURATION = 20 # Новый базовый хронометраж
MIN_PRODUCTION_COST = 2000
MIN_BUDGET = 7000

# КОНСТАНТЫ ДЛЯ ВИЗУАЛА
E_CHECK = "✅"
E_UNCHECK = "⚪"
E_RADIO = "📻"
E_PERIOD = "📅"
E_TIME = "🕒"
E_COST = "💰"
E_REACH = "🎯"
E_NEXT = "➡️"
E_BACK = "⬅️"
E_SKIP = "⏩"
E_TTS = "🎧"
E_XLSX = "💾"
E_SEND = "📤"
E_CANCEL = "❌"
E_MIC = "🎙️"
E_TEXT = "✍️"

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
    'auto': 1.2,
    'realty': 1.15,
    'medical': 1.25,
    'custom': 1.3
}

PRODUCTION_OPTIONS = {
    'standard': {'price': 2000, 'name': 'СТАНДАРТНЫЙ РОЛИК', 'desc': 'Профессиональная озвучка, музыкальное оформление, 2 правки, срок: 2-3 дня'},
    'premium': {'price': 4000, 'name': 'ПРЕМИУМ РОЛИК', 'desc': 'Озвучка 2-мя голосами, индивидуальная музыка, 5 правок, срочное производство 1 день'},
    'ready': {'price': 0, 'name': 'ГОТОВЫЙ РОЛИК', 'desc': 'У меня есть свой ролик, пришлю файлом'}
}

PERIOD_OPTIONS = {
    '15_days': {'days': 15, 'name': '15 ДНЕЙ (минимум)'},
    '30_days': {'days': 30, 'name': '30 ДНЕЙ (рекомендуем)'},
    '60_days': {'days': 60, 'name': '60 ДНЕЙ'}
}

# Инициализация базы данных (без изменений)
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

# Валидация телефона (без изменений)
def validate_phone(phone: str) -> bool:
    pattern = r'^(\+7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
    return bool(re.match(pattern, phone))

# Форматирование чисел (без изменений)
def format_number(num):
    return f"{num:,}".replace(',', ' ')

# Мок функция для TTS (поскольку нет доступа к реальному TTS API)
def mock_generate_tts_audio():
    # Создаем фиктивный аудиофайл (пустой IO buffer) для имитации TTS
    audio_buffer = io.BytesIO(b'\x00\x00\x00\x00\x00\x00\x00\x00')
    audio_buffer.name = "sample_audio.mp3"
    return audio_buffer

# Расчет стоимости кампании и охвата (ОБНОВЛЕННЫЙ КОД)
def calculate_campaign_price_and_reach(user_data):
    try:
        # 1. Базовые параметры
        # Используем кастомный хронометраж, если он есть, иначе - дефолтный 20 сек
        base_duration = user_data.get('custom_duration', DEFAULT_DURATION)
        spots_per_slot = 5
        
        period_days = user_data.get('campaign_period_days', 30)
        num_stations = len(user_data.get('selected_radios', []))
        num_slots = len(user_data.get('selected_time_slots', []))
        
        # Стоимость одного выхода (base_duration сек * 2р/сек)
        price_per_spot = base_duration * BASE_PRICE_PER_SECOND 
        
        # 2. Базовая стоимость эфира (без наценок)
        base_air_cost = price_per_spot * spots_per_slot * num_slots * period_days * num_stations
        
        # 3. Надбавки за премиум-время (ПРИМЕНЯЕТСЯ К BASE_AIR_COST)
        time_premium_multiplier = 1.0
        selected_time_slots = user_data.get('selected_time_slots', [])
        
        premium_slots_count = 0
        total_available_slots = len(TIME_SLOTS_DATA)
        
        for slot_index in selected_time_slots:
            if 0 <= slot_index < total_available_slots and TIME_SLOTS_DATA[slot_index]['premium']:
                premium_slots_count += 1
        
        if num_slots > 0:
            # Наценка 20% применяется к той части выходов, которая попала в прайм-тайм
            premium_ratio = premium_slots_count / num_slots
            time_premium_multiplier = 1.0 + (premium_ratio * 0.2)

        # 4. Надбавка за рубрику (ПРИМЕНЯЕТСЯ К BASE_AIR_COST)
        branded_multiplier = 1.0
        branded_section = user_data.get('branded_section')
        if branded_section in BRANDED_SECTION_PRICES:
            branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
        
        # Стоимость эфира после всех наценок (Air Cost Final)
        air_cost_final = int(base_air_cost * time_premium_multiplier * branded_multiplier)
        
        # 5. Применяем скидку 50% ТОЛЬКО к Стоимости ЭФИРА
        discount = int(air_cost_final * 0.5)
        discounted_air_cost = air_cost_final - discount
        
        # 6. Стоимость производства
        production_cost = user_data.get('production_cost', 0)
        
        # 7. Итоговая стоимость
        final_price = discounted_air_cost + production_cost
        
        # Проверяем минимальный бюджет
        final_price = max(final_price, MIN_BUDGET)
        
        # Сохранение данных о выходах и ценах
        base_price_before_discount = air_cost_final + production_cost

        # Расчет охвата
        daily_listeners = sum({
            'LOVE RADIO': 1600,
            'АВТОРАДИО': 1400,
            'РАДИО ДАЧА': 1800,
            'РАДИО ШАНСОН': 1200,
            'РЕТРО FM': 1500,
            'ЮМОР FM': 1100
        }.get(radio, 0) for radio in user_data.get('selected_radios', []))
        
        period_reach_factor = 0.7 
        unique_daily_reach = int(daily_listeners * period_reach_factor)
        total_reach = unique_daily_reach * period_days

        # Сохранение данных для отчетности (ОБНОВЛЕНО)
        user_data['base_duration'] = base_duration
        user_data['spots_per_slot'] = spots_per_slot 
        user_data['total_outputs_day'] = num_slots * spots_per_slot * num_stations
        user_data['total_outputs_period'] = user_data['total_outputs_day'] * period_days
        user_data['air_cost_base'] = base_air_cost 
        user_data['air_cost_final'] = air_cost_final 
        user_data['discounted_air_cost'] = discounted_air_cost 
        user_data['unique_daily_reach'] = unique_daily_reach 
        user_data['daily_listeners'] = daily_listeners 

        return base_price_before_discount, discount, final_price, total_reach, daily_listeners
        
    except Exception as e:
        logger.error(f"Ошибка расчета стоимости: {e}")
        return 0, 0, 0, 0, 0

def get_branded_section_name(section):
    names = {
        'auto': 'Авторубрики (+20%)',
        'realty': 'Недвижимость (+15%)',
        'medical': 'Медицинские рубрики (+25%)',
        'custom': 'Индивидуальная рубрика (+30%)'
    }
    return names.get(section, 'Не выбрана')

# Создание Excel файла (ОБНОВЛЕНО: Детализация охвата, новая цена, хронометраж)
def create_excel_file(user_data, campaign_number):
    try:
        base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(user_data)
        
        buffer = io.BytesIO()
        wb = openpyxl.Workbook()
        
        # --- ЛИСТ 1: СВОДКА И ФИНАНСЫ ---
        ws_summary = wb.active
        ws_summary.title = "Сводка"
        
        # Стили
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="800000", end_color="800000", fill_type="solid") # Dark Red
        bold_font = Font(bold=True)
        
        # Заголовок
        ws_summary['A1'] = f"МЕДИАПЛАН КАМПАНИИ #{campaign_number}"
        ws_summary['A1'].font = Font(bold=True, size=16, color="800000")
        ws_summary.merge_cells('A1:B1')
        
        # Параметры кампании
        row_num = 3
        ws_summary.cell(row=row_num, column=1, value="ПАРАМЕТРЫ КАМПАНИИ").font = bold_font
        row_num += 1
        
        ws_summary.cell(row=row_num, column=1, value="Радиостанции:").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=', '.join(user_data.get('selected_radios', [])))
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Период (дней):").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=user_data.get('campaign_period_days', 30))
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Хронометраж ролика (сек):").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=user_data.get('base_duration', DEFAULT_DURATION))
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Выходов/день на всех станциях:").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=user_data.get('total_outputs_day', 0))
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Общее количество выходов за период:").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=user_data.get('total_outputs_period', 0))
        row_num += 1
        
        # Финансы
        row_num += 2
        ws_summary.cell(row=row_num, column=1, value="ФИНАНСОВАЯ ИНФОРМАЦИЯ").font = bold_font
        row_num += 1
        
        ws_summary.cell(row=row_num, column=1, value="Позиция").fill = header_fill
        ws_summary.cell(row=row_num, column=1, value="Позиция").font = header_font
        ws_summary.cell(row=row_num, column=2, value="Сумма (₽)").fill = header_fill
        ws_summary.cell(row=row_num, column=2, value="Сумма (₽)").font = header_font
        row_num += 1
        
        ws_summary.cell(row=row_num, column=1, value="Базовая стоимость эфира (до наценок и скидок)")
        ws_summary.cell(row=row_num, column=2, value=user_data.get('air_cost_base', 0)).number_format = '#,##0 ₽'
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Стоимость эфира с наценками (прайм/рубрика)")
        ws_summary.cell(row=row_num, column=2, value=user_data.get('air_cost_final', 0)).number_format = '#,##0 ₽'
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Скидка 50% (от стоимости эфира)").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=-discount).number_format = '#,##0 ₽'
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Итого стоимость эфира (со скидкой)")
        ws_summary.cell(row=row_num, column=2, value=user_data.get('discounted_air_cost', 0)).number_format = '#,##0 ₽'
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Стоимость производства ролика")
        ws_summary.cell(row=row_num, column=2, value=user_data.get('production_cost', 0)).number_format = '#,##0 ₽'
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="ИТОГО К ОПЛАТЕ").font = Font(bold=True, size=11, color="800000")
        ws_summary.cell(row=row_num, column=2, value=final_price).number_format = '#,##0 ₽'
        row_num += 1
        
        # Охват (ОБНОВЛЕНО)
        row_num += 2
        ws_summary.cell(row=row_num, column=1, value="ОХВАТ КАМПАНИИ").font = bold_font
        row_num += 1
        
        ws_summary.cell(row=row_num, column=1, value="Ежедневный охват в день (Суммарно)").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=daily_listeners).number_format = '#,##0 человек'
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Уникальный охват в день (Расчетно)").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=user_data.get('unique_daily_reach', 0)).number_format = '#,##0 человек'
        row_num += 1
        ws_summary.cell(row=row_num, column=1, value="Охват всего за период").font = bold_font
        ws_summary.cell(row=row_num, column=2, value=total_reach).number_format = '#,##0 человек'
        row_num += 1
        
        # Автоширина для листа "Сводка"
        for col in ws_summary.columns:
            max_length = 0
            column = col[0].column
            for cell in col:
                try:
                    # Упрощенная оценка для чисел, чтобы учесть разделители и валюту
                    val = str(cell.value)
                    if cell.number_format:
                        val = format_number(cell.value) if isinstance(cell.value, (int, float)) else str(cell.value)
                        
                    if len(val) > max_length:
                        max_length = len(val)
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws_summary.column_dimensions[get_column_letter(column)].width = adjusted_width
            
        # --- ЛИСТ 2: ДЕТАЛИЗИРОВАННОЕ РАСПИСАНИЕ ---
        ws_schedule = wb.create_sheet(title="Расписание")
        
        # Получаем данные
        period_days = user_data.get('campaign_period_days', 30)
        selected_radios = user_data.get('selected_radios', [])
        selected_slots_indices = user_data.get('selected_time_slots', [])
        spots_per_slot = user_data.get('spots_per_slot', 5)
        
        # Начальная дата: для простоты возьмем сегодня
        start_date = datetime.now().date()
        
        # 1. Заголовки (Радиостанции)
        radio_row = 1
        col_offset = 2
        
        # Первый столбец - время
        ws_schedule.cell(row=radio_row, column=1, value="Время выхода ролика")
        ws_schedule.column_dimensions['A'].width = 20
        
        for radio in selected_radios:
            ws_schedule.cell(row=radio_row, column=col_offset, value=radio).font = bold_font
            ws_schedule.merge_cells(start_row=radio_row, start_column=col_offset, end_row=radio_row, end_column=col_offset + period_days - 1)
            ws_schedule.cell(row=radio_row, column=col_offset).alignment = Alignment(horizontal='center')
            col_offset += period_days

        # 2. Строка с датами
        date_row = 2
        col_offset = 2
        for _ in selected_radios:
            for i in range(period_days):
                date = start_date + timedelta(days=i)
                ws_schedule.cell(row=date_row, column=col_offset + i, value=date).number_format = 'DD-MM'
                ws_schedule.cell(row=date_row, column=col_offset + i).alignment = Alignment(text_rotation=90)
                ws_schedule.column_dimensions[get_column_letter(col_offset + i)].width = 3
            col_offset += period_days

        # 3. Заполнение расписания (перебираем станции и слоты)
        start_data_row = 3
        
        for slot_index in selected_slots_indices:
            slot = TIME_SLOTS_DATA[slot_index]
            ws_schedule.cell(row=start_data_row, column=1, value=slot['time'])
            
            col_offset = 2 # Начинаем заполнять со второго столбца
            for _ in selected_radios:
                for i in range(period_days):
                    # Проставляем 5 выходов (spots_per_slot) в каждой ячейке
                    ws_schedule.cell(row=start_data_row, column=col_offset + i, value=spots_per_slot)
                    ws_schedule.cell(row=start_data_row, column=col_offset + i).alignment = Alignment(horizontal='center')
                col_offset += period_days

            start_data_row += 1

        # 4. Итоговые строки
        
        # Строка "Всего выходов"
        total_outputs_row = start_data_row 
        ws_schedule.cell(row=total_outputs_row, column=1, value="Всего выходов").font = bold_font
        
        col_offset = 2
        for _ in selected_radios:
            # Суммируем выходы по слотам и дням
            for i in range(period_days):
                # Формула SUM(B3:B[start_data_row - 1])
                sum_formula = f"=SUM({get_column_letter(col_offset + i)}{3}:{get_column_letter(col_offset + i)}{start_data_row - 1})"
                ws_schedule.cell(row=total_outputs_row, column=col_offset + i, value=sum_formula)
                ws_schedule.cell(row=total_outputs_row, column=col_offset + i).font = bold_font
            
            col_offset += period_days
        
        # Сохраняем и возвращаем
        wb.save(buffer)
        excel_data = buffer.getvalue()
        buffer.close()
        
        logger.info(f"Excel успешно создан для кампании #{campaign_number}")
        return excel_data
        
    except Exception as e:
        logger.error(f"Ошибка при создании Excel: {e}")
        return None

# Отправка Excel (обновлено)
async def send_excel_file(update: Update, context: ContextTypes.DEFAULT_TYPE, campaign_number: str):
    try:
        excel_data = create_excel_file(context.user_data, campaign_number)
        
        if not excel_data:
            return False
            
        file_io = io.BytesIO(excel_data)
        file_io.name = f"mediaplan_{campaign_number}.xlsx"
        
        # Определяем, откуда пришел запрос
        if update.callback_query:
            message_obj = update.callback_query.message
        elif update.message:
            message_obj = update.message
        else:
            return False

        await message_obj.reply_document(
            document=file_io,
            filename=f"mediaplan_{campaign_number}.xlsx",
            caption=f"💾 Ваш детализированный медиаплан кампании #{campaign_number} в Excel"
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке Excel: {e}")
        return False

# Отправка уведомления админу (ОБНОВЛЕНО: Детализация охвата, удаление PDF)
async def send_admin_notification(context, user_data, campaign_number):
    """Отправка уведомления админу о новой заявке"""
    try:
        base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(user_data)
        
        notification_text = f"""
🔔 **НОВАЯ ЗАЯВКА** `{campaign_number}`
──────────────
**👤 КЛИЕНТ:**
Имя: {user_data.get('contact_name', 'Не указано')}
Телефон: `{user_data.get('phone', 'Не указан')}`
Email: `{user_data.get('email', 'Не указан')}`
Компания: {user_data.get('company', 'Не указана')}
Telegram ID: `{context._user_id}`

**💰 СТОИМОСТЬ:**
Базовая стоимость эфира (с наценками): {format_number(user_data.get('air_cost_final', 0))}₽
Скидка 50% (от эфира): -{format_number(discount)}₽
Стоимость производства: {format_number(user_data.get('production_cost', 0))}₽
**Итоговая: {format_number(final_price)}₽**

**🎯 ПАРАМЕТРЫ:**
• Радиостанции: {', '.join(user_data.get('selected_radios', []))}
• Период: {user_data.get('campaign_period_days', 30)} дней
• Хронометраж: {user_data.get('base_duration', DEFAULT_DURATION)} сек
• Выходов/день: {user_data.get('total_outputs_day', 0)}
• Рубрика: {get_branded_section_name(user_data.get('branded_section'))}
• Ролик: {PRODUCTION_OPTIONS.get(user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}

**📊 ОХВАТ:**
• **Охват в день** (Суммарно): ~{format_number(daily_listeners)} чел.
• **Уникальный охват в день**: ~{format_number(user_data.get('unique_daily_reach', 0))} чел.
• **Охват всего за период**: ~{format_number(total_reach)} чел.
"""
        
        # Создаем клавиатуру с кнопками действий (Только Excel)
        keyboard = [
            [
                InlineKeyboardButton(f"{E_XLSX} EXCEL ОТЧЕТ", callback_data=f"generate_excel_admin_{campaign_number}"),
            ],
            [
                InlineKeyboardButton(f"📞 {user_data.get('phone', 'Телефон')}", callback_data=f"call_{user_data.get('phone', '')}"),
                InlineKeyboardButton(f"✉️ Email", callback_data=f"email_{user_data.get('email', '')}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=notification_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"Уведомление админу отправлено для кампании #{campaign_number}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")
        return False


# --- ВСЕ ФУНКЦИИ КОНВЕРСАЦИИ ---

# Главное меню (обновлено: терминология охвата)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"🚀 СОЗДАТЬ КАМПАНИЮ", callback_data="create_campaign")],
        [InlineKeyboardButton("📊 СТАТИСТИКА ОХВАТА", callback_data="statistics")],
        [InlineKeyboardButton("📋 МОИ ЗАКАЗЫ", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ О НАС", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Обновлен текст для охвата и цены
    text = (
        f"🎙️ **РАДИО ТЮМЕНСКОЙ ОБЛАСТИ**\n"
        f"📍 *Ялуторовск • Заводоуковск*\n"
        "📍 Территория +35 км вокруг городов\n"
        "──────────────\n"
        f"{E_REACH} Охват **в день** (Суммарно): **9,200+**\n"
        f"👥 Охват **всего за период** (30 дней): **68,000+**\n"
        f"🎯 **52%** доля местного радиорынка\n"
        f"{E_COST} **2₽/сек** базовая цена"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return MAIN_MENU

# Шаг 1: Выбор радиостанций (обновлено: терминология охвата)
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
    
    keyboard = []
    radio_stations = [
        ("LOVE RADIO", "radio_love", 1600, '👩 Молодёжь 18-35 лет'),
        ("АВТОРАДИО", "radio_auto", 1400, '👨 Автомобилисты 25-50 лет'),
        ("РАДИО ДАЧА", "radio_dacha", 1800, '👨👩 Семья 35-65 лет'), 
        ("РАДИО ШАНСОН", "radio_chanson", 1200, '👨 Мужчины 30-60 лет'),
        ("РЕТРО FM", "radio_retro", 1500, '👴👵 Ценители хитов 30-55 лет'),
        ("ЮМОР FM", "radio_humor", 1100, '👦👧 Слушатели 25-45 лет')
    ]
    
    for name, callback, listeners, _ in radio_stations:
        emoji = E_CHECK if name in selected_radios else E_UNCHECK
        button_text = f"{emoji} {name} ({format_number(listeners)} ч/день)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])
    
    keyboard.append([InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_main")])
    keyboard.append([InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_campaign_period")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"**ШАГ 1/7: ВЫБОР РАДИОСТАНЦИЙ {E_RADIO}**\n"
        "──────────────\n"
        f"{E_CHECK if 'LOVE RADIO' in selected_radios else E_UNCHECK} **LOVE RADIO** | *1,600* | Молодёжь 18-35\n"
        f"{E_CHECK if 'АВТОРАДИО' in selected_radios else E_UNCHECK} **АВТОРАДИО** | *1,400* | Автомобилисты 25-50\n"
        f"{E_CHECK if 'РАДИО ДАЧА' in selected_radios else E_UNCHECK} **РАДИО ДАЧА** | *1,800* | Семья 35-65\n"
        f"{E_CHECK if 'РАДИО ШАНСОН' in selected_radios else E_UNCHECK} **РАДИО ШАНСОН** | *1,200* | Мужчины 30-60\n"
        f"{E_CHECK if 'РЕТРО FM' in selected_radios else E_UNCHECK} **РЕТРО FM** | *1,500* | Ценители хитов 30-55\n"
        f"{E_CHECK if 'ЮМОР FM' in selected_radios else E_UNCHECK} **ЮМОР FM** | *1,100* | Слушатели 25-45\n"
        "──────────────\n"
        f"**ВЫБРАНО:** {len(selected_radios)} станции | {E_REACH} Охват **в день**: {format_number(total_listeners)} слушателей\n"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return RADIO_SELECTION

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
    
    elif query.data == "to_campaign_period":
        if not context.user_data.get('selected_radios'):
            await query.answer(f"{E_CANCEL} Выберите хотя бы одну радиостанцию!", show_alert=True)
            return RADIO_SELECTION
        return await campaign_period(update, context)
    
    return RADIO_SELECTION

# Шаг 2: Период кампании (обновлено: отображение цены)
async def campaign_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_period = context.user_data.get('campaign_period')
    selected_radios = context.user_data.get('selected_radios', [])
    
    # Информация о выбранных станциях
    stations_info = "📻 **ВЫБРАНЫ СТАНЦИИ:**\n"
    station_listeners = {
        'LOVE RADIO': 1600, 'АВТОРАДИО': 1400, 'РАДИО ДАЧА': 1800,
        'РАДИО ШАНСОН': 1200, 'РЕТРО FM': 1500, 'ЮМОР FM': 1100
    }
    
    for radio in selected_radios:
        listeners = station_listeners.get(radio, 0)
        stations_info += f"• *{radio}* ({format_number(listeners)} ч/день)\n"
    
    keyboard = []
    # Обновлен расчет для отображения более реалистичной цены (20 сек * 2р/сек)
    base_duration_calc = context.user_data.get('custom_duration', DEFAULT_DURATION)
    price_per_spot_calc = base_duration_calc * BASE_PRICE_PER_SECOND 
    
    for key, option in PERIOD_OPTIONS.items():
        is_selected = E_CHECK if selected_period == key else E_UNCHECK
        # Расчет стоимости для каждого периода (примерная цена эфира после скидки)
        # 5 выходов/слот * 10 слотов (для оценки) * цена_выхода * дней / 2 (скидка)
        base_cost_estimate = 5 * 10 * price_per_spot_calc * option['days'] * len(selected_radios)
        discounted_cost = base_cost_estimate * 0.5
        
        keyboard.append([
            InlineKeyboardButton(
                f"{is_selected} {option['name']} - {format_number(int(discounted_cost))}₽", 
                callback_data=f"period_{key}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_radio")])
    keyboard.append([InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_time_slots")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"**ШАГ 2/7: ПЕРИОД КАМПАНИИ {E_PERIOD}**\n"
        "──────────────\n"
        f"{stations_info}\n"
        f"📅 **ВЫБЕРИТЕ ПЕРИОД КАМПАНИИ**:\n\n"
        f"🎯 Старт кампании: в течение *3 дней* после подтверждения\n"
        f"⏱️ Минимальный период: **15 дней**\n\n"
        f"Цены указаны со скидкой 50% и для 20 сек ролика"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return CAMPAIGN_PERIOD

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
            await query.answer(f"{E_CANCEL} Выберите период кампании!", show_alert=True)
            return CAMPAIGN_PERIOD
        return await time_slots(update, context)
    
    return CAMPAIGN_PERIOD

# Шаг 3: Временные слоты (обновлено: терминология охвата)
async def time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_slots = context.user_data.get('selected_time_slots', [])
    selected_radios = context.user_data.get('selected_radios', [])
    period_days = context.user_data.get('campaign_period_days', 30)
    
    # Создаем клавиатуру с временными слотами
    keyboard = []
    
    # Кнопка "Выбрать все"
    keyboard.append([InlineKeyboardButton(f"{E_CHECK} ВЫБРАТЬ ВСЕ СЛОТЫ", callback_data="select_all_slots")])
    
    # Утренние слоты
    keyboard.append([InlineKeyboardButton("🌅 УТРЕННИЕ СЛОТЫ (ПРЕМИУМ)", callback_data="header_morning")])
    for i in range(4):
        slot = TIME_SLOTS_DATA[i]
        emoji = E_CHECK if i in selected_slots else E_UNCHECK
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    # Дневные слоты
    keyboard.append([InlineKeyboardButton("☀️ ДНЕВНЫЕ СЛОТЫ", callback_data="header_day")])
    for i in range(4, 10):
        slot = TIME_SLOTS_DATA[i]
        emoji = E_CHECK if i in selected_slots else E_UNCHECK
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    # Вечерние слоты
    keyboard.append([InlineKeyboardButton("🌇 ВЕЧЕРНИЕ СЛОТЫ (ПРЕМИУМ)", callback_data="header_evening")])
    for i in range(10, 15):
        slot = TIME_SLOTS_DATA[i]
        emoji = E_CHECK if i in selected_slots else E_UNCHECK
        button_text = f"{emoji} {slot['time']} • {slot['label']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"time_{i}")])
    
    keyboard.append([InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_period")])
    keyboard.append([InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_branded_sections")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    total_slots = len(selected_slots)
    total_outputs_per_day = total_slots * 5 * len(selected_radios)
    total_outputs_period = total_outputs_per_day * period_days
    
    # Информация о выбранных параметрах
    stations_text = "📻 **СТАНЦИИ:** " + ", ".join([f"*{radio}*" for radio in selected_radios])
    
    text = (
        f"**ШАГ 3/7: ВРЕМЕННЫЕ СЛОТЫ {E_TIME}**\n"
        "──────────────\n"
        f"{stations_text}\n"
        f"{E_PERIOD} **ПЕРИОД:** {period_days} дней\n"
        f"─────────────────\n"
        f"🕒 **ВЫБЕРИТЕ ВРЕМЯ ВЫХОДА РОЛИКОВ**\n\n"
        f"📊 **Статистика выбора:**\n"
        f"• Выбрано слотов: **{total_slots}**\n"
        f"• Выходов **в день** на всех радио: **{total_outputs_per_day}**\n"
        f"• Всего выходов **за период**: **{format_number(total_outputs_period)}**\n\n"
        f"🎯 Выберите подходящие временные интервалы"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return TIME_SLOTS

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
            await query.answer(f"{E_CANCEL} Выберите хотя бы один временной слот!", show_alert=True)
            return TIME_SLOTS
        return await branded_sections(update, context)
    
    return TIME_SLOTS

# Шаг 4: Брендированные рубрики (обновлено: навигация)
async def branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_branded = context.user_data.get('branded_section')
    
    keyboard = [
        [InlineKeyboardButton(f"{E_CHECK} АВТОРУБРИКИ (+20%)" if selected_branded == 'auto' else f"{E_UNCHECK} АВТОРУБРИКИ (+20%)", callback_data="branded_auto")],
        [InlineKeyboardButton(f"{E_CHECK} НЕДВИЖИМОСТЬ (+15%)" if selected_branded == 'realty' else f"{E_UNCHECK} НЕДВИЖИМОСТЬ (+15%)", callback_data="branded_realty")],
        [InlineKeyboardButton(f"{E_CHECK} МЕДИЦИНСКИЕ РУБРИКИ (+25%)" if selected_branded == 'medical' else f"{E_UNCHECK} МЕДИЦИНСКИЕ РУБРИКИ (+25%)", callback_data="branded_medical")],
        [InlineKeyboardButton(f"{E_CHECK} ИНДИВИДУАЛЬНАЯ РУБРИКА (+30%)" if selected_branded == 'custom' else f"{E_UNCHECK} ИНДИВИДУАЛЬНАЯ РУБРИКА (+30%)", callback_data="branded_custom")],
        [InlineKeyboardButton("📋 Посмотреть пример", callback_data="show_example")],
        [InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_time_slots")],
        [InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_campaign_creator")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"**ШАГ 4/7: БРЕНДИРОВАННЫЕ РУБРИКИ 🏷️**\n"
        "──────────────\n"
        "Выбор рубрики увеличивает охват и таргетирует вашу аудиторию, но добавляет наценку к стоимости эфира.\n\n"
        "**🎯 ВЫБЕРИТЕ ТЕМАТИЧЕСКУЮ РУБРИКУ** (один выбор)"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return BRANDED_SECTIONS

async def handle_branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_time_slots":
        return await time_slots(update, context)
    
    elif query.data.startswith("branded_"):
        section = query.data.replace("branded_", "")
        context.user_data['branded_section'] = section
        return await branded_sections(update, context)
    
    elif query.data == "to_campaign_creator":
        return await campaign_creator(update, context)
    
    return BRANDED_SECTIONS

# Шаг 5: Конструктор ролика (ОБНОВЛЕНО: Новые кнопки, навигация)
async def campaign_creator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Определяем объект для ответа (Query или Message)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
    
    # Предварительно устанавливаем production_option и custom_duration, если их нет
    if 'production_option' not in context.user_data:
        context.user_data['production_option'] = 'ready' # По умолчанию "Готовый ролик"
    if 'custom_duration' not in context.user_data:
        context.user_data['custom_duration'] = DEFAULT_DURATION
        
    production_option = context.user_data['production_option']
    
    # Формирование кнопок выбора опции производства
    keyboard_options = []
    for key, option in PRODUCTION_OPTIONS.items():
        emoji = E_CHECK if production_option == key else E_UNCHECK
        keyboard_options.append([
            InlineKeyboardButton(f"{emoji} {option['name']} ({format_number(option['price'])}₽)", callback_data=f"prod_option_{key}")
        ])
    
    # Блок ввода/выбора текста и хронометража (НОВЫЙ ФЛОУ)
    keyboard_actions = [
        # Кнопка "Ввести текст ролика" - исправлено
        [InlineKeyboardButton(f"{E_TEXT} ВВЕСТИ ТЕКСТ РОЛИКА {E_TEXT}", callback_data="action_input_text")], 
        [
            # Кнопка "Указать хронометраж" - НОВОЕ
            InlineKeyboardButton(f"⏱️ УКАЗАТЬ ХРОНОМЕТРАЖ", callback_data="action_input_duration"),
        ],
        [
            # Навигация
            InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_branded"),
            InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_production_option")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard_options + keyboard_actions)
    
    # Динамический текст
    duration = context.user_data.get('custom_duration', DEFAULT_DURATION)
    production_cost = PRODUCTION_OPTIONS[production_option]['price']
    
    text = (
        f"**ШАГ 5/7: КОНСТРУКТОР РОЛИКА {E_MIC}**\n"
        "──────────────\n"
        f"Текущий хронометраж: **{duration} сек**\n"
        f"Выбранная опция: **{PRODUCTION_OPTIONS[production_option]['name']}** ({format_number(production_cost)}₽)\n"
        f"Описание: *{PRODUCTION_OPTIONS[production_option]['desc']}*\n"
        "────────────────\n"
        f"**1. ВЫБЕРИТЕ ВАРИАНТ ПРОИЗВОДСТВА:**\n"
        f"**2. ОПРЕДЕЛИТЕ ХРОНОМЕТРАЖ И ТЕКСТ:**"
    )
    
    if update.callback_query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
         await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
         
    return CAMPAIGN_CREATOR

async def handle_campaign_creator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_to_branded":
        return await branded_sections(update, context)

    elif data.startswith("prod_option_"):
        option = data.replace("prod_option_", "")
        context.user_data['production_option'] = option
        context.user_data['production_cost'] = PRODUCTION_OPTIONS[option]['price']
        return await campaign_creator(update, context)

    elif data == "action_input_text":
        await query.edit_message_text(
            f"{E_TEXT} **ВВОД ТЕКСТА РОЛИКА**\n\n"
            "Пожалуйста, отправьте мне текст, который вы хотите озвучить в ролике.\n"
            "После этого вы сможете прослушать пример звучания (Mock TTS) и оценить длительность.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_creator")]
            ]),
            parse_mode='Markdown'
        )
        return WAITING_TEXT

    elif data == "action_input_duration":
        await query.edit_message_text(
            f"⏱️ **УКАЗАНИЕ ХРОНОМЕТРАЖА**\n\n"
            "Введите желаемый хронометраж ролика в **секундах** (например: `15`, `25`, `40`).\n"
            "Это число будет использовано для расчета стоимости эфира.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_creator")]
            ]),
            parse_mode='Markdown'
        )
        return WAITING_DURATION
        
    elif data == "to_production_option":
        # Проверяем, если ролик готовый, то идем дальше
        if context.user_data.get('production_option') == 'ready' or context.user_data.get('campaign_text'):
            return await contact_info(update, context)
        
        # Если ролик требует производства, проверяем наличие текста
        elif context.user_data.get('production_option') != 'ready' and not context.user_data.get('campaign_text'):
            await query.answer(f"{E_CANCEL} Вы выбрали производство ролика. Пожалуйста, введите текст!", show_alert=True)
            return CAMPAIGN_CREATOR

    return CAMPAIGN_CREATOR

# НОВОЕ СОСТОЯНИЕ: Ожидание хронометража
async def process_custom_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        duration = int(text.strip())
        if 5 <= duration <= 60:
            context.user_data['custom_duration'] = duration
            await update.message.reply_text(
                f"✅ Хронометраж **{duration} сек** сохранен. Он будет использован для расчета стоимости эфира.",
                parse_mode='Markdown'
            )
            # Возвращаемся в конструктор ролика
            return await campaign_creator(update, context) 
        else:
            await update.message.reply_text("⏱️ Пожалуйста, введите число от 5 до 60 (секунд).")
            return WAITING_DURATION
    except ValueError:
        await update.message.reply_text("❌ Введите хронометраж только числом.")
        return WAITING_DURATION

# ИСПРАВЛЕНО: Обработка текста ролика с функцией mock TTS
async def process_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    campaign_text = update.message.text
    context.user_data['campaign_text'] = campaign_text
    
    # 1. Отправляем текст обратно
    await update.message.reply_text(
        f"✅ Текст сохранен:\n\n---\n*{campaign_text}*\n---",
        parse_mode='Markdown'
    )

    # 2. Имитируем генерацию TTS и отправляем аудио
    audio_file = mock_generate_tts_audio()
    
    # 3. Предлагаем послушать (имитация) и подтвердить
    keyboard = [
        [InlineKeyboardButton(f"{E_TTS} ПРОСЛУШАТЬ ПРИМЕР (Mock)", callback_data="action_listen_tts")],
        [InlineKeyboardButton(f"✅ ПОДТВЕРДИТЬ ТЕКСТ", callback_data="action_confirm_text")],
        [InlineKeyboardButton(f"{E_BACK} НАЗАД/ИЗМЕНИТЬ", callback_data="back_to_creator")]
    ]
    
    await update.message.reply_document(
        document=InputFile(audio_file, filename='sample.mp3'),
        caption="🎧 Примерное звучание вашего текста (Mock TTS) и оценка длительности. Нажмите, чтобы подтвердить.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return CONFIRM_TEXT

# НОВОЕ СОСТОЯНИЕ: Подтверждение текста после TTS
async def handle_confirm_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "action_listen_tts":
        # Поскольку это mock, просто отвечаем
        await query.answer("Прослушивание имитировано. Длительность оценена в 20 сек.")
        return CONFIRM_TEXT
        
    elif data == "action_confirm_text":
        # Текст подтвержден, вычисляем примерный хронометраж
        # Для простоты: 10 символов = 1 секунда, мин 10 сек, макс 60 сек
        text_len = len(context.user_data.get('campaign_text', ''))
        estimated_duration = max(10, min(60, round(text_len / 10))) 
        
        # Обновляем хронометраж, если он не был установлен вручную
        if 'custom_duration' not in context.user_data:
             context.user_data['custom_duration'] = estimated_duration
             
        await query.edit_message_text(
            f"✅ Текст подтвержден.\n"
            f"Расчетный хронометраж: **{context.user_data.get('custom_duration')} сек**.\n\n"
            f"Переходим к шагу ввода контактов.",
            parse_mode='Markdown'
        )
        return await contact_info(update, context) # Переход к контактам

    elif data == "back_to_creator":
        # Возврат в конструктор для изменения текста/параметров
        return await campaign_creator(update, context)
        
    return CONFIRM_TEXT

# Функция для возврата в главное меню/конструктор ролика
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_to_creator":
        return await campaign_creator(update, context)
        
    # Обработка админских кнопок (без изменений, кроме удаления PDF)
    if data.startswith("generate_excel_admin_"):
        campaign_number = data.replace("generate_excel_admin_", "")
        await send_excel_file(update, context, campaign_number)
        return
        
    elif data.startswith("call_"):
        phone = data.replace("call_", "")
        await query.answer(f"Телефон: {phone}", show_alert=True)
        return
        
    elif data.startswith("email_"):
        email = data.replace("email_", "")
        await query.answer(f"Email: {email}", show_alert=True)
        return
        
    # Если это просто возврат в главное меню
    return await start(update, context)

# Шаг 6: Контактная информация (обновлено: хронометраж, охват)
async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    # Определяем объект для ответа (Query или Message)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message_obj = query.message
    else:
        message_obj = update.message

    keyboard = [
        [InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_creator")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Расчет для отображения
    base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(context.user_data)
    
    text = (
        f"**ШАГ 6/7: КОНТАКТНАЯ ИНФОРМАЦИЯ 📞**\n"
        "──────────────\n"
        f"**ВАШ ЗАКАЗ:**\n"
        f"• Хронометраж: **{context.user_data.get('base_duration', DEFAULT_DURATION)} сек**\n"
        f"• Радиостанций: **{len(context.user_data.get('selected_radios', []))}**\n"
        f"• Итоговая стоимость: **{format_number(final_price)}₽**\n"
        f"• Охват **всего за период**: **{format_number(total_reach)}** чел.\n"
        "────────────────\n"
        "Пожалуйста, отправьте свои контактные данные одним сообщением в формате:\n"
        "**Имя, Компания, Телефон, Email**\n\n"
        "*Пример: Иван Петров, ООО РадиоПроект, +79001234567, ivan@example.com*"
    )
    
    await message_obj.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return CONTACT_INFO

# Обработка контактов (без изменений)
async def process_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    parts = [part.strip() for part in text.split(',')]
    
    if len(parts) < 4:
        await update.message.reply_text("❌ Ошибка: Введите все 4 поля через запятую: **Имя, Компания, Телефон, Email**.")
        return CONTACT_INFO
        
    contact_name, company, phone, email = parts[:4]
    
    if not validate_phone(phone):
        await update.message.reply_text("❌ Ошибка: Некорректный формат телефона. Пожалуйста, используйте формат `+79001234567` или `89001234567`.")
        return CONTACT_INFO
        
    context.user_data.update({
        'contact_name': contact_name,
        'company': company,
        'phone': phone,
        'email': email
    })
    
    # Генерируем номер кампании
    campaign_number = datetime.now().strftime("%Y%m%d%H%M")
    context.user_data['campaign_number'] = campaign_number
    
    base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(context.user_data)
    
    # Сохранение в БД
    try:
        conn = sqlite3.connect('campaigns.db')
        cursor = conn.cursor()
        
        cursor.execute(f"""
            INSERT INTO campaigns (user_id, campaign_number, radio_stations, campaign_period, time_slots, branded_section, campaign_text, production_option, contact_name, company, phone, email, base_price, discount, final_price, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            update.effective_user.id,
            campaign_number,
            ', '.join(context.user_data.get('selected_radios', [])),
            context.user_data.get('campaign_period'),
            ', '.join(map(str, context.user_data.get('selected_time_slots', []))),
            context.user_data.get('branded_section'),
            context.user_data.get('campaign_text'),
            context.user_data.get('production_option'),
            contact_name, company, phone, email,
            base_price, discount, final_price, 'pending'
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Кампания #{campaign_number} успешно сохранена в БД.")
    except Exception as e:
        logger.error(f"Ошибка сохранения в БД: {e}")

    await send_admin_notification(context, context.user_data, campaign_number)

    return await final_actions(update, context)

# Шаг 7: Финальные действия (обновлено: только Excel)
async def final_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    # Определяем объект для ответа (Query или Message)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message_obj = query.message
    else:
        message_obj = update.message
        
    campaign_number = context.user_data.get('campaign_number')
    final_price = calculate_campaign_price_and_reach(context.user_data)[2]
    
    text = (
        f"**🎉 ЗАЯВКА ПРИНЯТА!**\n\n"
        f"Ваша кампания **#{campaign_number}** успешно создана и сохранена.\n"
        f"Итоговая стоимость: **{format_number(final_price)}₽**\n\n"
        f"Менеджер свяжется с вами в течение 30 минут для подтверждения заказа и деталей.\n"
        f"Вы можете сразу скачать детализированный медиаплан в Excel."
    )
    
    keyboard = [
        [InlineKeyboardButton(f"{E_XLSX} СКАЧАТЬ EXCEL", callback_data=f"generate_excel_user_{campaign_number}")],
        [InlineKeyboardButton(f"📋 МОИ ЗАКАЗЫ", callback_data="my_orders")]
    ]
    
    await message_obj.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return FINAL_ACTIONS

# Обработка финальных действий (обновлено: только Excel)
async def handle_final_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("generate_excel_user_"):
        campaign_number = data.replace("generate_excel_user_", "")
        success = await send_excel_file(update, context, campaign_number)
        if success:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ EXCEL СКАЧАН", callback_data="dummy_excel_downloaded")],
                [InlineKeyboardButton(f"📋 МОИ ЗАКАЗЫ", callback_data="my_orders")]
            ]))
        return FINAL_ACTIONS
    
    elif data == "my_orders":
        # Логика показа моих заказов (заглушка)
        await query.answer("Показ истории заказов (функция в разработке).")
        return FINAL_ACTIONS
        
    return FINAL_ACTIONS

# Основная функция (обновлено: ConversationHandler)
def main():
    # Инициализация БД
    if not init_db():
        logger.error("Критическая ошибка: Не удалось инициализировать базу данных.")
        return

    application = Application.builder().token(TOKEN).build()
    
    # Обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(radio_selection, pattern='^create_campaign$'),
                CallbackQueryHandler(start, pattern='^(statistics|my_orders|about)$') # Заглушка для других кнопок
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
                CallbackQueryHandler(handle_campaign_creator, pattern='^.*$')
            ],
            WAITING_DURATION: [ # НОВОЕ СОСТОЯНИЕ
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_custom_duration),
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_creator$') 
            ],
            WAITING_TEXT: [ # ИСПРАВЛЕНО
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_campaign_text),
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_creator$')
            ],
            CONFIRM_TEXT: [ # НОВОЕ СОСТОЯНИЕ
                CallbackQueryHandler(handle_confirm_text, pattern='^.*$')
            ],
            CONTACT_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_contact_info),
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_creator$') # Возврат на шаг 5
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
    # Удалена 'generate_pdf_' и 'get_pdf_'
    application.add_handler(CallbackQueryHandler(
        handle_main_menu, 
        pattern='^(generate_excel_admin_|call_|email_)'
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
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
