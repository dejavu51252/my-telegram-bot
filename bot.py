import logging
import os
import sqlite3
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

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RENDER (ФОНОВЫЙ ПОТОК ДЛЯ 24/7) ---
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- 2. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (SQLite) ---
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 3. НАСТРОЙКА ЛОГИРОВАНИЯ И ТОКЕНА ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

# --- 4. КЛАВИАТУРЫ И ХЭНДЛЕРЫ ---
def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💅 Записаться на услугу", callback_data="service"),
            InlineKeyboardButton("📊 Мои работы", callback_data="portfolio")
        ],
        [
            InlineKeyboardButton("✍️ Оставить отзыв", callback_data="leave_feedback"),
            InlineKeyboardButton("📞 Контакты", callback_data="contacts")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Сохраняем пользователя в БД
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user.id, user.username, user.first_name)
    )
    conn.commit()
    conn.close()

    context.user_data["awaiting_feedback"] = False
    await update.message.reply_text(
        f"Добро пожаловать, {user.first_name}! Выберите нужный раздел:", 
        reply_markup=get_main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "service":
        await query.edit_message_text(
            text="Вы выбрали раздел записи. Скоро здесь появится календарь!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]])
        )
    elif query.data == "portfolio":
        await query.edit_message_text(
            text="Наше портфолио: https://github.com/",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]])
        )
    elif query.data == "contacts":
        await query.edit_message_text(
            text="Наш телефон: +998 (90) 123-45-67\nАдрес: г. Ташкент",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]])
        )
    elif query.data == "leave_feedback":
        context.user_data["awaiting_feedback"] = True
        await query.edit_message_text(
            text="Напишите ваш отзыв или пожелание следующим сообщением (он сохранится в базу данных):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="back")]])
        )
    elif query.data == "back":
        context.user_data["awaiting_feedback"] = False
        await query.edit_message_text(
            text="Добро пожаловать! Выберите нужный раздел:", 
            reply_markup=get_main_keyboard()
        )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_feedback"):
        user_text = update.message.text
        user_id = update.effective_user.id
        context.user_data["awaiting_feedback"] = False
        
        # Запись отзыва в SQLite
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO feedback (user_id, text) VALUES (?, ?)", (user_id, user_text))
        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"✅Спасибо за отзыв! Он успешно сохранён:\n\n«{user_text}»",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки для навигации:",
            reply_markup=get_main_keyboard()
        )

# --- 5. ЗАПУСК БОТА И ВЕБ-СЕРВЕРА ---
if __name__ == '__main__':
    keep_alive()  # Запуск фонового сервера Flask для Render/UptimeRobot
    
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Бот запущен!")
    app.run_polling()
