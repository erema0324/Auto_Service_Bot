import os
import telebot
import re
import db
import hashlib
import calendar
import time as t
from telebot import types
from dotenv import load_dotenv
from datetime import datetime, timedelta, time as dtime
from db import add_termin
from db import check_appointment_availability
from db import has_appointment
from notification import handle_announcement_command, process_announcement_preview, send_announcement_to_all_users
import json
import sqlite3

with open('autobd.txt', 'r', encoding='utf-8') as f:
    car_db = json.load(f)



load_dotenv()
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(bot_token)
user_data = {}

email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
phone_pattern = re.compile(r"^\+?[0-9]{10,15}$")
vin_pattern = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")

class User:
    def __init__(self, name=None, email=None, password=None, phone=None, car_model=None, car_year=None, car_vin=None):
        self.name = name
        self.email = email
        self.password = password
        self.phone = phone
        self.car_model = car_model
        self.car_year = car_year
        self.car_vin = car_vin
        self.state = "START"

def hash_password(password):
    salt = "somesalt"  # Здесь вы можете использовать любую случайную строку в качестве соли
    hashed_password = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed_password

def create_back_button():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add('Назад↩️')
    return markup

def create_main_menu():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add('Назначить Termin📅', 'Личный Кабинет👤', 'Пользовательские соглашения📜', 'Контакты📞')
    return markup

def update_keyboard(message, markup):
    bot.send_message(message.chat.id, "Выберите действие", reply_markup=markup)

def create_time_buttons(day_of_week):
    markup = types.InlineKeyboardMarkup()
    row = []
    if day_of_week < 5:  # Рабочие дни с понедельника по пятницу
        work_hours = ["16:00", "17:00", "18:00", "19:00"]
    elif day_of_week == 5:  # Суббота
        work_hours = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00"]
    else:  # Воскресенье
        work_hours = []

    for hour in work_hours:
        row.append(types.InlineKeyboardButton(hour, callback_data="time-" + hour))
    markup.row(*row)

    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_data[user_id] = User()

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add('Согласие на обработку персональных данных 🔐')
    msg = bot.send_message(message.chat.id, "Согласны ли вы на обработку персональных данных? Нажмите , на кнопку (Согласие на обработку персональных данных) , которая находиться внизу ", reply_markup=markup)
    bot.register_next_step_handler(msg, process_agreement_step)



def process_agreement_step(message):
    user_id = message.from_user.id
     
    if message.text == 'Согласие на обработку персональных данных 🔐':
        user_data[user_id].state = "AGREEMENT"

        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add('Войти🔑', 'Зарегистрироваться📝')
        update_keyboard(message, markup)
        bot.register_next_step_handler(message, process_auth_step)
    else:
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add('Согласие на обработку персональных данных 🔐')
        msg = bot.send_message(message.chat.id, "Пожалуйста, нажмите на кнопку для согласия на обработку персональных данных.", reply_markup=markup)
        bot.register_next_step_handler(msg, process_agreement_step) # Регистрируем тот же обработчик, чтобы повторить шаг


def process_auth_step(message):
    user_id = message.from_user.id

    if user_data[user_id].state == "AGREEMENT":
        if message.text == "Войти🔑":
            user_data[user_id].state = "LOGIN"
            msg = bot.send_message(message.chat.id, "Введите ваш email📧", reply_markup=create_back_button())
            bot.register_next_step_handler(msg, process_login_step)
        elif message.text == "Зарегистрироваться📝":
            user_data[user_id].state = "REGISTRATION"
            msg = bot.send_message(message.chat.id, "Введите ваше имя", reply_markup=create_back_button())
            bot.register_next_step_handler(msg, process_name_step)
        else:
            msg = bot.send_message(message.chat.id, "Неправильный ввод.")
            bot.register_next_step_handler(msg, process_auth_step)
    else:
        send_welcome(message)

def process_login_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_auth_step(message)

    if user_data[user_id].state != "LOGIN":
        return send_welcome(message)

    if not email_pattern.match(message.text):
        msg = bot.send_message(message.chat.id, "Введите корректный email.📝")
        bot.register_next_step_handler(msg, process_login_step)
    else:
        user_data[user_id].email = message.text
        session = db.get_db_session()
        user = session.query(db.User).filter(db.User.email == user_data[user_id].email).first()
        if user:
            msg = bot.send_message(message.chat.id, "Введите ваш пароль🔐", reply_markup=create_back_button())
            bot.register_next_step_handler(msg, process_password_login_step)
        else:
            bot.send_message(message.chat.id, "Неправильный email.")
            msg = bot.send_message(message.chat.id, "Введите ваш email", reply_markup=create_back_button())
            bot.register_next_step_handler(msg, process_login_step)

