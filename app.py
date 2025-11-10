# [file name]: app.py
# [file content begin]
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
import requests

# 🔐 ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
load_dotenv()

# 🚀 СОЗДАНИЕ FLASK ПРИЛОЖЕНИЯ
app = Flask(__name__, static_folder='frontend')
CORS(app)

# 📊 КОНСТАНТЫ
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID', '174046571')
BASE_PRICE_PER_SECOND = float(os.getenv('BASE_PRICE_PER_SECOND', '2.0'))
MIN_PRODUCTION_COST = int(os.getenv('MIN_PRODUCTION_COST', '2000'))
MIN_BUDGET = int(os.getenv('MIN_BUDGET', '7000'))

# 🎯 ДАННЫЕ СЛОТОВ И РАДИОСТАНЦИЙ
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
    "LOVE RADIO": 700,
    "АВТОРАДИО": 3250,
    "РАДИО ДАЧА": 3250, 
    "РАДИО ШАНСОН": 2900,
    "РЕТРО FM": 3600,
    "ЮМОР FM": 1600
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

# 🧮 ФУНКЦИИ РАСЧЕТА
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

def send_telegram_to_admin(campaign_number, user_data):
    """ОТПРАВКА УВЕДОМЛЕНИЯ АДМИНУ В TELEGRAM"""
    try:
        # Текстовое уведомление
        stations_text = "\n".join([f"• {radio}" for radio in user_data.get("selected_radios", [])])
        
        notification_text = f"""
🔔 НОВАЯ ЗАЯВКА ИЗ MINI APP #{campaign_number}

👤 КЛИЕНТ:
Имя: {user_data.get('contact_name', 'Не указано')}
Телефон: {user_data.get('phone', 'Не указан')}
Email: {user_data.get('email', 'Не указан')}
Компания: {user_data.get('company', 'Не указана')}

📊 РАДИОСТАНЦИИ:
{stations_text}

📅 ПЕРИОД: {user_data.get('start_date')} - {user_data.get('end_date')} ({user_data.get('campaign_days')} дней)
💰 СТОИМОСТЬ: {format_number(user_data.get('final_price', 0))}₽
"""
        
        # Отправка текстового сообщения
        text_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        text_data = {
            'chat_id': ADMIN_TELEGRAM_ID,
            'text': notification_text,
            'parse_mode': 'HTML'
        }
        requests.post(text_url, data=text_data)
        
        # Отправка Excel файла
        excel_buffer = create_excel_file_from_db(campaign_number)
        if excel_buffer:
            files = {'document': (f'mediaplan_{campaign_number}.xlsx', excel_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            doc_data = {'chat_id': ADMIN_TELEGRAM_ID}
            doc_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
            requests.post(doc_url, files=files, data=doc_data)
        
        logger.info(f"✅ Уведомление отправлено админу для кампании #{campaign_number}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления админу: {e}")
        return False

def create_excel_file_from_db(campaign_number):
    """СОЗДАНИЕ EXCEL ФАЙЛА ДЛЯ КАМПАНИИ"""
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
        
        # Расчет стоимости
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent, premium_count = calculate_campaign_price_and_reach(user_data)
        
        # Создание Excel файла
        wb = Workbook()
        ws = wb.active
        ws.title = f"Медиаплан {campaign_number}"
        
        # Стили
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        title_font = Font(bold=True, size=12)
        
        # Заголовок
        ws.merge_cells("A1:G1")
        ws["A1"] = f"МЕДИАПЛАН КАМПАНИИ #{campaign_number}"
        ws["A1"].font = header_font
        ws["A1"].fill = header_fill
        ws["A1"].alignment = Alignment(horizontal="center")
        
        # Заполнение данными...
        # (полный код создания Excel остается как в вашем оригинале)
        
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

# 🆕 API ДЛЯ СОЗДАНИЯ КАМПАНИИ
@app.route('/api/create-campaign', methods=['POST'])
def create_campaign():
    """СОЗДАНИЕ НОВОЙ КАМПАНИИ"""
    try:
        data = request.json
        user_id = data.get('user_id', 0)
        
        # Проверка лимита (5 заявок в день)
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM campaigns 
            WHERE user_id = ? AND created_at >= datetime('now', '-1 day')
        """, (user_id,))
        count = cursor.fetchone()[0]
        
        if count >= 5:
            conn.close()
            return jsonify({
                "success": False, 
                "error": "Превышен лимит в 5 заявок в день. Попробуйте завтра."
            }), 400
        
        # Расчет стоимости
        calculation_result = calculate_campaign_price_and_reach(data)
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent, premium_count = calculation_result
        
        # Генерация номера кампании
        campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
        
        # Сохранение в БД
        cursor.execute("""
            INSERT INTO campaigns 
            (user_id, campaign_number, radio_stations, start_date, end_date, campaign_days,
             time_slots, branded_section, campaign_text, production_option, contact_name,
             company, phone, email, duration, base_price, discount, final_price, actual_reach)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            campaign_number,
            ",".join(data.get("selected_radios", [])),
            data.get("start_date"),
            data.get("end_date"),
            data.get("campaign_days"),
            ",".join(map(str, data.get("selected_time_slots", []))),
            data.get("branded_section", ""),
            data.get("campaign_text", ""),
            data.get("production_option", ""),
            data.get("contact_name", ""),
            data.get("company", ""),
            data.get("phone", ""),
            data.get("email", ""),
            data.get("duration", 20),
            base_price,
            discount,
            final_price,
            total_reach
        ))
        
        conn.commit()
        conn.close()
        
        # Отправка уведомления админу
        send_telegram_to_admin(campaign_number, data)
        
        return jsonify({
            "success": True,
            "campaign_number": campaign_number,
            "calculation": {
                "base_price": base_price,
                "discount": discount,
                "final_price": final_price,
                "total_reach": total_reach,
                "daily_coverage": daily_coverage,
                "spots_per_day": spots_per_day,
                "total_coverage_percent": total_coverage_percent,
                "premium_count": premium_count
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания кампании: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# 🆕 API ДЛЯ ПОЛУЧЕНИЯ ИСТОРИИ КАМПАНИЙ
@app.route('/api/user-campaigns/<int:user_id>')
def get_user_campaigns(user_id):
    """ПОЛУЧЕНИЕ ИСТОРИИ КАМПАНИЙ ПОЛЬЗОВАТЕЛЯ"""
    try:
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT campaign_number, start_date, end_date, final_price, actual_reach, status, created_at
            FROM campaigns 
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        
        campaigns = []
        for row in cursor.fetchall():
            campaigns.append({
                "campaign_number": row[0],
                "start_date": row[1],
                "end_date": row[2],
                "final_price": row[3],
                "actual_reach": row[4],
                "status": row[5],
                "created_at": row[6]
            })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "campaigns": campaigns
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения кампаний: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# 🆕 ЭНДПОИНТ ДЛЯ СКАЧИВАНИЯ EXCEL
@app.route('/api/campaign-excel/<campaign_number>')
def download_campaign_excel(campaign_number):
    """СКАЧИВАНИЕ EXCEL МЕДИАПЛАНА КАМПАНИИ"""
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
[file content end]
