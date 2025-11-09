from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__, static_folder='frontend')
CORS(app)

# Константы из вашего bot.py
BASE_PRICE_PER_SECOND = 2.0
MIN_PRODUCTION_COST = 2000
MIN_BUDGET = 7000

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

STATION_COVERAGE = {
    "LOVE RADIO": 540,
    "АВТОРАДИО": 3250,
    "РАДИО ДАЧА": 3250,
    "РАДИО ШАНСОН": 2900,
    "РЕТРО FM": 3600,
    "ЮМОР FM": 1260
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

# Инициализация БД
def init_db():
    try:
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        cursor.execute("""
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
                actual_reach INTEGER,
                status TEXT DEFAULT "active",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
        return False

# Функции расчета из вашего bot.py
def format_number(num):
    return f"{num:,}".replace(",", " ")

def calculate_campaign_price_and_reach(user_data):
    try:
        base_duration = user_data.get("duration", 20)
        campaign_days = user_data.get("campaign_days", 30)
        selected_radios = user_data.get("selected_radios", [])
        selected_time_slots = user_data.get("selected_time_slots", [])
        
        if not selected_radios or not selected_time_slots:
            return 0, 0, MIN_BUDGET, 0, 0, 0, 0
            
        num_stations = len(selected_radios)
        spots_per_day = len(selected_time_slots) * num_stations
        
        cost_per_spot = base_duration * BASE_PRICE_PER_SECOND
        base_air_cost = cost_per_spot * spots_per_day * campaign_days
        
        time_multiplier = 1.0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                if slot["premium"]:
                    time_multiplier = max(time_multiplier, 1.1)
        
        branded_multiplier = 1.0
        branded_section = user_data.get("branded_section")
        if branded_section in BRANDED_SECTION_PRICES:
            branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
        
        production_cost = user_data.get("production_cost", 0)
        air_cost = int(base_air_cost * time_multiplier * branded_multiplier)
        base_price = air_cost + production_cost
        
        discount = int(base_price * 0.5)
        discounted_price = base_price - discount
        final_price = max(discounted_price, MIN_BUDGET)
        
        total_listeners = sum(STATION_COVERAGE.get(radio, 0) for radio in selected_radios)
        
        total_coverage_percent = 0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                total_coverage_percent += slot["coverage_percent"]
        
        unique_daily_coverage = int(total_listeners * 0.7 * (total_coverage_percent / 100))
        total_reach = int(unique_daily_coverage * campaign_days)
        
        return base_price, discount, final_price, total_reach, unique_daily_coverage, spots_per_day, total_coverage_percent
        
    except Exception as e:
        print(f"Ошибка расчета стоимости: {e}")
        return 0, 0, MIN_BUDGET, 0, 0, 0, 0

# 🔥 ГЛАВНЫЙ МАРШРУТ - фронтенд
@app.route('/')
def serve_frontend():
    return send_from_directory('frontend', 'index.html')

# 🔥 Маршруты для статических файлов
@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('frontend/js', filename)

# API маршруты
@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "database": "connected" if init_db() else "error",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/radio-stations')
def get_radio_stations():
    return jsonify({"stations": STATION_COVERAGE})

@app.route('/api/time-slots')
def get_time_slots():
    return jsonify({
        "success": True,
        "time_slots": TIME_SLOTS_DATA
    })

@app.route('/api/branded-sections')
def get_branded_sections():
    return jsonify({
        "success": True,
        "branded_sections": BRANDED_SECTION_PRICES
    })

@app.route('/api/production-options')
def get_production_options():
    return jsonify({
        "success": True,
        "production_options": PRODUCTION_OPTIONS
    })

@app.route('/api/calculate', methods=['POST'])
def calculate_campaign():
    try:
        data = request.json
        user_data = {
            "selected_radios": data.get('selected_radios', []),
            "selected_time_slots": data.get('selected_time_slots', []),
            "duration": data.get('duration', 20),
            "campaign_days": data.get('campaign_days', 30),
            "branded_section": data.get('branded_section', 'auto'),
            "production_cost": data.get('production_cost', 0)
        }
        
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent = calculate_campaign_price_and_reach(user_data)
        
        return jsonify({
            "success": True,
            "calculation": {
                "base_price": base_price,
                "discount": discount,
                "final_price": final_price,
                "total_reach": total_reach,
                "daily_coverage": daily_coverage,
                "spots_per_day": spots_per_day,
                "total_coverage_percent": total_coverage_percent
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/create-campaign', methods=['POST'])
def create_campaign():
    try:
        data = request.json
        
        campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO campaigns 
            (user_id, campaign_number, radio_stations, time_slots, contact_name,
             company, phone, email, duration, base_price, discount, final_price, actual_reach)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('user_id', 0),
            campaign_number,
            ",".join(data.get("selected_radios", [])),
            ",".join(map(str, data.get("selected_time_slots", []))),
            data.get("contact_name", ""),
            data.get("company", ""),
            data.get("phone", ""),
            data.get("email", ""),
            data.get("duration", 20),
            data.get("base_price", 0),
            data.get("discount", 0),
            data.get("final_price", 0),
            data.get("total_reach", 0)
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "campaign_number": campaign_number,
            "message": "Кампания успешно создана"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
