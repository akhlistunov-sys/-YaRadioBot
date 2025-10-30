import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора
MAIN_MENU, RADIO_SELECTION, CAMPAIGN_PERIOD, TIME_SLOTS, BRANDED_SECTIONS, CAMPAIGN_CREATOR, PRODUCTION_OPTION, CONTACT_INFO = range(8)

# Токен бота
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

# Ваш Telegram ID для уведомлений
ADMIN_TELEGRAM_ID = "@AlexeyKhlistunov"

# Цены и параметры
BASE_PRICE_PER_SECOND = 4
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
    'premium': {'price': 4000, 'name': 'ПРЕМИУМ РОЛИК', 'desc': 'Озвучка 2-мя голосами, индивидуальная музыка, 5 правок, срочное производство 1 день'},
    'ready': {'price': 0, 'name': 'ГОТОВЫЙ РОЛИК', 'desc': 'У меня есть свой ролик, пришлю файлом'}
}

PERIOD_OPTIONS = {
    '15_days': {'days': 15, 'name': '15 ДНЕЙ (минимум)'},
    '30_days': {'days': 30, 'name': '30 ДНЕЙ (рекомендуем)'},
    '60_days': {'days': 60, 'name': '60 ДНЕЙ'}
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

# Расчет стоимости кампании
def calculate_campaign_price(context):
    user_data = context.user_data
    
    # Базовые параметры
    base_duration = 30  # секунд
    spots_per_day = 5
    
    # Период кампании
    period_days = user_data.get('campaign_period_days', 30)
    
    # Базовая стоимость эфира
    base_air_cost = base_duration * BASE_PRICE_PER_SECOND * spots_per_day * period_days
    
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
    
    return base_price, discount, final_price

# Создание реального PDF файла
def create_pdf_file(user_data, campaign_number):
    base_price, discount, final_price = calculate_campaign_price({'user_data': user_data})
    
    # Создаем PDF в памяти
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Стили для PDF
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.red,
        spaceAfter=30,
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.darkred,
        spaceAfter=12,
    )
    
    normal_style = styles["Normal"]
    
    # Содержимое PDF
    story = []
    
    # Заголовок
    story.append(Paragraph(f"МЕДИАПЛАН КАМПАНИИ #{campaign_number}", title_style))
    story.append(Paragraph("РАДИО ТЮМЕНСКОЙ ОБЛАСТИ", heading_style))
    story.append(Spacer(1, 20))
    
    # Статус заявки
    story.append(Paragraph("✅ Ваша заявка принята! Спасибо за доверие!", normal_style))
    story.append(Spacer(1, 20))
    
    # Параметры кампании
    story.append(Paragraph("📊 ПАРАМЕТРЫ КАМПАНИИ:", heading_style))
    story.append(Paragraph(f"• Радиостанции: {', '.join(user_data.get('selected_radios', []))}", normal_style))
    story.append(Paragraph(f"• Период: {user_data.get('campaign_period_days', 30)} дней", normal_style))
    story.append(Paragraph(f"• Выходов в день: {len(user_data.get('selected_time_slots', [])) * 5}", normal_style))
    story.append(Paragraph(f"• Брендированная рубрика: {get_branded_section_name(user_data.get('branded_section'))}", normal_style))
    story.append(Paragraph(f"• Производство: {PRODUCTION_OPTIONS[user_data.get('production_option', 'ready')]['name']}", normal_style))
    story.append(Spacer(1, 20))
    
    # Финансовая информация
    story.append(Paragraph("💰 ФИНАНСОВАЯ ИНФОРМАЦИЯ:", heading_style))
    
    # Таблица стоимости
    financial_data = [
        ['Позиция', 'Сумма (₽)'],
        ['Эфирное время', f"{base_price - user_data.get('production_cost', 0)}"],
        ['Производство ролика', f"{user_data.get('production_cost', 0)}"],
        ['', ''],
        ['Базовая стоимость', f"{base_price}"],
        ['Скидка 50%', f"-{discount}"],
        ['', ''],
        ['ИТОГО', f"{final_price}"]
    ]
    
    financial_table = Table(financial_data, colWidths=[3*inch, 1.5*inch])
    financial_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    
    story.append(financial_table)
    story.append(Spacer(1, 20))
    
    # Контактные данные клиента
    story.append(Paragraph("👤 ВАШИ КОНТАКТЫ:", heading_style))
    story.append(Paragraph(f"• Имя: {user_data.get('contact_name', 'Не указано')}", normal_style))
    story.append(Paragraph(f"• Телефон: {user_data.get('phone', 'Не указан')}", normal_style))
    story.append(Paragraph(f"• Email: {user_data.get('email', 'Не указан')}", normal_style))
    story.append(Paragraph(f"• Компания: {user_data.get('company', 'Не указана')}", normal_style))
    story.append(Spacer(1, 20))
    
    # Контакты компании
    story.append(Paragraph("📞 НАШИ КОНТАКТЫ:", heading_style))
    story.append(Paragraph("• Менеджер: Надежда", normal_style))
    story.append(Paragraph("• Телефон: +7 (34535) 5-01-51", normal_style))
    story.append(Paragraph("• Email: a.khlistunov@gmail.com", normal_style))
    story.append(Spacer(1, 20))
    
    # Дополнительная информация
    story.append(Paragraph("🎯 СТАРТ КАМПАНИИ:", heading_style))
    story.append(Paragraph("В течение 3 рабочих дней после подтверждения", normal_style))
    story.append(Spacer(1, 20))
    
    # Дата формирования
    story.append(Paragraph(f"📅 Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}", normal_style))
    
    # Собираем PDF
    doc.build(story)
    
    # Получаем PDF данные
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

