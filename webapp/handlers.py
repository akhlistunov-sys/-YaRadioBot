async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ГЛАВНОЕ МЕНЮ"""
    keyboard = [
        [InlineKeyboardButton("🚀 НАЧАТЬ РАСЧЕТ", callback_data="create_campaign")],
        [InlineKeyboardButton("📊 ВОЗРАСТНАЯ СТРУКТУРА", callback_data="statistics")],
        [InlineKeyboardButton("🏆 О НАС", callback_data="about")],
        [InlineKeyboardButton("📋 ЛИЧНЫЙ КАБИНЕТ", callback_data="personal_cabinet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = (
        "🎙️ РАДИО ТЮМЕНСКОЙ ОБЛАСТИ\n"
        "📍 Ялуторовск • Заводоуковск\n\n"
        "🤖 **Рассчитайте рекламу за 2 минуты**\n"
        "3 простых шага → готовый медиаплан\n\n"
        "• 6 федеральных радиостанций\n"
        "• Скидка 50% на первую кампанию\n"
        "• Старт через 3 дня\n"
        "• Персональный медиаплан\n\n"
        "🏆 70+ кампаний в 2025 году\n"
        "✅ От 7 000₽"
    )
    
    if update.message:
        await update.message.reply_text(
            caption,
            reply_markup=reply_markup
        )
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            caption,
            reply_markup=reply_markup
        )
    
    return "MAIN_MENU"
