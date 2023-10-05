from telebot import types

YOUR_USER_ID = 123456  # Замените на ваш реальный идентификатор пользователя в Telegram

# Обработка команды /объявление
def handle_announcement_command(bot, message):
    if message.from_user.id != YOUR_USER_ID:
        bot.reply_to(message, "Извините, у вас нет прав на использование этой команды.")
        return
    msg = bot.send_message(message.chat.id, "Напишите свое объявление:")
    bot.register_next_step_handler(msg, lambda m: process_announcement_preview(bot, m, m.text))

def process_announcement_preview(bot, message, text):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="Да", callback_data="announcement_confirm"),
               types.InlineKeyboardButton(text="Отменить", callback_data="announcement_cancel"))
    bot.send_message(message.chat.id, f"Вы точно хотите отправить данное объявление?\n{text}", reply_markup=markup)

def send_announcement_to_all_users(bot, call, get_all_users_func):
    if call.data == "announcement_confirm":
        question_text = "Вы точно хотите отправить данное объявление?"
        announcement_text = call.message.text.split(question_text)[1].strip()

        for user_id in get_all_users_func():
            bot.send_message(user_id, announcement_text)
        bot.answer_callback_query(call.id, "Объявление отправлено.")
    elif call.data == "announcement_cancel":
        bot.answer_callback_query(call.id, "Объявление отменено.")