# Генерация PDF контента (для текстового отображения)
def generate_pdf_content(user_data, campaign_number):
    base_price, discount, final_price = calculate_campaign_price({'user_data': user_data})
    
    pdf_content = f"""
📄 МЕДИАПЛАН КАМПАНИИ #{campaign_number}
🔴 РАДИО ТЮМЕНСКОЙ ОБЛАСТИ

✅ Ваша заявка принята!
Спасибо за доверие! 😊

📊 ПАРАМЕТРЫ КАМПАНИИ:
• Радиостанции: {', '.join(user_data.get('selected_radios', []))}
• Период: {user_data.get('campaign_period_days', 30)} дней
• Выходов в день: {len(user_data.get('selected_time_slots', [])) * 5}
• Брендированная рубрика: {get_branded_section_name(user_data.get('branded_section'))}
• Производство: {PRODUCTION_OPTIONS[user_data.get('production_option', 'ready')]['name']}

💰 ФИНАНСОВАЯ ИНФОРМАЦИЯ:
• Эфирное время: {base_price - user_data.get('production_cost', 0)}₽
• Производство ролика: {user_data.get('production_cost', 0)}₽
────────────────────
• Базовая стоимость: {base_price}₽
• Скидка 50%: -{discount}₽
────────────────────
• Итоговая стоимость: {final_price}₽

👤 ВАШИ КОНТАКТЫ:
• Имя: {user_data.get('contact_name', 'Не указано')}
• Телефон: {user_data.get('phone', 'Не указан')}
• Email: {user_data.get('email', 'Не указан')}
• Компания: {user_data.get('company', 'Не указана')}

📞 НАШИ КОНТАКТЫ:
• Менеджер: Надежда
• Телефон: +7 (34535) 5-01-51
• Email: a.khlistunov@gmail.com

🎯 СТАРТ КАМПАНИИ:
В течение 3 рабочих дней после подтверждения

📅 Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}
    """
    
    return pdf_content

