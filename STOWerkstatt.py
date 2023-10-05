import os
import time
import threading
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from telebot import TeleBot, types
import sqlite3
import calendar

load_dotenv()

TOKEN = os.getenv('WORKER_BOT_TOKEN')
bot = TeleBot(TOKEN)
WORK_HOURS_WEEKDAYS = (16, 20)
WORK_HOURS_SATURDAY = (8, 14)
USER_STATE = {}


# Глобальные переменные для хранения текущего состояния таблиц
current_users = []
current_termins = []
current_work_orders = []
current_parts = []
current_fertig = []

# IDs of users who are allowed to interact with the bot
ALLOWED_USER_IDS = [123456, 123456]

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id  # Получение ID пользователя
    
    # Проверка, разрешен ли доступ для данного пользователя
    if user_id not in ALLOWED_USER_IDS:
        bot.send_message(user_id, "У вас нет доступа к этому боту.")
        return  # Прекращение выполнения функции, если доступ не разрешен

    # Оставшаяся часть вашего кода
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())



def fetch_data_from_db():
    """Извлекает все данные из базы данных."""
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    users = cursor.execute("SELECT * FROM users").fetchall()
    termins = cursor.execute("SELECT * FROM termins").fetchall()
    work_orders = cursor.execute("SELECT * FROM work_orders").fetchall()
    parts = cursor.execute("SELECT * FROM parts").fetchall()
    fertig = cursor.execute("SELECT * FROM fertig").fetchall()
    
    conn.close()
    
    return users, termins, work_orders, parts, fertig

def check_for_updates():
    """Проверяет базу данных на наличие изменений и пишет в лог при их обнаружении."""
    global current_users, current_termins, current_work_orders, current_parts, current_fertig
    
    users, termins, work_orders, parts, fertig = fetch_data_from_db()
    
    if users != current_users:
        print("[LOG] Table 'users' has been updated.")
        current_users = users
        
    if termins != current_termins:
        print("[LOG] Table 'termins' has been updated.")
        current_termins = termins
        
    if work_orders != current_work_orders:
        print("[LOG] Table 'work_orders' has been updated.")
        current_work_orders = work_orders
        
    if parts != current_parts:
        print("[LOG] Table 'parts' has been updated.")
        current_parts = parts
        
    if fertig != current_fertig:
        print("[LOG] Table 'fertig' has been updated.")
        current_fertig = fertig

def periodic_db_check():
    """Регулярно проверяет базу данных на обновления."""
    while True:
        check_for_updates()
        time.sleep(60)  # Задержка в 60 секунд

# Запуск регулярной проверки в отдельном потоке
thread = threading.Thread(target=periodic_db_check)
thread.start()

def initialize_work_orders_table():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    # Создание таблицы для заказов на работу, если она не существует
    cur.execute('''
        CREATE TABLE IF NOT EXISTS work_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                description TEXT,
                total_cost REAL,
                parts_count INTEGER,
                work_time TEXT,
                start_date DATE,
                end_date DATE,
                termin_id INTEGER,
                status TEXT,
                price_for_work REAL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(termin_id) REFERENCES termins(id)
        )
    ''')

    # Check if the column already exists
    cur.execute("PRAGMA table_info(work_orders)")
    columns = cur.fetchall()
    column_names = [column[1] for column in columns]

    # If the 'price_for_work' column doesn't exist, add it
    if 'price_for_work' not in column_names:
        cur.execute("ALTER TABLE work_orders ADD COLUMN price_for_work REAL")
        print("Column 'price_for_work' has been added.")
    else:
        print("Column 'price_for_work' already exists.")
        
    # If the 'created_at' column doesn't exist, add it
    if 'created_at' not in column_names:
        cur.execute("ALTER TABLE work_orders ADD COLUMN created_at DATE")
        print("Column 'created_at' has been added.")
    else:
        print("Column 'created_at' already exists.")
        
    print("Таблица work_orders создана или уже существует.")

    conn.commit()
    conn.close()