def process_password_login_step(message):
    user_id = message.from_user.id

    if user_data[user_id].state != "LOGIN":
        return send_welcome(message)

    session = db.get_db_session()
    user = session.query(db.User).filter(db.User.email == user_data[user_id].email).first()
    if user and db.check_password(user.password, message.text):
        bot.send_message(message.chat.id, "Вы успешно вошли в систему!")
        update_keyboard(message, create_main_menu())
    else:
        bot.send_message(message.chat.id, "Неправильный пароль.")
        msg = bot.send_message(message.chat.id, "Введите ваш email", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_login_step)


def process_name_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_auth_step(message)

    if user_data[user_id].state != "REGISTRATION" and user_data[user_id].state != "LOGIN":
        return send_welcome(message)

    if user_data[user_id].state == "LOGIN":
        user_data[user_id] = User()

    user_data[user_id].name = message.text
    msg = bot.send_message(message.chat.id, "Введите ваш номер телефона", reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_phone_step)

def process_phone_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_name_step(message)

    if user_data[user_id].state != "REGISTRATION":
        return send_welcome(message)

    if not phone_pattern.match(message.text):
        msg = bot.send_message(message.chat.id, "Введите корректный номер телефона.", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_phone_step)
    else:
        user_data[user_id].phone_number = message.text
        msg = bot.send_message(message.chat.id, "Введите ваш email", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_email_step)

def process_email_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_phone_step(message)

    if user_data[user_id].state != "REGISTRATION":
        return send_welcome(message)

    if not email_pattern.match(message.text):
        msg = bot.send_message(message.chat.id, "Введите корректный email.📝", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_email_step)
    else:
        user_data[user_id].email = message.text
        try:
            session = db.get_db_session()
            user = session.query(db.User).filter(db.User.email == user_data[user_id].email).first()
            if user:
                msg = bot.send_message(message.chat.id, "Данный email уже используется. Если вы забыли пароль, прошу Вас обратиться к Администратору.🔧", reply_markup=create_back_button())
                bot.register_next_step_handler(msg, process_email_step)
            else:
                msg = bot.send_message(message.chat.id, "Введите ваш пароль🔐", reply_markup=create_back_button())
                bot.register_next_step_handler(msg, process_password_step)
        except Exception as e:
            print(f"Ошибка при обращении к базе данных: {e}")
            msg = bot.send_message(message.chat.id, "Произошла ошибка, пожалуйста, попробуйте снова.", reply_markup=create_back_button())
            bot.register_next_step_handler(msg, process_email_step)

def create_confirm_buttons():
    markup = types.InlineKeyboardMarkup()
    itembtn1 = types.InlineKeyboardButton('Подтвердить✅', callback_data='confirm')
    itembtn2 = types.InlineKeyboardButton('Отменить❌', callback_data='cancel') 
    markup.add(itembtn1, itembtn2)
    return markup

def process_password_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_email_step(message)

    if user_id not in user_data:
        user_data[user_id] = User()

    if user_data[user_id].state != "REGISTRATION":
        return send_welcome(message)

    user_data[user_id].password = message.text  # Сохраняем пароль без хеширования

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    countries = set()  # Используем set, чтобы избежать дубликатов
    for brand in car_db:
        countries.add(brand['country'])
    for country in sorted(countries):  # Сортировка стран
        markup.add(country)
    msg = bot.send_message(message.chat.id, "Выберите страну происхождения Вашего автомобиля🌍", reply_markup=markup)
    bot.register_next_step_handler(msg, process_car_country_step)