# Отправка реального PDF файла
async def send_pdf_file(update: Update, context: ContextTypes.DEFAULT_TYPE, campaign_number: str):
    try:
        # Создаем PDF файл
        pdf_data = create_pdf_file(context.user_data, campaign_number)
        
        # Отправляем PDF файл
        await update.message.reply_document(
            document=io.BytesIO(pdf_data),
            filename=f"mediaplan_{campaign_number}.pdf",
            caption=f"📄 Ваш медиаплан кампании #{campaign_number}"
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании PDF: {e}")
        # Если не удалось создать PDF, отправляем текстовую версию
        pdf_content = generate_pdf_content(context.user_data, campaign_number)
        await update.message.reply_text(f"📄 ВАШ PDF МЕДИАПЛАН\n\n{pdf_content}")
        return False

# Отправка уведомления админу
async def send_admin_notification(context, user_data, campaign_number):
    """Отправка уведомления админу о новой заявке"""
    
    base_price, discount, final_price = calculate_campaign_price(context)
    
    notification_text = f"""
🔔 НОВАЯ ЗАЯВКА #{campaign_number}

👤 КЛИЕНТ:
Имя: {user_data.get('contact_name', 'Не указано')}
Телефон: {user_data.get('phone', 'Не указан')}
Email: {user_data.get('email', 'Не указан')}
Компания: {user_data.get('company', 'Не указана')}

💰 СТОИМОСТЬ:
Базовая: {base_price}₽
Скидка 50%: -{discount}₽
Итоговая: {final_price}₽

🎯 ПАРАМЕТРЫ:
• Радиостанции: {', '.join(user_data.get('selected_radios', []))}
• Период: {user_data.get('campaign_period_days', 30)} дней
• Слоты: {len(user_data.get('selected_time_slots', []))} слотов
• Рубрика: {get_branded_section_name(user_data.get('branded_section'))}
• Ролик: {PRODUCTION_OPTIONS[user_data.get('production_option', 'ready')]['name']}
"""
    
    # Создаем клавиатуру с кнопками действий
    keyboard = [
        [
            InlineKeyboardButton("📄 СФОРМИРОВАТЬ PDF", 
                               callback_data=f"generate_pdf_{campaign_number}"),
        ],
        [
            InlineKeyboardButton(f"📞 {user_data.get('phone', 'Телефон')}", 
                               callback_data=f"call_{user_data.get('phone', '')}"),
            InlineKeyboardButton(f"✉️ Написать", 
                               callback_data=f"email_{user_data.get('email', '')}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем уведомление админу
    await context.bot.send_message(
        chat_id=ADMIN_TELEGRAM_ID,
        text=notification_text,
        reply_markup=reply_markup
    )

# Генерация PDF для клиента
async def generate_client_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
    
    try:
        # Пытаемся отправить реальный PDF
        if isinstance(update, Update) and update.message:
            success = await send_pdf_file(update, context, campaign_number)
        else:
            # Если это callback query, создаем сообщение и отправляем PDF
            pdf_content = generate_pdf_content(context.user_data, campaign_number)
            await query.message.reply_text(f"📄 ВАШ PDF МЕДИАПЛАН\n\n{pdf_content}")
            success = False
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        pdf_content = generate_pdf_content(context.user_data, campaign_number)
        await query.message.reply_text(f"📄 ВАШ PDF МЕДИАПЛАН\n\n{pdf_content}")
        success = False
    
    # Отправляем уведомление админу
    await send_admin_pdf_notification(context, campaign_number, "")

async def send_admin_pdf_notification(context, campaign_number, pdf_content):
    """Отправка PDF уведомления админу"""
    
    admin_text = f"""
📄 НОВЫЙ PDF МЕДИАПЛАН #{campaign_number}

👤 КЛИЕНТ:
{context.user_data.get('contact_name')} • {context.user_data.get('phone')}
{context.user_data.get('email')} • {context.user_data.get('company')}

💰 СТОИМОСТЬ: {context.user_data.get('final_price', 0)}₽
🎯 СТАНЦИИ: {', '.join(context.user_data.get('selected_radios', []))}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("📞 ПОЗВОНИТЬ", 
                               callback_data=f"call_{context.user_data.get('phone', '')}"),
            InlineKeyboardButton("✉️ НАПИСАТЬ", 
                               callback_data=f"email_{context.user_data.get('email', '')}")
        ],
        [
            InlineKeyboardButton("📄 ПОЛУЧИТЬ PDF ДЛЯ КЛИЕНТА", 
                               callback_data=f"get_pdf_{campaign_number}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=ADMIN_TELEGRAM_ID,
        text=admin_text,
        reply_markup=reply_markup
    )

def get_branded_section_name(section):
    names = {
        'auto': 'Авторубрики (+20%)',
        'realty': 'Недвижимость (+15%)',
        'medical': 'Медицинские рубрики (+25%)',
        'custom': 'Индивидуальная рубрика (+30%)'
    }
    return names.get(section, 'Не выбрана')

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
        "📊 9,200+ в день\n👥 68,000+ в месяц\n\n"
        "🎯 52% доля рынка\n💰 4₽/сек базовая цена"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    
    return MAIN_MENU

# [ОСТАЛЬНЫЕ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ - radio_selection, handle_radio_selection, campaign_period, и т.д.]
# ... (все остальные функции остаются такими же как в предыдущей версии)

# Улучшенный обработчик главного меню с PDF
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Обработка основных действий
    if query.data == "create_campaign":
        context.user_data.clear()
        return await radio_selection(update, context)
    
    elif query.data == "statistics":
        keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📊 СТАТИСТИКА ОХВАТА\n\n"
            "• Ежедневный охват: 9,200+\n"
            "• Месячный охват: 68,000+\n"
            "• Радиус вещания: 40 км от городов\n"
            "• Доля рынка: 52%\n"
            "• Базовая цена: 4₽/сек\n\n"
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
            "📍 +40 км вокруг + деревни\n\n"
            "📈 Источник: исследование RADIOPORTAL.RU\n"
            "🔗 https://radioportal.ru/radio-auditory-research\n\n"
            "🎧 В малых городах слушают 2.5 часа/день\n"
            "🚗 65% аудитории - автомобилисты\n"
            "🏘️ +35% охват за счет сельской местности",
            reply_markup=reply_markup
        )
        return MAIN_MENU
    
    elif query.data == "my_orders":
        return await personal_cabinet(update, context)
    
    elif query.data == "about":
        keyboard = [[InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "ℹ️ О НАС\n\n"
            "🔴 РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
            "📍 Ялуторовск • Заводоуковск\n\n"
            "Ведущий радиовещатель в регионе\n"
            "Охватываем 52% радиорынка\n\n"
            "Юридическая информация:\n"
            "Индивидуальный предприниматель\n"
            "Хлыстунов Алексей Александрович\n"
            "ОГРНИП 315723200067362\n\n"
            "📞 +7 (34535) 5-01-51\n"
            "📧 a.khlistunov@gmail.com\n"
            "👤 Менеджер: Надежда",
            reply_markup=reply_markup
        )
        return MAIN_MENU
    
    # ОБРАБОТКА КНОПОК PDF И ТЕЛЕГРАМ - ИСПРАВЛЕННЫЕ
    elif query.data == "generate_pdf":
        campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
        try:
            # Создаем и отправляем реальный PDF
            pdf_data = create_pdf_file(context.user_data, campaign_number)
            await query.message.reply_document(
                document=io.BytesIO(pdf_data),
                filename=f"mediaplan_{campaign_number}.pdf",
                caption=f"📄 Ваш медиаплан кампании #{campaign_number}"
            )
        except Exception as e:
            # Если ошибка, отправляем текстовую версию
            logger.error(f"Ошибка PDF: {e}")
            pdf_content = generate_pdf_content(context.user_data, campaign_number)
            await query.message.reply_text(f"📄 ВАШ PDF МЕДИАПЛАН\n\n{pdf_content}")
        return ConversationHandler.END
    
    elif query.data.startswith("send_to_telegram_"):
        campaign_number = query.data.replace("send_to_telegram_", "")
        
        try:
            # Пытаемся отправить реальный PDF
            pdf_data = create_pdf_file(context.user_data, campaign_number)
            await query.message.reply_document(
                document=io.BytesIO(pdf_data),
                filename=f"mediaplan_{campaign_number}.pdf",
                caption=f"📄 Ваш медиаплан кампании #{campaign_number}"
            )
        except Exception as e:
            # Если ошибка, отправляем текстовую версию
            logger.error(f"Ошибка PDF: {e}")
            pdf_content = generate_pdf_content(context.user_data, campaign_number)
            await query.message.reply_text(f"📋 ВАША ЗАЯВКА #{campaign_number}\n\n{pdf_content}")
        
        # Отправляем уведомление админу
        await send_admin_notification(context, context.user_data, campaign_number)
        
        # Подтверждаем клиенту
        await query.message.reply_text(
            "✅ Ваша заявка отправлена менеджеру!\n"
            "📞 Мы свяжемся с вами в течение 1 часа"
        )
        return ConversationHandler.END
    
    elif query.data == "new_order":
        context.user_data.clear()
        return await radio_selection(update, context)
    
    elif query.data == "personal_cabinet":
        return await personal_cabinet(update, context)
    
    # ОБРАБОТКА АДМИНСКИХ КНОПОК
    elif query.data.startswith("generate_pdf_"):
        campaign_number = query.data.replace("generate_pdf_", "")
        try:
            pdf_data = create_pdf_file(context.user_data, campaign_number)
            await query.message.reply_document(
                document=io.BytesIO(pdf_data),
                filename=f"mediaplan_{campaign_number}.pdf",
                caption=f"📄 PDF для клиента #{campaign_number}"
            )
        except Exception as e:
            pdf_content = generate_pdf_content(context.user_data, campaign_number)
            await query.message.reply_text(f"📄 PDF ДЛЯ КЛИЕНТА #{campaign_number}\n\n{pdf_content}")
    
    elif query.data.startswith("get_pdf_"):
        campaign_number = query.data.replace("get_pdf_", "")
        try:
            pdf_data = create_pdf_file(context.user_data, campaign_number)
            await query.message.reply_document(
                document=io.BytesIO(pdf_data),
                filename=f"mediaplan_{campaign_number}.pdf",
                caption=f"📄 PDF для клиента #{campaign_number}"
            )
        except Exception as e:
            pdf_content = generate_pdf_content(context.user_data, campaign_number)
            await query.message.reply_text(f"📄 PDF ДЛЯ КЛИЕНТА #{campaign_number}\n\n{pdf_content}")
    
    elif query.data.startswith("call_"):
        phone = query.data.replace("call_", "")
        await query.answer(f"📞 Наберите: {phone}")
    
    elif query.data.startswith("email_"):
        email = query.data.replace("email_", "")
        await query.answer(f"✉️ Email: {email}")
    
    # [ОСТАЛЬНАЯ НАВИГАЦИЯ ОСТАЕТСЯ БЕЗ ИЗМЕНЕНИЙ]
    # ... (все остальные обработчики навигации)

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
                CallbackQueryHandler(handle_main_menu, pattern='^(back_to_|skip_text|cancel_text|to_production_option|provide_own_audio|enter_text)'),
                CallbackQueryHandler(enter_campaign_text, pattern='^enter_text$')
            ],
            "WAITING_TEXT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_campaign_text),
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_creator$'),
                CallbackQueryHandler(handle_main_menu, pattern='^cancel_text$')
            ],
            PRODUCTION_OPTION: [
                CallbackQueryHandler(handle_production_option, pattern='^.*$')
            ],
            CONTACT_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_contact_info),
                CallbackQueryHandler(handle_main_menu, pattern='^back_to_production$')
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    
    # Добавляем отдельный обработчик для кнопок после завершения разговора
    application.add_handler(CallbackQueryHandler(
        handle_main_menu, 
        pattern='^(generate_pdf|send_to_telegram_|personal_cabinet|new_order|back_to_main|generate_pdf_|get_pdf_|call_|email_)'
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
