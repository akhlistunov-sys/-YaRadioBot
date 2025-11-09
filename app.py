from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Базовая инициализация БД (из вашего bot.py)
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

@app.route('/')
def home():
    return jsonify({
        "status": "success", 
        "message": "YaRadioBot API работает!",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "database": "connected" if init_db() else "error",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/radio-stations', methods=['GET'])
def get_radio_stations():
    """Получить список радиостанций (данные из вашего bot.py)"""
    stations = {
        "LOVE RADIO": 540,
        "АВТОРАДИО": 3250,
        "РАДИО ДАЧА": 3250,
        "РАДИО ШАНСОН": 2900,
        "РЕТРО FM": 3600,
        "ЮМОР FM": 1260
    }
    return jsonify({"stations": stations})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