def process_car_country_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_password_step(message)

    if user_data[user_id].state != "REGISTRATION":
        return send_welcome(message)

    countries = set()  # Используем set, чтобы избежать дубликатов
    for brand in car_db:
        countries.add(brand['country'])
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    for country in sorted(countries):  # Сортировка стран
        markup.add(country)

    if message.text not in countries:
        msg = bot.send_message(message.chat.id, "Пожалуйста, выберите страну из предложенных", reply_markup=markup)
        bot.register_next_step_handler(msg, process_car_country_step)
    else:
        user_data[user_id].car_country = message.text

        brands = set()  # Используем set, чтобы избежать дубликатов
        for brand in car_db:
            if brand['country'] == user_data[user_id].car_country:
                brands.add(brand['name'])
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for brand in sorted(brands):  # Сортировка брендов
            markup.add(brand)
        msg = bot.send_message(message.chat.id, "Выберите бренд Вашего автомобиля🚗🏁", reply_markup=markup)
        bot.register_next_step_handler(msg, process_car_brand_step)




def process_car_model_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_password_step(message)

    if user_id not in user_data:
        user_data[user_id] = User()

    if user_data[user_id].state != "REGISTRATION":
        return send_welcome(message)

    user_data[user_id].car_model = message.text

    msg = bot.send_message(message.chat.id, "Введите год выпуска Вашего автомобиля📅🚗", reply_markup=create_back_button())
    bot.register_next_step_handler(msg, process_car_year_step)

def process_car_brand_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_car_country_step(message)

    if user_data[user_id].state != "REGISTRATION":
        return send_welcome(message)

    # Проверяем, выбрал ли пользователь бренд из предложенного списка
    chosen_brand = None
    brands = set()  # Создаем набор brands здесь
    for brand in car_db:
        if brand['country'] == user_data[user_id].car_country:
            brands.add(brand['name'])
            if brand['name'] == message.text:
                chosen_brand = brand
                break

    if chosen_brand is None:
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for brand in sorted(brands):  # Сортировка брендов
            markup.add(brand)
        msg = bot.send_message(message.chat.id, "Пожалуйста, выберите бренд из предложенных🚫", reply_markup=markup)
        bot.register_next_step_handler(msg, process_car_brand_step)
    else:
        user_data[user_id].car_brand = message.text

        models = sorted(model['name'] for model in chosen_brand['models'])  # Сортировка моделей
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for model in models:
            markup.add(model)
        msg = bot.send_message(message.chat.id, "Выберите модель автомобиля🚗📋", reply_markup=markup)
        bot.register_next_step_handler(msg, process_car_model_step)





def process_car_model_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_car_brand_step(message)

    if user_id not in user_data:
        user_data[user_id] = User()

    if user_data[user_id].state != "REGISTRATION":
        return send_welcome(message)

    # Проверяем, выбрал ли пользователь модель из предложенного списка
    chosen_brand = None
    for brand in car_db:
        if brand['country'] == user_data[user_id].car_country and brand['name'] == user_data[user_id].car_brand:
            chosen_brand = brand
            break

    if chosen_brand is None:
        return process_car_brand_step(message)

    chosen_model = None
    for model in chosen_brand['models']:
        if model['name'] == message.text:
            chosen_model = model
            break

    if chosen_model is None:
        # Создаем markup здесь
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for model in sorted(model['name'] for model in chosen_brand['models']):  # Сортировка моделей
            markup.add(model)
        msg = bot.send_message(message.chat.id, "Пожалуйста, выберите модель из предложенных🚫", reply_markup=markup)
        bot.register_next_step_handler(msg, process_car_model_step)
    else:
        user_data[user_id].car_model = message.text
        msg = bot.send_message(message.chat.id, "Введите год выпуска вашего автомобиля📅🚗", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_car_year_step)




def process_car_year_step(message):
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_car_model_step(message)

    if user_data[user_id].state != "REGISTRATION":
        return send_welcome(message)

    if not (message.text.isdigit() and 1885 < int(message.text) <= datetime.now().year):
        msg = bot.send_message(message.chat.id, "Введите корректный год выпуска автомобиля.🚫", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_car_year_step)
    else:
        user_data[user_id].car_year = message.text
        msg = bot.send_message(message.chat.id, "Введите VIN-код Вашего автомобиля🚗🔍", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_car_vin_step)

