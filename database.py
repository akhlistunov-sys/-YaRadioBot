import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Данные радиостанций (из оригинального бота)
STATION_COVERAGE = {
    "LOVE RADIO": 540,
    "АВТОРАДИО": 3250,
    "РАДИО ДАЧА": 3250,
    "РАДИО ШАНСОН": 2900,
    "РЕТРО FM": 3600,
    "ЮМОР FM": 1260
}

# Временные слоты (из оригинального бота)
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

# Брендированные рубрики
BRANDED_SECTION_PRICES = {
    "auto": 1.2,
    "realty": 1.15,
    "medical": 1.25,
    "custom": 1.3
}

# Производство роликов
PRODUCTION_OPTIONS = {
    "standard": {"price": 2000, "name": "СТАНДАРТНЫЙ РОЛИК", "desc": "Профессиональная озвучка, музыкальное оформление, срок: 2-3 дня"},
    "premium": {"price": 5000, "name": "ПРЕМИУМ РОЛИК", "desc": "Озвучка 2-мя голосами, индивидуальная музыка, срочное производство 1 день"}
}

# Цены
BASE_PRICE_PER_SECOND = 2.0
MIN_PRODUCTION_COST = 2000
MIN_BUDGET = 7000

def init_db():
    """Инициализация базы данных"""
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
                source TEXT DEFAULT "webapp",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")
        return False

def calculate_campaign_price_and_reach(campaign_data):
    """Расчет стоимости и охвата кампании (из оригинального бота)"""
    try:
        base_duration = campaign_data.get("duration", 20)
        campaign_days = campaign_data.get("campaign_days", 30)
        selected_radios = campaign_data.get("radio_stations", [])
        selected_time_slots = campaign_data.get("time_slots", [])
        
        if not selected_radios or not selected_time_slots:
            return 0, 0, MIN_BUDGET, 0, 0, 0, 0
            
        num_stations = len(selected_radios)
        spots_per_day = len(selected_time_slots) * num_stations
        
        cost_per_spot = base_duration * BASE_PRICE_PER_SECOND
        base_air_cost = cost_per_spot * spots_per_day * campaign_days
        
        # Множитель времени
        time_multiplier = 1.0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                if slot["premium"]:
                    time_multiplier = max(time_multiplier, 1.1)
        
        # Множитель рубрики
        branded_multiplier = 1.0
        branded_section = campaign_data.get("branded_section")
        if branded_section in BRANDED_SECTION_PRICES:
            branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
        
        # Стоимость производства
        production_cost = campaign_data.get("production_cost", 0)
        
        # Расчет стоимости
        air_cost = int(base_air_cost * time_multiplier * branded_multiplier)
        base_price = air_cost + production_cost
        
        discount = int(base_price * 0.5)  # Скидка 50%
        discounted_price = base_price - discount
        final_price = max(discounted_price, MIN_BUDGET)
        
        # Расчет охвата
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
        logger.error(f"Ошибка расчета стоимости: {e}")
        return 0, 0, MIN_BUDGET, 0, 0, 0, 0

def save_campaign_to_db(data):
    """Сохранение кампании в базу данных"""
    try:
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        campaign_number = f"WA-{datetime.now().strftime('%H%M%S')}"
        
        cursor.execute("""
            INSERT INTO campaigns 
            (user_id, campaign_number, radio_stations, start_date, end_date, 
             campaign_days, time_slots, branded_section, campaign_text, production_option,
             contact_name, company, phone, email, duration, 
             base_price, discount, final_price, actual_reach)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('user_id'),
            campaign_number,
            ",".join(data.get('radio_stations', [])),
            data.get('start_date'),
            data.get('end_date'),
            data.get('campaign_days'),
            ",".join(map(str, data.get('time_slots', []))),
            data.get('branded_section'),
            data.get('campaign_text'),
            data.get('production_option'),
            data.get('contact_name'),
            data.get('company'),
            data.get('phone'),
            data.get('email'),
            data.get('duration', 20),
            data.get('base_price', 0),
            data.get('discount', 0),
            data.get('final_price', 0),
            data.get('actual_reach', 0)
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Кампания {campaign_number} сохранена в БД")
        return campaign_number
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения кампании: {e}")
        return None

def format_number(num):
    """Форматирование чисел с пробелами"""
    return f"{num:,}".replace(",", " ")

def get_branded_section_name(section):
    """Название брендированной рубрики"""
    names = {
        "auto": "Авторубрики (+20%)",
        "realty": "Недвижимость (+15%)",
        "medical": "Медицинские рубрики (+25%)",
        "custom": "Индивидуальная рубрика (+30%)"
    }
    return names.get(section, "Не выбрана")

def get_production_option_name(option):
    """Название опции производства"""
    return PRODUCTION_OPTIONS.get(option, {}).get("name", "Не выбрано")
