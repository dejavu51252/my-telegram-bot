import logging
import os
import sqlite3
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

# --- 1. СЕКРЕТНЫЕ ПЕРЕМЕННЫЕ ---
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
# Считываем токен Click из Render
PAYMENT_TOKEN = os.environ.get("PAYMENT_TOKEN", "398062629:TEST:999999999_F91D8F69C042267444B74CC0B3C747757EB0E065")

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
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO products (name, price) VALUES (?, ?)",
            [
                ("Курс Telegram-разработчик", 350000),
                ("Бот для бизнеса", 650000),
                ("Консультация", 150000)
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

def keep_alive():
    def run_web():
        port = int(os.environ.get('PORT', 8080))
        web_app.run(host='0.0.0.0', port=port)
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 4. КЛАВИАТУРЫ ---
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍 Каталог товаров", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Моя корзина", callback_data="view_cart")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Здравствуйте, {update.effective_user.first_name}! Выберите действие:",
        reply_markup=get_main_keyboard()
    )

# --- 5. ОБРАБОТКА КАТАЛОГА И КОРЗИНЫ ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "catalog":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price FROM products")
        products = cursor.fetchall()
        conn.close()

        keyboard = []
        for p_id, name, price in products:
            keyboard.append([InlineKeyboardButton(f"{name} — {price:,} сум", callback_data=f"buy_{p_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Меню", callback_data="main_menu")])

        await query.edit_message_text(text="🛒 **Каталог товаров:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("buy_"):
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
        await query.edit_message_text("✅ Товар добавлен в корзину!", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "view_cart":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT products.name, products.price 
            FROM cart JOIN products ON cart.product_id = products.id 
            WHERE cart.user_id = ?
        ''', (user_id,))
        items = cursor.fetchall()
        conn.close()

        if not items:
            await query.edit_message_text("Ваша корзина пуста.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Каталог", callback_data="catalog")]]))
            return

        total = sum(item[1] for item in items)
        text = "🛒 **Ваша корзина:**\n\n" + "\n".join([f"• {name} — {price:,} сум" for name, price in items])
        text += f"\n\n💰 **Итого:** {total:,} сум"

        keyboard = [
            [InlineKeyboardButton("💳 Оплатить через Click", callback_data="checkout")],
            [InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "checkout":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT products.name, products.price 
            FROM cart JOIN products ON cart.product_id = products.id 
            WHERE cart.user_id = ?
        ''', (user_id,))
        items = cursor.fetchall()
        conn.close()

        if not items:
            await query.edit_message_text("Корзина пуста!")
            return

        # Умножаем price на 100 (перевод сумов в тийины)
        prices = [LabeledPrice(name, price * 100) for name, price in items]

        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="Оплата заказа",
            description="Тестовая оплата через Click",
            payload="click_order_payload",
            provider_token=PAYMENT_TOKEN,
            currency="UZS",
            prices=prices
        )

    elif query.data == "clear_cart":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("🗑 Корзина очищена!", reply_markup=get_main_keyboard())

    elif query.data == "main_menu":
        await query.edit_message_text("Выберите действие:", reply_markup=get_main_keyboard())

# --- 6. ОБРАБОТКА ТЕСТОВОГО ПЛАТЕЖА CLICK ---
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != "click_order_payload":
        await query.answer(ok=False, error_message="Ошибка оформления заказа...")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Очищаем корзину после оплаты
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "🎉 **Спасибо за покупку!**\nТестовая оплата через Click прошла успешно!",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# --- 7. ЗАПУСК ---
if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    print("Бот с оплатой Click запущен!")
    app.run_polling()
