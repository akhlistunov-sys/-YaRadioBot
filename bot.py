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

# Состояния разговора
MAIN_MENU, RADIO_SELECTION, CAMPAIGN_PERIOD, TIME_SLOTS, BRANDED_SECTIONS, CAMPAIGN_CREATOR, PRODUCTION_OPTION, CONTACT_INFO, FINAL_ACTIONS = range(9)

# Токен бота
TOKEN = "8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU"

# Ваш Telegram ID для уведомлений
ADMIN_TELEGRAM_ID = 174046571  # Твой числовой ID

# Цены и параметры (без изменений)
BASE_PRICE_PER_SECOND = 4
MIN_PRODUCTION_COST = 2000
MIN_BUDGET = 7000

# НОВЫЕ КОНСТАНТЫ ДЛЯ ВИЗУАЛА
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
E_PDF = "📄"
E_SEND = "📤"
E_CANCEL = "❌"

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

# Расчет стоимости кампании и охвата (ОБНОВЛЕНО: сохранение данных о выходах)
def calculate_campaign_price_and_reach(user_data):
    try:
        # Базовые параметры
        base_duration = 30  # секунд
        spots_per_slot = 5
        
        # Период кампании
        period_days = user_data.get('campaign_period_days', 30)
        
        # Количество радиостанций
        num_stations = len(user_data.get('selected_radios', []))
        
        # Количество слотов
        num_slots = len(user_data.get('selected_time_slots', []))
        
        # Базовая стоимость эфира
        spots_per_day_per_station = num_slots * spots_per_slot
        
        # Стоимость одного выхода (30 сек * 4р/сек)
        price_per_spot = base_duration * BASE_PRICE_PER_SECOND 
        
        # Базовая стоимость эфира (без наценок)
        base_air_cost = price_per_spot * spots_per_day_per_station * period_days * num_stations
        
        # Надбавки за премиум-время (10% за утренние и вечерние)
        selected_time_slots = user_data.get('selected_time_slots', [])
        time_multiplier = 1.0
        
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                if slot['premium']:
                    # Наценка применяется, если выбран хотя бы один премиум-слот
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

        # Сохранение данных о выходах для отчетности (КРИТИЧНО)
        user_data['spots_per_day_per_station'] = spots_per_slot 
        user_data['total_outputs_day'] = spots_per_day_per_station * num_stations
        user_data['total_outputs_period'] = user_data['total_outputs_day'] * period_days
        
        return base_price, discount, final_price, total_reach, daily_listeners
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

# Создание реального PDF файла (ОБНОВЛЕНО: детализация расписания)
def create_pdf_file(user_data, campaign_number):
    try:
        base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(user_data)
        
        # Создаем PDF в памяти
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        
        # Стили для PDF
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.darkred,
            spaceAfter=30,
            alignment=1  # Центрирование
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
        story.append(Paragraph("<b>✅ Ваша заявка принята!</b> Спасибо за доверие!", normal_style))
        story.append(Spacer(1, 10))
        
        # Параметры кампании
        story.append(Paragraph("<b>📊 ПАРАМЕТРЫ КАМПАНИИ:</b>", heading_style))
        story.append(Paragraph(f"• <b>Радиостанции:</b> {', '.join(user_data.get('selected_radios', []))}", normal_style))
        story.append(Paragraph(f"• <b>Период:</b> {user_data.get('campaign_period_days', 30)} дней", normal_style))
        story.append(Paragraph(f"• <b>Выходов в день:</b> {user_data.get('total_outputs_day', 0)}", normal_style))
        story.append(Paragraph(f"• <b>Брендированная рубрика:</b> {get_branded_section_name(user_data.get('branded_section'))}", normal_style))
        story.append(Paragraph(f"• <b>Производство:</b> {PRODUCTION_OPTIONS.get(user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}", normal_style))
        story.append(Spacer(1, 20))
        
        # Детализация расписания (НОВЫЙ БЛОК)
        story.append(Paragraph("<b>🕒 ПОДРОБНОЕ РАСПИСАНИЕ:</b>", heading_style))
        
        spots_per_day_per_station = user_data.get('spots_per_day_per_station', 5)
        period_days = user_data.get('campaign_period_days', 30)
        
        # Данные расписания
        schedule_data = [
            ['Радиостанция', 'Слот', 'Выходов в день', 'Всего выходов']
        ]
        
        selected_radios = user_data.get('selected_radios', [])
        selected_slots_indices = user_data.get('selected_time_slots', [])
        
        for radio in selected_radios:
            for slot_index in selected_slots_indices:
                if 0 <= slot_index < len(TIME_SLOTS_DATA):
                    slot = TIME_SLOTS_DATA[slot_index]
                    schedule_data.append([
                        radio, 
                        slot['time'], 
                        str(spots_per_day_per_station), 
                        format_number(spots_per_day_per_station * period_days)
                    ])

        schedule_table = Table(schedule_data, colWidths=[2*inch, 1.5*inch, 1*inch, 1*inch])
        schedule_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.8, 0.8, 0.8)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ]))
        
        story.append(schedule_table)
        story.append(Spacer(1, 20))
        
        # Охват кампании
        story.append(Paragraph("<b>🎯 РАСЧЕТНЫЙ ОХВАТ:</b>", heading_style))
        story.append(Paragraph(f"• <b>Ежедневный охват:</b> ~{format_number(daily_listeners)} человек", normal_style))
        story.append(Paragraph(f"• <b>Общий охват за период:</b> ~{format_number(total_reach)} человек", normal_style))
        story.append(Spacer(1, 20))
        
        # Финансовая информация
        story.append(Paragraph("<b>💰 ФИНАНСОВАЯ ИНФОРМАЦИЯ:</b>", heading_style))
        
        # Таблица стоимости
        production_cost = user_data.get('production_cost', 0)
        financial_data = [
            ['Позиция', 'Сумма (₽)'],
            ['Эфирное время', format_number(base_price - production_cost)],
            ['Производство ролика', format_number(production_cost)],
            ['', ''],
            ['Базовая стоимость', format_number(base_price)],
            ['Скидка 50%', f"-{format_number(discount)}"],
            ['', ''],
            ['ИТОГО', format_number(final_price)]
        ]
        
        financial_table = Table(financial_data, colWidths=[3*inch, 1.5*inch])
        financial_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.8, 0.8, 0.8)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        story.append(financial_table)
        story.append(Spacer(1, 20))
        
        # Контактные данные клиента
        story.append(Paragraph("<b>👤 ВАШИ КОНТАКТЫ:</b>", heading_style))
        story.append(Paragraph(f"• <b>Имя:</b> {user_data.get('contact_name', 'Не указано')}", normal_style))
        story.append(Paragraph(f"• <b>Телефон:</b> {user_data.get('phone', 'Не указан')}", normal_style))
        story.append(Paragraph(f"• <b>Email:</b> {user_data.get('email', 'Не указан')}", normal_style))
        story.append(Paragraph(f"• <b>Компания:</b> {user_data.get('company', 'Не указана')}", normal_style))
        story.append(Spacer(1, 20))
        
        # Контакты компании (без изменений)
        story.append(Paragraph("<b>📞 НАШИ КОНТАКТЫ:</b>", heading_style))
        story.append(Paragraph("• Email: a.khlistunov@gmail.com", normal_style))
        story.append(Paragraph("• Telegram: t.me/AlexeyKhlistunov", normal_style))
        story.append(Spacer(1, 20))
        
        # Дополнительная информация
        story.append(Paragraph("<b>🎯 СТАРТ КАМПАНИИ:</b>", heading_style))
        story.append(Paragraph("В течение 3 рабочих дней после подтверждения", normal_style))
        story.append(Spacer(1, 20))
        
        # Дата формирования
        story.append(Paragraph(f"📅 Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}", normal_style))
        
        # Собираем PDF
        doc.build(story)
        
        # Получаем PDF данные
        pdf_data = buffer.getvalue()
        buffer.close()
        
        logger.info(f"PDF успешно создан для кампании #{campaign_number}")
        return pdf_data
        
    except Exception as e:
        logger.error(f"Ошибка при создании PDF: {e}")
        return None

