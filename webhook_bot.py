from flask import Flask, request
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram import Update
import os

app = Flask(__name__)
BOT_TOKEN = os.getenv('8281804030:AAEFEYgqigL3bdH4DL0zl1tW71fwwo_8cyU')
WEBHOOK_URL = os.getenv('RENDER_EXTERNAL_URL') + '/webhook'

# ... (все функции обработчики остаются такими же)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), application.bot)
    application.update_queue.put(update)
    return 'ok'

@app.route('/')
def index():
    return '🤖 YA-RADIO Bot is running!'

if __name__ == '__main__':
    # Инициализация бота
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_station_selection, pattern="^station_"))
    application.add_handler(CallbackQueryHandler(contact_manager, pattern="^contact_manager$"))
    application.add_handler(CallbackQueryHandler(goto_stations, pattern="^goto_stations$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Установка вебхука
    application.bot.set_webhook(WEBHOOK_URL)
    
    # Flask app запускается автоматически на Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