def process_car_vin_step(message):
    print("process_car_vin_step called") # Логирование
    user_id = message.from_user.id

    if message.text == 'Назад↩️':
        return process_car_year_step(message)

    if user_id not in user_data:
        user_data[user_id] = User()

    if user_data[user_id].state != "REGISTRATION":
        print("State is not REGISTRATION") # Логирование
        return send_welcome(message)

    if not vin_pattern.match(message.text):
        msg = bot.send_message(message.chat.id, "Введите корректный VIN.🚫", reply_markup=create_back_button())
        bot.register_next_step_handler(msg, process_car_vin_step)
    else:
        user_data[user_id].car_vin = message.text
        user_added = db.add_user(
            user_id,
            user_data[user_id].name,
            user_data[user_id].phone_number,
            user_data[user_id].email,
            user_data[user_id].password,
            user_data[user_id].car_country,
            user_data[user_id].car_brand,
            user_data[user_id].car_model,
            user_data[user_id].car_year,
            user_data[user_id].car_vin,
            bot  # Добавляем объект бота в качестве аргумента
        )

        print(f"user_added: {user_added}") # Логирование
        
        if not user_added:  # Если пользователь уже существует, возвращаемся к началу
            print("User already exists, going to auth step") # Логирование
            return process_auth_step(message)

        bot.send_message(message.chat.id, "Вы успешно зарегистрировались!🎉🥳")
        update_keyboard(message, create_main_menu())




@bot.message_handler(commands=['back'])
def handle_back_command(message):
    user_id = message.from_user.id

    if user_data[user_id].state == "AGREEMENT":
        send_welcome(message)
    elif user_data[user_id].state == "LOGIN":
        user_data[user_id].state = "START"  # Сбросить состояние пользователя
        msg = bot.send_message(message.chat.id, "Согласны ли вы на обработку персональных данных?", reply_markup=create_agreement_buttons())
        bot.register_next_step_handler(msg, process_agreement_step)
    elif user_data[user_id].state == "REGISTRATION":
        user_data[user_id].state = "START"  # Сбросить состояние пользователя
        msg = bot.send_message(message.chat.id, "Согласны ли вы на обработку персональных данных?", reply_markup=create_agreement_buttons())
        bot.register_next_step_handler(msg, process_agreement_step)
    else:
        update_keyboard(message, create_main_menu())

@bot.message_handler(func=lambda message: message.text == 'Назначить Termin📅')
def handle_appointment_button(message):
    user_id = message.from_user.id

    # Убедитесь, что user_id присутствует в user_data. Если нет, добавьте новый объект User
    if user_id not in user_data:
        user_data[user_id] = User()

    # Проверяем, есть ли у пользователя уже назначенный termin
    if has_appointment(user_id):
        bot.send_message(message.chat.id, "У вас уже есть назначенный termin. Вы не можете назначить новый, пока не завершите предыдущий.")
        return

    user_data[user_id].year = None
    user_data[user_id].month = None
    user_data[user_id].day = None
    user_data[user_id].time = None
    user_data[user_id].note = None

    msg = bot.send_message(message.chat.id, "Тут вы можете записаться на диагностику вашего авто, замену масла и т.д. Пожалуйста, укажите в примечании тип услуги:")
    bot.register_next_step_handler(msg, process_appointment_note)



def process_appointment_note(message):
    user_id = message.from_user.id

    user_data[user_id].note = message.text

    now = datetime.now()
    user_data[user_id].year = now.year
    user_data[user_id].month = now.month

    bot.send_message(message.chat.id, "Пожалуйста, выберите дату: ", reply_markup=create_calendar(now.year, now.month))

def create_calendar(year, month):
    markup = types.InlineKeyboardMarkup()
    now = datetime.now() + timedelta(days=1)  # Устанавливаем дату на следующий день

    # First row - Month and Year
    months = {
        1: 'Январь',
        2: 'Февраль',
        3: 'Март',
        4: 'Апрель',
        5: 'Май',
        6: 'Июнь',
        7: 'Июль',
        8: 'Август',
        9: 'Сентябрь',
        10: 'Октябрь',
        11: 'Ноябрь',
        12: 'Декабрь'
    }
    row = []
    row.append(types.InlineKeyboardButton(months[month] + " " + str(year), callback_data="ignore"))
    markup.row(*row)

    # Second row - Week Days
    row = []
    for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
        row.append(types.InlineKeyboardButton(day, callback_data="ignore"))
    markup.row(*row)

    # Days of the month
    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            elif day < now.day and month == now.month and year == now.year:
                row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                row.append(types.InlineKeyboardButton(str(day), callback_data="calendar-day-" + str(day)))
        markup.row(*row)

    # Last row - Buttons
    row = []
    if month == datetime.now().month and year == datetime.now().year:
        row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
    else:
        row.append(types.InlineKeyboardButton("<", callback_data="previous-month"))
    row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
    row.append(types.InlineKeyboardButton(">", callback_data="next-month"))
    markup.row(*row)

    return markup

