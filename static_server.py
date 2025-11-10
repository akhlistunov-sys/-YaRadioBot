# [file name]: static_server.py
# [file content begin]
from flask import send_from_directory
import os

def register_static_routes(app):
    
    # Главная страница Mini App
    @app.route('/')
    def serve_index():
        return send_from_directory('frontend', 'index.html')
    
    # Статические файлы (JS, CSS)
    @app.route('/<path:filename>')
    def serve_static(filename):
        return send_from_directory('frontend', filename)
    
    # API маршруты остаются прежними
    @app.route('/api/health')
    def health_check():
        from app import init_db
        return {
            "status": "healthy",
            "database": "connected" if init_db() else "error"
        }
# [file content end]