def initialize_parts_table():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    # Создание таблицы для запчастей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            part_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            part_name TEXT,
            quantity INTEGER,
            cost_per_unit REAL,
            labor_cost REAL,
            FOREIGN KEY(order_id) REFERENCES work_orders(order_id)
        )
    ''')

    print("Таблица parts создана или уже существует.")

    conn.commit()
    conn.close()

def initialize_database():
    initialize_work_orders_table()
    initialize_parts_table()

    print("База данных инициализирована.")











def create_main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton('Поиск клиента'))
    markup.row(types.KeyboardButton('Календарь терминов'))
    markup.row(types.KeyboardButton('Отчёты'))
    markup.row(types.KeyboardButton('Бухгалтерия'))
    markup.row(types.KeyboardButton('Редактирование')) 
    return markup

@bot.message_handler(func=lambda message: message.text == "Редактирование")
def handle_edit_options_modified(message):
    """
    Display the edit options when "Редактирование" is clicked.
    """
    markup = types.InlineKeyboardMarkup()
    
    # Inline buttons for editing options
    user_edit_button = types.InlineKeyboardButton("Редактировать клиента", callback_data="edit_user")
    work_order_edit_button = types.InlineKeyboardButton("Редактировать наряды на работу", callback_data="edit_work_order")
    
    # Add buttons vertically
    markup.add(user_edit_button)
    markup.add(work_order_edit_button)
    
    bot.send_message(message.chat.id, "Выберите что хотите отредактировать:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "edit_user")
def handle_edit_user(call):
    chat_id = call.message.chat.id

    # Перенаправляем пользователя на этап "Поиск клиента"
    search_criteria_keyboard = create_search_criteria_keyboard()
    bot.send_message(chat_id, "Выберите критерий для поиска:", reply_markup=search_criteria_keyboard)



@bot.callback_query_handler(func=lambda call: call.data == "edit_work_order")
def handle_edit_work_order(call):
    """
    Handle the "Редактировать наряды на работу" button press.
    """
    chat_id = call.message.chat.id
    # Calling the function to display search options
    display_search_options_for_work_orders(chat_id)

def display_search_options_for_work_orders(chat_id):
    """
    Display search options to the user for finding work orders.
    """
    markup = types.InlineKeyboardMarkup()
    
    # Inline buttons for search options
    search_by_name_button = types.InlineKeyboardButton("Поиск по имени", callback_data="search_by_name_edit")
    search_by_phone_button = types.InlineKeyboardButton("Поиск по номеру телефона", callback_data="search_by_phone_edit")
    
    # Add buttons vertically
    markup.add(search_by_name_button)
    markup.add(search_by_phone_button)
    
    bot.send_message(chat_id, "Выберите критерий поиска:", reply_markup=markup)

def create_parts_edit_keyboard(order_id):
    markup = types.InlineKeyboardMarkup()
    edit_button = types.InlineKeyboardButton("Обновить запчасти", callback_data=f"edit_parts_{order_id}")
    markup.add(edit_button)
    return markup



@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id) == "awaiting_name_input", content_types=['text'])
def handle_name_input(message):
    chat_id = message.chat.id
    name = message.text
    
    USER_STATE[chat_id] = None  # Reset the state for this user
    
    conn = sqlite3.connect('bot.db')  # Connect to the database
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM users WHERE name=?", (name,))  # Search for the user by name
    user_info = cur.fetchone()
    
    if user_info:
        user_id = user_info[0]
        user_name = user_info[1]
        user_phone = user_info[2]
        user_email = user_info[3]
        
        cur.execute("SELECT * FROM work_orders WHERE user_id=?", (user_id,))  # Search for work orders for this user
        work_orders = cur.fetchall()
        
        if work_orders:
            for order in work_orders:
                order_id, _, description, total_cost, parts_count, work_time, start_date, end_date, termin_id, status, price_for_work, created_at = order
                response_markup = create_parts_edit_keyboard(order_id)  # <-- Это место
        
                cur.execute("SELECT part_name, cost_per_unit FROM parts WHERE order_id=?", (order_id,))  # Fetch parts associated with this work order
                parts = cur.fetchall()
    
                # Formatting the response
                response = "Описание наряда:\nКлиент: " + user_name
                response += f"\nТелефон: {user_phone}"
                response += f"\nE-Mail: {user_email}"
                response += f"\nДата: {start_date}\nОписание: {description}"
                response += f"\nКоличество запчастей: {parts_count}"
                response += f"\nСтоимость работы без учета деталей: {price_for_work} USD"
    
                # Check for None values before subtraction
                if total_cost is None:
                    total_cost = 0.0
                if price_for_work is None:
                    price_for_work = 0.0
    
                response += f"\nСтоимость запчастей: {total_cost - price_for_work} USD"
    
                for part_name, part_price in parts:
                    response += f"\n{part_name}: {part_price} USD"
    
                bot.send_message(chat_id, response, reply_markup=response_markup)
        else:
            bot.send_message(chat_id, f"Нет нарядов на работу для {name}.")
    else:
        bot.send_message(chat_id, f"Пользователь {name} не найден.")
    
    conn.close()

@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id) == "awaiting_phone_input", content_types=['text'])
def handle_phone_input(message):
    chat_id = message.chat.id
    phone_number = message.text
    
    # Сброс состояния для этого пользователя
    USER_STATE[chat_id] = None
    
    # Подключение к базе данных
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Поиск пользователя по номеру телефона
    cur.execute("SELECT * FROM users WHERE phone_number=?", (phone_number,))
    user_info = cur.fetchone()
    
    if user_info:
        user_id = user_info[0]
        user_name = user_info[1]
        user_phone = user_info[2]
        user_email = user_info[3]
        
        # Поиск нарядов на работу для данного пользователя
        cur.execute("SELECT * FROM work_orders WHERE user_id=?", (user_id,))
        work_orders = cur.fetchall()
        
        if work_orders:
            for order in work_orders:
                order_id, _, description, total_cost, parts_count, work_time, start_date, end_date, termin_id, status, price_for_work, created_at = order
                response_markup = create_parts_edit_keyboard(order_id)  # Это место должно быть определено в другой части вашего кода
                
                # Выборка частей, связанных с этим нарядом на работу
                cur.execute("SELECT part_name, cost_per_unit FROM parts WHERE order_id=?", (order_id,))
                parts = cur.fetchall()
    
                # Форматирование ответа
                response = "Описание наряда:\nКлиент: " + user_name
                response += f"\nТелефон: {user_phone}"
                response += f"\nE-Mail: {user_email}"
                response += f"\nДата: {start_date}\nОписание: {description}"
                response += f"\nКоличество запчастей: {parts_count}"
                response += f"\nСтоимость работы без учета деталей: {price_for_work} USD"
    
                if total_cost is None:
                    total_cost = 0.0
                if price_for_work is None:
                    price_for_work = 0.0
    
                response += f"\nСтоимость запчастей: {total_cost - price_for_work} USD"
    
                for part_name, part_price in parts:
                    response += f"\n{part_name}: {part_price} USD"
    
                bot.send_message(chat_id, response, reply_markup=response_markup)
        else:
            bot.send_message(chat_id, f"Нет нарядов на работу для номера телефона {phone_number}.")
    else:
        bot.send_message(chat_id, f"Пользователь с номером телефона {phone_number} не найден.")
    
    # Закрытие соединения с базой данных
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_parts_"))
def handle_edit_parts_selection(call):
    order_id = int(call.data.split("_")[2])
    
    chat_id = call.message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id] is None:
        USER_STATE[chat_id] = {}
    
    USER_STATE[chat_id]['selected_order_id'] = order_id
    USER_STATE[chat_id]['state'] = 'awaiting_parts_count_input'
    USER_STATE[chat_id]['parts'] = []
    
    bot.send_message(chat_id, "Введите количество запчастей, которое вы хотите добавить или обновить:")

@bot.callback_query_handler(func=lambda call: call.data == "search_order_by_name")
def ask_for_name_search_order(call):
    chat_id = call.message.chat.id
    print("[DEBUG] Received callback for search_order_by_name")  # Добавьте это для отладки
    USER_STATE[chat_id] = "awaiting_name_input"
    bot.edit_message_text("Введите имя для поиска:", chat_id=chat_id, message_id=call.message.message_id)

def add_work_order(user_id, description, status, created_at, price_for_work, total_cost, parts_count, work_time, start_date, end_date):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO work_orders (user_id, description, status, created_at, price_for_work, total_cost, parts_count, work_time, start_date, end_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, description, status, created_at, price_for_work, total_cost, parts_count, work_time, start_date, end_date))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


@bot.callback_query_handler(func=lambda call: call.data == "search_by_name_edit")
def ask_for_name_search_order_edit(call):
    chat_id = call.message.chat.id
    USER_STATE[chat_id] = "awaiting_name_input"  # Устанавливаем состояние ожидания ввода имени
    bot.edit_message_text("Введите имя для поиска:", chat_id=chat_id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "search_by_phone_edit")
def ask_for_phone_search_order_edit(call):
    chat_id = call.message.chat.id
    USER_STATE[chat_id] = "awaiting_phone_input"  # Устанавливаем состояние ожидания ввода номера телефона
    bot.edit_message_text("Введите номер телефона для поиска:", chat_id=chat_id, message_id=call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == "update_parts")
def update_parts_handler(call):
    chat_id = call.message.chat.id
    USER_STATE[chat_id] = "awaiting_parts_count_input"
    bot.send_message(chat_id, "Введите количество запчастей, которое вы хотите добавить или обновить:")

@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') == 'entering_part_name_edit')
def handle_part_name_edit_input(message):
    chat_id = message.chat.id

    # Сохраняем введенное имя запчасти
    part_name = message.text

    # Проверяем, есть ли уже запись о текущей запчасти в USER_STATE
    if chat_id in USER_STATE and 'parts' in USER_STATE[chat_id]:
        if len(USER_STATE[chat_id]['parts']) < USER_STATE[chat_id]['current_part']:
            USER_STATE[chat_id]['parts'].append({'name': part_name, 'price': 0.0})  # Инициализируем поле "price"
        else:
            USER_STATE[chat_id]['parts'][USER_STATE[chat_id]['current_part']-1]['name'] = part_name

        # Переводим состояние на ввод цены для текущей запчасти
        USER_STATE[chat_id]['state'] = 'entering_part_price_edit'
        bot.send_message(chat_id, f"Введите цену для запчасти №{USER_STATE[chat_id]['current_part']}:")



@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') == 'entering_part_price_edit')
def handle_part_price_edit_input(message):
    chat_id = message.chat.id

    try:
        part_price = float(message.text)
        USER_STATE[chat_id]['parts'][USER_STATE[chat_id]['current_part']-1]['price'] = part_price

        # Если это была последняя запчасть, завершаем процесс ввода
        if USER_STATE[chat_id]['current_part'] == USER_STATE[chat_id]['parts_count']:
            # Отправка финального сообщения
            send_final_order_description(chat_id, USER_STATE[chat_id]['selected_order_id'])
        else:
            # Если еще остались запчасти, переходим к следующей
            USER_STATE[chat_id]['current_part'] += 1
            USER_STATE[chat_id]['state'] = 'entering_part_name_edit'
            bot.send_message(chat_id, f"Введите наименование запчасти №{USER_STATE[chat_id]['current_part']}:")
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введите корректную цену.")



def create_confirmation_keyboard_parts():
    markup = types.InlineKeyboardMarkup()
    btn_confirm = types.InlineKeyboardButton("Подтвердить изменение", callback_data="confirm_parts_change")
    btn_cancel = types.InlineKeyboardButton("Отменить изменение", callback_data="cancel_parts_change")
    markup.add(btn_confirm, btn_cancel)
    return markup


@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') == 'awaiting_parts_count_input')
def handle_parts_count_input_edit(message):
    chat_id = message.chat.id
    try:
        parts_count = int(message.text)
        
        # Проверка на ввод 0
        if parts_count == 0:
            bot.send_message(chat_id, "Количество запчастей не может быть равным нулю. Попробуйте снова.")
            return
        
        # Проверяем наличие chat_id в USER_STATE и обновляем соответствующие поля
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        USER_STATE[chat_id].update({
            'state': 'entering_part_name_edit',
            'parts_count': parts_count,
            'current_part': 1,
            'parts': []
        })
        
        bot.send_message(chat_id, "Введите наименование запчасти №1:")
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введите корректное количество.")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_parts_change")
def handle_cancel_parts_change(call):
    chat_id = call.message.chat.id
    
    # Очищаем временные данные из USER_STATE
    if chat_id in USER_STATE:
        del USER_STATE[chat_id]

    bot.edit_message_text("Изменения отменены.", chat_id=chat_id, message_id=call.message.message_id)


def send_final_order_description(chat_id, selected_order_id):
    # Подключаемся к базе данных
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    # Получаем информацию о пользователе по id (который соответствует chat_id)
    cur.execute("SELECT * FROM users WHERE id=?", (chat_id,))
    user_info = cur.fetchone()

    # Проверяем, найден ли пользователь
    if not user_info:
        bot.send_message(chat_id, "Пользователь не найден.")
        conn.close()
        return

    user_id, user_name, user_phone, user_email, *_ = user_info

    # Получаем наряд на работу по selected_order_id
    cur.execute("SELECT * FROM work_orders WHERE order_id=?", (selected_order_id,))
    order = cur.fetchone()

    # Проверяем, есть ли наряд для данного пользователя
    if not order:
        bot.send_message(chat_id, "Наряд на работу не найден.")
        conn.close()
        return

    response = "Обновленное описание наряда:\n"
    
    order_id, _, description, total_cost, parts_count, work_time, start_date, end_date, termin_id, status, price_for_work, created_at = order

    # Проверяем наличие временных данных в USER_STATE
    if 'parts' in USER_STATE.get(chat_id, {}):
        parts = [(part['name'], part['price']) for part in USER_STATE[chat_id]['parts']]
        parts_cost = sum(part['price'] for part in USER_STATE[chat_id]['parts'])
    else:
        cur.execute("SELECT part_name, cost_per_unit FROM parts WHERE order_id=?", (order_id,))
        parts = cur.fetchall()
        parts_cost = sum(price for _, price in parts)

    # Форматирование ответа
    response += "\nКлиент: " + user_name
    response += f"\nТелефон: {user_phone}"
    response += f"\nE-Mail: {user_email}"
    response += f"\nДата: {start_date}\nОписание: {description}"
    response += f"\nКоличество запчастей: {parts_count}"
    response += f"\nСтоимость работы без учета деталей: {price_for_work} USD"
    response += f"\nСтоимость запчастей: {parts_cost} USD"
    
    for part_name, part_price in parts:
        response += f"\n{part_name}: {part_price} USD"

    markup = create_confirmation_keyboard_parts()
    bot.send_message(chat_id, response, reply_markup=markup)

    conn.close()

def update_parts_in_db(order_id, new_parts, conn):
    try:
        cur = conn.cursor()

        # Удаляем старые записи о запчастях для данного order_id
        cur.execute("DELETE FROM parts WHERE order_id=?", (order_id,))

        # Добавляем новые запчасти
        total_parts_cost = 0  # Инициализируем переменную для хранения общей стоимости запчастей
        for part in new_parts:
            cur.execute("INSERT INTO parts (part_name, cost_per_unit, order_id) VALUES (?, ?, ?)",
                        (part['name'], part['price'], order_id))
            total_parts_cost += part['price']  # Добавляем стоимость текущей запчасти к общей сумме

        # Получаем текущую стоимость работы из таблицы work_orders
        cur.execute("SELECT price_for_work FROM work_orders WHERE order_id = ?", (order_id,))
        row = cur.fetchone()
        if row:
            price_for_work = row[0]
        else:
            return "Ошибка: не удалось найти наряд с данным order_id."

        # Обновляем общую стоимость наряда на работу
        new_total_cost = total_parts_cost + price_for_work
        cur.execute("UPDATE work_orders SET total_cost = ? WHERE order_id = ?", (new_total_cost, order_id))

        conn.commit()
        return "Изменения сохранены."
        
    except Exception as e:
        conn.rollback()
        return f"Произошла ошибка: {str(e)}"




@bot.callback_query_handler(func=lambda call: call.data == "confirm_parts_change")
def handle_confirm_parts_change(call):
    chat_id = call.message.chat.id
    
    print(f"Entered handle_confirm_parts_change with chat_id {chat_id}")  # Debug info for logging
    
    # Открываем единое соединение с базой данных
    conn = sqlite3.connect('bot.db')
    
    try:
        print(f"USER_STATE: {USER_STATE}")  # Debug info for logging
        
        if USER_STATE.get(chat_id, {}).get('parts'):
            print("Updating parts in DB...")  # Debug info for logging
            
            # Передаем соединение с базой данных как аргумент
            update_result = update_parts_in_db(
                USER_STATE[chat_id]['selected_order_id'], 
                USER_STATE[chat_id]['parts'],
                conn  # передаем соединение с базой данных
            )
            
            print(f"Update result: {update_result}")  # Debug info for logging
            
            del USER_STATE[chat_id]
    
            bot.edit_message_text(
                update_result, 
                chat_id=chat_id, 
                message_id=call.message.message_id
            )
        else:
            print("Error: Missing data in USER_STATE")  # Debug info for logging
            bot.edit_message_text(
                "Произошла ошибка при сохранении изменений.", 
                chat_id=chat_id, 
                message_id=call.message.message_id
            )
            
        # Закрыть соединение с базой данных
        conn.close()
            
    except sqlite3.DatabaseError as db_err:
        print(f"Database error: {db_err}")
        bot.edit_message_text(
            f"Произошла ошибка базы данных: {db_err}", 
            chat_id=chat_id, 
            message_id=call.message.message_id
        )
        conn.close()  # Закрыть соединение при ошибке
        
    except KeyError as key_err:
        print(f"Key error: {key_err}")
        bot.edit_message_text(
            f"Произошла ошибка с ключом: {key_err}", 
            chat_id=chat_id, 
            message_id=call.message.message_id
        )
        conn.close()  # Закрыть соединение при ошибке
        
    except Exception as e:
        print(f"General error in handle_confirm_parts_change: {e}")  # Debug info for logging
        bot.edit_message_text(
            f"Произошла непредвиденная ошибка: {e}", 
            chat_id=chat_id, 
            message_id=call.message.message_id
        )
        conn.close()  # Закрыть соединение при ошибке












def find_available_slots(work_hours, user_id):
    # Получите текущую дату и время
    now = datetime.datetime.now()

    # Подключитесь к базе данных и получите информацию о занятых временных слотах
    connection = sqlite3.connect('bot.db')
    cursor = connection.cursor()
    # Ваш запрос для получения занятых слотов в данном месяце
    query = "SELECT day, month, year, time FROM termins WHERE ... "
    cursor.execute(query, (now.year, now.month))
    occupied_slots = cursor.fetchall()
    connection.close()

    # Здесь вы можете реализовать логику поиска доступных временных слотов
    # на основе занятых слотов и количества часов работы

    available_slots = []

    return available_slots

def create_available_slots_keyboard(available_slots):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for slot in available_slots:
        day, month, year, time = slot
        date_str = f"{day:02d}.{month:02d}.{year:04d} {time}"
        callback_data = f"select-slot-{day}-{month}-{year}-{time}"
        keyboard.add(types.InlineKeyboardButton(date_str, callback_data=callback_data))
    return keyboard

@bot.callback_query_handler(func=lambda call: call.data.startswith('select-slot-'))
def handle_slot_selection(call):
    data_parts = call.data.split('-')
    day, month, year, time = map(int, data_parts[2:])
    user_id = call.from_user.id

    # Здесь вы можете сохранить выбранный термин в состоянии пользователя
    # и перейти к следующему шагу

    # Предложите пользователю заказать детали
    bot.send_message(user_id, "Вы хотите заказать детали для данного клиента?", reply_markup=create_yes_no_keyboard())


def create_termins_calendar(year=None, month=None):
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    data_ignore = calendar.monthcalendar(year, month)
    markup = types.InlineKeyboardMarkup(row_width=7)

    # Add navigation buttons
    prev_month_data = "previous-month-{}-{}".format(year, month)
    next_month_data = "next-month-{}-{}".format(year, month)
    if year == now.year and month <= now.month:
        navigation_buttons = [types.InlineKeyboardButton(" ", callback_data="ignore"),
                              types.InlineKeyboardButton(calendar.month_name[month] + " " + str(year), callback_data=f"calendar-month-{month}-{year}"),
                              types.InlineKeyboardButton(">", callback_data=next_month_data)]
    else:
        navigation_buttons = [types.InlineKeyboardButton("<", callback_data=prev_month_data),
                              types.InlineKeyboardButton(calendar.month_name[month] + " " + str(year), callback_data=f"calendar-month-{month}-{year}"),
                              types.InlineKeyboardButton(">", callback_data=next_month_data)]
    markup.row(*navigation_buttons)

    week_days = ["M", "T", "W", "R", "F", "S", "U"]
    markup.row(*[types.InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

    for week in data_ignore:
        row_buttons = []
        for day in week:
            if day == 0 or (year == now.year and month == now.month and day < now.day):
                row_buttons.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                day_str = str(day)
                # Check for termins for the date
                conn = sqlite3.connect('bot.db')
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM termins WHERE day={day} AND month={month} AND year={year}")
                termins_for_date = cur.fetchall()
                conn.close()

                if termins_for_date:
                    day_str += " 📅"

                row_buttons.append(types.InlineKeyboardButton(day_str, callback_data=f"calendar-day-{day}-{month}-{year}"))

        markup.row(*row_buttons)
    return markup

def create_work_assignment_calendar(year=None, month=None, work_hours=4):  
    from datetime import datetime, date
    import calendar
    from telebot import types
    
    # Assuming the 'year' and 'month' are already determined using the datetime module
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    # Create a markup for the inline keyboard
    markup = types.InlineKeyboardMarkup(row_width=7)
    
    # Navigation buttons
    prev_month_data = "previous-month-work-{}-{}".format(year, month)
    next_month_data = "next-month-work-{}-{}".format(year, month)
    
    # Create current date for comparison
    
    # Check if the current year and month are the same as the displayed calendar
    if year == now.year and month <= now.month:
        navigation_buttons = [
            types.InlineKeyboardButton(" ", callback_data="ignore"),
            types.InlineKeyboardButton(calendar.month_name[month] + " " + str(year), callback_data=f"calendar-month-{month}-{year}"),
            types.InlineKeyboardButton(">", callback_data=next_month_data)
        ]
    else:
        navigation_buttons = [
            types.InlineKeyboardButton("<", callback_data=prev_month_data),
            types.InlineKeyboardButton(calendar.month_name[month] + " " + str(year), callback_data=f"calendar-month-{month}-{year}"),
            types.InlineKeyboardButton(">", callback_data=next_month_data)
        ]
    
    markup.row(*navigation_buttons)

    # Display weekdays
    week_days = ["M", "T", "W", "R", "F", "S", "U"]
    markup.row(*[types.InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

    # Display days of the month
    for week in calendar.monthcalendar(year, month):
        row_buttons = []
        for day in week:
            if day == 0:
                row_buttons.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                current_date = date(year, month, day)
                if current_date < now.date():  # Если день прошел
                    row_buttons.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
                    continue
                
                day_str = str(day)
                available_slots = get_available_time_slots(current_date, work_hours)  # Используется переданный параметр work_hours

                # Add ❌ if no available slots
                if not available_slots:
                    day_str += " ❌"

                row_buttons.append(types.InlineKeyboardButton(day_str, callback_data=f"calendar-day-{day}-{month}-{year}"))

        markup.row(*row_buttons)

    return markup






#Назначение наряда на работу
def get_available_time_slots(date, work_hours):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    day, month, year = date.day, date.month, date.year
    cur.execute(f"SELECT * FROM termins WHERE day={day} AND month={month} AND year={year}")
    termins = cur.fetchall()
    conn.close()

    # Преобразование занятых слотов времени в список
    occupied_slots = [datetime.strptime(termin[6], "%H:%M") for termin in termins]
    print(f"[LOG - get_available_time_slots] Occupied slots for {day}-{month}-{year}: {occupied_slots}")  # Логирование занятых слотов

    # Определение рабочего времени в зависимости от дня недели
    if date.weekday() == 5:  # Если суббота
        start_hour, end_hour = WORK_HOURS_SATURDAY
    else:
        start_hour, end_hour = WORK_HOURS_WEEKDAYS
    print(f"[LOG - get_available_time_slots] Work hours for {day}-{month}-{year}: {start_hour} to {end_hour}")  # Логирование рабочего времени

    # Определение доступных слотов времени
    available_slots = []
    for hour in range(start_hour, end_hour - work_hours + 1):
        slot_start = datetime(year, month, day, hour, 0)
        slot_end = datetime(year, month, day, hour + work_hours, 0)
        if any(slot_start.time() <= occupied_slot.time() < slot_end.time() for occupied_slot in occupied_slots):
            continue
        available_slots.append(f"{hour}:00")

    print(f"[LOG - get_available_time_slots] Available slots for {day}-{month}-{year} with work duration {work_hours} hrs: {available_slots}")  # Логирование доступных слотов
    return available_slots



@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') == 'entering_work_time')
def handle_work_time_input(message):
    work_time_text = message.text
    client_id = USER_STATE[message.chat.id]['client_id']

    try:
        work_time = int(work_time_text)
        if work_time < 1 or work_time > 4:
            bot.send_message(message.chat.id, "Введите время работы от 1-4 часов.")
            return
    except ValueError:
        bot.send_message(message.chat.id, "Введено неверное значение времени. Пожалуйста, введите число от 1 до 4:")
        return

    # Обновление состояния пользователя
    USER_STATE[message.chat.id]['work_duration'] = work_time
    USER_STATE[message.chat.id]['state'] = 'choosing_start_date'

    # Вызов функции для отправки календаря с учетом выбранного пользователем количества рабочих часов
    calendar_markup = create_work_assignment_calendar(work_hours=work_time)
    bot.send_message(message.chat.id, "Выберите дату начала работы:", reply_markup=calendar_markup)




@bot.callback_query_handler(func=lambda call: call.data.startswith('calendar-day-'))
def handle_calendar_day_selection(call):
    day, month, year = map(int, call.data.split('-')[2:])
    chat_id = call.message.chat.id
    selected_date = datetime(year, month, day).date()
    
    # Сохраняем выбранную дату в USER_STATE
    if chat_id not in USER_STATE:
        USER_STATE[chat_id] = {}
    USER_STATE[chat_id].update({'selected_date': selected_date.isoformat()})
    
    # Проверяем, какое действие было выбрано пользователем ранее
    user_state = USER_STATE[chat_id].get('state', '')
    print(f'[LOG] Value of state for chat_id {chat_id}: {user_state}')
    
    if user_state == 'choosing_start_date':
        work_duration = int(USER_STATE[chat_id].get('work_duration', 0))
        available_slots = get_available_slots(selected_date, work_duration)
        print(f'[LOG] Available slots: {available_slots}')
        if not available_slots:
            bot.send_message(chat_id, "На выбранную дату нет доступных слотов. Пожалуйста, выберите другую дату.")
            return
        keyboard = types.InlineKeyboardMarkup()
        for slot in available_slots:
            button_text = f"{slot}:00"
            callback_data = f"slot-{year}-{month}-{day}-{slot}"
            keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))
        bot.send_message(chat_id, "Выберите удобное для вас время:", reply_markup=keyboard)
    
    elif user_state == 'view_termins':
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM termins WHERE day=? AND month=? AND year=?", (day, month, year))
        termins_for_selected_date = cur.fetchall()
    
        if not termins_for_selected_date:
            bot.send_message(chat_id, "На выбранную дату термины отсутствуют.")
            conn.close()
            return

        for termin in termins_for_selected_date:
            # Извлекаем информацию о клиенте
            cur.execute(f"SELECT * FROM users WHERE id=?", (termin[1],))
            client_data = cur.fetchone()

            # Формируем сообщение для каждого термина
            message = (
                f"Дата: {termin[3]}.{termin[4]}.{termin[5]}\n"
                f"Примечание: {termin[2]}\n"
                f"Время: {termin[6]}\n"
                f"Имя: {termin[7]}\n"
                f"Марка автомобиля: {termin[8]}\n"
                f"VIN: {termin[9]}\n"
                f"Номер телефона: {termin[10]}"
            )
            # Создаем клавиатуру для данного термина
            termin_keyboard = create_termin_inline_keyboard(termin[0])
            bot.send_message(chat_id, message, reply_markup=termin_keyboard)

        conn.close()
   
    else:
        # Если пользователь находится в другом состоянии, не связанном с календарем
        bot.send_message(chat_id, "Выберите действие из меню или начните заново с /start.")






def add_parts(conn, order_id, parts_list):
    print("add_parts called with order_id:", order_id)
    
    cur = conn.cursor()
    
    part_ids = []
    total_parts_cost = sum([part.get('price', 0) for part in parts_list])

    for part in parts_list:
        part_name = part.get("part_name", part.get("name"))
        
        if not part_name or "price" not in part:
            print("Skipping part due to missing 'part_name'/'name' or 'price':", part)
            continue

        quantity = 1  # Default value
        
        cur.execute('''
            INSERT INTO parts (order_id, part_name, quantity, cost_per_unit, labor_cost)
            VALUES (?, ?, ?, ?, ?)
        ''', (order_id, part_name, quantity, part["price"], total_parts_cost))

        part_id = cur.lastrowid
        part_ids.append(part_id)
    
    print("Parts added with IDs:", part_ids)
    return part_ids






def add_termins(chat_id, start_time, work_hours, order_id):
    # Проверка наличия user_id в USER_STATE
    if 'user_id' not in USER_STATE.get(chat_id, {}):
        print("Ошибка: user_id не найден в USER_STATE для chat_id:", chat_id)
        return

    user_id = USER_STATE[chat_id]['user_id']

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    # Разбираем начальное время
    start_date_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M")

    # Добавляем записи для каждого часа работы
    for hour_offset in range(work_hours):
        termin_time = start_date_time + datetime.timedelta(hours=hour_offset)
        cur.execute(
            "INSERT INTO termins (user_id, order_id, day, month, year, time) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, order_id, termin_time.day, termin_time.month, termin_time.year, termin_time.strftime("%H:%M"))
        )

    conn.commit()
    conn.close()


def assign_work(update, context):
    
    query = update.callback_query
    chat_id = query.message.chat_id
    client_id = int(query.data.split("-")[2])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Запрашиваем данные о клиенте из базы данных
    cursor.execute("SELECT name, car_brand, car_model, car_year, vin FROM clients WHERE id=?", (client_id,))
    client_data = cursor.fetchone()
    conn.close()
    
    if client_data:
        client_name, car_brand, car_model, car_year, vin_code = client_data
        
        # Обновляем USER_STATE для данного chat_id
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        
        USER_STATE[chat_id].update({
            'state': 'entering_work_time',
            'client_id': client_id,
            'client_name': client_name,
            'car_brand': car_brand,
            'car_model': car_model,
            'car_year': car_year,
            'vin_code': vin_code
        })
        bot.send_message(chat_id, "Введите время данной работы в часах:")
    else:
        bot.send_message(chat_id, "Ошибка: Не удалось найти данные клиента.")


def assign_work(update, context):
    
    query = update.callback_query
    chat_id = query.message.chat_id
    client_id = int(query.data.split("-")[2])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Запрашиваем данные о клиенте из базы данных
    cursor.execute("SELECT name, car_brand, car_model, car_year, car_vin FROM clients WHERE id=?", (client_id,))
    client_data = cursor.fetchone()
    conn.close()
    
    if client_data:
        client_name, car_brand, car_model, car_year, car_vin = client_data
        
        # Обновляем USER_STATE для данного chat_id
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        
        USER_STATE[chat_id].update({
            'state': 'entering_work_time',
            'client_id': client_id,
            'client_name': client_name,
            'car_brand': car_brand,
            'car_model': car_model,
            'car_year': car_year,
            'vin_code': car_vin  # добавьте эту строку
        })

        
        bot.send_message(chat_id, "Введите время данной работы в часах:")
    else:
        bot.send_message(chat_id, "Ошибка: Не удалось найти данные клиента.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('final_confirmation'))
def handle_final_confirmation(call):
    chat_id = call.message.chat.id
    if chat_id not in USER_STATE:
        bot.send_message(chat_id, "Ошибка: отсутствуют данные состояния.")
        return

    user_data = USER_STATE[chat_id]
    client_id = user_data['client_id']

    # Извлечь информацию о клиенте из базы данных
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE id=?", (client_id,))
    client_info = cur.fetchone()
    conn.close()

    if not client_info:
        bot.send_message(chat_id, "Ошибка: клиент не найден.")
        return

    # Проверка наличия всех необходимых ключей в USER_STATE
    required_keys = ['client_name', 'client_phone', 'client_email', 'car_brand', 'car_model', 'car_year', 'vin_code']
    missing_keys = [key for key in required_keys if key not in user_data]

    if missing_keys:
        missing_keys_str = ', '.join(missing_keys)
        bot.send_message(chat_id, f"Ошибка: отсутствуют следующие ключи в USER_STATE: {missing_keys_str}")
        return

    # Формирование и отправка итогового сообщения с подтверждением
    response = "Описание наряда:\n"
    response += f"\nКлиент: {user_data['client_name']}"
    response += f"\nТелефон: {user_data['client_phone']}"
    response += f"\nE-Mail: {user_data['client_email']}"
    response += f"\nБрэнд Авто: {user_data['car_brand']}"
    response += f"\nМодель Авто: {user_data['car_model']}"
    response += f"\nГод Авто: {user_data['car_year']}"
    response += f"\nVIN Код: {user_data['vin_code']}"
    response += f"\nДата: {user_data.get('selected_date', 'Неизвестно')}\n"
    response += f"Время: {user_data.get('selected_time', 'Неизвестно')}\n"
    response += f"Описание: {user_data.get('work_description', 'Неизвестно')}\n"
    response += f"Количество запчастей: {user_data.get('parts_count', 'Неизвестно')}\n"
    response += f"Стоимость работы без учета деталей: {user_data.get('work_cost', 'Неизвестно')} USD\n"
    
    total_parts_cost = sum([int(part['price']) for part in user_data.get('parts', [])])
    response += f"Стоимость запчастей: {total_parts_cost} USD\n"
    
    for part in user_data.get('parts', []):
        response += f"{part.get('name', 'Неизвестно')}: {part.get('price', 'Неизвестно')} USD\n"

    # Отправляем подтверждение и добавляем инлайн кнопки
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Подтвердить", callback_data="confirm_order"),
        types.InlineKeyboardButton("Изменить", callback_data="edit_order"),
        types.InlineKeyboardButton("Отменить", callback_data="cancel_order")
    )
    bot.send_message(chat_id, response, reply_markup=markup)

    # Дополнительный код для сохранения данных в базе данных и очистки состояния может быть добавлен здесь. 1)





def get_available_slots(date, duration):
    print(f"[LOG] Checking available slots for date {date} with duration {duration} hours...")

    weekday = date.weekday()

    if weekday == 6:  # Воскресенье
        print(f"[LOG] It's Sunday, no slots available.")
        return []

    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()

    if weekday == 5:  # Суббота
        slots = list(range(8, 14))  # 08:00 - 13:00
    else:
        slots = list(range(16, 20))  # 16:00 - 19:00

    available_slots = []
    for slot in slots:
        if slot + duration > slots[-1] + 1:  # Check if the slot exceeds the working hours
            # Check the next day
            next_day = date + timedelta(days=1)
            if next_day.weekday() == 6:  # If next day is Sunday, move to Monday
                next_day += timedelta(days=1)
            
            for hour in range(0, duration):
                time_str = f"{hour}:00"
                cur.execute(f"SELECT * FROM termins WHERE day=? AND month=? AND year=? AND time=?", 
                            (next_day.day, next_day.month, next_day.year, time_str))
                if cur.fetchone():
                    break
            else:
                continue  # If the next day is available, then continue to the next slot
        
        for hour in range(slot, slot + duration):
            time_str = f"{hour}:00"
            cur.execute(f"SELECT * FROM termins WHERE day=? AND month=? AND year=? AND time=?", 
                        (date.day, date.month, date.year, time_str))
            if cur.fetchone():
                break
        else:
            available_slots.append(slot)

    conn.close()

    print(f"[LOG] Found available slots: {available_slots}")
    return available_slots



@bot.callback_query_handler(func=lambda call: call.data.startswith('slot-'))
def handle_time_slot_selection(call):
    # Разбор выбранного слота времени
    year, month, day, slot = map(int, call.data.split('-')[1:])
    chat_id = call.message.chat.id

    # Проверка наличия chat_id в USER_STATE
    if chat_id not in USER_STATE:
        USER_STATE[chat_id] = {}

    # Сохранение выбранного времени и обновление состояния пользователя
    USER_STATE[chat_id].update({
        'selected_time': f"{year}-{month}-{day} {slot}:00",
        'state': 'entering_work_description'
    })

    # Запрос описания работы
    bot.send_message(chat_id, "Введите описание данной работы:")


@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') == 'entering_work_description')
def handle_work_description_input(message):
    chat_id = message.chat.id
    work_description = message.text

    # Проверка наличия chat_id в USER_STATE
    if chat_id not in USER_STATE:
        USER_STATE[chat_id] = {}

    # Сохранение описания работы
    USER_STATE[chat_id].update({'work_description': work_description})

    # Переход к вводу стоимости работы без учета запчастей
    USER_STATE[chat_id].update({'state': 'entering_work_cost'})
    bot.send_message(chat_id, "Введите стоимость работы без стоимости запчастей:")


@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') in ['entering_work_cost', 'final_confirmation'])
def handle_work_cost_input(message):
    chat_id = message.chat.id
    try:
        work_cost = int(message.text)

        # Проверка наличия chat_id в USER_STATE и обновление стоимости работы
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        USER_STATE[chat_id].update({'work_cost': work_cost})

        if USER_STATE[chat_id]['state'] == 'entering_work_cost':
            # Вопрос о заказе запчастей
            parts_order_keyboard = types.InlineKeyboardMarkup()
            parts_order_keyboard.add(types.InlineKeyboardButton(text="Да", callback_data="order_parts_yes"))
            parts_order_keyboard.add(types.InlineKeyboardButton(text="Нет", callback_data="order_parts_no"))
            bot.send_message(chat_id, "Будите ли вы заказывать запчасти для данной работы?", reply_markup=parts_order_keyboard)

        elif USER_STATE[chat_id]['state'] == 'final_confirmation':
            # Вычисляем общую стоимость деталей
            total_parts_cost = sum([int(part['price']) for part in USER_STATE[chat_id]['parts']])

            # Формирование и отправка итогового сообщения с подтверждением
            user_data = USER_STATE[chat_id]
            response = "Описание наряда:\n"
            response += f"Клиент: {user_data['client_name']}\n"
            response += f"Телефон: {user_data.get('client_phone', 'Неизвестно')}\n"
            response += f"E-Mail: {user_data.get('client_email', 'Неизвестно')}\n"
            response += f"Брэнд Авто: {user_data['car_brand']}\n"
            response += f"Модель Авто: {user_data['car_model']}\n"
            response += f"Год Авто: {user_data['car_year']}\n"
            response += f"VIN Код: {user_data.get('vin_code', 'Неизвестно')}\n"
            response += f"Дата начала работы: {USER_STATE[chat_id].get('start_date')}\n"
            response += f"Время начала работы: {USER_STATE[chat_id].get('start_time')}\n"
            response += f"Количество рабочих часов: {USER_STATE[chat_id].get('work_time')}\n"
            response += f"Стоимость работы: {work_cost}\n"
            response += f"Общая стоимость деталей с учетом доставки: {total_parts_cost}\n"
            bot.send_message(chat_id, response)

            # Здесь можно добавить логику сохранения данных в базу данных

    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введите корректную стоимость работы.")

  # Дополнительный код для сохранения данных в базе данных и очистки состояния может быть добавлен здесь. 2)


@bot.callback_query_handler(func=lambda call: call.data in ["order_parts_yes", "order_parts_no"])
def handle_parts_order(call):
    chat_id = call.message.chat.id

    if call.data == "order_parts_yes":
        # Проверка наличия chat_id в USER_STATE и обновление состояния
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        USER_STATE[chat_id].update({'state': 'entering_parts_count'})
        
        bot.send_message(chat_id, "Введите количество запчастей:")
    else:
        # Если выбрано "Нет", устанавливаем parts в пустой список
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        USER_STATE[chat_id]['parts'] = []
        
        send_final_confirmation(chat_id)




@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') == 'entering_parts_count')
def handle_parts_count_input(message):
    chat_id = message.chat.id
    try:
        parts_count = int(message.text)
        
        # Проверяем наличие chat_id в USER_STATE и обновляем соответствующие поля
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        USER_STATE[chat_id].update({
            'state': 'entering_part_name',
            'parts_count': parts_count,
            'current_part': 1,
            'parts': []
        })
        
        bot.send_message(chat_id, "Введите наименование запчасти №1:")
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введите корректное количество.")



@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') == 'entering_part_name')
def handle_part_name_input(message):
    chat_id = message.chat.id
    
    # Сохраняем введенное имя запчасти
    part_name = message.text
    if len(USER_STATE[chat_id]['parts']) < USER_STATE[chat_id]['current_part']:
        USER_STATE[chat_id]['parts'].append({'name': part_name})
    else:
        USER_STATE[chat_id]['parts'][USER_STATE[chat_id]['current_part']-1]['name'] = part_name
    
    # Просим пользователя ввести цену запчасти
    USER_STATE[chat_id]['state'] = 'entering_part_price'
    bot.send_message(chat_id, f"Введите цену для запчасти №{USER_STATE[chat_id]['current_part']}:")







def check_required_fields(chat_id):
    required_fields = ['client_name', 'car_brand', 'car_model', 'car_year', 'selected_time', 'work_description', 'work_cost', 'parts']
    
    user_data = USER_STATE.get(chat_id, {})
    missing_fields = [field for field in required_fields if field not in user_data]
    
    if missing_fields:
        error_message = f"Ошибка: отсутствуют следующие поля: {', '.join(missing_fields)}"
        bot.send_message(chat_id, error_message)
        return False
    return True

#------------------------------------------------------------------------------------------!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!_____________________________________________________________-


def send_final_confirmation(chat_id):
    user_data = USER_STATE.get(chat_id, {})
    
    # Проверка наличия всех необходимых полей
    required_fields = ['client_name', 'car_brand', 'car_model', 'car_year', 'selected_time', 'work_description', 'work_cost', 'parts']
    missing_fields = [field for field in required_fields if field not in user_data]
    
    if missing_fields:
        error_message = f"Ошибка: отсутствуют следующие поля: {', '.join(missing_fields)}"
        bot.send_message(chat_id, error_message)
        return

    parts_summary = ""
    total_parts_cost = 0

    for part in user_data['parts']:
        parts_summary += f"{part['name']}: {part['price']} USD\n"
        total_parts_cost += part['price']

    try:
        start_time_str = user_data['selected_time']
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        end_time = start_time + timedelta(hours=user_data['work_duration'])
    except Exception as e:
        print("[DEBUG] Error while processing time:", str(e))
        start_time_str = "00:00"  # Set a default start time
        end_time = start_time  # Set a default end time

    final_message = (
        f"Клиент: {user_data['client_name']}\n"
        f"Телефон: {user_data.get('client_phone', 'Неизвестно')}\n"
        f"E-Mail: {user_data.get('client_email', 'Неизвестно')}\n"
        f"Брэнд Авто: {user_data['car_brand']}\n"
        f"Модель Авто: {user_data['car_model']}\n"
        f"Год Авто: {user_data['car_year']}\n"
        f"VIN Код: {user_data.get('vin_code', 'Неизвестно')}\n"
        f"Дата: {start_time_str[:10]}\n"
        f"Время: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}\n"
        f"Описание: {user_data['work_description']}\n"
        f"Количество запчастей: {len(user_data['parts'])}\n"
        f"Стоимость работы без учета деталей: {user_data['work_cost']} USD\n"
        f"Стоимость запчастей: {total_parts_cost} USD\n"
        f"Детали:\n{parts_summary}"
    )

    # Create inline keyboard with "Edit", "Confirm", and "Cancel" buttons
    keyboard = types.InlineKeyboardMarkup()
    edit_btn = types.InlineKeyboardButton("Изменить", callback_data="edit_order")
    confirm_btn = types.InlineKeyboardButton("Подтвердить", callback_data="confirm_order")
    cancel_btn = types.InlineKeyboardButton("Отменить", callback_data="cancel_order")
    keyboard.add(edit_btn, confirm_btn, cancel_btn)

    bot.send_message(chat_id, final_message, reply_markup=keyboard)

  # Дополнительный код для сохранения данных в базе данных и очистки состояния может быть добавлен здесь. 3)

@bot.callback_query_handler(func=lambda call: call.data == "edit_order")
def handle_edit_order(call):
    chat_id = call.message.chat.id
    
    # Проверяем, существует ли chat_id в USER_STATE
    if chat_id not in USER_STATE or 'client_id' not in USER_STATE[chat_id]:
        bot.send_message(chat_id, "Ошибка: не удалось получить информацию о наряде. Пожалуйста, начните сначала.")
        return
    
    # Начинаем процесс "Назначить наряд на работу" с начала
    user_id = USER_STATE[chat_id]['client_id'] # Получаем ID клиента из состояния
    bot.send_message(call.message.chat.id, "Введите время данной работы в часах:")
    
    # Загрузим информацию о клиенте из базы данных
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE id={user_id}")
    user_data = cur.fetchone()
    conn.close()

    if user_data:
        USER_STATE[chat_id] = {
            'state': 'entering_work_time',
            'client_id': user_id,
            'client_name': user_data[1],
            'car_brand': user_data[6],
            'car_model': user_data[8],
            'car_year': user_data[9],
            'car_vin': user_data[10]
        }

def validate_user_data(user_data):
    """
    Validates the user data to ensure all required fields are present.
    
    Args:
    - user_data (dict): Dictionary containing the user data to validate.
    
    Raises:
    - ValueError: If any of the required fields are missing from user_data.
    """
    
    # List of required fields
    required_fields = [
        'client_id', 'work_description', 'selected_time', 'work_duration', 
        'client_name', 'car_model', 'vin_code', 'client_phone'
    ]
    
    # Check for missing fields
    missing_fields = [field for field in required_fields if field not in user_data]
    
    # If any fields are missing, raise a ValueError
    if missing_fields:
        raise ValueError(f"Missing required fields in user_data: {', '.join(missing_fields)}")


@bot.callback_query_handler(func=lambda call: call.data == "confirm_order")
def handle_confirm_order(call):
    chat_id = call.message.chat.id
    user_data = USER_STATE.get(chat_id, {})
    
    try:
        # Validate user data before saving to database
        validate_user_data(user_data)
        
        # Save the validated user data to the database
        save_to_database(user_data)
        
        # Send a confirmation message to the user
        bot.send_message(chat_id, "Ваш наряд на работу был успешно подтвержден и сохранен в базе данных.")
        
        # Clear the user's state
        if chat_id in USER_STATE:
            del USER_STATE[chat_id]
    
    except ValueError as e:
        # Send an error message to the user
        bot.send_message(chat_id, str(e))


def save_to_database(user_data):
    with sqlite3.connect('bot.db') as conn:
        cur = conn.cursor()
        
        # Extract required data for work order
        user_id = user_data['client_id']
        description = user_data['work_description']
        price_for_work = user_data.get('work_cost', 0)  # Extracting the work cost
        status = "Confirmed"
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculating the total cost
        total_parts_cost = sum([int(part['price']) for part in user_data.get('parts', [])])
        total_cost = price_for_work + total_parts_cost
        
        # Extracting additional fields
        parts_count = len(user_data.get('parts', []))
        work_time = user_data.get('work_duration', 0)
        start_date = user_data.get('selected_date', '0000-00-00')  # Placeholder default date
        end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(hours=work_time)).strftime('%Y-%m-%d')

        # Call add_work_order function with the new argument
        order_id = add_work_order(user_id, description, status, created_at, price_for_work, total_cost, parts_count, work_time, start_date, end_date)
        
        # Extract start time from user_data
        start_time = datetime.strptime(user_data['selected_time'], "%Y-%m-%d %H:%M")
        
        # Insert data for each hour of the work duration
        for hour_offset in range(work_time):  # Using work_time instead of direct extraction
            # Calculate time for the current termin
            current_time = start_time + timedelta(hours=hour_offset)
            
            # Set the value for notification_sent
            notification_sent = None if hour_offset == 0 else 1
            
            # Insert data into termins table
            cur.execute(f"""
                INSERT INTO termins (user_id, day, month, year, time, name, car_brand, vin, phone_number, note, canceled, notification_sent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                current_time.day,
                current_time.month,
                current_time.year,
                current_time.strftime('%H:%M'), 
                user_data['client_name'],
                user_data['car_model'],
                user_data['vin_code'],   
                user_data['client_phone'],
                description,  # Using extracted description
                0, 
                notification_sent
            ))

        # Call add_parts function with the complete list of parts, only if 'parts' exists in user_data
        if 'parts' in user_data:
            add_parts(conn, order_id, user_data['parts'])
            
        conn.commit()


@bot.callback_query_handler(func=lambda call: call.data == "cancel_order")
def handle_cancel_order(call):
    chat_id = call.message.chat.id
    
    # Очищаем состояние пользователя
    if chat_id in USER_STATE:
        del USER_STATE[chat_id]
    
    bot.send_message(chat_id, "Ваш заказ был отменен.")





#---------------------------------------------------------------------------------------------------------------!!!!!!!!!!!!!!!!!!__________________________________________________
@bot.message_handler(func=lambda message: USER_STATE.get(message.chat.id, {}).get('state') == 'entering_part_price')
def handle_part_price_input(message):
    chat_id = message.chat.id
    
    try:
        part_price = int(message.text)  # Преобразуем ввод в целое число
        USER_STATE[chat_id]['parts'][USER_STATE[chat_id]['current_part']-1]['price'] = part_price

        current_part = USER_STATE[chat_id]['current_part']
        if current_part < USER_STATE[chat_id]['parts_count']:
            # Переходим к следующей запчасти
            USER_STATE[chat_id]['current_part'] += 1
            USER_STATE[chat_id]['state'] = 'entering_part_name'
            bot.send_message(chat_id, f"Введите наименование запчасти №{USER_STATE[chat_id]['current_part']}:")
        else:
            # Все запчасти введены, переходим к следующему этапу
            send_final_confirmation(chat_id)
    except ValueError:
        bot.send_message(chat_id, f"Ошибка! Введите корректную цену для запчасти №{USER_STATE[chat_id]['current_part']}.")





#-------------------------------------------------------------------------------------------------------------------------------------------------------
def create_order_parts_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Да", callback_data="order-parts-yes"))
    keyboard.add(types.InlineKeyboardButton("Нет", callback_data="order-parts-no"))
    return keyboard

def create_termin_inline_keyboard(termin_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Удалить термин", callback_data=f"delete-termin-{termin_id}"))
    return keyboard

def send_termin_info(message, termin):
    date_str = f"{termin[3]:02d}.{termin[4]:02d}.{termin[5]:04d}"
    response = f"Дата: {date_str}\nПримечание: {termin[2]}\nВремя: {termin[6]}\nИмя: {termin[7]}\nМарка автомобиля: {termin[8]}\nVIN: {termin[9]}\nНомер телефона: {termin[10]}\n"
    bot.send_message(message.chat.id, response, reply_markup=create_termin_inline_keyboard(termin[0]))

def create_client_info_keyboard(client_id, delete_confirmation=False):
    keyboard = types.InlineKeyboardMarkup()
    if delete_confirmation:
        keyboard.add(types.InlineKeyboardButton("Да", callback_data=f"confirm-delete-user-{client_id}"))
        keyboard.add(types.InlineKeyboardButton("Нет", callback_data=f"cancel-delete-user-{client_id}"))
    else:
        keyboard.add(types.InlineKeyboardButton("Удалить клиента", callback_data=f"delete-user-{client_id}")) # Фикс строки
        keyboard.add(types.InlineKeyboardButton("Редактировать клиента", callback_data=f"edit-user-{client_id}"))
        keyboard.add(types.InlineKeyboardButton("Назначить наряд на работу", callback_data=f"assign-work-{client_id}"))
    return keyboard


#ОКОНЧАНИЕ 1ОЙ ЧАСТИ КОДА!!!-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def format_client_info(client):
    print(f"[LOG - format_client_info] Client info: {client}")  # Добавим логирование
    response = f"\nИмя: {client[1]}"
    response += f"\nТелефон: {client[2]}"
    response += f"\nE-Mail: {client[3]}"
    response += f"\nСтрана производства авто: {client[5]}"
    response += f"\nБрэнд Авто: {client[6]}"
    response += f"\nКласс Авто: {client[7]}"
    response += f"\nМодель Авто: {client[8]}"
    response += f"\nГод Авто: {client[9]}"
    response += f"\nVIN Код: {client[10]}"
    return response

def search_clients(chat_id, criterion, value):
    field_mapping = {
        "имя": "name",
        "номер телефона": "phone_number",
        "email": "email", 
        "бренд авто": "car_brand",
        "модель авто": "car_model",
    }

    field_name = field_mapping.get(criterion.lower())
    if not field_name:
        bot.send_message(chat_id, "Неизвестный критерий поиска.")
        return

    connection = sqlite3.connect('bot.db')
    cursor = connection.cursor()
    query = f"SELECT * FROM users WHERE {field_name} LIKE ?"
    cursor.execute(query, (f"%{value}%",))
    clients = cursor.fetchall()
    connection.close()

    if clients:
        for client in clients:
            response = f"Результат поиска по {criterion}:"
            response += format_client_info(client)
            bot.send_message(chat_id, response, reply_markup=create_client_info_keyboard(client[0]))
            # Обновление состояния пользователя, вместо перезаписывания
            USER_STATE[chat_id].update({
                'client_name': client[1],
                'client_phone': client[2],
                'client_email': client[3],
                'car_country': client[5],
                'car_brand': client[6],
                'car_class': client[7],
                'car_model': client[8],
                'car_year': client[9],
                'vin_code': client[10]
            })
            print(f"[LOG - search_clients] Updated USER_STATE for chat_id {chat_id}: {USER_STATE[chat_id]}")

    else:
        bot.send_message(chat_id, f"Клиенты по критерию {criterion} '{value}' не найдены.")





def create_edit_client_keyboard(client_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Изменить Имя", callback_data=f"edit-user-name-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("Изменить Телефон", callback_data=f"edit-user-phone-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("Изменить Е-mail", callback_data=f"edit-user-email-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("Изменить Брэнд Авто", callback_data=f"edit-user-carbrand-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("Изменить Модель Авто", callback_data=f"edit-user-carmodel-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("Изменить Год Авто", callback_data=f"edit-user-caryear-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("Изменить VIN Код", callback_data=f"edit-user-vin-{client_id}"))
    return keyboard

def create_search_criteria_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Поиск по Имени", callback_data="search-by-name"))
    keyboard.add(types.InlineKeyboardButton("Поиск по Номеру телефона", callback_data="search-by-phone"))
    keyboard.add(types.InlineKeyboardButton("Поиск по E-mail", callback_data="search-by-email"))
    keyboard.add(types.InlineKeyboardButton("Поиск по Бренду авто", callback_data="search-by-carbrand"))
    keyboard.add(types.InlineKeyboardButton("Поиск по Модели авто", callback_data="search-by-carmodel"))
    return keyboard



@bot.message_handler(content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    user_input = message.text
    chat_state = USER_STATE.get(chat_id, {})

    if user_input == "Отчёты":
        reports_keyboard = create_reports_inline_keyboard()
        bot.send_message(chat_id, "Какой отчёт Вы хотите?", reply_markup=reports_keyboard)
        return

    if user_input == "Бухгалтерия":
        bot.send_message(chat_id, "Здесь будет информация о бухгалтерии или другие действия.")
        return

    if chat_state and chat_state.get('state') == "SEARCHING_CRITERION":
        criterion = message.text
        USER_STATE[chat_id].update({"state": f"SEARCHING_VALUE-{criterion}"})
        bot.send_message(chat_id, f"Введите значение для поиска по {criterion}.")

    elif chat_state and chat_state.get('state') and chat_state['state'].startswith("SEARCHING_VALUE"):
        criterion = chat_state['state'].split('-')[1]
        value = message.text
        search_clients(chat_id, criterion, value)
        del USER_STATE[chat_id]

    elif user_input == "Поиск клиента":
        search_criteria_keyboard = create_search_criteria_keyboard()
        bot.send_message(chat_id, "Выберите критерий для поиска:", reply_markup=search_criteria_keyboard)

    elif chat_state and chat_state.get('state').startswith("EDITING"):
        parts = chat_state['state'].split('-')
        field_to_edit = parts[1]
        user_id = int(parts[2])
        connection = sqlite3.connect('bot.db')
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
        client = cursor.fetchone()

        if client and message.text != '/skip':
            response = ""
            if field_to_edit == "NAME":
                new_name = message.text
                cursor.execute("UPDATE users SET name=? WHERE id=?", (new_name, user_id))
                response = "Имя успешно обновлено."
            elif field_to_edit == "PHONE":
                new_phone = message.text
                cursor.execute("UPDATE users SET phone_number=? WHERE id=?", (new_phone, user_id))
                response = "Номер телефона успешно обновлен."
            elif field_to_edit == "EMAIL":
                new_email = message.text
                cursor.execute("UPDATE users SET email=? WHERE id=?", (new_email, user_id))
                response = "E-mail успешно обновлен."
            elif field_to_edit == "CARBRAND":
                new_car_brand = message.text
                cursor.execute("UPDATE users SET car_brand=? WHERE id=?", (new_car_brand, user_id))
                response = "Брэнд автомобиля успешно обновлен."
            elif field_to_edit == "CARMODEL":
                new_car_model = message.text
                cursor.execute("UPDATE users SET car_model=? WHERE id=?", (new_car_model, user_id))
                response = "Модель автомобиля успешно обновлена."
            elif field_to_edit == "CARYEAR":
                new_car_year = message.text
                cursor.execute("UPDATE users SET car_year=? WHERE id=?", (new_car_year, user_id))
                response = "Год автомобиля успешно обновлен."
            elif field_to_edit == "VIN":
                new_vin = message.text
                cursor.execute("UPDATE users SET car_vin=? WHERE id=?", (new_vin, user_id))
                response = "VIN-код успешно обновлен."
            
            bot.send_message(chat_id, response)

            connection.commit()
            connection.close()
            del USER_STATE[message.chat.id]
        else:
            connection.close()
            bot.send_message(message.chat.id, "Операция отменена.")
            del USER_STATE[message.chat.id]

    elif user_input == "Календарь терминов":
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        USER_STATE[chat_id]['state'] = 'view_termins'  # Устанавливаем состояние view_termins
        calendar_markup = create_termins_calendar()
        bot.send_message(chat_id, "Выберите дату", reply_markup=calendar_markup)

    elif chat_state and chat_state.get('state') == "ADDING_WORK_DESCRIPTION":
        description = message.text
        USER_STATE[chat_id].update({'description': description})
        parts_keyboard = create_order_parts_keyboard()
        bot.send_message(chat_id, "Будите ли Вы заказывать запчасти для данной работы?", reply_markup=parts_keyboard)

    elif chat_state and chat_state.get('state') == "ADDING_PARTS_COUNT":
        try:
            parts_count = int(message.text)
            USER_STATE[chat_id].update({
                'parts_count': parts_count,
                'current_part': 1,
                'state': "assign_work"  # Установка состояния после ввода продолжительности работы
            })
            calendar_markup = create_calendar()
            bot.send_message(chat_id, "Выберите дату начала работы:", reply_markup=calendar_markup)
        except ValueError:
            bot.send_message(chat_id, "Пожалуйста, введите корректное количество.")

    elif chat_state and chat_state.get('state').startswith("AWAITING_VALUE_FOR_REPORT"):
        search_client_for_report(message)
        return



@bot.message_handler(func=lambda message: message.text == "Добавить наряд на работу")
def start_add_work_order(message):
    user_id = message.from_user.id
    USER_STATE[user_id] = {'state': 'FINDING_CLIENT'}
    bot.send_message(user_id, "Пожалуйста, введите идентификационный номер или имя клиента:")

@bot.message_handler(func=lambda message: USER_STATE.get(message.from_user.id) == 'FINDING_CLIENT')
def find_client(message):
    user_id = message.from_user.id
    client_info = message.text
    # TODO: Find the client in the database using client_info
    # If found, proceed to the next step
    USER_STATE[user_id] = {'state': 'ADDING_DESCRIPTION', 'client_id': client_id}
    bot.send_message(user_id, "Клиент найден. Пожалуйста, введите описание работы:")

@bot.message_handler(content_types=['text'])
def handle_work_order_input(message):
    chat_id = message.chat.id
    user_input = message.text
    chat_state = USER_STATE.get(chat_id, {}).get('state')

    if chat_state == "ADDING_WORK_ORDER_DESCRIPTION":
        USER_STATE[chat_id].update({'description': user_input, 'state': "ADDING_WORK_ORDER_TOTAL_COST"})
        bot.send_message(chat_id, "Введите общую стоимость работы:")

    elif chat_state == "ADDING_WORK_ORDER_TOTAL_COST":
        try:
            total_cost = int(user_input)
            USER_STATE[chat_id].update({'total_cost': total_cost, 'state': "ADDING_WORK_ORDER_PARTS_COUNT"})
            bot.send_message(chat_id, "Введите количество запчастей:")
        except ValueError:
            bot.send_message(chat_id, "Пожалуйста, введите корректную стоимость.")

    elif chat_state == "ADDING_WORK_ORDER_PARTS_COUNT":
        try:
            parts_count = int(user_input)
            USER_STATE[chat_id].update({'parts_count': parts_count, 'state': "ADDING_WORK_ORDER_WORK_TIME"})
            bot.send_message(chat_id, "Введите общее время работы (в часах):")
        except ValueError:
            bot.send_message(chat_id, "Пожалуйста, введите корректное количество.")

    elif chat_state == "ADDING_WORK_ORDER_WORK_TIME":
        try:
            work_time = int(user_input)
            USER_STATE[chat_id].update({'work_time': work_time, 'state': "ADDING_WORK_ORDER_START_DATE"})
            bot.send_message(chat_id, "Введите дату начала работы (в формате ГГГГ-ММ-ДД):")
        except ValueError:
            bot.send_message(chat_id, "Пожалуйста, введите корректное количество времени.")

    elif chat_state == "ADDING_WORK_ORDER_START_DATE":
        USER_STATE[chat_id].update({'start_date': user_input, 'state': "ADDING_WORK_ORDER_END_DATE"})
        bot.send_message(chat_id, "Введите дату окончания работы (в формате ГГГГ-ММ-ДД):")

    elif chat_state == "ADDING_WORK_ORDER_END_DATE":
        end_date = user_input
        user_data = USER_STATE[chat_id]
        user_id = chat_id  # Вы можете использовать другой способ определения user_id

        # Добавление наряда на работу в базу данных
        order_id = add_work_order(
            user_id,
            user_data['description'],
            user_data['total_cost'],
            user_data['parts_count'],
            user_data['work_time'],
            user_data['start_date'],
            end_date,
        )

        del USER_STATE[chat_id]
        bot.send_message(chat_id, f"Наряд на работу с ID {order_id} успешно добавлен.")

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id

    # Логирование полученных callback-данных
    print(f"[LOG] Received callback with data: {call.data}")

    if call.data.startswith('search-by-'):
        criteria_mapping = {
            "search-by-name": "имя",
            "search-by-phone": "номер телефона",
            "search-by-email": "email",
            "search-by-carbrand": "бренд авто",
            "search-by-carmodel": "модель авто",
        }
        criterion = criteria_mapping.get(call.data)
        if criterion:
            USER_STATE.update({chat_id: {"state": f"SEARCHING_VALUE-{criterion}"}})
            bot.send_message(chat_id, f"Введите значение для поиска по {criterion}.")
            print(f"[LOG - callback_inline (search-by-)] Updated USER_STATE for chat_id {chat_id}: {USER_STATE[chat_id]}")
        else:
            print(f"[LOG - callback_inline (search-by-)] No criterion matched for {call.data}")

    elif call.data.startswith('edit-user-'):
        parts = call.data.split('-')
        if len(parts) == 3:
            user_id = int(parts[2])
            edit_keyboard = create_edit_client_keyboard(user_id)
            bot.send_message(chat_id, "Выберите поле для редактирования:", reply_markup=edit_keyboard)
            print(f"[LOG] Prompting user to select a field to edit for user_id: {user_id}")
        else:
            field_to_edit, user_id = parts[2], parts[3]
            USER_STATE.update({chat_id: {"state": f"EDITING-{field_to_edit.upper()}-{user_id}"}})
            field_name_map = {
                "name": "Имя",
                "phone": "Телефон",
                "email": "Е-mail",
                "carbrand": "Брэнд Авто",
                "carmodel": "Модель Авто",
                "caryear": "Год Авто",
                "vin": "VIN Код"
            }
            field_prompt = field_name_map.get(field_to_edit, "Поле")
            response = f"Введите новое значение для {field_prompt} или отправьте /skip, если не хотите его менять."
            bot.send_message(chat_id, response)
            print(f"[LOG - callback_inline (edit-user-)] Updated USER_STATE for chat_id {chat_id}: {USER_STATE[chat_id]}")

    elif call.data.startswith('assign-work-'):
        user_id = int(call.data.split('-')[2])
        bot.send_message(call.message.chat.id, "Введите время данной работы в часах:")

        # Загрузим информацию о клиенте из базы данных
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM users WHERE id={user_id}")
        user_data = cur.fetchone()
        conn.close()

        if user_data:
            USER_STATE[chat_id] = {
                'state': 'entering_work_time',
                'client_id': user_id,
                'client_name': user_data[1],
                'client_phone': user_data[2],
                'client_email': user_data[3],
                'car_brand': user_data[6],
                'car_model': user_data[8],
                'car_year': user_data[9],
                'vin_code': user_data[10]
            }
            print(f"[LOG - callback_inline (assign-work-)] Updated USER_STATE for chat_id {chat_id}: {USER_STATE[chat_id]}")


    elif call.data == "order-parts-yes":
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        USER_STATE[chat_id].update({'order_parts': True, 'state': 'ADDING_PARTS_COUNT'})
        bot.send_message(chat_id, "В каком количестве деталей Вы закажете?")
        print(f"[LOG - callback_inline (order-parts-yes)] Updated USER_STATE for chat_id {chat_id}: {USER_STATE[chat_id]}")

    elif call.data == "order-parts-no":
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
        USER_STATE[chat_id].update({'order_parts': False})
        print(f"[LOG - callback_inline (order-parts-no)] Updated USER_STATE for chat_id {chat_id}: {USER_STATE[chat_id]}")

    elif call.data.startswith('calendar-month-'):
        month, year = map(int, call.data.split('-')[2:])
    
        # Проверка на наличие ключа в USER_STATE и инициализация при необходимости
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = {}
            print(f"[LOG - callback_inline (calendar-month-)] Initialized USER_STATE for chat_id {chat_id}: {USER_STATE[chat_id]}")
    
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM termins WHERE month={month} AND year={year} ORDER BY day")
        termins = cur.fetchall()
        conn.close()

        if not termins:
            bot.send_message(chat_id, "В этом месяце термины отсутствуют.")
        else:
            for termin in termins:
                send_termin_info(call.message, termin)
            
        print(f"[LOG - callback_inline (calendar-month-)] USER_STATE for chat_id {chat_id}: {USER_STATE[chat_id]}")

    # Handling previous-month for work calendar
    elif call.data.startswith('previous-month-work'):
        year, month = map(int, call.data.split('-')[-2:])
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        calendar_markup = create_work_assignment_calendar(year, month)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=calendar_markup)
    
    # Handling next-month for work calendar
    elif call.data.startswith('next-month-work'):
        year, month = map(int, call.data.split('-')[-2:])
        month += 1
        if month == 13:
            month = 1
            year += 1
        calendar_markup = create_work_assignment_calendar(year, month)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=calendar_markup)

    elif call.data.startswith('previous-month'):
        year, month = map(int, call.data.split('-')[2:])
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        calendar_markup = create_termins_calendar(year, month)
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=calendar_markup)

    elif call.data.startswith('next-month'):
        year, month = map(int, call.data.split('-')[2:])
        month += 1
        if month == 13:
            month = 1
            year += 1
        calendar_markup = create_termins_calendar(year, month)
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=calendar_markup)

    elif 'next-year-month' in call.data:
        year, month = map(int, call.data.split('-')[2:])
        month = 1
        year += 1
        calendar_markup = create_calendar(year, month)
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=calendar_markup)

    elif call.data.startswith('delete-user-'):
        user_id = int(call.data.split('-')[2])
        confirmation_keyboard = create_client_info_keyboard(user_id, delete_confirmation=True)
        bot.send_message(chat_id, f"Вы точно хотите удалить данного клиента с ID {user_id}?", reply_markup=confirmation_keyboard)
        print(f"[LOG] Prompting user for deletion confirmation for user_id: {user_id}")

    elif call.data.startswith('confirm-delete-user-'):
        try:
            user_id = int(call.data.split('-')[3])
            conn = sqlite3.connect('bot.db')
            cur = conn.cursor()
            cur.execute(f"DELETE FROM users WHERE id=?", (user_id,))
            cur.execute(f"DELETE FROM termins WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
            bot.send_message(chat_id, "Клиент успешно удален.")
            print(f"[LOG] Successfully deleted user with user_id: {user_id}")
        except ValueError:
            bot.send_message(chat_id, "Произошла ошибка при удалении клиента. Пожалуйста, попробуйте снова.")
            print(f"[LOG] Error occurred while deleting user with user_id: {user_id}")

    elif call.data.startswith('cancel-delete-user-'):
        bot.send_message(chat_id, "Отмена удаления клиента.")
        print(f"[LOG] User cancelled client deletion.")

    elif call.data.startswith('delete-termin-'):
        termin_id = int(call.data.split('-')[2])
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM termins WHERE id={termin_id}")
        termin = cur.fetchone()
        if termin:
            date_time_str = f"{termin[3]:02d}.{termin[4]:02d}.{termin[5]:04d} {termin[6]}"
            cur.execute(f"DELETE FROM termins WHERE id={termin_id}")
            conn.commit()
            bot.send_message(chat_id, f"Термин на {date_time_str} успешно удален.")
            print(f"[LOG] Successfully deleted termin with termin_id: {termin_id}")
        else:
            bot.send_message(chat_id, "Термин не найден.")
            print(f"[LOG] Termin with termin_id: {termin_id} not found.")

#Отчеты 

    elif call.data == "clients_report":
        keyboard = create_clients_report_keyboard()
        bot.send_message(chat_id, "Выберите тип отчета по клиентам:", reply_markup=keyboard)

    elif call.data == "monthly_clients_report":
        # Подключение к базе данных
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()

        # Получение общего числа зарегистрированных клиентов
        total_clients = cur.execute("SELECT COUNT(*) FROM users;").fetchone()[0]

        # Получение списка марок автомобилей и их количества
        car_brands_count = cur.execute("SELECT car_brand, COUNT(*) FROM users GROUP BY car_brand;").fetchall()

        # Закрытие соединения
        conn.close()

        # Формирование и отправка ответа
        response = f"Общее количество зарегистрированных клиентов: {total_clients}\n\n"
        response += "Марки автомобилей:\n"
        for brand, count in car_brands_count:
            response += f"{brand} = {count}\n"
        
        bot.send_message(chat_id, response)

    elif call.data.startswith('report-'):
        parts = call.data.split('-')
        period = parts[1]
        client_id = int(parts[2])
    
        # Инициализация соединения и курсора
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM users WHERE id=?", (client_id,))
        client_name = cursor.fetchone()[0]
        report = get_report_for_client(client_name, period)
        bot.send_message(chat_id, report)

        # Закрытие соединения с базой данных
        conn.close()


    elif call.data == "work_report_clients":
        bot.send_message(chat_id, "Выберите критерий поиска клиента:", reply_markup=create_search_criterion_keyboard())

    elif call.data.startswith('search_criterion-'):
        criterion = call.data.split('-')[1]
        USER_STATE[chat_id] = {"state": f"AWAITING_VALUE_FOR_REPORT-{criterion}"}
        bot.send_message(chat_id, f"Введите {criterion} клиента:")




def create_reports_inline_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Клиенты", callback_data="clients_report"))
    return keyboard

# Second function: Clients report keyboard with "Monthly clients count" button
def create_clients_report_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Отчет  Клиентов (количество)", callback_data="monthly_clients_report"))
    keyboard.add(types.InlineKeyboardButton("Отчет о проделанных работах (на каждого клиента)", callback_data="work_report_clients"))
    return keyboard


#Отчеты на каждого клиента

def search_client_for_report(message):
    chat_id = message.chat.id
    value = message.text.strip()

    # Получаем текущий критерий из состояния пользователя
    chat_state = USER_STATE.get(chat_id, {})
    if not chat_state or not chat_state.get('state').startswith("AWAITING_VALUE_FOR_REPORT"):
        bot.send_message(chat_id, "Произошла ошибка. Попробуйте начать поиск снова.")
        return

    criterion = chat_state['state'].split('-')[1]

    field_mapping = {
        "имя": "name",
        "номер телефона": "phone_number",
        "email": "email", 
        "бренд авто": "car_brand",
        "модель авто": "car_model",
    }

    field_name = field_mapping.get(criterion)
    if not field_name:
        bot.send_message(chat_id, "Неизвестный критерий поиска.")
        return

    connection = sqlite3.connect('bot.db')
    cursor = connection.cursor()
    query = f"SELECT * FROM users WHERE {field_name} LIKE ?"
    cursor.execute(query, (f"%{value}%",))
    clients = cursor.fetchall()
    connection.close()

    if clients:
        for client in clients:
            response = f"Результат поиска по {criterion}:"
            response += format_client_info(client)
            bot.send_message(chat_id, response, reply_markup=create_period_selection_keyboard(client[0]))
    else:
        bot.send_message(chat_id, f"Клиенты по критерию {criterion} '{value}' не найдены.")



def create_period_selection_keyboard(client_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("За неделю", callback_data=f"report-week-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("За месяц", callback_data=f"report-month-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("За 6 месяцев", callback_data=f"report-six_months-{client_id}"))
    keyboard.add(types.InlineKeyboardButton("За год", callback_data=f"report-year-{client_id}"))
    return keyboard

def create_search_criterion_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    criteria = ["имя", "номер телефона", "email", "бренд авто", "модель авто"]
    for criterion in criteria:
        keyboard.add(types.InlineKeyboardButton(criterion, callback_data=f"search_criterion-{criterion}"))
    return keyboard

def create_report_period_keyboard(client_id):
    keyboard = types.InlineKeyboardMarkup()
    periods = ["неделю", "месяц", "6 месяцев", "год"]
    for period in periods:
        callback_data = f"report_for-{period}-{client_id}"
        keyboard.add(types.InlineKeyboardButton(f"Отчет за {period}", callback_data=callback_data))
    return keyboard

def get_report_for_client(client_name, period):
    # Initializing the connection and cursor
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()

    # Find the client's ID based on the provided name
    cursor.execute("SELECT id FROM users WHERE name=?", (client_name,))
    client_id = cursor.fetchone()
    if not client_id:
        conn.close()  # Closing the connection before exiting
        return [f"Client with name {client_name} not found."]
    client_id = client_id[0]
    
    # Define the date range based on the period
    end_date = datetime.now()
    if period == "week":
        start_date = end_date - timedelta(days=7)
    elif period == "month":
        start_date = end_date - timedelta(days=30)
    elif period == "six_months":
        start_date = max(end_date - timedelta(days=180), datetime(end_date.year, 1, 1))
    elif period == "year":
        start_date = datetime(end_date.year, 1, 1)
    else:
        return [f"Unknown period: {period}"]
    
    # Fetch the completed tasks (fertig) for the client within the date range
    cursor.execute("""
        SELECT note, day, month, year, time 
        FROM fertig 
        WHERE user_id=? AND 
              year BETWEEN ? AND ? AND
              (year = ? AND month * 100 + day >= ? OR year = ? AND month * 100 + day <= ?)
    """, (client_id, start_date.year, end_date.year, start_date.year, start_date.month * 100 + start_date.day, end_date.year, end_date.month * 100 + end_date.day))
    tasks = cursor.fetchall()
    
    # Fetch the work orders related to the fetched tasks
    work_orders = {}
    for task in tasks:
        cursor.execute("SELECT order_id, description, price_for_work FROM work_orders WHERE user_id=? AND description=?", (client_id, task[0]))
        work_order = cursor.fetchone()
        if work_order:
            work_orders[work_order[0]] = work_order[1:]
    
    # Fetch the parts related to the work orders
    parts_info = {}
    for order_id, (description, price_for_work) in work_orders.items():
        cursor.execute("SELECT part_name, quantity, cost_per_unit, labor_cost FROM parts WHERE order_id=?", (order_id,))
        parts = cursor.fetchall()
        parts_info[description] = (price_for_work, parts)
    
    # Compile the report
    reports = []  # Here we will store each report as a separate item in the list
    
    for task in tasks:
        single_report = f"Имя: {client_name}\n"
        single_report += "-" * 56 + "\n"
        
        note, day, month, year, time = task
        price_for_work, parts = parts_info.get(note, (0, []))
        price_for_work = price_for_work or 0  # Handling the None case
        single_report += f"Проделанная работа {day}.{month}.{year}: {note}\n"
        single_report += f"Стоимость данной работы: {price_for_work}\n"
        single_total_cost = price_for_work

        if parts:
            single_report += "Запчасти к данной работе:\n"
            total_parts_cost = 0
            for idx, (part_name, quantity, cost_per_unit, labor_cost) in enumerate(parts, 1):
                single_report += f"Наименование запчасти №{idx} : {part_name}\n"
                single_report += f"Стоимость запчасти №{idx} : {cost_per_unit * quantity}\n"
                total_parts_cost += cost_per_unit * quantity
            single_total_cost += total_parts_cost
            single_report += f"Общая стоимость запчастей: {total_parts_cost}\n"
            single_report += "-" * 56 + "\n"

        single_report += f"Итого: {single_total_cost}\n"
        reports.append(single_report)
    
    conn.close()  # Closing the connection at the end of the function
    return reports



if __name__ == "__main__":
    initialize_database()
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=50)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(15)