def get_all_users_func():
    session = db.get_db_session()
    return [user.id for user in session.query(db.User).all()]

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id

    # Проверка пользователя в базе данных на каждом этапе
    user = db.find_user(user_id)
    if not user:
        bot.send_message(chat_id=call.message.chat.id, text="Ошибка: пользователь не найден. Пожалуйста, зарегистрируйтесь или войдите в систему.")
        return

    if call.data in ["announcement_confirm", "announcement_cancel"]:
        # Вызываем функцию из модуля notification.py
        send_announcement_to_all_users(bot, call, get_all_users_func)
        return

    # Инициализируем временные данные пользователя, если они ещё не были инициализированы
    if user_id not in user_data:
        user_data[user_id] = {
            "year": None,
            "month": None,
            "day": None,
            "time": None,
            "note": None
        }

    # Проверяем, есть ли у пользователя уже назначенные термины, за исключением случая отмены термина
    if not call.data.startswith("cancel_") and db.has_appointment(user_id):
        bot.send_message(call.message.chat.id, "У вас уже есть назначенный термин. Если вы хотите его изменить, пожалуйста, сначала отмените текущий термин.")
        return

    # Если пользователь нажимает на кнопку "Отменить Термин"
    if call.data.startswith("cancel_"):
        termin_id = int(call.data.split('_')[1])
        session = db.get_db_session()
        termin = session.query(db.Termin).filter(db.Termin.id == termin_id).first()
        if termin and termin.user_id == user_id:
            session.delete(termin)
            session.commit()
            user = session.query(db.User).filter(db.User.id == user_id).first()
            if user:
                notify_admin_about_canceled_termin(user.name, user_id, user.phone_number, f"{termin.day}-{termin.month}-{termin.year}", termin.time, termin.note, user.car_model, user.car_vin)
            bot.send_message(call.message.chat.id, "Запись успешно отменена.")
        else:
            bot.send_message(call.message.chat.id, "Ошибка: запись не найдена.")
        return

    # Если пользователь выбирает конкретный день в календаре
    elif call.data.startswith("calendar-day-"):
        _, _, day = call.data.split("-", 2)
        year = user_data[user_id].year
        month = user_data[user_id].month
        if year is None or month is None:
            bot.send_message(call.message.chat.id, "Пожалуйста, начните процесс назначения термина заново, нажав на кнопку 'Назначить Термин'.")
            return
        user_data[user_id].day = day
        day_of_week = datetime(year, month, int(day)).weekday()
        if day_of_week == 6:
            bot.send_message(chat_id=call.message.chat.id, text="Выходной день, пожалуйста выберите другую дату.")
        else:
            bot.send_message(chat_id=call.message.chat.id, text="Пожалуйста, выберите время: ", reply_markup=create_time_buttons(day_of_week))

    # Если пользователь нажимает на кнопку "Следующий месяц"
    elif call.data == "next-month":
        year = user_data[user_id].year
        month = user_data[user_id].month
        if month is not None:
            month += 1
            if month > 12:
                month = 1
                year += 1
            user_data[user_id].year = year
            user_data[user_id].month = month
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Пожалуйста, выберите дату: ", reply_markup=create_calendar(year, month))
        else:
            bot.send_message(call.message.chat.id, "Пожалуйста, начните процесс назначения термина заново, нажав на кнопку 'Назначить Термин'.")

    # Если пользователь нажимает на кнопку "Предыдущий месяц"
    elif call.data == "previous-month":
        year = user_data[user_id].year
        month = user_data[user_id].month
        if month is not None:
            month -= 1
            if month < 1:
                month = 12
                year -= 1
            user_data[user_id].year = year
            user_data[user_id].month = month
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Пожалуйста, выберите дату: ", reply_markup=create_calendar(year, month))
        else:
            bot.send_message(call.message.chat.id, "Пожалуйста, начните процесс назначения термина заново, нажав на кнопку 'Назначить Термин'.")

    # Если пользователь выбирает конкретное время
    elif call.data.startswith("time-"):
        _, time = call.data.split("-", 1)
        user_data[user_id].time = time
        if check_appointment_availability(user_data[user_id].year, user_data[user_id].month, user_data[user_id].day, user_data[user_id].time):
            bot.send_message(chat_id=call.message.chat.id, text="Пожалуйста, подтвердите или измените выбор: ", reply_markup=create_confirm_buttons())
        else:
            bot.send_message(chat_id=call.message.chat.id, text="Данное время уже занято, пожалуйста выберите другое время или попробуйте другой день.")

    # Если пользователь подтверждает выбранное время
    elif call.data == "confirm":
        year = user_data[user_id].year
        month = user_data[user_id].month
        day = user_data[user_id].day
        time = user_data[user_id].time
        note = user_data[user_id].note

        if None in (year, month, day, time, note):
            bot.send_message(chat_id=call.message.chat.id, text="Пожалуйста, заполните все поля, прежде чем подтвердить запись.")
            return

        if check_appointment_availability(year, month, day, time):
            session = db.get_db_session()
        
            # Измененная строка: поиск пользователя по chat_id (id) вместо email
            user = session.query(db.User).filter(db.User.id == user_id).first()
        
            if user:
                name = user.name
                car_brand = user.car_model
                vin = user.car_vin
                phone_number = user.phone_number
                bot.send_message(chat_id=call.message.chat.id, text=f"Вы записаны на:\nДата: {day}-{month}-{year}\nВремя: {time}\nУслуга: {note}")
                add_termin(user.id, note, day, month, year, time, name, car_brand, vin, phone_number)
                notify_admin_about_new_termin(name, user_id, phone_number, f"{day}-{month}-{year}", time, note, car_brand, vin)
            else:
                bot.send_message(chat_id=call.message.chat.id, text="Ошибка: пользователь не найден.")
        else:
            bot.send_message(chat_id=call.message.chat.id, text="Данное время уже занято, пожалуйста выберите другое время или попробуйте другой день.")


    # Если пользователь подтверждает или отменяет объявление
    elif call.data in ["confirm_announcement", "cancel_announcement"]:
        confirm_announcement(call)


    # Если пользователь отменяет выбор времени
    elif call.data == "cancel":
        user_data[user_id].year = None
        user_data[user_id].month = None
        user_data[user_id].day = None
        user_data[user_id].time = None
        user_data[user_id].note = None
        bot.send_message(chat_id=call.message.chat.id, text="Вы отменили запись.")
    else:
        pass



