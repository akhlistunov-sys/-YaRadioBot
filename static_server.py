from flask import send_from_directory
import os

def register_static_routes(app):
    
    # Главная страница Mini App
    @app.route('/')
    def serve_index():
        return send_from_directory('frontend', 'index.html')
    
    # Статические файлы (JS, CSS)
    @app.route('/js/<path:filename>')
    def serve_js(filename):
        return send_from_directory('frontend/js', filename)
    
    # API маршруты остаются прежними
    @app.route('/api/health')
    def health_check():
        from app import init_db
        return {
            "status": "healthy",
            "database": "connected" if init_db() else "error"
        }
