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

# --- 1. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (SQLite) ---
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

# --- 2. ВЕБ-СЕРВЕР ДЛЯ RENDER ---
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
# -----------------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8314078721:AAG2FiCKSx2cQdFE4ml7cRuf2DTHwPHuXHs"

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("ℹ️ О нас", callback_data="about")],
        [InlineKeyboardButton("✍️ Оставить отзыв", callback_data="leave_feedback")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
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
        f"Привет, {user.first_name}! Я бот с поддержкой базы данных. Выбери действие:",
        reply_markup=get_main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "about":
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
        await query.edit_message_text(
            text="Этот бот умеет сохранять данные в локальную базу данных SQLite!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "leave_feedback":
        context.user_data["awaiting_feedback"] = True
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]]
        await query.edit_message_text(
            text="Напиши свой отзыв следующим сообщением (он сохранится в базу данных):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "main_menu":
        context.user_data["awaiting_feedback"] = False
        await query.edit_message_text(
            text="Выбери действие из меню:",
            reply_markup=get_main_keyboard()
        )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_feedback"):
        user_text = update.message.text
        user_id = update.effective_user.id
        context.user_data["awaiting_feedback"] = False
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO feedback (user_id, text) VALUES (?, ?)", (user_id, user_text))
        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"✅ Отзыв успешно сохранён в базу данных!\n\nТекст: «{user_text}»",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, используй кнопки для навигации по меню:",
            reply_markup=get_main_keyboard()
        )

# Функция админ-панели
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT user_id, text FROM feedback ORDER BY id DESC LIMIT 5")
    feedbacks = cursor.fetchall()
    conn.close()

    text = f"📊 Панель Администратора\n\nВсего пользователей в базе: {users_count}\n\nПоследние отзывы:\n"
    if feedbacks:
        for u_id, fb_text in feedbacks:
            text += f"• ID {u_id}: {fb_text}\n"
    else:
        text += "Отзывов пока нет."

    await update.message.reply_text(text)

if __name__ == "__main__":
    keep_alive()
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Бот запущен!")
    app.run_polling()
