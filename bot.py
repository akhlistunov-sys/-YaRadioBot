import os
import logging
import sqlite3
import io
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from reportlab.lib.pagesizes import A4 
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ВОССТАНОВЛЕННЫЕ ОРИГИНАЛЬНЫЕ СОСТОЯНИЯ ---
MAIN_MENU, RADIO_SELECTION, CAMPAIGN_PERIOD, TIME_SLOTS, BRANDED_SECTIONS, \
CAMPAIGN_CREATOR, PRODUCTION_OPTION, CONTACT_INFO, FINAL_ACTIONS = range(9)

# Токен бота
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

# Ваш Telegram ID для уведомлений
ADMIN_TELEGRAM_ID = 174046571  # Твой числовой ID

# Цены и параметры
BASE_PRICE_PER_SECOND = 4
MIN_PRODUCTION_COST = 2000
MIN_BUDGET = 7000

TIME_SLOTS_DATA = [
    {"time": "06:00-09:00", "multipliers": {"Пн": 1.2, "Вт": 1.2, "Ср": 1.2, "Чт": 1.2, "Пт": 1.5, "Сб": 0.8, "Вс": 0.8}, "base_rate": 20},
    {"time": "09:00-14:00", "multipliers": {"Пн": 1.0, "Вт": 1.0, "Ср": 1.0, "Чт": 1.0, "Пт": 1.2, "Сб": 0.9, "Вс": 0.9}, "base_rate": 20},
    {"time": "14:00-19:00", "multipliers": {"Пн": 1.1, "Вт": 1.1, "Ср": 1.1, "Чт": 1.1, "Пт": 1.3, "Сб": 0.8, "Вс": 0.8}, "base_rate": 20},
    {"time": "19:00-24:00", "multipliers": {"Пн": 0.9, "Вт": 0.9, "Ср": 0.9, "Чт": 0.9, "Пт": 1.1, "Сб": 1.0, "Вс": 1.0}, "base_rate": 20},
    {"time": "24:00-06:00", "multipliers": {"Пн": 0.7, "Вт": 0.7, "Ср": 0.7, "Чт": 0.7, "Пт": 0.8, "Сб": 0.7, "Вс": 0.7}, "base_rate": 20},
]

RADIO_STATIONS = [
    {"id": "CITY", "name": "Радио СИТИ 105,9 FM", "base_price": BASE_PRICE_PER_SECOND},
    {"id": "DACHA", "name": "Радио ДАЧА 105,9 FM", "base_price": BASE_PRICE_PER_SECOND},
]

# --- DB SETUP (Оставлено без изменений) ---

def init_db():
    conn = sqlite3.connect('campaigns.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            radio_id TEXT,
            radio_name TEXT,
            start_date TEXT,
            end_date TEXT,
            total_days INTEGER,
            time_slots TEXT,
            days_of_week TEXT,
            is_branded INTEGER,
            production_needed INTEGER,
            contact_name TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            company_name TEXT,
            total_budget REAL,
            creation_date TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect('campaigns.db')

def calculate_budget(context):
    # Логика расчета бюджета (упрощенная)
    data = context.user_data
    radio_station = next((r for r in RADIO_STATIONS if r['id'] == data.get('radio_id')), None)
    
    if not radio_station or 'start_date' not in data or 'end_date' not in data:
        return 0, 0

    total_budget = 0
    total_slots = 0
    
    try:
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        
        selected_slots = data.get('selected_time_slots', [])
        
        current_date = start_date
        while current_date <= end_date:
            day_of_week_rus = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][current_date.weekday()]
            
            if day_of_week_rus in data['days_of_week']:
                for slot_time in selected_slots:
                    slot_data = next((s for s in TIME_SLOTS_DATA if s['time'] == slot_time), None)
                    if slot_data:
                        multiplier = slot_data['multipliers'].get(day_of_week_rus, 1.0)
                        
                        duration_seconds = slot_data['base_rate'] 
                        
                        # Применяем мультипликатор брендинга, если выбран
                        branded_multiplier = 1.15 if data.get('is_branded') else 1.0

                        price_per_slot = radio_station['base_price'] * duration_seconds * multiplier * branded_multiplier
                        total_budget += price_per_slot
                        total_slots += 1
                        
            current_date = current_date + timedelta(days=1)
            
        if data.get('production_needed'):
            total_budget += MIN_PRODUCTION_COST
            
    except Exception as e:
        logger.error(f"Error during budget calculation: {e}")
        return 0, 0

    return round(total_budget), total_slots

