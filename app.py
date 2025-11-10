from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import io
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# 🔐 ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
load_dotenv()

# 🚀 СОЗДАНИЕ FLASK ПРИЛОЖЕНИЯ
app = Flask(__name__, static_folder='frontend')
CORS(app)

# 📊 ОБНОВЛЕННЫЕ КОНСТАНТЫ ИЗ .env
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU')
ADMIN_TELEGRAM_ID = int(os.getenv('ADMIN_TELEGRAM_ID', '174046571'))
BASE_PRICE_PER_SECOND = float(os.getenv('BASE_PRICE_PER_SECOND', '2.0'))
MIN_PRODUCTION_COST = int(os.getenv('MIN_PRODUCTION_COST', '2000'))
MIN_BUDGET = int(os.getenv('MIN_BUDGET', '7000'))

# 🔧 ОБНОВЛЕННЫЕ КОНСТАНТЫ ИЗ BOT.PY
TIME_SLOTS_DATA = [
    {"time": "06:00-07:00", "label": "Подъем, сборы", "premium": True, "coverage_percent": 6},
    {"time": "07:00-08:00", "label": "Утренние поездки", "premium": True, "coverage_percent": 10},
    {"time": "08:00-09:00", "label": "Пик трафика", "premium": True, "coverage_percent": 12},
    {"time": "09:00-10:00", "label": "Начало работы", "premium": True, "coverage_percent": 8},
    {"time": "10:00-11:00", "label": "Рабочий процесс", "premium": True, "coverage_percent": 7},
    {"time": "11:00-12:00", "label": "Предобеденное время", "premium": True, "coverage_percent": 6},
    {"time": "12:00-13:00", "label": "Обеденный перерыв", "premium": True, "coverage_percent": 5},
    {"time": "13:00-14:00", "label": "После обеда", "premium": True, "coverage_percent": 5},
    {"time": "14:00-15:00", "label": "Вторая половина дня", "premium": True, "coverage_percent": 5},
    {"time": "15:00-16:00", "label": "Рабочий финиш", "premium": True, "coverage_percent": 6},
    {"time": "16:00-17:00", "label": "Конец рабочего дня", "premium": True, "coverage_percent": 7},
    {"time": "17:00-18:00", "label": "Вечерние поездки", "premium": True, "coverage_percent": 10},
    {"time": "18:00-19:00", "label": "Пик трафика", "premium": True, "coverage_percent": 8},
    {"time": "19:00-20:00", "label": "Домашний вечер", "premium": True, "coverage_percent": 4},
    {"time": "20:00-21:00", "label": "Вечерний отдых", "premium": True, "coverage_percent": 4}
]

# 🎯 ОБНОВЛЕННЫЕ ОХВАТЫ РАДИОСТАНЦИЙ
STATION_COVERAGE = {
    "LOVE RADIO": 700,      # 👈 ОБНОВЛЕНО: 600-800 → 700
    "АВТОРАДИО": 3250,
    "РАДИО ДАЧА": 3250, 
    "РАДИО ШАНСОН": 2900,
    "РЕТРО FM": 3600,
    "ЮМОР FM": 1600         # 👈 ОБНОВЛЕНО: 1400-1800 → 1600
}

BRANDED_SECTION_PRICES = {
    "auto": 1.2,
    "realty": 1.15,
    "medical": 1.25,
    "custom": 1.3
}

PRODUCTION_OPTIONS = {
    "standard": {"price": 2000, "name": "СТАНДАРТНЫЙ РОЛИК", "desc": "Профессиональная озвучка, музыкальное оформление, срок: 2-3 дня"},
    "premium": {"price": 5000, "name": "ПРЕМИУМ РОЛИК", "desc": "Озвучка 2-мя голосами, индивидуальная музыка, срочное производство 1 день"}
}

# 🗄️ ФУНКЦИИ РАБОТЫ С БАЗОЙ ДАННЫХ
def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                campaign_number TEXT UNIQUE,
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
                actual_reach INTEGER,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return False

# 🧮 ОБНОВЛЕННЫЕ ФУНКЦИИ РАСЧЕТА
def format_number(num):
    """Форматирование чисел с пробелами"""
    return f"{num:,}".replace(",", " ")

