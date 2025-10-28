# bot.py
import os
import logging
import datetime
import random
from io import BytesIO

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, InputFile
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
# Для генерации простого PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------- Настройки ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")   # Установите в Render
MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID")  # опционально: куда отправлять заявки (chat id)
# Если MANAGER_CHAT_ID не задан, бот будет отправлять PDF только пользователю.

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Исходные данные (настройте при необходимости) ----------
stations = [
    {"id": 1, "name": "Love Radio", "listeners": 3200, "price": 280, "emoji": "❤️"},
    {"id": 2, "name": "Авторадио", "listeners": 2800, "price": 260, "emoji": "🚗"},
    {"id": 3, "name": "Радио Дача", "listeners": 3500, "price": 240, "emoji": "🏡"},
    {"id": 4, "name": "Радио Шансон", "listeners": 2600, "price": 250, "emoji": "🎵"},
    {"id": 5, "name": "Ретро FM", "listeners": 2900, "price": 230, "emoji": "📻"},
    {"id": 6, "name": "Юмор FM", "listeners": 2100, "price": 270, "emoji": "😊"}
]

time_slots = [
    "06:00-07:00 🌅", "07:00-08:00 🚀", "08:00-09:00 📈",
    "09:00-10:00 ☕", "10:00-11:00 📊", "11:00-12:00 ⏰",
    "12:00-13:00 🍽️", "13:00-14:00 📋", "14:00-15:00 🔄",
    "15:00-16:00 📝", "16:00-17:00 🏃", "17:00-18:00 🚀",
    "18:00-19:00 📈", "19:00-20:00 🏠", "20:00-21:00 🌙"
]

rubrics = [
    {"key": "auto", "title": "АВТОРУБРИКИ", "delta": 0.20},
    {"key": "realty", "title": "НЕДВИЖИМОСТЬ", "delta": 0.15},
    {"key": "medical", "title": "МЕДИЦИНСКИЕ РУБРИКИ", "delta": 0.25},
    {"key": "custom", "title": "ИНДИВИДУАЛЬНАЯ РУБРИКА", "delta": 0.30},
]

BASE_PRICE_PER_SEC = 4.0  # рублей за секунду (информационная)

# ---------- Хранилище (в памяти) ----------
# Структура: user_sessions[user_id] = {...}
user_sessions = {}
# Для истории заказов на сессии (можно хранить отдельно)
orders_store = {}

# ---------- Помощники ----------
def format_station_line(s):
    return f"{s['emoji']} {s['name']} — {s['listeners']} слушателей/день — {s['price']}₽/ролик"

def calc_total_cost(session):
    # Возвращает сумму в рублях (float)
    selected_ids = session.get('selected_stations', [])
    if not selected_ids:
        return 0.0
    selected_stations = [s for s in stations if s['id'] in selected_ids]

    spots_per_day = session.get('spots_per_day', 5)
    campaign_days = session.get('campaign_days', 30)
    total = 0.0
    spots_per_station = spots_per_day / max(1, len(selected_stations))

    for st in selected_stations:
        station_cost = st['price'] * spots_per_station * campaign_days
        # premium slots multiplier
        premium_slots = 0
        for slot in session.get('selected_slots', []):
            if '🌅' in slot or '🚀' in slot or '🌇' in slot:
                premium_slots += 1
        station_cost *= (1 + premium_slots * 0.05)
        total += station_cost

    # скидки за объем
    total_spots = spots_per_day * campaign_days
    discount = 0.0
    if total_spots >= 300:
        discount = 0.6
    elif total_spots >= 200:
        discount = 0.5
    elif total_spots >= 100:
        discount = 0.4
    elif total_spots >= 50:
        discount = 0.2

    # бонус за multiple станций
    station_bonus = 0.1 if len(selected_stations) > 1 else 0.0

    # рубрики надбавка
    rubric_key = session.get('selected_rubric')
    rubric_delta = 0.0
    for r in rubrics:
        if r['key'] == rubric_key:
            rubric_delta = r['delta']
            break

    final = total * (1 - discount - station_bonus)
    final *= (1 + rubric_delta)
    return final

