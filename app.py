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

load_dotenv()

app = Flask(__name__, static_folder='frontend')
CORS(app)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID', '174046571')

from campaign_calculator import (
    calculate_campaign_price_and_reach,
    STATION_COVERAGE,
    TIME_SLOTS_DATA,
    PRODUCTION_OPTIONS,
    format_number
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON campaigns(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaign_number ON campaigns(campaign_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON campaigns(created_at)")
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return False

def send_telegram_to_admin(campaign_number, user_data):
    """ОТПРАВКА УВЕДОМЛЕНИЯ АДМИНУ В TELEGRAM"""
    try:
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
👥 ОХВАТ: ~{format_number(user_data.get('total_reach', 0))} чел.
"""
        
        text_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        text_data = {
            'chat_id': ADMIN_TELEGRAM_ID,
            'text': notification_text,
            'parse_mode': 'HTML'
        }
        response = requests.post(text_url, data=text_data)
        
        if response.status_code != 200:
            logger.error(f"❌ Ошибка отправки текста в Telegram: {response.text}")
            return False
        
        excel_buffer = create_excel_file_from_db(campaign_number)
        if excel_buffer:
            files = {'document': (f'mediaplan_{campaign_number}.xlsx', excel_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            doc_data = {'chat_id': ADMIN_TELEGRAM_ID}
            doc_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
            doc_response = requests.post(doc_url, files=files, data=doc_data)
            
            if doc_response.status_code != 200:
                logger.error(f"❌ Ошибка отправки файла в Telegram: {doc_response.text}")
        
        logger.info(f"✅ Уведомление отправлено админу для кампании #{campaign_number}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления админу: {e}")
        return False

def send_excel_to_client(campaign_number, user_telegram_id):
    """ОТПРАВКА EXCEL КЛИЕНТУ В TELEGRAM"""
    try:
        excel_buffer = create_excel_file_from_db(campaign_number)
        if excel_buffer and user_telegram_id:
            files = {'document': (f'mediaplan_{campaign_number}.xlsx', excel_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            doc_data = {'chat_id': user_telegram_id}
            doc_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
            doc_response = requests.post(doc_url, files=files, data=doc_data)
            
            if doc_response.status_code == 200:
                logger.info(f"✅ Excel отправлен клиенту {user_telegram_id} для кампании #{campaign_number}")
                return True
            else:
                logger.error(f"❌ Ошибка отправки Excel клиенту: {doc_response.text}")
                return False
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки Excel клиенту: {e}")
        return False

def create_excel_file_from_db(campaign_number):
    """СОЗДАНИЕ EXCEL МЕДИАПЛАНА БЕЗ РУБРИК И СКИДКИ"""
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
            
        user_data = {
            "selected_radios": campaign_data[3].split(",") if campaign_data[3] else [],
            "start_date": campaign_data[4],
            "end_date": campaign_data[5],
            "campaign_days": campaign_data[6],
            "selected_time_slots": list(map(int, campaign_data[7].split(","))) if campaign_data[7] else [],
            "campaign_text": campaign_data[8],
            "production_option": campaign_data[9],
            "contact_name": campaign_data[10],
            "company": campaign_data[11],
            "phone": campaign_data[12],
            "email": campaign_data[13],
            "duration": campaign_data[14],
            "base_price": campaign_data[15],
            "discount": campaign_data[16],
            "final_price": campaign_data[17],
            "actual_reach": campaign_data[18]
        }
        
        wb = Workbook()
        ws = wb.active
        ws.title = f"Медиаплан {campaign_number}"
        
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        title_font = Font(bold=True, size=12)
        normal_font = Font(size=10)
        
        ws.merge_cells("A1:B1")
        ws["A1"] = f"МЕДИАПЛАН КАМПАНИИ #{campaign_number}"
        ws["A1"].font = header_font
        ws["A1"].fill = header_fill
        ws["A1"].alignment = Alignment(horizontal="center")
        
        ws.merge_cells("A2:B2")
        ws["A2"] = "РАДИО ТЮМЕНСКОЙ ОБЛАСТИ"
        ws["A2"].font = title_font
        ws["A2"].alignment = Alignment(horizontal="center")
        
        ws.append([])
        
        ws.merge_cells("A4:B4")
        ws["A4"] = "✅ Ваша заявка принята! Спасибо за доверие!"
        ws["A4"].font = Font(bold=True, size=11)
        
        ws.append([])
        
        ws.merge_cells("A6:B6")
        ws["A6"] = "📊 ПАРАМЕТРЫ КАМПАНИИ:"
        ws["A6"].font = title_font
        
        ws["A7"] = "• Радиостанции: " + ", ".join(user_data["selected_radios"])
        ws["A8"] = f"• Период: {user_data['start_date']} - {user_data['end_date']} ({user_data['campaign_days']} дней)"
        
        spots_per_day = len(user_data["selected_time_slots"]) * len(user_data["selected_radios"])
        ws["A9"] = f"• Выходов в день: {spots_per_day}"
        ws["A10"] = f"• Всего выходов за период: {spots_per_day * user_data['campaign_days']}"
        ws["A11"] = f"• Хронометраж ролика: {user_data['duration']} сек"
        
        production_name = PRODUCTION_OPTIONS.get(user_data["production_option"], {}).get("name", "Не выбрано")
        ws["A12"] = f"• Производство: {production_name}"
        
        ws.append([])
        
        ws.merge_cells("A14:B14")
        ws["A14"] = "📻 ВЫБРАННЫЕ РАДИОСТАНЦИИ:"
        ws["A14"].font = title_font
        
        row = 15
        total_listeners = 0
        for radio in user_data["selected_radios"]:
            listeners = STATION_COVERAGE.get(radio, 0)
            total_listeners += listeners
            ws[f"A{row}"] = f"• {radio}: ~{format_number(listeners)} слушателей"
            row += 1
        
        ws[f"A{row}"] = f"• ИТОГО: ~{format_number(total_listeners)} слушателей"
        
        ws.append([])
        row += 2
        
        ws.merge_cells(f"A{row}:B{row}")
        ws[f"A{row}"] = "🕒 ВЫБРАННЫЕ ВРЕМЕННЫЕ СЛОТЫ:"
        ws[f"A{row}"].font = title_font
        row += 1
        
        for slot_index in user_data["selected_time_slots"]:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                ws[f"A{row}"] = f"• {slot['time']} - {slot['label']}"
                row += 1
        
        ws.append([])
        row += 1
        
        ws.merge_cells(f"A{row}:B{row}")
        ws[f"A{row}"] = "🎯 РАСЧЕТНЫЙ ОХВАТ:"
        ws[f"A{row}"].font = title_font
        row += 1
        
        calculation_data = {
            "selected_radios": user_data["selected_radios"],
            "selected_time_slots": user_data["selected_time_slots"],
            "campaign_days": user_data["campaign_days"],
            "duration": user_data["duration"]
        }
        
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent, premium_count = calculate_campaign_price_and_reach(calculation_data)
        
        ws[f"A{row}"] = f"• Выходов в день: {spots_per_day}"
        row += 1
        ws[f"A{row}"] = f"• Ежедневный охват: ~{format_number(daily_coverage)} чел."
        row += 1
        ws[f"A{row}"] = f"• Общий охват за период: ~{format_number(total_reach)} чел."
        
        ws.append([])
        row += 2
        
        ws.merge_cells(f"A{row}:B{row}")
        ws[f"A{row}"] = "💰 ФИНАНСОВАЯ ИНФОРМАЦИЯ:"
        ws[f"A{row}"].font = title_font
        row += 1
        
        ws[f"A{row}"] = "Позиция"
        ws[f"B{row}"] = "Сумма (₽)"
        row += 1
        
        production_cost = PRODUCTION_OPTIONS.get(user_data["production_option"], {}).get("price", 0)
        air_cost = user_data["base_price"] - production_cost
        
        ws[f"A{row}"] = "Эфирное время"
        ws[f"B{row}"] = air_cost
        row += 1
        
        if user_data["production_option"]:
            ws[f"A{row}"] = "Производство ролика"
            ws[f"B{row}"] = production_cost
            row += 1
        
        ws.append([])
        row += 1
        
        # УБРАНА СТРОКА СО СКИДКОЙ (discount всегда 0)
        ws[f"A{row}"] = "Базовая стоимость"
        ws[f"B{row}"] = user_data["base_price"]
        row += 1
        
        # Пропускаем строку со скидкой
        ws.append([])
        row += 1
        
        ws[f"A{row}"] = "ИТОГО"
        ws[f"B{row}"] = user_data["final_price"]
        ws[f"A{row}"].font = Font(bold=True)
        ws[f"B{row}"].font = Font(bold=True)
        
        for i in range(2):
            ws.append([])
            row += 1
        
        ws.merge_cells(f"A{row}:B{row}")
        ws[f"A{row}"] = "👤 ВАШИ КОНТАКТЫ:"
        ws[f"A{row}"].font = title_font
        row += 1
        
        ws[f"A{row}"] = f"• Имя: {user_data['contact_name']}"
        row += 1
        ws[f"A{row}"] = f"• Телефон: {user_data['phone']}"
        row += 1
        ws[f"A{row}"] = f"• Email: {user_data['email']}"
        row += 1
        ws[f"A{row}"] = f"• Компания: {user_data['company']}"
        
        ws.append([])
        row += 2
        
        ws.merge_cells(f"A{row}:B{row}")
        ws[f"A{row}"] = "📞 НАШИ КОНТАКТЫ:"
        ws[f"A{row}"].font = title_font
        row += 1
        
        ws[f"A{row}"] = "• Email: man@ya-radio.ru"
        row += 1
        ws[f"A{row}"] = "• Telegram: @AlexeyKhlistunov"
        
        ws.append([])
        row += 2
        
        ws.merge_cells(f"A{row}:B{row}")
        # ИЗМЕНЕНО: 24 часа вместо 3 дней
        ws[f"A{row}"] = "🎯 СТАРТ КАМПАНИИ:"
        ws[f"A{row}"].font = title_font
        row += 1
        
        ws[f"A{row}"] = "В течение 24 часов после подтверждения"
        
        ws.append([])
        row += 2
        
        ws.merge_cells(f"A{row}:B{row}")
        ws[f"A{row}"] = f"📅 Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        ws[f"A{row}"].font = Font(size=9, italic=True)
        
        ws.column_dimensions['A'].width = 50
        ws.column_dimensions['B'].width = 15
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        logger.info(f"✅ Excel файл успешно создан для кампании #{campaign_number}")
        return buffer
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании Excel: {e}")
        return None

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
@app.route('/')
def home():
    return jsonify({
        "status": "running", 
        "service": "YaRadioBot",
        "timestamp": datetime.now().isoformat()
    })
@app.route('/api/calculate', methods=['POST'])
def calculate_campaign():
    """Расчет стоимости кампании"""
    try:
        data = request.json
        user_data = {
            "selected_radios": data.get('selected_radios', []),
            "start_date": data.get('start_date'),
            "end_date": data.get('end_date'),
            "campaign_days": data.get('campaign_days', 30),
            "selected_time_slots": data.get('selected_time_slots', []),
            "duration": data.get('duration', 20),
            "production_option": data.get('production_option'),
            "production_cost": PRODUCTION_OPTIONS.get(data.get('production_option'), {}).get('price', 0)
        }
        
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent, premium_count = calculate_campaign_price_and_reach(user_data)
        
        return jsonify({
            "success": True,
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
        logger.error(f"Ошибка расчета стоимости: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/time-slots', methods=['GET'])
def get_time_slots():
    """Получить временные слоты"""
    try:
        return jsonify({
            "success": True,
            "time_slots": TIME_SLOTS_DATA
        })
    except Exception as e:
        logger.error(f"Ошибка получения временных слотов: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/production-options', methods=['GET'])
def get_production_options():
    """Получить варианты производства"""
    return jsonify({
        "success": True,
        "production_options": PRODUCTION_OPTIONS
    })

@app.route('/api/radio-stations', methods=['GET'])
def get_radio_stations():
    """Получить список радиостанций с охватами"""
    return jsonify({
        "success": True,
        "stations": STATION_COVERAGE
    })

@app.route('/api/create-campaign', methods=['POST'])
def create_campaign():
    """СОЗДАНИЕ НОВОЙ КАМПАНИИ С ЛИМИТОМ 2 В ДЕНЬ"""
    try:
        if not init_db():
            return jsonify({"success": False, "error": "Ошибка инициализации базы данных"}), 500
            
        data = request.json
        user_id = data.get('user_id', 0)
        user_telegram_id = data.get('user_telegram_id')
        
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM campaigns 
            WHERE user_id = ? AND created_at >= datetime('now', '-1 day')
        """, (user_id,))
        count = cursor.fetchone()[0]
        
        # ИЗМЕНЕНО: лимит с 5 на 2 кампании в день
        if count >= 2:
            conn.close()
            return jsonify({
                "success": False, 
                "error": "Превышен лимит в 2 заявки в день. Попробуйте завтра."
            }), 400
        
        calculation_data = {
            "selected_radios": data.get('selected_radios', []),
            "selected_time_slots": data.get('selected_time_slots', []),
            "campaign_days": data.get('campaign_days', 30),
            "duration": data.get('duration', 20),
            "production_option": data.get('production_option'),
            "production_cost": PRODUCTION_OPTIONS.get(data.get('production_option'), {}).get('price', 0)
        }
        
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent, premium_count = calculate_campaign_price_and_reach(calculation_data)
        
        campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
        
        cursor.execute("""
            INSERT INTO campaigns 
            (user_id, campaign_number, radio_stations, start_date, end_date, campaign_days,
             time_slots, campaign_text, production_option, contact_name,
             company, phone, email, duration, base_price, discount, final_price, actual_reach)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            campaign_number,
            ",".join(data.get("selected_radios", [])),
            data.get("start_date"),
            data.get("end_date"),
            data.get("campaign_days"),
            ",".join(map(str, data.get("selected_time_slots", []))),
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
        
        send_telegram_to_admin(campaign_number, data)
        
        if user_telegram_id:
            send_excel_to_client(campaign_number, user_telegram_id)
        
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

@app.route('/api/user-campaigns/<int:user_id>')
def get_user_campaigns(user_id):
    """ПОЛУЧЕНИЕ ИСТОРИИ КАМПАНИЙ ПОЛЬЗОВАТЕЛЯ"""
    try:
        if not init_db():
            return jsonify({"success": False, "error": "Ошибка инициализации базы данных"}), 500
            
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

@app.route('/api/send-excel/<campaign_number>', methods=['POST'])
def send_excel_to_user(campaign_number):
    """ОТПРАВКА EXCEL КЛИЕНТУ ПО ТРЕБОВАНИЮ"""
    try:
        data = request.json
        user_telegram_id = data.get('user_telegram_id')
        
        if not user_telegram_id:
            return jsonify({"success": False, "error": "Не указан Telegram ID"}), 400
            
        success = send_excel_to_client(campaign_number, user_telegram_id)
        
        if success:
            return jsonify({"success": True, "message": "Excel отправлен в Telegram"})
        else:
            return jsonify({"success": False, "error": "Ошибка отправки"}), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки Excel: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/delete-campaign/<campaign_number>', methods=['DELETE'])
def delete_campaign(campaign_number):
    """УДАЛЕНИЕ КАМПАНИИ"""
    try:
        if not init_db():
            return jsonify({"success": False, "error": "Ошибка инициализации базы данных"}), 500
            
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT status, start_date FROM campaigns WHERE campaign_number = ?", (campaign_number,))
        campaign = cursor.fetchone()
        
        if not campaign:
            conn.close()
            return jsonify({"success": False, "error": "Кампания не найдена"}), 404
            
        status, start_date = campaign
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d') if start_date else datetime.now()
        
        if status != 'active' or start_date_obj <= datetime.now():
            conn.close()
            return jsonify({"success": False, "error": "Можно удалять только активные кампании с будущей датой старта"}), 400
        
        cursor.execute("DELETE FROM campaigns WHERE campaign_number = ?", (campaign_number,))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Кампания удалена"})
        
    except Exception as e:
        logger.error(f"❌ Ошибка удаления кампании: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

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

@app.route('/api/confirmation/<campaign_number>')
def get_campaign_confirmation(campaign_number):
    """ПОЛУЧЕНИЕ ДАННЫХ ДЛЯ СТРАНИЦЫ ПОДТВЕРЖДЕНИЯ"""
    try:
        if not init_db():
            return jsonify({"success": False, "error": "Ошибка инициализации базы данных"}), 500
            
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT campaign_number, final_price, actual_reach, contact_name, phone, email, company, created_at
            FROM campaigns 
            WHERE campaign_number = ?
        """, (campaign_number,))
        
        campaign = cursor.fetchone()
        conn.close()
        
        if not campaign:
            return jsonify({"success": False, "error": "Кампания не найдена"}), 404
        
        return jsonify({
            "success": True,
            "campaign": {
                "campaign_number": campaign[0],
                "final_price": campaign[1],
                "actual_reach": campaign[2],
                "contact_name": campaign[3],
                "phone": campaign[4],
                "email": campaign[5],
                "company": campaign[6],
                "created_at": campaign[7]
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения данных подтверждения: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
import threading
import time
import requests
import atexit

class KeepAlive:
    def __init__(self):
        self.is_running = False
        self.thread = None
        
    def start(self):
        """Запуск фонового пинга"""
        if self.is_running:
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
        self.thread.start()
        logger.info("🚀 Фоновый самопинг запущен (интервал: 8 минут)")
    
    def _keep_alive_loop(self):
        """Основной цикл пинга"""
        while self.is_running:
            try:
                # Пингуем основной URL
                response = requests.get('https://yaradiobot.onrender.com/', timeout=30)
                logger.info(f"✅ Самопинг успешен: {response.status_code} - {datetime.now().strftime('%H:%M:%S')}")
            except requests.exceptions.Timeout:
                logger.warning("⏰ Таймаут самопинга")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка самопинга: {str(e)[:100]}")  # Обрезаем длинные сообщения
            
            # Ждем 8 минут (меньше 10, чтобы Render не успел уснуть)
            for _ in range(48):  # 48 * 10 сек = 8 минут
                if not self.is_running:
                    break
                time.sleep(10)
    
    def stop(self):
        """Остановка пинга"""
        self.is_running = False
        logger.info("🛑 Фоновый самопинг остановлен")

# Глобальный объект
keep_alive = KeepAlive()

# Добавьте в конец файла перед if __name__ == '__main__':
def setup_keep_alive():
    """Настройка и запуск самопинга"""
    # Регистрируем остановку при выходе
    atexit.register(keep_alive.stop)
    
    # Ждем немного перед стартом (чтобы приложение точно запустилось)
    def delayed_start():
        time.sleep(10)
        keep_alive.start()
    
    start_thread = threading.Thread(target=delayed_start, daemon=True)
    start_thread.start()

# В основном блоке:
if __name__ == '__main__':
    # Запускаем самопинг
    setup_keep_alive()
    
    # Существующий код
    init_db()
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Запуск приложения на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Запуск приложения на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
# [file content end]
