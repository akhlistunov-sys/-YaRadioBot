from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv  # 👈 ДОБАВИТЬ ЭТУ СТРОКУ

# 🔐 ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
load_dotenv()  # 👈 ДОБАВИТЬ ЭТУ СТРОКУ

# 📊 КОНСТАНТЫ ИЗ .env
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU')
ADMIN_TELEGRAM_ID = int(os.getenv('ADMIN_TELEGRAM_ID', '174046571'))
BASE_PRICE_PER_SECOND = float(os.getenv('BASE_PRICE_PER_SECOND', '2.0'))
MIN_PRODUCTION_COST = int(os.getenv('MIN_PRODUCTION_COST', '2000'))
MIN_BUDGET = int(os.getenv('MIN_BUDGET', '7000'))

# Остальной код остается без изменений...

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

# 🗄️ ФУНКЦИИ РАБОТЫ С БАЗОЙ ДАННЫХ
def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        # Таблица кампаний
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
        
        # Таблица для ограничения частоты запросов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return False

def check_rate_limit(user_id: int) -> bool:
    """Проверка ограничения в 5 заявок в день"""
    try:
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM campaigns 
            WHERE user_id = ? AND created_at >= datetime('now', '-1 day')
        """, (user_id,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count < 5
    except Exception as e:
        logger.error(f"❌ Ошибка проверки лимита: {e}")
        return True

# 🧮 ФУНКЦИИ РАСЧЕТА ИЗ BOT.PY
def format_number(num):
    """Форматирование чисел с пробелами"""
    return f"{num:,}".replace(",", " ")

def calculate_campaign_price_and_reach(user_data):
    """ОБНОВЛЕННАЯ ФУНКЦИЯ РАСЧЕТА С РАЗНЫМ ОХВАТОМ СЛОТОВ (из bot.py)"""
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
        
        # ОБНОВЛЕННЫЙ РАСЧЕТ ОХВАТА С РАЗНЫМИ % СЛОТОВ
        total_listeners = sum(STATION_COVERAGE.get(radio, 0) for radio in selected_radios)
        
        # Сумма % охвата выбранных слотов
        total_coverage_percent = 0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                total_coverage_percent += slot["coverage_percent"]
        
        # Уникальный охват с учетом пересечения аудитории (0.7)
        unique_daily_coverage = int(total_listeners * 0.7 * (total_coverage_percent / 100))
        total_reach = int(unique_daily_coverage * campaign_days)
        
        return base_price, discount, final_price, total_reach, unique_daily_coverage, spots_per_day, total_coverage_percent
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчета стоимости: {e}")
        return 0, 0, MIN_BUDGET, 0, 0, 0, 0

def validate_date(date_text: str) -> bool:
    """Проверка валидности даты"""
    try:
        date = datetime.strptime(date_text, "%d.%m.%Y")
        if date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            return False
        if date > datetime.now() + timedelta(days=365):
            return False
        return True
    except ValueError:
        return False

def validate_phone(phone: str) -> bool:
    """Упрощенная валидация телефона"""
    if not phone:
        return False
    # Базовая проверка - телефон должен содержать цифры
    return any(char.isdigit() for char in phone)

# 🌐 API МАРШРУТЫ

@app.route('/')
def serve_frontend():
    """Главная страница фронтенда"""
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Статические файлы фронтенда"""
    return send_from_directory('frontend', filename)

# 🔍 ИНФОРМАЦИОННЫЕ ЭНДПОИНТЫ

