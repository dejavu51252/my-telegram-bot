import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

# Команда /start — создает сообщение с кнопками
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("💅 Записаться на услугу", callback_data="service"),
            InlineKeyboardButton("📊 Мои работы", callback_data="portfolio")
        ],
        [
            InlineKeyboardButton("📞 Контакты", callback_data="contacts")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Добро пожаловать! Выберите нужный раздел:", 
        reply_markup=reply_markup
    )

# Обработчик нажатий на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Обязательный ответ для Telegram, чтобы убрать анимацию загрузки на кнопке

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
    elif query.data == "back":
        keyboard = [
            [
                InlineKeyboardButton("💅 Записаться на услугу", callback_data="service"),
                InlineKeyboardButton("📊 Мои работы", callback_data="portfolio")
            ],
            [
                InlineKeyboardButton("📞 Контакты", callback_data="contacts")
            ]
        ]
        await query.edit_message_text(
            text="Добро пожаловать! Выберите нужный раздел:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Бот с кнопками запущен!")
    app.run_polling()
