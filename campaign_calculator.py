# [file name]: campaign_calculator.py
# [file content begin]
import sqlite3
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# НОВАЯ ЛОГИКА: Умные скидки за количество радио
BASE_PRICE_PER_SECOND = 1.5  # Базовая ставка 1.5 ₽/секунда

# Скидки за количество радиостанций
PRICE_TIERS = {
    1: 1.5,    # 1-2 радио: без скидки
    2: 1.5,    # 1-2 радио: без скидки  
    3: 1.3,    # 3-4 радио: -13%
    4: 1.3,    # 3-4 радио: -13%
    5: 1.1,    # 5+ радио: -27%
    6: 1.1     # 5+ радио: -27%
}

MIN_BUDGET = 7000  # Минимальная стоимость кампании

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

# ОБНОВЛЕННЫЕ ОХВАТЫ РАДИОСТАНЦИЙ
STATION_COVERAGE = {
    "LOVE RADIO": 700,
    "АВТОРАДИО": 3250,
    "РАДИО ДАЧА": 3250, 
    "РАДИО ШАНСОН": 2900,
    "РЕТРО FM": 3600,
    "ЮМОР FM": 2100
}

BRANDED_SECTION_PRICES = {
    "auto": 1.2,      # +20%
    "realty": 1.15,   # +15%
    "medical": 1.25,  # +25%
    "custom": 1.3     # +30%
}

PRODUCTION_OPTIONS = {
    "standard": {"price": 2000, "name": "СТАНДАРТНЫЙ РОЛИК", "desc": "Профессиональная озвучка, музыкальное оформление"},
    "premium": {"price": 5000, "name": "ПРЕМИУМ РОЛИК", "desc": "Озвучка 2-мя голосами, индивидуальная музыка"}
}

def format_number(num):
    """Форматирование чисел с пробелами"""
    return f"{num:,}".replace(",", " ")

def calculate_campaign_price_and_reach(user_data):
    """ОБНОВЛЕННАЯ ФУНКЦИЯ РАСЧЕТА С УМНЫМИ СКИДКАМИ"""
    try:
        base_duration = user_data.get("duration", 20)
        campaign_days = user_data.get("campaign_days", 30)
        selected_radios = user_data.get("selected_radios", [])
        selected_time_slots = user_data.get("selected_time_slots", [])
        
        if not selected_radios or not selected_time_slots:
            return 0, 0, MIN_BUDGET, 0, 0, 0, 0, 0
            
        num_stations = len(selected_radios)
        spots_per_day = len(selected_time_slots) * num_stations
        
        # УМНАЯ СКИДКА В ЗАВИСИМОСТИ ОТ КОЛИЧЕСТВА РАДИО
        price_per_second = PRICE_TIERS.get(num_stations, PRICE_TIERS[6])
        
        # БАЗОВАЯ СТОИМОСТЬ ЭФИРА
        cost_per_spot = base_duration * price_per_second
        base_air_cost = cost_per_spot * spots_per_day * campaign_days
        
        # ПРЕМИУМ-СЛОТЫ: +2% ЗА КАЖДЫЙ
        premium_count = 0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                if slot["premium"]:
                    premium_count += 1
        
        time_multiplier = 1.0 + (premium_count * 0.02)
        
        # БРЕНДИРОВАННЫЕ РУБРИКИ
        branded_multiplier = 1.0
        branded_section = user_data.get("branded_section")
        if branded_section in BRANDED_SECTION_PRICES:
            branded_multiplier = BRANDED_SECTION_PRICES[branded_section]
        
        # ПРОИЗВОДСТВО РОЛИКА
        production_cost = user_data.get("production_cost", 0)
        air_cost = int(base_air_cost * time_multiplier * branded_multiplier)
        base_price = air_cost + production_cost
        
        # ФИНАЛЬНАЯ ЦЕНА (без скидки 50%, только MIN_BUDGET)
        final_price = max(base_price, MIN_BUDGET)
        discount = 0  # Убрали скидку 50%
        
        # РАСЧЕТ ОХВАТА
        total_listeners = sum(STATION_COVERAGE.get(radio, 0) for radio in selected_radios)
        
        # Расчет потенциального охвата за день
        potential_coverage = 0
        for slot_index in selected_time_slots:
            if 0 <= slot_index < len(TIME_SLOTS_DATA):
                slot = TIME_SLOTS_DATA[slot_index]
                slot_coverage = total_listeners * (slot["coverage_percent"] / 100)
                potential_coverage += slot_coverage
        
        # Уникальный охват с учетом пересечения аудитории
        unique_daily_coverage = int(potential_coverage * 0.7)
        total_reach = int(unique_daily_coverage * campaign_days)
        
        # Суммарный процент охвата для отображения
        total_coverage_percent = sum(
            TIME_SLOTS_DATA[slot_index]["coverage_percent"] 
            for slot_index in selected_time_slots 
            if 0 <= slot_index < len(TIME_SLOTS_DATA)
        )
        
        return base_price, discount, final_price, total_reach, unique_daily_coverage, spots_per_day, total_coverage_percent, premium_count
        
    except Exception as e:
        logger.error(f"Ошибка расчета стоимости: {e}")
        return 0, 0, MIN_BUDGET, 0, 0, 0, 0, 0

def get_branded_section_name(section):
    names = {
        "auto": "Авторубрики (+20%)",
        "realty": "Недвижимость (+15%)",
        "medical": "Медицинские рубрики (+25%)",
        "custom": "Индивидуальная рубрика (+30%)"
    }
    return names.get(section, "Не выбрана")

def get_time_slots_text(selected_slots):
    """Получить текстовое представление выбранных слотов"""
    slots_text = ""
    for slot_index in selected_slots:
        if 0 <= slot_index < len(TIME_SLOTS_DATA):
            slot = TIME_SLOTS_DATA[slot_index]
            premium_emoji = "🚀" if slot["premium"] else "📊"
            slots_text += f"• {slot['time']} - {slot['label']} {premium_emoji}\n"
    return slots_text

def get_production_cost(production_option):
    """Получить стоимость производства ролика"""
    return PRODUCTION_OPTIONS.get(production_option, {}).get('price', 0)
# [file content end]