@app.route('/api/health')
def health_check():
    """Проверка здоровья приложения"""
    return jsonify({
        "status": "healthy",
        "database": "connected" if init_db() else "error",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route('/api/radio-stations', methods=['GET'])
def get_radio_stations():
    """Получить список радиостанций с описаниями"""
    try:
        stations_with_info = [
            {
                "name": "LOVE RADIO",
                "listeners": 540,
                "description": "👩 Молодёжь 16-35 лет",
                "emoji": "💖"
            },
            {
                "name": "АВТОРАДИО", 
                "listeners": 3250,
                "description": "👨 Автомобилисты 25-55 лет",
                "emoji": "🚗"
            },
            {
                "name": "РАДИО ДАЧА",
                "listeners": 3250,
                "description": "👨👩 Семья 35-60 лет", 
                "emoji": "🏠"
            },
            {
                "name": "РАДИО ШАНСОН",
                "listeners": 2900,
                "description": "👨 Мужчины 30-60+ лет",
                "emoji": "🎸"
            },
            {
                "name": "РЕТРО FM",
                "listeners": 3600,
                "description": "👴👵 Взрослые 35-65 лет",
                "emoji": "🎵"
            },
            {
                "name": "ЮМОР FM",
                "listeners": 1260,
                "description": "👦👧 Молодежь 12-19 и взрослые 25-45 лет",
                "emoji": "🎭"
            }
        ]
        
        return jsonify({
            "success": True,
            "stations": stations_with_info,
            "total_stations": len(stations_with_info)
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения радиостанций: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/time-slots', methods=['GET'])
def get_time_slots():
    """Получить временные слоты"""
    try:
        return jsonify({
            "success": True,
            "time_slots": TIME_SLOTS_DATA,
            "total_slots": len(TIME_SLOTS_DATA)
        })
    except Exception as e:
        logger.error(f"❌ Ошибка получения временных слотов: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/branded-sections', methods=['GET'])
def get_branded_sections():
    """Получить брендированные рубрики"""
    try:
        branded_sections = [
            {
                "id": "auto",
                "name": "АВТОРУБРИКИ",
                "price_multiplier": 1.2,
                "price_text": "+20%",
                "description": "Готовые сценарии для автосалонов. \"30 секунд о китайских автомобилях\", \"30 секунд об АвтоВАЗе\""
            },
            {
                "id": "realty", 
                "name": "НЕДВИЖИМОСТЬ",
                "price_multiplier": 1.15,
                "price_text": "+15%",
                "description": "Рубрики для агентств недвижимости. \"Совет по недвижимости\", \"Полезно знать при покупке квартиры\""
            },
            {
                "id": "medical",
                "name": "МЕДИЦИНСКИЕ РУБРИКИ", 
                "price_multiplier": 1.25,
                "price_text": "+25%",
                "description": "Экспертные форматы для клиник. \"Здоровое серде\", \"Совет врача\""
            },
            {
                "id": "custom",
                "name": "ИНДИВИДУАЛЬНАЯ РУБРИКА",
                "price_multiplier": 1.3, 
                "price_text": "+30%",
                "description": "Разработка под ваш бизнес. Уникальный контент и сценарий"
            }
        ]
        
        return jsonify({
            "success": True,
            "branded_sections": branded_sections,
            "total_sections": len(branded_sections)
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения брендированных рубрик: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/production-options', methods=['GET'])
def get_production_options():
    """Получить варианты производства роликов"""
    try:
        production_options = [
            {
                "id": "standard",
                "name": "СТАНДАРТНЫЙ РОЛИК",
                "price": 2000,
                "price_text": "от 2 000₽",
                "description": "Профессиональная озвучка, музыкальное оформление, срок: 2-3 дня"
            },
            {
                "id": "premium",
                "name": "ПРЕМИУМ РОЛИК", 
                "price": 5000,
                "price_text": "от 5 000₽",
                "description": "Озвучка 2-мя голосами, индивидуальная музыка, срочное производство 1 день"
            }
        ]
        
        return jsonify({
            "success": True,
            "production_options": production_options,
            "total_options": len(production_options)
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения вариантов производства: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# 🧮 ЭНДПОИНТЫ РАСЧЕТА

@app.route('/api/calculate', methods=['POST'])
def calculate_campaign():
    """Расчет стоимости кампании"""
    try:
        data = request.json
        logger.info(f"📊 Получен запрос на расчет: {data}")
        
        # Валидация обязательных полей
        if not data.get('selected_radios'):
            return jsonify({"success": False, "error": "Не выбраны радиостанции"}), 400
            
        if not data.get('selected_time_slots'):
            return jsonify({"success": False, "error": "Не выбраны временные слоты"}), 400
        
        # Подготовка данных для расчета
        user_data = {
            "selected_radios": data.get('selected_radios', []),
            "selected_time_slots": data.get('selected_time_slots', []),
            "duration": data.get('duration', 20),
            "campaign_days": data.get('campaign_days', 30),
            "branded_section": data.get('branded_section', ''),
            "production_option": data.get('production_option', ''),
            "production_cost": PRODUCTION_OPTIONS.get(data.get('production_option', ''), {}).get('price', 0)
        }
        
        # Вызов функции расчета из bot.py
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent = calculate_campaign_price_and_reach(user_data)
        
        result = {
            "success": True,
            "calculation": {
                "base_price": base_price,
                "discount": discount,
                "final_price": final_price,
                "total_reach": total_reach,
                "daily_coverage": daily_coverage,
                "spots_per_day": spots_per_day,
                "total_coverage_percent": total_coverage_percent,
                "campaign_days": user_data["campaign_days"],
                "duration": user_data["duration"]
            }
        }
        
        logger.info(f"✅ Расчет выполнен: {result['calculation']}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчета кампании: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/validate-dates', methods=['POST'])
def validate_dates():
    """Валидация дат кампании"""
    try:
        data = request.json
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({"success": False, "error": "Не указаны даты"}), 400
        
        # Проверка формата дат
        if not validate_date(start_date):
            return jsonify({
                "success": False, 
                "error": "Неверная дата начала. Формат: ДД.ММ.ГГГГ, дата не должна быть в прошлом"
            }), 400
            
        if not validate_date(end_date):
            return jsonify({
                "success": False, 
                "error": "Неверная дата окончания. Формат: ДД.ММ.ГГГГ, дата не должна быть в прошлом"
            }), 400
        
        # Парсинг дат
        start = datetime.strptime(start_date, "%d.%m.%Y")
        end = datetime.strptime(end_date, "%d.%m.%Y")
        
        if end <= start:
            return jsonify({
                "success": False, 
                "error": "Дата окончания должна быть после даты начала"
            }), 400
        
        campaign_days = (end - start).days + 1
        
        if campaign_days < 15:
            return jsonify({
                "success": False, 
                "error": "Минимальный период кампании - 15 дней"
            }), 400
        
        return jsonify({
            "success": True,
            "campaign_days": campaign_days,
            "start_date": start_date,
            "end_date": end_date
        })
        
    except ValueError as e:
        return jsonify({"success": False, "error": "Неверный формат даты. Используйте ДД.ММ.ГГГГ"}), 400
    except Exception as e:
        logger.error(f"❌ Ошибка валидации дат: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# 💾 ЭНДПОИНТЫ СОХРАНЕНИЯ ДАННЫХ

@app.route('/api/create-campaign', methods=['POST'])
def create_campaign():
    """Создание новой кампании"""
    try:
        data = request.json
        logger.info(f"📝 Создание кампании: {data.get('contact_name', 'Unknown')}")
        
        # Валидация обязательных полей
        required_fields = ['contact_name', 'contact_phone', 'selected_radios', 'selected_time_slots']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"success": False, "error": f"Не заполнено поле: {field}"}), 400
        
        # Валидация телефона
        if not validate_phone(data['contact_phone']):
            return jsonify({"success": False, "error": "Неверный формат телефона"}), 400
        
        # Проверка лимита заявок
        user_id = data.get('user_id', 0)
        if not check_rate_limit(user_id):
            return jsonify({
                "success": False, 
                "error": "Превышен лимит в 5 заявок в день. Попробуйте завтра или свяжитесь с поддержкой: @AlexeyKhlistunov"
            }), 429
        
        # Расчет стоимости
        user_data = {
            "selected_radios": data.get('selected_radios', []),
            "selected_time_slots": data.get('selected_time_slots', []),
            "duration": data.get('duration', 20),
            "campaign_days": data.get('campaign_days', 30),
            "branded_section": data.get('branded_section', ''),
            "production_option": data.get('production_option', ''),
            "production_cost": PRODUCTION_OPTIONS.get(data.get('production_option', ''), {}).get('price', 0)
        }
        
        base_price, discount, final_price, total_reach, daily_coverage, spots_per_day, total_coverage_percent = calculate_campaign_price_and_reach(user_data)
        
        # Генерация номера кампании
        campaign_number = f"R-{datetime.now().strftime('%H%M%S')}"
        
        # Сохранение в базу данных
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
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
            data.get("campaign_days", 30),
            ",".join(map(str, data.get("selected_time_slots", []))),
            data.get("branded_section", ""),
            data.get("campaign_text", ""),
            data.get("production_option", ""),
            data.get("contact_name", ""),
            data.get("company", ""),
            data.get("contact_phone", ""),
            data.get("contact_email", ""),
            data.get("duration", 20),
            base_price,
            discount,
            final_price,
            total_reach
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Кампания создана: #{campaign_number}")
        
        return jsonify({
            "success": True,
            "campaign_number": campaign_number,
            "calculation": {
                "base_price": base_price,
                "discount": discount,
                "final_price": final_price,
                "total_reach": total_reach,
                "daily_coverage": daily_coverage,
                "spots_per_day": spots_per_day
            },
            "message": "Кампания успешно создана! Менеджер свяжется с вами в течение 24 часов."
        })
        
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Ошибка базы данных: номер кампании уже существует"}), 500
    except Exception as e:
        logger.error(f"❌ Ошибка создания кампании: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# 📊 ЭНДПОИНТЫ ДЛЯ ЛИЧНОГО КАБИНЕТА

@app.route('/api/user-campaigns', methods=['GET'])
def get_user_campaigns():
    """Получить кампании пользователя"""
    try:
        user_id = request.args.get('user_id', type=int)
        
        if not user_id:
            return jsonify({"success": False, "error": "Не указан user_id"}), 400
        
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        # Активные кампании
        cursor.execute("""
            SELECT campaign_number, start_date, end_date, final_price, actual_reach, status, created_at
            FROM campaigns 
            WHERE user_id = ? AND status = 'active'
            ORDER BY created_at DESC
        """, (user_id,))
        active_campaigns = cursor.fetchall()
        
        # Завершенные кампании
        cursor.execute("""
            SELECT campaign_number, start_date, end_date, final_price, actual_reach, status, created_at
            FROM campaigns 
            WHERE user_id = ? AND status = 'completed'
            ORDER BY created_at DESC
        """, (user_id,))
        completed_campaigns = cursor.fetchall()
        
        # Статистика за 2025 год
        cursor.execute("""
            SELECT COUNT(*), SUM(final_price), SUM(actual_reach)
            FROM campaigns 
            WHERE user_id = ? AND strftime('%Y', created_at) = '2025'
        """, (user_id,))
        stats = cursor.fetchone()
        
        conn.close()
        
        # Форматирование результатов
        active_formatted = []
        for campaign in active_campaigns:
            active_formatted.append({
                "campaign_number": campaign[0],
                "start_date": campaign[1],
                "end_date": campaign[2],
                "final_price": campaign[3],
                "actual_reach": campaign[4],
                "status": campaign[5],
                "created_at": campaign[6]
            })
        
        completed_formatted = []
        for campaign in completed_campaigns:
            completed_formatted.append({
                "campaign_number": campaign[0],
                "start_date": campaign[1],
                "end_date": campaign[2],
                "final_price": campaign[3],
                "actual_reach": campaign[4],
                "status": campaign[5],
                "created_at": campaign[6]
            })
        
        stats_formatted = {
            "total_campaigns": stats[0] if stats and stats[0] else 0,
            "total_revenue": stats[1] if stats and stats[1] else 0,
            "total_reach": stats[2] if stats and stats[2] else 0
        }
        
        return jsonify({
            "success": True,
            "active_campaigns": active_formatted,
            "completed_campaigns": completed_formatted,
            "stats": stats_formatted
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения кампаний пользователя: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/campaign-stats', methods=['GET'])
def get_campaign_stats():
    """Получить детальную статистику по кампаниям"""
    try:
        user_id = request.args.get('user_id', type=int)
        
        if not user_id:
            return jsonify({"success": False, "error": "Не указан user_id"}), 400
        
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        # Все кампании пользователя
        cursor.execute("""
            SELECT campaign_number, start_date, end_date, final_price, actual_reach, status, created_at
            FROM campaigns 
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        all_campaigns = cursor.fetchall()
        
        # Статистика по годам
        cursor.execute("""
            SELECT strftime('%Y', created_at) as year, 
                   COUNT(*), SUM(final_price), SUM(actual_reach)
            FROM campaigns 
            WHERE user_id = ?
            GROUP BY strftime('%Y', created_at)
            ORDER BY year DESC
        """, (user_id,))
        yearly_stats = cursor.fetchall()
        
        conn.close()
        
        # Форматирование всех кампаний
        campaigns_formatted = []
        for campaign in all_campaigns:
            campaigns_formatted.append({
                "campaign_number": campaign[0],
                "start_date": campaign[1],
                "end_date": campaign[2],
                "final_price": campaign[3],
                "actual_reach": campaign[4],
                "status": campaign[5],
                "created_at": campaign[6]
            })
        
        # Форматирование статистики по годам
        yearly_formatted = []
        for year_stat in yearly_stats:
            yearly_formatted.append({
                "year": year_stat[0],
                "campaign_count": year_stat[1],
                "total_revenue": year_stat[2] if year_stat[2] else 0,
                "total_reach": year_stat[3] if year_stat[3] else 0
            })
        
        return jsonify({
            "success": True,
            "all_campaigns": campaigns_formatted,
            "yearly_stats": yearly_formatted
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# 🎯 ОБРАБОТЧИКИ ОШИБОК

@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint не найден"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "error": "Внутренняя ошибка сервера"}), 500

# 🚀 ЗАПУСК ПРИЛОЖЕНИЯ

if __name__ == '__main__':
    # Инициализация базы данных при запуске
    init_db()
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Запуск приложения на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
