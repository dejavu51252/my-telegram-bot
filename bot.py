import logging
import os
import sqlite3
import asyncio
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

# --- 1. СЕКРЕТНЫЕ ПЕРЕМЕННЫЕ ---
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# --- 2. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            description TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER
        )
    ''')

    # Наполняем тестовыми товарами, если пусто
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO products (name, price, description) VALUES (?, ?, ?)",
            [
                ("VIP Подписка", 500, "Доступ в закрытый канал на 1 месяц"),
                ("Курс по Telegram", 1500, "Полный гайд по созданию ботов"),
                ("Консультация", 3000, "1 час личного разбора проекта")
            ]
        )
    
    conn.commit()
    conn.close()

init_db()

# --- 3. ВЕБ-СЕРВЕР Flask ---
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- 4. КЛАВИАТУРЫ ---
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛍 Каталог товаров", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Моя корзина", callback_data="view_cart")],
        [InlineKeyboardButton("🎲 Бросить кубик", callback_data="roll_dice")],
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
        f"Привет, {user.first_name}! Добро пожаловать в наш магазин. Выбери действие:",
        reply_markup=get_main_keyboard()
    )

# --- 5. ОБРАБОТКА КНОПОК МЕНЮ И КАТАЛОГА ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "catalog":
        # Показываем список товаров из БД
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price FROM products")
        products = cursor.fetchall()
        conn.close()

        keyboard = []
        for p_id, name, price in products:
            keyboard.append([InlineKeyboardButton(f"{name} — {price} руб.", callback_data=f"buy_{p_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])

        await query.edit_message_text(
            text="🛒 **Каталог товаров:**\n\nНажми на товар, чтобы добавить его в корзину:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("buy_"):
        # Добавление товара в корзину
        p_id = int(query.data.split("_")[1])
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO cart (user_id, product_id) VALUES (?, ?)", (user_id, p_id))
        conn.commit()
        conn.close()

        keyboard = [
            [InlineKeyboardButton("🛍 Продолжить покупки", callback_data="catalog")],
            [InlineKeyboardButton("🛒 Перейти в корзину", callback_data="view_cart")]
        ]
        await query.edit_message_text(
            text="✅ Товар успешно добавлен в корзину!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "view_cart":
        # Просмотр содержимого корзины
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT products.name, products.price 
            FROM cart 
            JOIN products ON cart.product_id = products.id 
            WHERE cart.user_id = ?
        ''', (user_id,))
        items = cursor.fetchall()
        conn.close()

        if not items:
            keyboard = [[InlineKeyboardButton("🛍 В каталог", callback_data="catalog")]]
            await query.edit_message_text("Ваша корзина пуста.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        total = sum(item[1] for item in items)
        text = "🛒 **Ваша корзина:**\n\n"
        for name, price in items:
            text += f"• {name} — {price} руб.\n"
        text += f"\n💰 **Итого к оплате:** {total} руб."

        keyboard = [
            [InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "clear_cart":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        keyboard = [[InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]]
        await query.edit_message_text("🗑 Корзина очищена!", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "roll_dice":
        dice_message = await context.bot.send_dice(chat_id=query.message.chat_id, emoji="🎲")
        value = dice_message.dice.value
        await asyncio.sleep(3)
        await query.message.reply_text(f"🎯 Выпало число: **{value}**!", parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif query.data == "leave_feedback":
        context.user_data["awaiting_feedback"] = True
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]]
        await query.edit_message_text("Напиши свой отзыв следующим сообщением:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "main_menu":
        context.user_data["awaiting_feedback"] = False
        await query.edit_message_text("Выбери действие из меню:", reply_markup=get_main_keyboard())

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

        await update.message.reply_text("✅ Отзыв успешно сохранён!", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("Пожалуйста, используй кнопки меню:", reply_markup=get_main_keyboard())

# --- 6. АДМИНКА ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Доступ запрещен!")
        return

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    conn.close()

    await update.message.reply_text(f"📊 **Панель Админа**\n\nПользователей: **{users_count}**", parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    msg = " ".join(context.args)
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=f"📢 {msg}")
            await asyncio.sleep(0.05)
        except Exception: pass
    await update.message.reply_text("✅ Рассылка завершена!")

async def export_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if os.path.exists("database.db"):
        with open("database.db", "rb") as f:
            await update.message.reply_document(document=f, filename="database.db")

if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("export", export_db))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Бот запущен!")
    app.run_polling()