def calculate_campaign_price_and_reach(user_data):
    """ОБНОВЛЕННАЯ ФУНКЦИЯ РАСЧЕТА С НОВОЙ МЕТОДИКОЙ"""
    try:
        base_duration = user_data.get("duration", 20)
        campaign_days = user_data.get("campaign_days", 30)
        selected_radios = user_data.get("selected_radios", [])
        selected_time_slots = user_data.get("selected_time_slots", [])
        
        if not selected_radios or not selected_time_slots:
            return 0, 0, MIN_BUDGET, 0, 0, 0, 0, 0
            
        num_stations = len(selected_radios)
        spots_per_day = len(selected_time_slots) * num_stations
        
        # БАЗОВАЯ СТОИМОСТЬ
        cost_per_spot = base_duration * BASE_PRICE_PER_SECOND
        base_air_cost = cost_per_spot * spots_per_day * campaign_days
        
        # 🆕 НОВАЯ МЕТОДИКА ПРЕМИУМ-СЛОТОВ: +5% ЗА КАЖДЫЙ
        premium_count = 0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                if slot["premium"]:
                    premium_count += 1
        
        time_multiplier = 1.0 + (premium_count * 0.05)  # 🆕 +5% за каждый премиум-слот
        
        # БРЕНДИРОВАННЫЕ РУБРИКИ
        branded_multiplier = 1.0
        branded_section = user_data.get("branded_section")
        if branded_section in BRANDED_SECTION_PRICES:
            branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
        
        # ПРОИЗВОДСТВО РОЛИКА
        production_cost = user_data.get("production_cost", 0)
        air_cost = int(base_air_cost * time_multiplier * branded_multiplier)
        base_price = air_cost + production_cost
        
        # СКИДКА И ИТОГ
        discount = int(base_price * 0.5)
        discounted_price = base_price - discount
        final_price = max(discounted_price, MIN_BUDGET)
        
        # 🆕 НОВАЯ ФОРМУЛА ОХВАТА С НАСЫЩЕНИЕМ
        total_listeners = sum(STATION_COVERAGE.get(radio, 0) for radio in selected_radios)
        
        total_coverage_percent = 0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                total_coverage_percent += slot["coverage_percent"]
        
        # 🆕 ФОРМУЛА: total_listeners × (1 - 0.7^(total_coverage_percent/100))
        unique_daily_coverage = int(total_listeners * (1 - 0.7 ** (total_coverage_percent / 100)))
        total_reach = int(unique_daily_coverage * campaign_days)
        
        return base_price, discount, final_price, total_reach, unique_daily_coverage, spots_per_day, total_coverage_percent, premium_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчета стоимости: {e}")
        return 0, 0, MIN_BUDGET, 0, 0, 0, 0, 0

def get_branded_section_name(section):
    names = {
        "auto": "Авторубрики (+20%)",
        "realty": "Недвижимость (+15%)",
        "medical": "Медицинские рубрики (+25%)",
        "custom": "Индивидуальная рубрика (+30%)"
    }
    return names.get(section, "Не выбрана")

def get_time_slots_detailed_text(selected_slots):
    """Получить детальное представление слотов с охватом"""
    slots_text = ""
    total_coverage = 0
    premium_count = 0
    
    for slot_index in selected_slots:
        if 0 <= slot_index < len(TIME_SLOTS_DATA):
            slot = TIME_SLOTS_DATA[slot_index]
            premium_emoji = "🚀" if slot["premium"] else "📊"
            coverage_percent = slot["coverage_percent"]
            total_coverage += coverage_percent
            if slot["premium"]:
                premium_count += 1
            slots_text += f"• {slot['time']} - {slot['label']}: {coverage_percent}% {premium_emoji}\n"
    
    return slots_text, total_coverage, premium_count