def generate_order_pdf(order_info: dict) -> BytesIO:
    """Создаёт простой pdf-файл в памяти и возвращает BytesIO."""
    bio = BytesIO()
    p = canvas.Canvas(bio, pagesize=A4)
    width, height = A4
    x = 50
    y = height - 50

    p.setFont("Helvetica-Bold", 16)
    p.drawString(x, y, "YA-RADIO — Предварительное предложение")
    y -= 30

    p.setFont("Helvetica", 11)
    for key, value in [
        ("Номер заявки", order_info.get("order_id")),
        ("Клиент", order_info.get("client_name") or "-"),
        ("Телефон", order_info.get("phone") or "-"),
        ("Email", order_info.get("email") or "-"),
        ("Компания", order_info.get("company") or "-"),
        ("Станции", ", ".join(order_info.get("stations", []))),
        ("Слоты", ", ".join(order_info.get("slots", []))),
        ("Рубрика", order_info.get("rubric") or "-"),
        ("Период (дни)", str(order_info.get("days"))),
        ("Роликов/день", str(order_info.get("spots_per_day"))),
        ("Итоговая стоимость (₽)", f"{order_info.get('total_cost'):.0f}")
    ]:
        p.drawString(x, y, f"{key}: {value}")
        y -= 18
        if y < 80:
            p.showPage()
            y = height - 50

    p.showPage()
    p.save()
    bio.seek(0)
    return bio