def notify_admin_about_new_termin(name, user_id, phone, date, time, description, car, vin):
    # Создание кликабельной ссылки для звонка на номер телефона
    phone_call_link = f"[{phone}](tel:{phone})"

    ADMIN_ID = 123456 # ID администратора
    termin_message = f'''У Вас новый Термин:
    Имя: {name}
    ID Телеграм Клиента: {user_id}
    Звонок: {phone_call_link}
    Дата: {date}
    Время: {time}
    Описание: {description}
    Авто: {car}
    VIN: {vin}'''

    # Отправка сообщения в формате Markdown для включения ссылок
    bot.send_message(ADMIN_ID, termin_message, parse_mode="Markdown")

def notify_admin_about_canceled_termin(name, user_id, phone, date, time, description, car, vin):
    # Создание кликабельной ссылки для звонка на номер телефона
    phone_call_link = f"[{phone}](tel:{phone})"

    ADMIN_ID = 123456  # ID администратора
    termin_message = f'''Термин был отменен:
    Имя: {name}
    ID Телеграм Клиента: {user_id}
    Звонок: {phone_call_link}
    Дата: {date}
    Время: {time}
    Описание: {description}
    Авто: {car}
    VIN: {vin}'''

    # Отправка сообщения в формате Markdown для включения ссылок
    bot.send_message(ADMIN_ID, termin_message, parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == 'Личный Кабинет👤')