def create_excel_file_from_db(campaign_number):
    """ОБНОВЛЕННАЯ ФУНКЦИЯ СОЗДАНИЯ EXCEL С НОВОЙ МЕТОДИКОЙ"""
    try:
        logger.info(f"🔍 Создание Excel для кампании #{campaign_number}")
        
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM campaigns WHERE campaign_number = ?", (campaign_number,))
        campaign_data = cursor.fetchone()
        conn.close()
        
        if not campaign_data:
            logger.error(f"❌ Кампания #{campaign_number} не найдена в БД")
            return None
            
        logger.info(f"✅ Кампания #{campaign_number} найдена в БД")
        
        # Подготовка данных пользователя
        user_data = {
            "selected_radios": campaign_data[3].split(",") if campaign_data[3] else [],
            "start_date": campaign_data[4],
            "end_date": campaign_data[5],
            "campaign_days": campaign_data[6],
            "selected_time_slots": list(map(int, campaign_data[7].split(","))) if campaign_data[7] else [],
            "branded_section": campaign_data[8],
            "campaign_text": campaign_data[9],
            "production_option": campaign_data[10],
            "contact_name": campaign_data[11],
            "company": campaign_data[12],
            "phone": campaign_data[13],
            "email": campaign_data[14],
            "duration": campaign_data[15],
            "production_cost": PRODUCTION_OPTIONS.get(campaign_data[10], {}).get("price", 0)
        }
        
        # 🆕 РАСЧЕТ С НОВОЙ МЕТОДИКОЙ
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent, premium_count = calculate_campaign_price_and_reach(user_data)
        
        # Создание Excel файла
        wb = Workbook()
        ws = wb.active
        ws.title = f"Медиаплан {campaign_number}"
        
        # Стили
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        title_font = Font(bold=True, size=12)
        border = Border(left=Side(style="thin"), right=Side(style="thin"), 
                       top=Side(style="thin"), bottom=Side(style="thin"))
        
        # Заголовок
        ws.merge_cells("A1:G1")
        ws["A1"] = f"МЕДИАПЛАН КАМПАНИИ #{campaign_number}"
        ws["A1"].font = header_font
        ws["A1"].fill = header_fill
        ws["A1"].alignment = Alignment(horizontal="center")
        
        ws.merge_cells("A2:G2")
        ws["A2"] = "РАДИО ТЮМЕНСКОЙ ОБЛАСТИ - ОБНОВЛЕННЫЕ РАСЧЕТЫ"
        ws["A2"].font = Font(bold=True, size=12, color="366092")
        ws["A2"].alignment = Alignment(horizontal="center")
        
        # Информация о кампании
        current_row = 4
        
        # 🆕 РАЗДЕЛ: ДЕТАЛИ РАСЧЕТА
        ws[f"A{current_row}"] = "🎯 ДЕТАЛИ РАСЧЕТА (ОБНОВЛЕННАЯ МЕТОДИКА):"
        ws[f"A{current_row}"].font = title_font
        current_row += 1
        
        # 🆕 Премиум-слоты
        ws[f"A{current_row}"] = f"• Премиум-слотов выбрано: {premium_count}"
        current_row += 1
        ws[f"A{current_row}"] = f"• Надбавка за премиум: +{premium_count * 5}% ({premium_count} × 5%)"
        current_row += 1
        
        # 🆕 Формула охвата
        ws[f"A{current_row}"] = "• Формула охвата: с учетом насыщения аудитории"
        current_row += 1
        ws[f"A{current_row}"] = "  (total_listeners × (1 - 0.7^(total_coverage_percent/100)))"
        current_row += 2
        
        # Параметры кампании
        ws[f"A{current_row}"] = "📊 ПАРАМЕТРЫ КАМПАНИИ:"
        ws[f"A{current_row}"].font = title_font
        current_row += 1
        
        params = [
            f"Радиостанции: {', '.join(user_data.get('selected_radios', []))}",
            f"Период: {user_data.get('start_date')} - {user_data.get('end_date')} ({user_data.get('campaign_days')} дней)",
            f"Выходов в день: {spots_per_day}",
            f"Всего выходов за период: {spots_per_day * user_data.get('campaign_days', 30)}",
            f"Хронометраж ролика: {user_data.get('duration', 20)} сек",
            f"Брендированная рубрика: {get_branded_section_name(user_data.get('branded_section'))}",
            f"Производство: {PRODUCTION_OPTIONS.get(user_data.get('production_option', 'ready'), {}).get('name', 'Не выбрано')}",
            f"Суммарный охват слотов: {total_coverage_percent}%"
        ]
        
        for param in params:
            ws[f"A{current_row}"] = f"• {param}"
            current_row += 1
        
        current_row += 1
        
        # 🆕 РАЗДЕЛ: ТИП РОЛИКА
        ws[f"A{current_row}"] = "🎙️ ТИП РОЛИКА:"
        ws[f"A{current_row}"].font = title_font
        current_row += 1
        
        if user_data.get('campaign_text'):
            ws[f"A{current_row}"] = f"• Текст ролика (авто хронометраж: {user_data.get('duration', 20)} сек)"
        else:
            ws[f"A{current_row}"] = f"• Готовый аудиофайл (хронометраж: {user_data.get('duration', 20)} сек)"
        current_row += 2
        
        # Радиостанции с ОБНОВЛЕННЫМИ охватами
        ws[f"A{current_row}"] = "📻 ВЫБРАННЫЕ РАДИОСТАНЦИИ (ОБНОВЛЕННЫЕ ОХВАТЫ):"
        ws[f"A{current_row}"].font = title_font
        current_row += 1
        
        total_listeners = 0
        for radio in user_data.get("selected_radios", []):
            listeners = STATION_COVERAGE.get(radio, 0)
            total_listeners += listeners
            ws[f"A{current_row}"] = f"• {radio}: ~{format_number(listeners)} слушателей"
            current_row += 1
        
        ws[f"A{current_row}"] = f"• ИТОГО: ~{format_number(total_listeners)} слушателей"
        ws[f"A{current_row}"].font = Font(bold=True)
        current_row += 2
        
        # Временные слоты
        ws[f"A{current_row}"] = "🕒 ВЫБРАННЫЕ ВРЕМЕННЫЕ СЛОТЫ:"
        ws[f"A{current_row}"].font = title_font
        current_row += 1
        
        slots_text, total_slots_coverage, premium_count_calc = get_time_slots_detailed_text(user_data.get("selected_time_slots", []))
        for line in slots_text.split('\n'):
            if line.strip():
                ws[f"A{current_row}"] = line
                current_row += 1
        
        current_row += 1
        
        # 🆕 РАСЧЕТНЫЙ ОХВАТ С НОВОЙ ФОРМУЛОЙ
        ws[f"A{current_row}"] = "🎯 РАСЧЕТНЫЙ ОХВАТ (ОБНОВЛЕННАЯ ФОРМУЛА):"
        ws[f"A{current_row}"].font = title_font
        current_row += 1
        
        ws[f"A{current_row}"] = f"• Выходов в день: {spots_per_day}"
        current_row += 1
        ws[f"A{current_row}"] = f"• Уникальных слушателей в день: ~{format_number(daily_coverage)} чел."
        current_row += 1
        ws[f"A{current_row}"] = f"• Общий охват за период: ~{format_number(total_reach)} чел."
        current_row += 2
        
        # Финансовая информация
        ws[f"A{current_row}"] = "💰 ФИНАНСОВАЯ ИНФОРМАЦИЯ:"
        ws[f"A{current_row}"].font = title_font
        current_row += 1
        
        financial_data = [
            ["Позиция", "Сумма (₽)"],
            ["Эфирное время", base_price - user_data.get("production_cost", 0)],
            ["Производство ролика", user_data.get("production_cost", 0)],
            ["", ""],
            ["Базовая стоимость", base_price],
            ["Скидка 50%", -discount],
            ["", ""],
            ["ИТОГО", final_price]
        ]
        
        for i, (item, value) in enumerate(financial_data):
            ws[f"A{current_row + i}"] = item
            if isinstance(value, int):
                ws[f"B{current_row + i}"] = value
                if item == "ИТОГО":
                    ws[f"B{current_row + i}"].font = Font(bold=True, color="FF0000")
                elif item == "Скидка 50%":
                    ws[f"B{current_row + i}"].font = Font(color="00FF00")
            else:
                ws[f"B{current_row + i}"] = value
        
        current_row += len(financial_data) + 2
        
        # Контакты
        ws[f"A{current_row}"] = "👤 ВАШИ КОНТАКТЫ:"
        ws[f"A{current_row}"].font = title_font
        current_row += 1
        
        contacts = [
            f"Имя: {user_data.get('contact_name', 'Не указано')}",
            f"Телефон: {user_data.get('phone', 'Не указан')}",
            f"Email: {user_data.get('email', 'Не указан')}",
            f"Компания: {user_data.get('company', 'Не указана')}"
        ]
        
        for contact in contacts:
            ws[f"A{current_row}"] = f"• {contact}"
            current_row += 1
        
        current_row += 1
        ws[f"A{current_row}"] = f"📅 Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        # Настройка столбцов
        ws.column_dimensions["A"].width = 45
        ws.column_dimensions["B"].width = 15
        
        # Сохранение в buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        logger.info(f"✅ Excel файл успешно создан для кампании #{campaign_number}")
        return buffer
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании Excel: {e}")
        return None

# 🌐 API МАРШРУТЫ
@app.route('/')
def serve_frontend():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('frontend', filename)

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy", 
        "database": "connected" if init_db() else "error",
        "timestamp": datetime.now().isoformat()
    })

# 🆕 ЭНДПОИНТ ДЛЯ СКАЧИВАНИЯ EXCEL
@app.route('/api/campaign-excel/<campaign_number>')
def download_campaign_excel(campaign_number):
    """Скачать Excel медиаплан кампании"""
    try:
        excel_buffer = create_excel_file_from_db(campaign_number)
        if excel_buffer:
            return send_file(
                excel_buffer,
                as_attachment=True,
                download_name=f"mediaplan_{campaign_number}.xlsx",
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            return jsonify({"success": False, "error": "Файл не найден"}), 404
    except Exception as e:
        logger.error(f"❌ Ошибка скачивания Excel: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# 🚀 ЗАПУСК ПРИЛОЖЕНИЯ
if __name__ == '__main__':
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Инициализация базы данных
    init_db()
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Запуск приложения на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