def gen_order_id():
    return f"R-{random.randint(10000, 99999)}"

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_sessions[user_id] = {
        'selected_stations': [],
        'selected_slots': [],
        'selected_rubric': None,
        'audio_file_id': None,
        'audio_info': None,
        'text_for_spot': None,
        'campaign_days': 30,
        'spots_per_day': 5,
        'step': 'main',
        'awaiting': None  # for sequential inputs (e.g., contact fields)
    }

    keyboard = [
        ['🚀 Создать кампанию', '📊 Статистика охвата'],
        ['📋 Мои заказы', 'ℹ️ О нас']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    message = (
        "🎧 *Добро пожаловать в YA-RADIO!*\n\n"
        "Официальный вещатель в Ялуторовске и Заводоуковске.\n\n"
        "Я помогу настроить и заказать радиокампанию — от выбора станций до отправки заявки."
    )
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

# Главное меню — обработка текстовых кнопок
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    session = user_sessions.setdefault(user_id, {
        'selected_stations': [], 'selected_slots': [], 'selected_rubric': None,
        'audio_file_id': None, 'audio_info': None, 'text_for_spot': None,
        'campaign_days': 30, 'spots_per_day': 5, 'step': 'main', 'awaiting': None
    })

    # Если ожидаем последовательный ввод (контактные данные или текст ролика)
    if session.get('awaiting'):
        await handle_sequential_input(update, context, session)
        return

    if text == '🚀 Создать кампанию':
        await show_stations_selection(update, context)
    elif text == '📊 Статистика охвата':
        await show_statistics(update, context)
    elif text == '📋 Мои заказы':
        await show_my_orders(update, context)
    elif text == 'ℹ️ О нас':
        await show_about(update, context)
    elif text == '🔙 Назад' or text == 'Назад':
        await start(update, context)
    else:
        # default help
        await update.message.reply_text(
            "Используйте кнопки меню:\n"
            "🚀 Создать кампанию\n📊 Статистика охвата\n📋 Мои заказы\nℹ️ О нас"
        )

# ========== СТЕНЫ (ЭКРАНЫ) ==========

# 2. Выбор радиостанций
async def show_stations_selection(update_or_ctx, context):
    """Можно передавать либо update, либо callback context; унифицируем."""
    if isinstance(update_or_ctx, Update):
        update = update_or_ctx
        callback_query = None
    else:
        # callback context passed (when called from other handlers)
        update = None
        callback_query = update_or_ctx

    # получаем user_id и session
    if update:
        user_id = update.effective_user.id
    else:
        user_id = callback_query.from_user.id

    session = user_sessions.setdefault(user_id, {
        'selected_stations': [], 'selected_slots': [], 'selected_rubric': None,
        'audio_file_id': None, 'audio_info': None, 'text_for_spot': None,
        'campaign_days': 30, 'spots_per_day': 5, 'step': 'main', 'awaiting': None
    })
    session['step'] = 'selecting_stations'

    keyboard = []
    for s in stations:
        selected = '✅ ' if s['id'] in session['selected_stations'] else ''
        keyboard.append([InlineKeyboardButton(f"{selected}{s['emoji']} {s['name']}", callback_data=f"station_{s['id']}")])
    keyboard.append([InlineKeyboardButton("🚀 Далее к расписанию", callback_data="next_to_slots"),
                     InlineKeyboardButton("🔄 Сбросить выбор", callback_data="reset_stations")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    stations_text = "\n".join([format_station_line(s) for s in stations])
    message = f"*YA-RADIO — Выбор радиостанций*\n\n{stations_text}\n\n*Выбрано:* {len(session['selected_stations'])}"
    if update:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await callback_query.message.edit_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_station_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = user_sessions.setdefault(user_id, {})
    data = query.data
    if data == "reset_stations":
        session['selected_stations'] = []
        await show_stations_selection(query, context)
        return
    if data.startswith("station_"):
        st_id = int(data.split("_", 1)[1])
        if st_id in session.get('selected_stations', []):
            session['selected_stations'].remove(st_id)
        else:
            session['selected_stations'].append(st_id)
        await show_stations_selection(query, context)
    elif data == "next_to_slots":
        await show_time_slots(query, context)

# 3. Временные слоты
async def show_time_slots(update_or_ctx, context):
    if isinstance(update_or_ctx, Update):
        update = update_or_ctx
        callback_query = None
    else:
        update = None
        callback_query = update_or_ctx

    if update:
        user_id = update.effective_user.id
    else:
        user_id = callback_query.from_user.id

    session = user_sessions.get(user_id, {})
    if not session.get('selected_stations'):
        if update:
            await update.message.reply_text("❌ Сначала выберите хотя бы одну радиостанцию!")
        else:
            await callback_query.message.reply_text("❌ Сначала выберите хотя бы одну радиостанцию!")
        return

    session['step'] = 'selecting_slots'
    keyboard = []
    for i in range(0, len(time_slots), 2):
        row = []
        for j in range(2):
            if i + j < len(time_slots):
                slot = time_slots[i + j]
                sel = '✅ ' if slot in session.get('selected_slots', []) else ''
                row.append(InlineKeyboardButton(f"{sel}{slot}", callback_data=f"slot_{i+j}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🗂 Выбрать рубрику", callback_data="to_rubrics"),
                     InlineKeyboardButton("🔄 Сбросить выбор", callback_data="reset_slots")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        "*YA-RADIO — Выбор временных слотов*\n\n"
        "🌅 Утренние слоты (+25%): 06:00-10:00\n"
        "☀️ Дневные слоты: 10:00-16:00\n"
        "🌇 Вечерние слоты (+20%): 16:00-21:00\n\n"
        f"✅ Выбрано слотов: {len(session.get('selected_slots', []))}"
    )
    if update:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await callback_query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_slot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = user_sessions.setdefault(user_id, {})
    data = query.data
    if data == "reset_slots":
        session['selected_slots'] = []
        await show_time_slots(query, context)
        return
    if data == "to_rubrics":
        await show_rubrics(query, context)
        return
    if data.startswith("slot_"):
        idx = int(data.split("_", 1)[1])
        slot = time_slots[idx]
        if slot in session.get('selected_slots', []):
            session['selected_slots'].remove(slot)
        else:
            session['selected_slots'].append(slot)
        await show_time_slots(query, context)

# 4. Рубрики
async def show_rubrics(update_or_ctx, context):
    if isinstance(update_or_ctx, Update):
        update = update_or_ctx
        callback_query = None
    else:
        update = None
        callback_query = update_or_ctx

    if update:
        user_id = update.effective_user.id
    else:
        user_id = callback_query.from_user.id

    session = user_sessions.setdefault(user_id, {})
    session['step'] = 'selecting_rubric'

    keyboard = []
    for r in rubrics:
        sel = '✅ ' if session.get('selected_rubric') == r['key'] else ''
        keyboard.append([InlineKeyboardButton(f"{sel}{r['title']} (+{int(r['delta']*100)}%)", callback_data=f"rubric_{r['key']}")])
    keyboard.append([InlineKeyboardButton("▶️ Далее — Конструктор ролика", callback_data="to_constructor")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "*YA-RADIO — Брендированные рубрики*\n\nВыберите тип рубрики (надбавки указаны):"
    if update:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_rubric_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = user_sessions.setdefault(user_id, {})
    data = query.data
    if data.startswith("rubric_"):
        key = data.split("_", 1)[1]
        session['selected_rubric'] = key
        await show_rubrics(query, context)
    elif data == "to_constructor":
        await show_constructor(query, context)

# 5. Конструктор ролика (upload audio или ввести текст)
async def show_constructor(update_or_ctx, context):
    if isinstance(update_or_ctx, Update):
        update = update_or_ctx
        callback_query = None
    else:
        update = None
        callback_query = update_or_ctx

    if update:
        user_id = update.effective_user.id
    else:
        user_id = callback_query.from_user.id
    session = user_sessions.setdefault(user_id, {})
    session['step'] = 'constructor'
    session['awaiting'] = None

    text = (
        "📎 *Прикрепите готовый ролик (MP3/WAV, до 10 МБ)*\n\n"
        "ИЛИ\n\n"
        "📝 *Вставьте текст для ролика (до 500 знаков)*\n\n"
        "Отправьте аудиофайл или текст. Можно сначала текст, потом заменить файлом."
    )
    keyboard = [
        [InlineKeyboardButton("▶️ Ввести текст вручную", callback_data="enter_text")],
        [InlineKeyboardButton("📝 Продолжить к предпросмотру", callback_data="to_preview")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_constructor_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = user_sessions.setdefault(user_id, {})
    data = query.data
    if data == "enter_text":
        session['awaiting'] = 'text_for_spot'
        await query.message.reply_text("Отправьте текст ролика (до 500 знаков):")
    elif data == "to_preview":
        await show_preview(query, context)

# Обработка загруженных аудио/файлов и текстовых сообщений, когда мы в constructor шаге
async def handle_incoming_file_or_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.setdefault(user_id, {})
    # Если ожидаем конкретное поле
    if session.get('awaiting'):
        await handle_sequential_input(update, context, session)
        return

    # Если отправили аудио или документ
    if update.message.audio:
        f = await update.message.audio.get_file()
        session['audio_file_id'] = f.file_id
        session['audio_info'] = {'file_size': update.message.audio.file_size, 'duration': update.message.audio.duration}
        await update.message.reply_text("Аудиофайл получен ✅. Можно прослушать в Telegram или продолжить.")
        return
    if update.message.document:
        # поддерживаем mp3/wav
        doc = update.message.document
        mime = doc.mime_type or ''
        if 'audio' in mime or doc.file_name.lower().endswith(('.mp3', '.wav')):
            f = await doc.get_file()
            session['audio_file_id'] = f.file_id
            session['audio_info'] = {'file_name': doc.file_name, 'file_size': doc.file_size}
            await update.message.reply_text("Файл-ролик получен ✅.")
            return
        else:
            await update.message.reply_text("Файл должен быть аудиофайлом (MP3/WAV).")
            return
    # Если текст и мы не в ожидании - возможно обычное сообщение
    # Пробуем интерпретировать как текст ролика (если длина < 500)
    text = update.message.text or ''
    if len(text) <= 500 and len(text) > 0:
        session['text_for_spot'] = text
        await update.message.reply_text(f"Текст для ролика сохранён (длина {len(text)} знаков).")
        return
    # Иначе общая реакция
    await update.message.reply_text("Отправьте аудиофайл (MP3/WAV) или текст до 500 знаков.")

# 6. Предпросмотр / итог заказа
async def show_preview(update_or_ctx, context):
    if isinstance(update_or_ctx, Update):
        update = update_or_ctx
        callback_query = None
    else:
        update = None
        callback_query = update_or_ctx

    if update:
        user_id = update.effective_user.id
    else:
        user_id = callback_query.from_user.id
    session = user_sessions.setdefault(user_id, {})
    # Проверки
    if not session.get('selected_stations') or not session.get('selected_slots'):
        if update:
            await update.message.reply_text("❌ Для предпросмотра выберите станции и слоты.")
        else:
            await callback_query.message.reply_text("❌ Для предпросмотра выберите станции и слоты.")
        return

    stations_names = [s['name'] for s in stations if s['id'] in session['selected_stations']]
    slots_text = ", ".join(session.get('selected_slots', []))
    rubric = next((r['title'] for r in rubrics if r['key'] == session.get('selected_rubric')), "—")
    text_preview = session.get('text_for_spot') or "Аудиофайл загружен" if session.get('audio_file_id') else "—"

    total_cost = calc_total_cost(session)
    msg = (
        "🎯 *ВАШ ЗАКАЗ (предпросмотр)*\n\n"
        f"📻 Станции: {', '.join(stations_names)}\n"
        f"🕒 Слоты: {slots_text}\n"
        f"🎙 Рубрика: {rubric}\n"
        f"⏱ Текст/Аудио: {text_preview[:180]}\n\n"
        f"📅 Период: {session.get('campaign_days')} дней\n"
        f"📊 Роликов в день: {session.get('spots_per_day')}\n"
        f"💰 Предварительная стоимость: {round(total_cost):,}₽"
    )
    keyboard = [
        [InlineKeyboardButton("📞 Связаться с менеджером", callback_data="contact_manager")],
        [InlineKeyboardButton("📇 Ввести контактные данные", callback_data="to_contacts")],
        [InlineKeyboardButton("🔄 Новый расчёт", callback_data="new_calculation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await callback_query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_preview_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    session = user_sessions.setdefault(user_id, {})
    if data == "contact_manager":
        manager_contact = "Наш менеджер свяжется с вами в ближайшее время."
        await query.message.reply_text(manager_contact)
    elif data == "to_contacts":
        await show_contact_form(query, context)
    elif data == "new_calculation":
        # сброс сессии
        user_sessions[user_id] = {
            'selected_stations': [], 'selected_slots': [], 'selected_rubric': None,
            'audio_file_id': None, 'audio_info': None, 'text_for_spot': None,
            'campaign_days': 30, 'spots_per_day': 5, 'step': 'main', 'awaiting': None
        }
        await show_stations_selection(query, context)

# 7. Контактная форма
async def show_contact_form(update_or_ctx, context):
    if isinstance(update_or_ctx, Update):
        update = update_or_ctx
        callback_query = None
    else:
        update = None
        callback_query = update_or_ctx

    if update:
        user_id = update.effective_user.id
    else:
        user_id = callback_query.from_user.id

    session = user_sessions.setdefault(user_id, {})
    session['step'] = 'contact_form'
    session['awaiting'] = 'phone'

    text = (
        "👤 *КОНТАКТЫ ДЛЯ СВЯЗИ*\n\n"
        "Отправьте ваш телефон в формате +7..."
    )
    keyboard = [[InlineKeyboardButton("Отмена", callback_data="cancel_contact_form")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_sequential_input(update: Update, context: ContextTypes.DEFAULT_TYPE, session=None):
    """Универсальная обработка для полей: phone, email, company, contact_name, position, requisites"""
    user_id = update.effective_user.id
    if session is None:
        session = user_sessions.setdefault(user_id, {})
    awaiting = session.get('awaiting')
    text = (update.message.text or "").strip()
    # Обработка специальных типов: файлы, документы
    if awaiting == 'phone':
        session['phone'] = text
        session['awaiting'] = 'email'
        await update.message.reply_text("Отлично. Теперь введите Email:")
    elif awaiting == 'email':
        session['email'] = text
        session['awaiting'] = 'company'
        await update.message.reply_text("Название компании:")
    elif awaiting == 'company':
        session['company'] = text
        session['awaiting'] = 'contact_name'
        await update.message.reply_text("Имя контактного лица:")
    elif awaiting == 'contact_name':
        session['contact_name'] = text
        session['awaiting'] = 'position'
        await update.message.reply_text("Должность контактного лица:")
    elif awaiting == 'position':
        session['position'] = text
        session['awaiting'] = 'requisites'
        await update.message.reply_text("Прикрепите файл с реквизитами (PDF/JPG/PNG до 5 МБ) или отправьте 'нет':")
    elif awaiting == 'requisites':
        # если прислали 'нет' — пропускаем
        if text.lower() == 'нет':
            session['requisites_file_id'] = None
            session['awaiting'] = None
            await finalize_and_submit_order(update, context, session)
            return
        # если документ
        if update.message.document:
            doc = update.message.document
            session['requisites_file_id'] = (doc.file_id, doc.file_name)
            session['awaiting'] = None
            await update.message.reply_text("Реквизиты получены. Отправляю заявку...")
            await finalize_and_submit_order(update, context, session)
            return
        else:
            await update.message.reply_text("Отправьте файл документом или напишите 'нет' если не хотите прикреплять.")
    elif awaiting == 'text_for_spot':
        if len(text) > 500:
            await update.message.reply_text("Текст слишком длинный, ограничение 500 знаков. Попробуйте снова:")
            return
        session['text_for_spot'] = text
        session['awaiting'] = None
        await update.message.reply_text("Текст сохранён. Нажмите 'Далее' для предпросмотра или отправьте аудиофайл.")
    else:
        # неожиданный ввод
        await update.message.reply_text("Обрабатываю ввод...")

# 8. Финализация и отправка заявки
async def finalize_and_submit_order(update: Update, context: ContextTypes.DEFAULT_TYPE, session=None):
    user_id = update.effective_user.id
    if session is None:
        session = user_sessions.get(user_id, {})
    # Формирование данных заявки
    order_id = gen_order_id()
    order_info = {
        "order_id": order_id,
        "client_name": session.get('contact_name'),
        "phone": session.get('phone'),
        "email": session.get('email'),
        "company": session.get('company'),
        "stations": [s['name'] for s in stations if s['id'] in session.get('selected_stations', [])],
        "slots": session.get('selected_slots', []),
        "rubric": next((r['title'] for r in rubrics if r['key'] == session.get('selected_rubric')), None),
        "days": session.get('campaign_days'),
        "spots_per_day": session.get('spots_per_day'),
        "total_cost": calc_total_cost(session)
    }
    # Сохраняем
    orders_store.setdefault(user_id, []).append(order_info)

    # Генерация PDF и отправка
    pdf_bio = generate_order_pdf(order_info)
    pdf_name = f"{order_id}_proposal.pdf"
    input_file = InputFile(pdf_bio, filename=pdf_name)

    # Отправляем PDF пользователю
    await update.message.reply_document(input_file, caption=f"📋 Предварительное предложение — {order_id}")

    # Если есть менеджерский чат, отправляем туда тоже
    if MANAGER_CHAT_ID:
        try:
            await context.bot.send_document(int(MANAGER_CHAT_ID), input_file, caption=f"Новая заявка {order_id} от {order_info.get('client_name')}")
        except Exception as e:
            logger.exception("Не удалось отправить PDF менеджеру: %s", e)

    # Показ экрана "Заявка принята"
    start_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%d.%m.%Y")
    msg = (
        "✅ ЗАЯВКА ПРИНЯТА!\n\n"
        f"📋 № заявки: {order_id}\n"
        f"📅 Старт: {start_date}\n"
        f"💰 Сумма: {round(order_info['total_cost']):,}₽\n\n"
        f"📧 PDF-предложение отправлено вам в Telegram\n\n"
        f"👤 Ваш менеджер свяжется в течение 1 часа для уточнения деталей\n\n"
        "📞 +7 (34535) 5-01-51\n"
        "✉️ aa@ya-radio.ru\n\n"
        "🚀 ЧТО ДАЛЬШЕ:\n"
        "• Сегодня: согласование деталей\n"
        "• Завтра: подготовка роликов\n"
        f"• {start_date}: запуск рекламы"
    )
    keyboard = [
        [KeyboardButton("В ЛИЧНЫЙ КАБИНЕТ"), KeyboardButton("НОВЫЙ ЗАКАЗ")]
    ]
    await update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup([['В ЛИЧНЫЙ КАБИНЕТ', 'НОВЫЙ ЗАКАЗ']], resize_keyboard=True))

# Мои заказы
async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    arr = orders_store.get(user_id, [])
    if not arr:
        await update.message.reply_text("У вас пока нет заказов.")
        return
    text = "Ваши заявки:\n\n"
    for o in arr:
        text += f"• {o['order_id']} — {round(o['total_cost']):,}₽ — старт { (datetime.date.today()+datetime.timedelta(days=1)).strftime('%d.%m.%Y') }\n"
    await update.message.reply_text(text)

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📊 *YA-RADIO — Статистика охвата*\n\n"
        "🏙️ Ялуторовск и район — население ~52 000, охват ~11 700/день\n"
        "🏘️ Заводоуковск и район — население ~46 500, охват ~6 800/день\n\n"
        "📈 Суточный охват: 18 500+ чел.\n"
        "👥 Месячный охват: 156 000+ контактов\n"
        "🎯 Доля рынка: 52%\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *YA-RADIO — О нас*\n\n"
        "Радио Тюменской области — ведущий региональный вещатель.\n"
        "Мы помогаем делать рекламные кампании с учётом форматов и аудитории."
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# Обработчики отмены/прочее
async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Операция отменена")
    await start(update, context)

# ========== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ==========
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    # Текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # Files & text when in constructor/contact flow
    app.add_handler(MessageHandler(filters.Document.ALL | filters.AUDIO | filters.VOICE | filters.TEXT & ~filters.COMMAND, handle_incoming_file_or_text))
    # CallbackQuery
    app.add_handler(CallbackQueryHandler(handle_station_callback, pattern=r"^station_"))
    app.add_handler(CallbackQueryHandler(handle_station_callback, pattern=r"^reset_stations$"))
    app.add_handler(CallbackQueryHandler(handle_station_callback, pattern=r"^next_to_slots$"))

    app.add_handler(CallbackQueryHandler(handle_slot_callback, pattern=r"^slot_"))
    app.add_handler(CallbackQueryHandler(handle_slot_callback, pattern=r"^reset_slots$"))
    app.add_handler(CallbackQueryHandler(handle_slot_callback, pattern=r"^to_rubrics$"))

    app.add_handler(CallbackQueryHandler(handle_rubric_callback, pattern=r"^rubric_"))
    app.add_handler(CallbackQueryHandler(handle_rubric_callback, pattern=r"^to_constructor$"))

    app.add_handler(CallbackQueryHandler(handle_constructor_callbacks, pattern=r"^enter_text$"))
    app.add_handler(CallbackQueryHandler(handle_constructor_callbacks, pattern=r"^to_preview$"))

    app.add_handler(CallbackQueryHandler(handle_preview_callbacks, pattern=r"^(contact_manager|to_contacts|new_calculation)$"))

    app.add_handler(CallbackQueryHandler(cancel_callback, pattern=r"^cancel_contact_form$"))

    # Прочие
    app.add_handler(CommandHandler("myorders", show_my_orders))

    logger.info("🤖 YA-RADIO bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
