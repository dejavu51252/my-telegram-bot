import logging
import os
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    # Render передает порт в переменную окружения PORT
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
# -----------------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("ℹ️ О нас", callback_data="about")],
        [InlineKeyboardButton("✍️ Оставить отзыв", callback_data="leave_feedback")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_feedback"] = False
    await update.message.reply_text(
        "Привет! Я твой новый учебный бот. Выбери действие:",
        reply_markup=get_main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "about":
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
        await query.edit_message_text(
            text="Этот бот создан для обучения разработке на Python!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "leave_feedback":
        context.user_data["awaiting_feedback"] = True
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]]
        await query.edit_message_text(
            text="Напиши свой отзыв или пожелание следующим сообщением:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "main_menu":
        context.user_data["awaiting_feedback"] = False
        await query.edit_message_text(
            text="Выбери действие из меню:",
            reply_markup=get_main_keyboard()
        )

import random

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Добавляем реакцию на «О ферме»
    if text == "❓ Помощь":
        await update.message.reply_text(
            "Раздел помощи:\nНажмите 'ℹ️ О нас' для информации или '✍️ Оставить отзыв' для связи."
        )
   elif text == "🎲 Бросить кость":
        await update.message.reply_dice(emoji="🎲")
    elif context.user_data.get("awaiting_feedback"):
        # Сохранение отзыва
        ...
    else:
        await update.message.reply_text(
            "Пожалуйста, используй кнопки для навигации по меню:",
            reply_markup=get_main_keyboard()
        )
    # 4. Во всех остальных случаях
    else:
        await update.message.reply_text(
            "Пожалуйста, используй кнопки для навигации по меню:",
            reply_markup=get_main_keyboard()
        )

if __name__ == "__main__":
    keep_alive()  # Запускаем фоновый веб-сервер
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Бот запущен!")
    app.run_polling()