# Создание реального Excel файла (НОВАЯ ФУНКЦИЯ)
def create_excel_file(user_data, campaign_number):
    try:
        base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(user_data)
        
        buffer = io.BytesIO()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Медиаплан #{campaign_number}"
        
        # Стили
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="800000", end_color="800000", fill_type="solid") # Dark Red
        border_style = Border(left=Side(style='thin'), 
                              right=Side(style='thin'), 
                              top=Side(style='thin'), 
                              bottom=Side(style='thin'))
        
        # Заголовок
        ws['A1'] = f"МЕДИАПЛАН КАМПАНИИ #{campaign_number}"
        ws['A1'].font = Font(bold=True, size=16, color="800000")
        ws.merge_cells('A1:E1')
        
        # Параметры кампании
        ws.append([])
        ws.append(["ПАРАМЕТРЫ КАМПАНИИ"])
        ws['A3'].font = Font(bold=True)
        
        row_num = 4
        ws.cell(row=row_num, column=1, value="Радиостанции:").font = Font(bold=True)
        ws.cell(row=row_num, column=2, value=', '.join(user_data.get('selected_radios', [])))
        row_num += 1
        ws.cell(row=row_num, column=1, value="Период (дней):").font = Font(bold=True)
        ws.cell(row=row_num, column=2, value=user_data.get('campaign_period_days', 30))
        row_num += 1
        ws.cell(row=row_num, column=1, value="Слотов (выходы/день/станция):").font = Font(bold=True)
        ws.cell(row=row_num, column=2, value=len(user_data.get('selected_time_slots', [])) * user_data.get('spots_per_day_per_station', 5))
        row_num += 1
        ws.cell(row=row_num, column=1, value="Общее количество выходов:").font = Font(bold=True)
        ws.cell(row=row_num, column=2, value=user_data.get('total_outputs_period', 0))
        row_num += 1
        
        # Финансы
        row_num += 1
        ws.cell(row=row_num, column=1, value="ФИНАНСОВАЯ ИНФОРМАЦИЯ").font = Font(bold=True)
        row_num += 1
        
        ws.cell(row=row_num, column=1, value="Позиция").fill = header_fill
        ws.cell(row=row_num, column=1, value="Позиция").font = header_font
        ws.cell(row=row_num, column=2, value="Сумма (₽)").fill = header_fill
        ws.cell(row=row_num, column=2, value="Сумма (₽)").font = header_font
        row_num += 1
        
        ws.cell(row=row_num, column=1, value="Эфирное время")
        ws.cell(row=row_num, column=2, value=base_price - user_data.get('production_cost', 0)).number_format = '#,##0 ₽'
        row_num += 1
        ws.cell(row=row_num, column=1, value="Производство ролика")
        ws.cell(row=row_num, column=2, value=user_data.get('production_cost', 0)).number_format = '#,##0 ₽'
        row_num += 1
        ws.cell(row=row_num, column=1, value="Базовая стоимость").font = Font(bold=True)
        ws.cell(row=row_num, column=2, value=base_price).number_format = '#,##0 ₽'
        row_num += 1
        ws.cell(row=row_num, column=1, value="Скидка 50%").font = Font(bold=True)
        ws.cell(row=row_num, column=2, value=-discount).number_format = '#,##0 ₽'
        row_num += 1
        ws.cell(row=row_num, column=1, value="ИТОГО").font = Font(bold=True, size=11, color="800000")
        ws.cell(row=row_num, column=2, value=final_price).number_format = '#,##0 ₽'
        row_num += 1
        
        # Детализация по слотам (Расписание)
        row_num += 1
        ws.cell(row=row_num, column=1, value="ДЕТАЛИЗАЦИЯ РАСПИСАНИЯ").font = Font(bold=True)
        row_num += 1
        
        slot_headers = ["Радиостанция", "Слот", "Описание", "Выходов в день", "Выходов за период"]
        for col_num, value in enumerate(slot_headers, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.font = header_font
            cell.fill = header_fill
        row_num += 1

        # Данные расписания
        spots_per_slot = user_data.get('spots_per_day_per_station', 5)
        period_days = user_data.get('campaign_period_days', 30)
        
        selected_radios = user_data.get('selected_radios', [])
        selected_slots_indices = user_data.get('selected_time_slots', [])
        
        for radio in selected_radios:
            for slot_index in selected_slots_indices:
                if 0 <= slot_index < len(TIME_SLOTS_DATA):
                    slot = TIME_SLOTS_DATA[slot_index]
                    ws.cell(row=row_num, column=1, value=radio)
                    ws.cell(row=row_num, column=2, value=slot['time'])
                    ws.cell(row=row_num, column=3, value=slot['label'])
                    ws.cell(row=row_num, column=4, value=spots_per_slot)
                    ws.cell(row=row_num, column=5, value=spots_per_slot * period_days).number_format = '#,##0'
                    row_num += 1

        # Применяем границы и автоширину
        for r in ws.iter_rows(min_row=row_num - len(selected_radios)*len(selected_slots_indices) - 1, max_row=row_num - 1):
            for cell in r:
                cell.border = border_style
        
        for col in ws.columns:
            max_length = 0
            column = col[0].column # Get the column number
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[get_column_letter(column)].width = adjusted_width
            
        wb.save(buffer)
        excel_data = buffer.getvalue()
        buffer.close()
        
        logger.info(f"Excel успешно создан для кампании #{campaign_number}")
        return excel_data
        
    except Exception as e:
        logger.error(f"Ошибка при создании Excel: {e}")
        return None

# Отправка Excel (НОВАЯ ФУНКЦИЯ)
async def send_excel_file(update: Update, context: ContextTypes.DEFAULT_TYPE, campaign_number: str):
    try:
        excel_data = create_excel_file(context.user_data, campaign_number)
        
        if not excel_data:
            return False
            
        file_io = io.BytesIO(excel_data)
        file_io.name = f"mediaplan_{campaign_number}.xlsx"
        
        if hasattr(update, 'message') and update.message:
            await update.message.reply_document(
                document=file_io,
                filename=f"mediaplan_{campaign_number}.xlsx",
                caption=f"💾 Ваш детализированный медиаплан кампании #{campaign_number} в Excel"
            )
        else:
            await update.callback_query.message.reply_document(
                document=file_io,
                filename=f"mediaplan_{campaign_number}.xlsx",
                caption=f"💾 Ваш детализированный медиаплан кампании #{campaign_number} в Excel"
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке Excel: {e}")
        return False

# Отправка реального PDF файла (без изменений)
async def send_pdf_file(update: Update, context: ContextTypes.DEFAULT_TYPE, campaign_number: str):
    try:
        # Создаем PDF файл
        pdf_data = create_pdf_file(context.user_data, campaign_number)
        
        if not pdf_data:
            return False
            
        # Отправляем PDF файл
        if hasattr(update, 'message') and update.message:
            await update.message.reply_document(
                document=io.BytesIO(pdf_data),
                filename=f"mediaplan_{campaign_number}.pdf",
                caption=f"📄 Ваш медиаплан кампании #{campaign_number}"
            )
        else:
            # Если это callback query
            await update.callback_query.message.reply_document(
                document=io.BytesIO(pdf_data),
                filename=f"mediaplan_{campaign_number}.pdf",
                caption=f"📄 Ваш медиаплан кампании #{campaign_number}"
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке PDF: {e}")
        return False

# Отправка уведомления админу (ОБНОВЛЕНО: формат и user_id)
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
Базовая: {format_number(base_price)}₽
Скидка 50%: -{format_number(discount)}₽
**Итоговая: {format_number(final_price)}₽**

**🎯 ПАРАМЕТРЫ:**
• Радиостанции: {', '.join(user_data.get('selected_radios', []))}
• Период: {user_data.get('campaign_period_days', 30)} дней
• Выходов/день: {user_data.get('total_outputs_day', 0)}
• Рубрика: {get_branded_section_name(user_data.get('branded_section'))}
• Ролик: {PRODUCTION_OPTIONS.get(user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}

**📊 ОХВАТ:**
• Ежедневно: ~{format_number(daily_listeners)} чел.
• За период: ~{format_number(total_reach)} чел.
"""
        
        # Создаем клавиатуру с кнопками действий
        keyboard = [
            [
                InlineKeyboardButton(f"{E_PDF} PDF ОТЧЕТ", callback_data=f"generate_pdf_admin_{campaign_number}"),
                InlineKeyboardButton(f"{E_XLSX} EXCEL ОТЧЕТ", callback_data=f"generate_excel_admin_{campaign_number}"),
            ],
            [
                InlineKeyboardButton(f"📞 {user_data.get('phone', 'Телефон')}", callback_data=f"call_{user_data.get('phone', '')}"),
                InlineKeyboardButton(f"✉️ Email", callback_data=f"email_{user_data.get('email', '')}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем уведомление админу
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

# Главное меню (ОБНОВЛЕНО: Формат)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"🚀 СОЗДАТЬ КАМПАНИЮ", callback_data="create_campaign")],
        [InlineKeyboardButton("📊 СТАТИСТИКА ОХВАТА", callback_data="statistics")],
        [InlineKeyboardButton("📋 МОИ ЗАКАЗЫ", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ О НАС", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🎙️ **РАДИО ТЮМЕНСКОЙ ОБЛАСТИ**\n"
        f"📍 *Ялуторовск • Заводоуковск*\n"
        "📍 Территория +35 км вокруг городов\n"
        "──────────────\n"
        f"{E_REACH} Охват: **9,200+** в день\n"
        f"👥 Охват: **68,000+** в месяц\n"
        f"🎯 **52%** доля местного радиорынка\n"
        f"{E_COST} **4₽/сек** базовая цена"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return MAIN_MENU

# Шаг 1: Выбор радиостанций (ОБНОВЛЕНО: Формат и кнопки)
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
        f"**ВЫБРАНО:** {len(selected_radios)} станции | {E_REACH} {format_number(total_listeners)} слушателей\n"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return RADIO_SELECTION

# Обработка выбора радиостанций (убрана логика details для упрощения UX)
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

# Шаг 2: Период кампании (ОБНОВЛЕНО: Формат)
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
    for key, option in PERIOD_OPTIONS.items():
        is_selected = E_CHECK if selected_period == key else E_UNCHECK
        # Расчет стоимости для каждого периода (примерная)
        base_cost = 750 * option['days'] * len(selected_radios)
        discounted_cost = base_cost * 0.5
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
        f"Цены указаны со скидкой 50%"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return CAMPAIGN_PERIOD

# Обработка выбора периода (без изменений)
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

# Шаг 3: Временные слоты (ОБНОВЛЕНО: Формат)
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
        f"• Выходов в день на всех радио: **{total_outputs_per_day}**\n"
        f"• Всего выходов за период: **{format_number(total_outputs_period)}**\n\n"
        f"🎯 Выберите подходящие временные интервалы"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return TIME_SLOTS

# Обработка выбора временных слотов (без изменений)
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

# Шаг 4: Брендированные рубрики (ОБНОВЛЕНО: Формат)
async def branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_branded = context.user_data.get('branded_section')
    
    keyboard = [
        [InlineKeyboardButton(f"{E_CHECK} АВТОРУБРИКИ" if selected_branded == 'auto' else f"{E_UNCHECK} АВТОРУБРИКИ", callback_data="branded_auto")],
        [InlineKeyboardButton(f"{E_CHECK} НЕДВИЖИМОСТЬ" if selected_branded == 'realty' else f"{E_UNCHECK} НЕДВИЖИМОСТЬ", callback_data="branded_realty")],
        [InlineKeyboardButton(f"{E_CHECK} МЕДИЦИНСКИЕ" if selected_branded == 'medical' else f"{E_UNCHECK} МЕДИЦИНСКИЕ", callback_data="branded_medical")],
        [InlineKeyboardButton(f"{E_CHECK} ИНДИВИДУАЛЬНАЯ" if selected_branded == 'custom' else f"{E_UNCHECK} ИНДИВИДУАЛЬНАЯ", callback_data="branded_custom")],
        [InlineKeyboardButton("📋 Посмотреть пример", callback_data="show_example")],
        [InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_time")],
        [InlineKeyboardButton(f"{E_SKIP} ПРОПУСТИТЬ", callback_data="skip_branded")],
        [InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_campaign_creator")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"**ШАГ 4/7: БРЕНДИРОВАННЫЕ РУБРИКИ**\n"
        "──────────────\n"
        f"🎙️ **ВЫБЕРИТЕ ТИП РУБРИКИ**:\n\n"
        f"*{E_CHECK if selected_branded == 'auto' else E_UNCHECK} АВТОРУБРИКИ* (+20%)\n"
        "Готовые сценарии для автосалонов\n"
        f"*{E_CHECK if selected_branded == 'realty' else E_UNCHECK} НЕДВИЖИМОСТЬ* (+15%)\n"
        "Рубрики для агентств недвижимости\n"
        f"*{E_CHECK if selected_branded == 'medical' else E_UNCHECK} МЕДИЦИНСКИЕ РУБРИКИ* (+25%)\n"
        "Экспертные форматы для клиник\n"
        f"*{E_CHECK if selected_branded == 'custom' else E_UNCHECK} ИНДИВИДУАЛЬНАЯ РУБРИКА* (+30%)\n"
        "Разработка под ваш бизнес\n"
        "──────────────\n"
        "Надбавка применяется к стоимости эфирного времени."
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return BRANDED_SECTIONS

# Обработка выбора рубрик (без изменений)
async def handle_branded_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_time":
        return await time_slots(update, context)
    
    elif query.data == "show_example":
        example_text = (
            "**ПРИМЕР БРЕНДИРОВАННОЙ РУБРИКИ**\n"
            "──────────────\n"
            "Комплексные рекламные решения для продвижения услуг Тюменского кардиологического научного центра на радиостанциях Тюмени.\n\n"
            "Форматы размещения:\n"
            "• Рекламные ролики (15–30 сек.)\n"
            "• Брендированные рубрики — «Здоровое сердце», «Совет врача»\n\n"
            "Пример рубрики (30 сек.):\n"
            "«❤️ Знаете ли вы, что регулярное обследование сердца помогает предупредить серьёзные заболевания? В Тюменском кардиологическом научном центре вы можете пройти диагностику и получить консультацию специалистов. Заботьтесь о себе и своих близких — здоровье сердца в надёжных руках!»"
        )
        
        keyboard = [[InlineKeyboardButton(f"{E_BACK} НАЗАД К ВЫБОРУ РУБРИК", callback_data="back_to_branded")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(example_text, reply_markup=reply_markup, parse_mode='Markdown')
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
        # Если рубрика не выбрана, ставим None
        if 'branded_section' not in context.user_data:
             context.user_data['branded_section'] = None
        return await campaign_creator(update, context)
    
    return BRANDED_SECTIONS

# Шаг 5: Конструктор ролика (ОБНОВЛЕНО: TTS кнопка и формат)
async def campaign_creator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Рассчитываем предварительную стоимость и охват (для обновления цен)
    base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(context.user_data)
    context.user_data['base_price'] = base_price
    context.user_data['discount'] = discount
    context.user_data['final_price'] = final_price
    
    provide_own = context.user_data.get('provide_own_audio', False)
    campaign_text = context.user_data.get('campaign_text', '')
    char_count = len(campaign_text) if campaign_text else 0
    
    tts_button = [InlineKeyboardButton(f"{E_TTS} Прослушать черновик", callback_data="request_tts")] if campaign_text else []

    keyboard = [
        [InlineKeyboardButton("📝 ВВЕСТИ ТЕКСТ РОЛИКА", callback_data="enter_text")],
        tts_button,
        [InlineKeyboardButton(f"{E_CHECK} Пришлю свой ролик" if provide_own else f"{E_UNCHECK} Пришлю свой ролик", callback_data="provide_own_audio")],
        [InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_branded")],
        [InlineKeyboardButton(f"{E_SKIP} ПРОПУСТИТЬ ТЕКСТ", callback_data="skip_text")],
        [InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_production_option")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"**ШАГ 5/7: КОНСТРУКТОР РОЛИКА**\n"
        "──────────────\n"
        f"📝 **ВАШ ТЕКСТ** (до 500 знаков):\n\n"
        f"`{campaign_text if campaign_text else '[Ваш текст появится здесь]'}`\n\n"
        f"○ **{char_count}** знаков из 500\n"
        f"⏱️ Примерная длительность: **{max(15, char_count // 7) if char_count > 0 else 0}** секунд\n"
        "─────────────────\n"
        f"💰 **Предварительная стоимость**:\n"
        f"   Базовая: {format_number(base_price)}₽\n"
        f"   Скидка 50%: -{format_number(discount)}₽\n"
        f"   **Итоговая: {format_number(final_price)}₽**\n\n"
        f"📊 Примерный охват кампании: **~{format_number(total_reach)}** человек за период\n\n"
        f"{E_CHECK if provide_own else E_UNCHECK} *Пришлю свой ролик* (если отмечено, шаг 6 будет пропущен)"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return CAMPAIGN_CREATOR

# Обработка запроса TTS (НОВАЯ ФУНКЦИЯ-ЗАГЛУШКА)
async def handle_tts_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(f"{E_TTS} Генерация аудио... (Функционал Text-to-Speech будет реализован в следующем обновлении, требуется API для озвучки)", show_alert=True)
    return CAMPAIGN_CREATOR

# Ввод текста ролика (ОБНОВЛЕНО: Формат)
async def enter_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_creator")],
        [InlineKeyboardButton(f"{E_CANCEL} ОТМЕНА ВВОДА", callback_data="cancel_text")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📝 **Введите текст для радиоролика** (до 500 знаков):\n\n"
        "Пример:\n"
        "`Автомобили в Тюмени! Новые модели в наличии. Выгодный трейд-ин и кредит 0%. Тест-драйв в день обращения!`\n\n"
        "**Отправьте текст сообщением:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return "WAITING_TEXT"

# Обработка текста ролика (ОБНОВЛЕНО: Формат)
async def process_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if len(text) > 500:
        await update.message.reply_text(f"{E_CANCEL} Текст превышает 500 знаков. Сократите текст.")
        return "WAITING_TEXT"
    
    context.user_data['campaign_text'] = text
    context.user_data['provide_own_audio'] = False
    
    base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(context.user_data)
    
    # Клавиатура с кнопкой TTS, если есть текст
    tts_button = [InlineKeyboardButton(f"{E_TTS} Прослушать черновик", callback_data="request_tts")] if text else []
    
    keyboard = [
        tts_button,
        [InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_production_option")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    char_count = len(text)
    text_display = (
        f"**ШАГ 5/7: КОНСТРУКТОР РОЛИКА**\n"
        "──────────────\n"
        f"📝 **ВАШ ТЕКСТ** (до 500 знаков):\n\n"
        f"`{text}`\n\n"
        f"○ **{char_count}** знаков из 500\n"
        f"⏱️ Примерная длительность: **{max(15, char_count // 7)}** секунд\n"
        "─────────────────\n"
        f"💰 **Предварительная стоимость**:\n"
        f"   Базовая: {format_number(base_price)}₽\n"
        f"   Скидка 50%: -{format_number(discount)}₽\n"
        f"   **Итоговая: {format_number(final_price)}₽**\n\n"
        f"📊 Примерный охват кампании: **~{format_number(total_reach)}** человек за период\n\n"
        f"{E_UNCHECK} *Пришлю свой ролик*"
    )
    
    await update.message.reply_text(text_display, reply_markup=reply_markup, parse_mode='Markdown')
    return CAMPAIGN_CREATOR

# Шаг 6: Производство ролика (ОБНОВЛЕНО: Формат)
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
        is_selected = E_CHECK if selected_production == key else E_UNCHECK
        keyboard.append([
            InlineKeyboardButton(
                f"{is_selected} {option['name']} - от {format_number(option['price'])}₽", 
                callback_data=f"production_{key}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_creator")])
    keyboard.append([InlineKeyboardButton(f"{E_NEXT} ДАЛЕЕ", callback_data="to_contact_info")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"**ШАГ 6/7: ПРОИЗВОДСТВО РОЛИКА**\n"
        "──────────────\n"
        f"🎙️ **ВЫБЕРИТЕ ВАРИАНТ РОЛИКА**:\n\n"
        f"*{E_UNCHECK} СТАНДАРТНЫЙ РОЛИК* - от **2,000₽**\n"
        "• Профессиональная озвучка, 2 правки, 2-3 дня\n"
        f"*{E_UNCHECK} ПРЕМИУМ РОЛИК* - от **4,000₽**\n"
        "• Озвучка 2-мя голосами, срочное производство 1 день\n"
        f"*{E_UNCHECK} ГОТОВЫЙ РОЛИК* - **0₽**\n"
        "• Пришлю свой ролик\n\n"
        f"{E_COST} Стоимость производства *прибавляется* к финальной сумме."
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return PRODUCTION_OPTION

# Обработка выбора производства (без изменений)
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
            await query.answer(f"{E_CANCEL} Выберите вариант производства ролика!", show_alert=True)
            return PRODUCTION_OPTION
        return await contact_info(update, context)
    
    return PRODUCTION_OPTION

# Шаг 7: Контактные данные (ОБНОВЛЕНО: Формат)
async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(context.user_data)
    
    keyboard = [[InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_production")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"**ШАГ 7/7: КОНТАКТНЫЕ ДАННЫЕ**\n"
        "──────────────\n"
        f"{E_COST} **Финальная стоимость кампании**:\n"
        f"   Базовая: {format_number(base_price)}₽\n"
        f"   Скидка 50%: -{format_number(discount)}₽\n"
        f"   **Итоговая: {format_number(final_price)}₽**\n\n"
        f"{E_REACH} **Примерный охват**: ~{format_number(total_reach)} человек\n"
        "─────────────────\n"
        f"📝 **ВВЕДИТЕ ВАШЕ ИМЯ**\n"
        "─────────────────\n"
        f"(нажмите Enter для отправки)"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return CONTACT_INFO

# Обработка контактной информации (КРИТИЧЕСКИ ОБНОВЛЕНО: Сохранение номера заявки и автоуведомление)
async def process_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        
        # 1. Имя
        if 'contact_name' not in context.user_data:
            context.user_data['contact_name'] = text
            await update.message.reply_text(
                "📞 **Введите ваш телефон**:\n\n"
                "Формат: `+79XXXXXXXXX`\n"
                "Пример: `+79123456789`",
                parse_mode='Markdown'
            )
            return CONTACT_INFO
        
        # 2. Телефон
        elif 'phone' not in context.user_data:
            if not validate_phone(text):
                await update.message.reply_text(f"{E_CANCEL} **Неверный формат телефона**. Используйте формат: `+79XXXXXXXXX`", parse_mode='Markdown')
                return CONTACT_INFO
            context.user_data['phone'] = text
            await update.message.reply_text("📧 **Введите ваш email**:", parse_mode='Markdown')
            return CONTACT_INFO
        
        # 3. Email
        elif 'email' not in context.user_data:
            context.user_data['email'] = text
            await update.message.reply_text("🏢 **Введите название компании**:", parse_mode='Markdown')
            return CONTACT_INFO
        
        # 4. Компания
        elif 'company' not in context.user_data:
            context.user_data['company'] = text
            
            # Рассчитываем финальную стоимость и охват
            base_price, discount, final_price, total_reach, daily_listeners = calculate_campaign_price_and_reach(context.user_data)
            context.user_data['base_price'] = base_price
            context.user_data['discount'] = discount
            context.user_data['final_price'] = final_price
            
            # --- ГЕНЕРАЦИЯ И СОХРАНЕНИЕ НОМЕРА ЗАЯВКИ (КРИТИЧНО) ---
            campaign_number = f"R-{datetime.now().strftime('%d%m%y')}-{datetime.now().strftime('%H%M%S')}"
            context.user_data['campaign_number'] = campaign_number # Сохраняем для дальнейших действий
            context.user_data['user_id'] = update.message.from_user.id
            
            # Сохраняем заявку в БД
            conn = sqlite3.connect('campaigns.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO campaigns 
                (user_id, campaign_number, radio_stations, campaign_period, time_slots, branded_section, campaign_text, production_option, contact_name, company, phone, email, base_price, discount, final_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                context.user_data['user_id'],
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
            
            # --- АВТОМАТИЧЕСКАЯ ОТПРАВКА УВЕДОМЛЕНИЯ АДМИНУ (КРИТИЧНО) ---
            await send_admin_notification(context, context.user_data, campaign_number)
            
            # Отправляем подтверждение с финальными кнопками
            keyboard = [
                [
                    InlineKeyboardButton(f"{E_PDF} СФОРМИРОВАТЬ PDF", callback_data="generate_pdf"),
                    InlineKeyboardButton(f"{E_XLSX} СФОРМИРОВАТЬ EXCEL", callback_data="generate_excel")
                ],
                [
                    InlineKeyboardButton(f"{E_SEND} ОТПРАВИТЬ СЕБЕ В ТЕЛЕГРАММ", callback_data=f"send_to_telegram_{campaign_number}")
                ],
                [InlineKeyboardButton("📋 МОИ ЗАКАЗЫ", callback_data="personal_cabinet")],
                [InlineKeyboardButton("🚀 НОВЫЙ ЗАКАЗ", callback_data="new_order")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"{E_CHECK} **ЗАЯВКА ПРИНЯТА!**\n"
                "──────────────\n"
                "Спасибо за доверие! 😊 Мы уже начали работу.\n"
                "Наш менеджер *уже* получил вашу заявку.\n\n"
                f"📋 **№ заявки**: `{campaign_number}`\n"
                f"📅 **Старт**: в течение 3 дней\n"
                f"{E_COST} **Сумма со скидкой 50%**: {format_number(final_price)}₽\n"
                f"{E_REACH} **Примерный охват**: ~{format_number(total_reach)} человек\n\n"
                f"Выберите формат отчета:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return FINAL_ACTIONS
            
    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА в process_contact_info: {e}")
        await update.message.reply_text(
            f"{E_CANCEL} Произошла ошибка при сохранении заявки.\n"
            "Пожалуйста, начните заново: /start\n"
            "Или свяжитесь с поддержкой: t.me/AlexeyKhlistunov"
        )
        return ConversationHandler.END

# Обработка финальных действий (ОБНОВЛЕНО: Используется сохраненный номер и добавлен Excel)
async def handle_final_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        # Получаем сохраненный номер заявки
        campaign_number = context.user_data.get('campaign_number', 'R-000000') # На случай, если что-то пошло не так
        
        if query.data == "generate_pdf":
            success = await send_pdf_file(update, context, campaign_number)
            if not success:
                await query.message.reply_text(f"{E_CANCEL} Ошибка при создании PDF для #{campaign_number}. Попробуйте еще раз.")
            return FINAL_ACTIONS
        
        elif query.data == "generate_excel":
            success = await send_excel_file(update, context, campaign_number)
            if not success:
                await query.message.reply_text(f"{E_CANCEL} Ошибка при создании Excel для #{campaign_number}. Попробуйте еще раз.")
            return FINAL_ACTIONS
        
        elif query.data.startswith("send_to_telegram_"):
            campaign_number_from_callback = query.data.replace("send_to_telegram_", "")
            
            pdf_success = await send_pdf_file(update, context, campaign_number_from_callback)
            excel_success = await send_excel_file(update, context, campaign_number_from_callback)

            if pdf_success or excel_success:
                await query.message.reply_text(
                    f"{E_CHECK} Отчеты в PDF и Excel отправлены вам в этот чат.\n"
                    "Менеджер уже получил вашу заявку."
                )
            else:
                 await query.message.reply_text(f"{E_CANCEL} Произошла ошибка при генерации отчетов. Заявка сохранена.")
            
            return FINAL_ACTIONS
        
        elif query.data == "personal_cabinet":
            return await personal_cabinet(update, context)
        
        elif query.data == "new_order":
            context.user_data.clear()
            await query.message.reply_text("🚀 **Начинаем новую кампанию!**", parse_mode='Markdown')
            return await radio_selection(update, context)
        
        return FINAL_ACTIONS
        
    except Exception as e:
        logger.error(f"Ошибка в handle_final_actions: {e}")
        await query.message.reply_text(f"{E_CANCEL} Ошибка. Начните заново: /start")
        return ConversationHandler.END

# Личный кабинет (без изменений)
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
        orders_text = "**📋 ПОСЛЕДНИЕ ЗАКАЗЫ:**\n\n"
        for order in orders:
            orders_text += f"`{order[0]}` | *{order[1]}* | **{format_number(order[2])}₽** | {order[3][:10]}\n"
    else:
        orders_text = "📋 **У вас пока нет заказов**"
    
    keyboard = [[InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_final")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"**📋 ЛИЧНЫЙ КАБИНЕТ**\n"
        "──────────────\n"
        f"{orders_text}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return FINAL_ACTIONS

# Статистика охвата (ОБНОВЛЕНО: Формат)
async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "**📊 СТАТИСТИКА ОХВАТА**\n"
        "──────────────\n"
        f"• Ежедневный охват: **9,200+**\n"
        f"• Месячный охват: **68,000+**\n"
        f"• Доля рынка: **52%**\n"
        "────────────────\n"
        "**По станциям (в день):**\n"
        "• LOVE RADIO: 1,600\n"
        "• АВТОРАДИО: 1,400\n"  
        "• РАДИО ДАЧА: 1,800\n"
        "• РАДИО ШАНСОН: 1,200\n"
        "• РЕТРО FM: 1,500\n"
        "• ЮМОР FM: 1,100\n"
        "────────────────\n"
        "**🎯 Охватываем:**\n"
        "📍 Ялуторовск, Заводоуковск и +35 км вокруг городов\n\n"
        "🎧 В малых городах слушают *2.5 часа/день*"
        ,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return MAIN_MENU

# О нас (ОБНОВЛЕНО: Формат)
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton(f"{E_BACK} НАЗАД", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎙️ **РАДИО ТЮМЕНСКОЙ ОБЛАСТИ**\n"
        "──────────────\n"
        "**ℹ️ О НАС**\n\n"
        "Ведущий радиовещатель в регионе. Охватываем 52% радиорынка.\n\n"
        "**Юридическая информация:**\n"
        "Индивидуальный предприниматель\n"
        "Хлыстунов Алексей Александрович\n"
        "ОГРНИП 315723200067362\n\n"
        "📧 a.khlistunov@gmail.com\n"
        "📱 Telegram: t.me/AlexeyKhlistunov",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return MAIN_MENU

# Улучшенный обработчик главного меню (ОБНОВЛЕНО: Добавлен Excel для админа)
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
    
    # PDF для админа (ОБНОВЛЕНО: паттерн)
    elif query.data.startswith("generate_pdf_admin_"):
        campaign_number = query.data.replace("generate_pdf_admin_", "")
        try:
            # Используем данные из контекста (предполагаем, что админ нажал сразу)
            pdf_data = create_pdf_file(context.user_data, campaign_number) 
            if pdf_data:
                await query.message.reply_document(
                    document=io.BytesIO(pdf_data),
                    filename=f"mediaplan_{campaign_number}.pdf",
                    caption=f"📄 PDF для клиента #{campaign_number}"
                )
            else:
                await query.message.reply_text(f"{E_CANCEL} Ошибка при создании PDF")
        except Exception as e:
            await query.message.reply_text(f"{E_CANCEL} Ошибка при создании PDF: {e}")
            
    # EXCEL для админа (НОВЫЙ БЛОК)
    elif query.data.startswith("generate_excel_admin_"): 
        campaign_number = query.data.replace("generate_excel_admin_", "")
        try:
            excel_data = create_excel_file(context.user_data, campaign_number)
            if excel_data:
                file_io = io.BytesIO(excel_data)
                file_io.name = f"mediaplan_{campaign_number}.xlsx"
                await query.message.reply_document(
                    document=file_io,
                    filename=f"mediaplan_{campaign_number}.xlsx",
                    caption=f"💾 EXCEL для клиента #{campaign_number}"
                )
            else:
                await query.message.reply_text(f"{E_CANCEL} Ошибка при создании EXCEL")
        except Exception as e:
            await query.message.reply_text(f"{E_CANCEL} Ошибка при создании EXCEL: {e}")
            
    # Кнопки-ссылки для админа
    elif query.data.startswith("call_"):
        phone = query.data.replace("call_", "")
        await query.answer(f"📞 Наберите: {phone}")
    
    elif query.data.startswith("email_"):
        email = query.data.replace("email_", "")
        await query.answer(f"✉️ Email: {email}")
    
    # НАВИГАЦИЯ (добавлены новые хэндлеры)
    elif query.data == "back_to_main":
        return await start(update, context)
    
    elif query.data == "back_to_radio":
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
    
    elif query.data == "back_to_final":
        # Возврат к финальным действиям после личного кабинета
        campaign_number = context.user_data.get('campaign_number', 'R-000000')
        keyboard = [
            [
                InlineKeyboardButton(f"{E_PDF} СФОРМИРОВАТЬ PDF", callback_data="generate_pdf"),
                InlineKeyboardButton(f"{E_XLSX} СФОРМИРОВАТЬ EXCEL", callback_data="generate_excel")
            ],
            [
                InlineKeyboardButton(f"{E_SEND} ОТПРАВИТЬ СЕБЕ В ТЕЛЕГРАММ", callback_data=f"send_to_telegram_{campaign_number}")
            ],
            [InlineKeyboardButton("📋 МОИ ЗАКАЗЫ", callback_data="personal_cabinet")],
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
    
    elif query.data == "provide_own_audio":
        # Переключатель "Пришлю свой ролик"
        current_state = context.user_data.get('provide_own_audio', False)
        context.user_data['provide_own_audio'] = not current_state
        return await campaign_creator(update, context)
    
    elif query.data == "to_production_option":
        return await production_option(update, context)
    
    elif query.data == "request_tts": # Новый хэндлер TTS
        return await handle_tts_request(update, context)
    
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
    
    # Обработчики разговоров (ОБНОВЛЕНО: Добавлен хэндлер для TTS)
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
                CallbackQueryHandler(handle_tts_request, pattern='^request_tts$'), # Новый хэндлер TTS
                CallbackQueryHandler(handle_main_menu, pattern='^(back_to_|skip_text|cancel_text|to_production_option|provide_own_audio|enter_text)')
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
            ],
            FINAL_ACTIONS: [
                CallbackQueryHandler(handle_final_actions, pattern='^.*$')
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    
    # Добавляем отдельный обработчик для админских кнопок (ОБНОВЛЕНО: Добавлен Excel)
    application.add_handler(CallbackQueryHandler(
        handle_main_menu, 
        pattern='^(generate_pdf_admin_|generate_excel_admin_|call_|email_)'
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