def handle_account_button(message):
    user_id = message.from_user.id

    # Получаем информацию о пользователе из базы данных
    session = db.get_db_session()
    user = session.query(db.User).filter(db.User.id == user_id).first()

    if user:
        # Выводим информацию о пользователе
        bot.send_message(message.chat.id, f"Имя: {user.name}\nEmail: {user.email}\nТелефон: {user.phone_number}\nБренд авто: {user.car_brand}\nМодель авто: {user.car_model}\nГод выпуска авто: {user.car_year}\nVIN авто: {user.car_vin}")

        # Получаем информацию о предстоящих записях пользователя
        termins = session.query(db.Termin).filter(db.Termin.user_id == user_id).all()

        if termins:
            for termin in termins:
                # Создание инлайн-кнопки для отмены термина
                markup = types.InlineKeyboardMarkup()
                cancel_btn = types.InlineKeyboardButton("Отменить Термин❌", callback_data=f"cancel_{termin.id}")
                markup.add(cancel_btn)

                bot.send_message(message.chat.id, f"Запись:\nДата: {termin.day}-{termin.month}-{termin.year}\nВремя: {termin.time}\nУслуга: {termin.note}", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "У вас нет предстоящих записей.")
    else:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.❌")



# Определение текста пользовательского соглашения
terms_text = """
Пользовательское соглашение для чат-бота Werkstatt

1. Общие положения

1.1. Настоящее Пользовательское соглашение (далее — Соглашение) регулирует отношения между владельцем чат-бота Werkstatt (далее — Администрация), с одной стороны, и Пользователем чат-бота, с другой стороны.

2. Предмет соглашения

2.1. Администрация предоставляет Пользователю право на использование функциональных возможностей чат-бота Werkstatt, включая возможность записи на сервисные услуги и получение информации о сервисе.

2.2. Вся информация, предоставляемая чат-ботом Werkstatt, носит исключительно информационный характер.

3. Права и обязанности сторон

3.1. Пользователь вправе:

- записываться на сервисные услуги через чат-бота Werkstatt;
- получать информацию о сервисных услугах и их стоимости;
- задавать вопросы и получать ответы от чат-бота на тему сервиса.

3.2. Администрация вправе:

- по своему усмотрению и необходимости создавать, изменять, удалять правила использования чат-бота Werkstatt;
- изменять функциональные возможности чат-бота Werkstatt;
- предоставлять или ограничивать доступ Пользователя к чат-боту при нарушении Соглашения.

3.3. Пользователь обязан:

- не использовать чат-бот Werkstatt в незаконных целях;
- не передавать свои учетные данные другим лицам;
- соблюдать Правила пользования чат-ботом Werkstatt и не нарушать работоспособность чат-бота.

3.4. Администрация обязана:

- поддерживать работоспособность чат-бота Werkstatt кроме случаев, когда это невозможно по независящим от Администрации причинам.

4. Ответственность сторон

4.1. Пользователь лично несет ответственность за использование чат-бота Werkstatt и предоставленной информации.

4.2. Администрация не несет ответственности за предоставляемую чат-ботом информацию, а также за услуги, предоставляемые третьими лицами через чат-бот Werkstatt.

5. Условия действия Соглашения

5.1. Данное Соглашение вступает в силу с момента начала использования чат-бота Werkstatt Пользователем. Соглашение прекращает действовать при появлении его новой версии.

5.2. Администрация оставляет за собой право в одностороннем порядке изменять данное соглашение по своему усмотрению. Администрация не оповещает Пользователей о внесении изменений в Соглашение.
"""

# Обработчик кнопки "Пользовательские соглашения"
@bot.message_handler(func=lambda message: message.text == 'Пользовательские соглашения📜')
def handle_terms_button(message):
    # Создаем сообщение с пользовательским соглашением и отправляем его
    bot.send_message(message.chat.id, terms_text, parse_mode='Markdown')

# Обработчик кнопки "Контакты"
@bot.message_handler(func=lambda message: message.text == 'Контакты📞')
def handle_contacts_button(message):
    # Создаем сообщение с контактными данными и гиперссылкой на Whatsapp
    contacts_text = """
    Контакты для связи:

    - [Telegram]()
    - [Whatsapp]()
    """

    # Отправляем сообщение с контактами и гиперссылкой на Whatsapp
    bot.send_message(message.chat.id, contacts_text, parse_mode='Markdown')



