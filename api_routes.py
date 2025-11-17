# [file name]: api_routes.py
# [file content begin]
from flask import jsonify, request
from campaign_calculator import *

def register_routes(app):
    
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
# [file content end]
