import sqlite3
import logging
from datetime import datetime

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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT "webapp"
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        return False

def save_campaign(data):
    """Сохранение кампании из WebApp"""
    try:
        campaign_number = f"WA-{datetime.now().strftime('%H%M%S')}"
        
        conn = sqlite3.connect("campaigns.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO campaigns 
            (user_id, campaign_number, radio_stations, start_date, end_date, 
             campaign_days, time_slots, branded_section, contact_name,
             company, phone, email, base_price, discount, final_price, actual_reach, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['user_id'],
            campaign_number,
            ",".join(data.get('radio_stations', [])),
            data.get('start_date'),
            data.get('end_date'),
            data.get('campaign_days'),
            ",".join(map(str, data.get('time_slots', []))),
            data.get('branded_section'),
            data.get('contact_name'),
            data.get('company'),
            data.get('phone'),
            data.get('email'),
            data.get('base_price'),
            data.get('discount'),
            data.get('final_price'),
            data.get('actual_reach'),
            "webapp"
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Кампания {campaign_number} сохранена через WebApp")
        return campaign_number
        
    except Exception as e:
        logger.error(f"Ошибка сохранения кампании: {e}")
        return None