def generate_excel_compatible_csv_report(context):
    # Генерируем отчет в формате CSV, который легко открывается в Excel
    data = context.user_data
    radio_name = data.get('radio_name', 'Неизвестно')
    total_budget, total_slots = calculate_budget(context)
    
    output = io.StringIO()
    # Заголовок
    output.write("Отчет по заявке на рекламную кампанию\n")
    output.write(f"Дата создания отчета,{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write("\n")
    
    # Основные данные кампании
    # Важно: используем запятую как разделитель
    output.write("Параметр,Значение\n")
    output.write(f"Название компании (Заказчик),{data.get('company_name', 'Не указано')}\n")
    output.write(f"Радиостанция,{radio_name}\n")
    output.write(f"Начало кампании,{data.get('start_date', 'Не указано')}\n")
    output.write(f"Конец кампании,{data.get('end_date', 'Не указано')}\n")
    output.write(f"Дни недели,\"{', '.join(data.get('days_of_week', ['Не указано']))}\"\n") # Кавычки для сложных полей
    output.write(f"Время выхода (Слоты),\n{', '.join(data.get('selected_time_slots', ['Не выбрано']))}\"\n")
    output.write(f"Брендированные секции,{('Да' if data.get('is_branded') else 'Нет')}\n")
    output.write(f"Необходимо производство,{('Да' if data.get('production_needed') else 'Нет')}\n")
    output.write("\n")
    
    # Итоговые расчеты
    output.write("Расчеты\n")
    output.write(f"Общее количество выходов (слотов),{total_slots}\n")
    output.write(f"Оценочный общий бюджет (руб.),{total_budget}\n")
    output.write("\n")
    
    # Контактные данные
    output.write("Контактная информация\n")
    output.write(f"Имя,{data.get('contact_name', 'Не указано')}\n")
    output.write(f"Телефон,{data.get('contact_phone', 'Не указано')}\n")
    output.write(f"Email,{data.get('contact_email', 'Не указано')}\n")

    return output.getvalue(), total_budget, total_slots

# --- HANDLERS (Восстановленная логика) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("Радио СИТИ 105,9 FM", callback_data='radio_CITY')],
        [InlineKeyboardButton("Радио ДАЧА 105,9 FM", callback_data='radio_DACHA')],
        [InlineKeyboardButton("Отмена", callback_data='cancel_text')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "Здравствуйте! Я бот для оформления заявки на размещение рекламы. "
            "Выберите радиостанцию:",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "Выберите радиостанцию:",
            reply_markup=reply_markup
        )
    return RADIO_SELECTION

async def handle_radio_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    radio_id = query.data.split('_')[1]
    radio_station = next((r for r in RADIO_STATIONS if r['id'] == radio_id), None)

    if radio_station:
        context.user_data['radio_id'] = radio_id
        context.user_data['radio_name'] = radio_station['name']
        
        await query.edit_message_text(
            f"Выбрана радиостанция: <b>{radio_station['name']}</b>. "
            "Теперь введите **начальную дату** кампании (формат ГГГГ-ММ-ДД):",
            parse_mode='HTML'
        )
        return CAMPAIGN_PERIOD
    
    return RADIO_SELECTION

async def process_campaign_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 2: Ввод начальной даты
    date_str = update.message.text.strip()
    try:
        start_date = datetime.strptime(date_str, '%Y-%m-%d')
        context.user_data['start_date'] = date_str
        
        # Переходим к ожиданию конечной даты
        context.user_data['awaiting_end_date'] = True 

        await update.message.reply_text(
            f"Начальная дата: <b>{date_str}</b>. "
            "Теперь введите **конечную дату** кампании (формат ГГГГ-ММ-ДД):",
            parse_mode='HTML'
        )
        return CAMPAIGN_PERIOD # Остаемся в CAMPAIGN_PERIOD, ожидая второе сообщение
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Пожалуйста, используйте ГГГГ-ММ-ДД.")
        return CAMPAIGN_PERIOD

async def process_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 2 (продолжение): Ввод конечной даты
    date_str = update.message.text.strip()
    try:
        end_date = datetime.strptime(date_str, '%Y-%m-%d')
        start_date = datetime.strptime(context.user_data['start_date'], '%Y-%m-%d')
        
        if end_date < start_date:
            await update.message.reply_text("Конечная дата не может быть раньше начальной даты. Введите корректную конечную дату:")
            return CAMPAIGN_PERIOD

        context.user_data['end_date'] = date_str
        context.user_data['total_days'] = (end_date - start_date).days + 1
        
        # Сбрасываем флаг и переходим к выбору слотов
        del context.user_data['awaiting_end_date']
        return await prompt_time_slots(update, context)
        
    except ValueError:
        await update.message.reply_text("Неверный формат конечной даты. Пожалуйста, используйте ГГГГ-ММ-ДД.")
        return CAMPAIGN_PERIOD
    except KeyError:
        # Если сюда попали без start_date, просим начать сначала
        await update.message.reply_text("Произошла ошибка (не найдена начальная дата). Пожалуйста, начните заново, введя /start.")
        return ConversationHandler.END


async def handle_campaign_period_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик для CAMPAIGN_PERIOD, который различает ввод первой и второй даты."""
    if context.user_data.get('awaiting_end_date'):
        return await process_end_date(update, context)
    else:
        return await process_campaign_period(update, context)

async def prompt_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 3: Выбор слотов и дней недели
    
    context.user_data['selected_time_slots'] = context.user_data.get('selected_time_slots', [])
    context.user_data['days_of_week'] = context.user_data.get('days_of_week', ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"])

    slot_buttons = [
        [InlineKeyboardButton(
            f"{'✅ ' if slot['time'] in context.user_data['selected_time_slots'] else ''}{slot['time']}", 
            callback_data=f'slot_{slot["time"]}'
        )] 
        for slot in TIME_SLOTS_DATA
    ]
    
    day_buttons = [
        InlineKeyboardButton(
            f"{'✅ ' if day in context.user_data['days_of_week'] else ''}{day}", 
            callback_data=f'day_{day}'
        ) 
        for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ]
    
    done_button = [InlineKeyboardButton("Продолжить (Слоты и Дни выбраны)", callback_data='slots_done')]
    
    keyboard = slot_buttons + [day_buttons] + [done_button]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "Выберите временные слоты для размещения (можно несколько) "
        "и дни недели, если не все (по умолчанию Пн-Вс):\n\n"
        f"Выбранные слоты: {', '.join(context.user_data.get('selected_time_slots', ['Нет']))}\n"
        f"Выбранные дни: {', '.join(context.user_data.get('days_of_week', ['Нет']))}"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
        
    return TIME_SLOTS

async def handle_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    data = context.user_data
    
    if query.data == 'slots_done':
        if not data.get('selected_time_slots'):
            await query.answer("Пожалуйста, выберите хотя бы один временной слот.", show_alert=True)
            return TIME_SLOTS

        # Переход к следующему шагу: BRANDED_SECTIONS
        return await prompt_branded_sections(update, context)

    # Обработка выбора слота или дня
    if query.data.startswith('slot_') or query.data.startswith('day_'):
        
        if query.data.startswith('slot_'):
            slot_time = query.data.split('_')[1]
            slots = data.get('selected_time_slots', [])
            if slot_time in slots:
                slots.remove(slot_time)
            else:
                slots.append(slot_time)
            data['selected_time_slots'] = slots
        
        elif query.data.startswith('day_'):
            day = query.data.split('_')[1]
            days = data.get('days_of_week', ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"])
            if day in days:
                if len(days) > 1:
                    days.remove(day)
                else:
                    await query.answer("Нельзя отменить единственный выбранный день.", show_alert=True)
                    return TIME_SLOTS
            else:
                days.append(day)
                days.sort(key=lambda d: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].index(d))
            data['days_of_week'] = days
        
        # Обновление клавиатуры и текста
        return await prompt_time_slots(query, context)
        
    return TIME_SLOTS # Остаемся, если нажата какая-то другая кнопка

async def prompt_branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 4: Выбор брендированных секций
    context.user_data['is_branded'] = context.user_data.get('is_branded', False) 
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, нужны", callback_data='branded_yes')],
        [InlineKeyboardButton("❌ Нет, не нужны", callback_data='branded_no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "Требуется ли размещение в брендированных секциях (повышает бюджет на 15%)?"
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return BRANDED_SECTIONS

async def handle_branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'branded_yes':
        context.user_data['is_branded'] = True
    elif query.data == 'branded_no':
        context.user_data['is_branded'] = False
        
    # Переход к CAMPAIGN_CREATOR (ввод названия компании)
    await query.edit_message_text(
        "Спасибо! Теперь введите **полное название компании (Заказчика)**:"
    )
    return CAMPAIGN_CREATOR # <-- ВОССТАНОВЛЕНО МЕСТО

async def process_campaign_creator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 5: Ввод названия компании
    company_name = update.message.text.strip()
    
    if len(company_name) < 2 or len(company_name) > 100:
        await update.message.reply_text("Пожалуйста, введите корректное название компании (от 2 до 100 символов).")
        return CAMPAIGN_CREATOR

    context.user_data['company_name'] = company_name

    # Переход к PRODUCTION_OPTION
    return await prompt_production_option(update, context)


async def prompt_production_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 6: Выбор производства
    context.user_data['production_needed'] = context.user_data.get('production_needed', False)
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, требуется (от 2000 руб.)", callback_data='prod_yes')],
        [InlineKeyboardButton("❌ Нет, ролик готов", callback_data='prod_no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "Требуется ли изготовление рекламного ролика?"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        # Переход с CAMPAIGN_CREATOR
        await update.message.reply_text(text, reply_markup=reply_markup)
        
    return PRODUCTION_OPTION # <-- ВОССТАНОВЛЕНО МЕСТО

async def handle_production_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'prod_yes':
        context.user_data['production_needed'] = True
    elif query.data == 'prod_no':
        context.user_data['production_needed'] = False

    # Переход к сбору контактных данных
    return await prompt_contact_info(update, context)


async def prompt_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 7: Запрос контактной информации
    
    text = (
        "Теперь введите ваши контактные данные, чтобы мы могли отправить вам медиаплан:\n"
        "Отправьте **ОДНИМ** сообщением в формате:\n\n"
        "Иван Иванов\n"
        "+79123456789\n"
        "ivan.ivanov@example.com"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)
        
    return CONTACT_INFO # <-- ВОССТАНОВЛЕНО МЕСТО

async def process_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 7 (продолжение): Обработка контактной информации
    
    contact_text = update.message.text.strip()
    lines = [line.strip() for line in contact_text.split('\n') if line.strip()]
    
    if len(lines) < 3:
        await update.message.reply_text(
            "Пожалуйста, введите имя, телефон и email, каждое с новой строки."
        )
        return CONTACT_INFO

    context.user_data['contact_name'] = lines[0]
    context.user_data['contact_phone'] = lines[1]
    context.user_data['contact_email'] = lines[2]
    
    # Переход к финальному обзору
    return await review_campaign_details(update, context)


async def review_campaign_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Шаг 8: Обзор и подтверждение заявки (FINAL_ACTIONS)
    
    # Генерируем отчет в памяти для отображения сводки
    report_csv, total_budget, total_slots = generate_excel_compatible_csv_report(context)
    
    data = context.user_data
    
    review_text = (
        "<b>ПРОВЕРЬТЕ ДЕТАЛИ ВАШЕЙ ЗАЯВКИ:</b>\n\n"
        f"✅ <b>Компания:</b> {data.get('company_name', 'Не указано')}\n"
        f"📻 <b>Радио:</b> {data.get('radio_name', 'Не выбрано')}\n"
        f"📅 <b>Период:</b> с {data.get('start_date', '?')} по {data.get('end_date', '?')}\n"
        f"⏳ <b>Слоты:</b> {', '.join(data.get('selected_time_slots', ['Не выбрано']))}\n"
        f"🗓️ <b>Дни недели:</b> {', '.join(data.get('days_of_week', ['Не выбрано']))}\n"
        f"🎁 <b>Брендинг:</b> {'Да' if data.get('is_branded') else 'Нет'}\n"
        f"🎙️ <b>Производство:</b> {'Нужно' if data.get('production_needed') else 'Не нужно'}\n\n"
        f"💰 <b>Оценочный Бюджет:</b> {total_budget:,.0f} руб. (за {total_slots} выходов)\n\n"
        "📞 <b>Контакт:</b>\n"
        f"   - {data.get('contact_name', 'Не указано')}\n"
        f"   - {data.get('contact_phone', 'Не указано')}\n"
        f"   - {data.get('contact_email', 'Не указано')}\n\n"
        "Всё верно? Нажмите 'Отправить заявку' для подтверждения."
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Отправить заявку", callback_data='send_final_request')],
        [InlineKeyboardButton("❌ Отмена (Начать заново)", callback_data='cancel_text')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            review_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        # При первом переходе из process_contact_info
        await update.message.reply_text(
            review_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    return FINAL_ACTIONS


async def handle_final_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка финальных действий (Отправить или Отменить)."""
    query = update.callback_query
    await query.answer()

    if query.data == 'send_final_request':
        return await finalize_and_send(update, context)
        
    elif query.data == 'cancel_text':
        await query.edit_message_text("Заявка отменена. Начните снова, используя команду /start.")
        context.user_data.clear()
        return ConversationHandler.END
        
    return FINAL_ACTIONS


async def finalize_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Финализация заявки, сохранение в БД и отправка админу
    query = update.callback_query
    await query.answer()

    data = context.user_data
    user_id = query.from_user.id
    
    # 1. Генерируем отчет и получаем данные
    report_csv_content, total_budget, total_slots = generate_excel_compatible_csv_report(context)
    
    # 2. Сохраняем в БД
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO campaigns (
                user_id, radio_id, radio_name, start_date, end_date, total_days, time_slots, 
                days_of_week, is_branded, production_needed, contact_name, contact_phone, 
                contact_email, company_name, total_budget, creation_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data['radio_id'],
            data['radio_name'],
            data['start_date'],
            data['end_date'],
            (datetime.strptime(data['end_date'], '%Y-%m-%d') - datetime.strptime(data['start_date'], '%Y-%m-%d')).days + 1,
            ', '.join(data.get('selected_time_slots', [])),
            ', '.join(data['days_of_week']),
            data.get('is_branded', 0),
            data.get('production_needed', 0),
            data.get('contact_name', ''),
            data.get('contact_phone', ''),
            data.get('contact_email', ''),
            data.get('company_name', ''),
            total_budget,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        campaign_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        logger.error(f"DB Error on final submit: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при сохранении заявки. Попробуйте еще раз или свяжитесь с поддержкой."
        )
        conn.close()
        return ConversationHandler.END
    finally:
        conn.close()

    # 3. Уведомление клиента
    await query.edit_message_text(
        f"✅ ЗАЯВКА ПРИНЯТА! №{campaign_id}\n\n"
        f"Ваша заявка на размещение рекламы для компании <b>{data.get('company_name', 'Неизвестно')}</b> успешно принята.\n"
        f"Оценочный бюджет: <b>{total_budget:,.0f} руб.</b>\n\n"
        "Мы уже формируем медиаплан и свяжемся в ближайшее время!",
        parse_mode='HTML'
    )
    
    # 4. Автоматическая отправка заявки АДМИНУ (в Excel-совместимом CSV)
    # Используем 'utf-8' для корректного отображения кириллицы в Telegram, а затем в Excel
    report_file = io.BytesIO(report_csv_content.encode('utf-8'))
    report_file.name = f"Заявка_№{campaign_id}_{data['company_name']}.csv" # Имя файла для админа

    admin_message = (
        f"🚨 НОВАЯ ЗАЯВКА №{campaign_id} (Excel-совместимый CSV) 🚨\n\n"
        f"<b>Компания:</b> {data.get('company_name', 'Не указано')}\n"
        f"<b>Бюджет:</b> {total_budget:,.0f} руб.\n"
        f"<b>Контакт:</b> {data.get('contact_name', 'Не указано')} ({data.get('contact_phone', 'Не указано')})\n"
        f"<b>Email:</b> {data.get('contact_email', 'Не указано')}\n\n"
        "Подробный отчет прикреплен (откроется в Excel)."
    )
    
    await context.bot.send_document(
        chat_id=ADMIN_TELEGRAM_ID,
        document=report_file,
        caption=admin_message,
        parse_mode='HTML'
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Обработчик для отмен и админских кнопок
    query = update.callback_query
    await query.answer()

    if query.data == 'cancel_text':
        await query.edit_message_text("Заявка отменена. Начните снова, используя команду /start.")
        context.user_data.clear()
        return ConversationHandler.END
        
    # Обработка админских кнопок (для полноты, хотя в этом сценарии они не видны)
    if query.data.startswith('generate_pdf_') or query.data.startswith('get_pdf_') or \
       query.data.startswith('call_') or query.data.startswith('email_'):
        await query.edit_message_text(f"Админское действие: {query.data} обработано.")
        return ConversationHandler.END 
        
    return MAIN_MENU 


# --- MAIN ---

def main() -> None:
    logger.info("Starting bot...")
    
    application = Application.builder().token(TOKEN).build()

    # Восстановленный оригинальный порядок состояний в ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            RADIO_SELECTION: [
                CallbackQueryHandler(handle_radio_selection, pattern='^radio_.*$'),
                CallbackQueryHandler(handle_main_menu, pattern='^cancel_text$')
            ],
            CAMPAIGN_PERIOD: [
                # Ловит оба сообщения с датами
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_campaign_period_message), 
            ],
            TIME_SLOTS: [
                CallbackQueryHandler(handle_time_slots, pattern='^slot_.*$|^day_.*$|^slots_done$')
            ],
            BRANDED_SECTIONS: [
                CallbackQueryHandler(handle_branded_sections, pattern='^branded_.*$')
            ],
            # Шаг 5
            CAMPAIGN_CREATOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_campaign_creator),
            ],
            # Шаг 6
            PRODUCTION_OPTION: [
                CallbackQueryHandler(handle_production_option, pattern='^prod_.*$')
            ],
            # Шаг 7
            CONTACT_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_contact_info),
            ],
            # Шаг 8: Обзор и финальные действия
            FINAL_ACTIONS: [
                CallbackQueryHandler(handle_final_actions, pattern='^send_final_request$|^cancel_text$'),
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    
    # Добавляем отдельный обработчик для админских кнопок
    application.add_handler(CallbackQueryHandler(\
        handle_main_menu, \
        pattern='^(generate_pdf_|get_pdf_|call_|email_)'\
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