@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_'))
def handle_cancel(call):
    user_id = call.from_user.id
    termin_id = int(call.data.split('_')[1])

    # Получаем информацию о записи из базы данных
    session = db.get_db_session()
    termin = session.query(db.Termin).filter(db.Termin.id == termin_id).first()

    if termin and termin.user_id == user_id:
        # Удаляем запись
        session.delete(termin)
        session.commit()

        bot.send_message(call.message.chat.id, "Запись успешно отменена.✅")
    else:
        bot.send_message(call.message.chat.id, "Ошибка: запись не найдена.🚫")

@bot.message_handler(commands=['объявление'])
def announcement_command(message):
    handle_announcement_command(bot, message)

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_announcement", "cancel_announcement"])
def confirm_announcement(call):
    send_announcement_to_all_users(bot, call, get_all_users)  # get_all_users должна быть функцией, которая возвращает список идентификаторов пользователей


def is_user_registered(user_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user is not None


@bot.message_handler(func=lambda message: message.text == "/appointment")
def appointment_handler(message):
    user_id = message.from_user.id
    if not is_user_registered(user_id):
        bot.send_message(message.chat.id, "Пожалуйста, сначала авторизуйтесь или зарегистрируйтесь.")
        return
    handle_appointment_button(message)


@bot.message_handler(func=lambda message: message.text == "/personal_cabinet")
def personal_cabinet_handler(message):
    user_id = message.from_user.id
    if not is_user_registered(user_id):
        bot.send_message(message.chat.id, "Пожалуйста, сначала авторизуйтесь или зарегистрируйтесь.")
        return
    handle_account_button(message)

@bot.message_handler(func=lambda message: message.text == "/user_agreements")
def user_agreements_handler(message):
    handle_terms_button(message)

@bot.message_handler(func=lambda message: message.text == "/contacts")
def contacts_handler(message):
    handle_contacts_button(message)











if __name__ == '__main__':
    import time
    from threading import Thread
    from datetime import datetime, timedelta
    import sqlalchemy

    def check_termins():
        while True:
            try:
                session = db.get_db_session()
                now = datetime.now()

                termins = session.query(db.Termin).filter(db.Termin.canceled == False)

                count = 0
                for termin in termins:
                    try:
                        termin_time = datetime.strptime(termin.time, '%H:%M')
                        termin_datetime = datetime(termin.year, termin.month, termin.day, termin_time.hour, termin_time.minute)
                    except ValueError:
                        continue

                    if termin_datetime.date() == now.date() + timedelta(days=1) and now.time() >= dtime(14, 0) and not termin.notification_sent:
                        send_reminder(termin, "Здравствуйте, у вас завтра назначена встреча в (time) по поводу (note). Если Вы не можете или хотите перенести время, прошу войти в наш ТГ бот и отменить встречу.")
                        termin.notification_sent = True

                    elif termin_datetime.date() == now.date() and now >= (termin_datetime - timedelta(hours=1)) and not termin.notification_sent:
                        send_reminder(termin, "Здравствуйте, у вас сегодня назначена встреча в (time) по поводу (note). Если Вы не можете или хотите перенести время, прошу войти в наш ТГ бот и отменить встречу. Так же прошу уведомить об этом мастера.")
                        termin.notification_sent = True

                    elif now > termin_datetime:
                        fertig = db.Fertig(
                            user_id=termin.user_id, 
                            note=termin.note, 
                            day=termin.day,
                            month=termin.month,
                            year=termin.year,
                            time=termin.time,
                            name=termin.name,
                            car_brand=termin.car_brand,
                            vin=termin.vin,
                            phone_number=termin.phone_number
                        )
                        session.add(fertig)
                        session.delete(termin)
                        count += 1

                session.commit()

                print(f"Проверка выполнена в {now}. Обработано событий: {count}")

            except sqlalchemy.exc.SQLAlchemyError as e:
                print(f"Ошибка при работе с базой данных: {e}")
            except Exception as e:
                print(f"Неожиданная ошибка: {e}")
            finally:
                time.sleep(1 * 60)


    def send_reminder(termin, message):
        user_id = termin.user_id
        termin_time = termin.time
        note = termin.note

        message_text = message.replace("(time)", termin_time).replace("(note)", note)
        bot.send_message(user_id, message_text)

        print(f"Отправлено уведомление о Termin {termin.day}/{termin.month}/{termin.year} и {termin.time}. User: {user_id} {message_text}")



    # Запускаем проверку termins в фоне
    thread = Thread(target=check_termins)
    thread.start()

    # Запускаем бота
    bot.polling(none_stop=True)