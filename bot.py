import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Создаем разметку кнопок (2 кнопки в первом ряду, 1 во втором)
keyboard = [
    ["🌱 О ферме", "🎲 Бросить кость"],
    ["❓ Помощь"]
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Привет, {user_name}! 🤖\nВыбери действие на кнопках ниже:",
        reply_markup=reply_markup
    )

# Обработчик нажатий на кнопки и любых текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🌱 О ферме":
        await update.message.reply_text("Ферма 22х22 полностью автоматизирована! Динозавр фармит кости, а лабиринт — золото. 🌾")
    elif text == "🎲 Бросить кость":
        await update.message.reply_dice(emoji="🎲")
    elif text == "❓ Помощь":
        await update.message.reply_text("Нажимай на кнопки внизу для управления ботом!")
    else:
        await update.message.reply_text(f"Ты написал: '{text}'. Воспользуйся кнопками меню! 👇")

if __name__ == '__main__':
    TOKEN = "8314078721:AAG2FicKSx2cQdFE4ml7cRuf2DTHwPHuXHs"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    # Регистрируем обработчик обычного текста
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот с кнопками запущен!")
    app.run_polling()