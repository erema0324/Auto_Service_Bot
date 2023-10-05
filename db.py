from sqlalchemy import Column, Integer, String, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import hashlib
import os

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    phone_number = Column(String)
    email = Column(String)
    password = Column(String)
    car_country = Column(String)  # new field
    car_brand = Column(String)  # new field
    car_class = Column(String)  # new field
    car_model = Column(String)
    car_year = Column(String)
    car_vin = Column(String)
    state = Column(String)

class Termin(Base):
    __tablename__ = 'termins'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    note = Column(String)
    day = Column(Integer)
    month = Column(Integer)
    year = Column(Integer)
    time = Column(String)
    name = Column(String)
    car_brand = Column(String)
    vin = Column(String)
    phone_number = Column(String)
    # Добавим поле для отмены события
    canceled = Column(Boolean, default=False)
    notification_sent = Column(Boolean, default=False)

class Fertig(Base):
    __tablename__ = 'fertig'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    note = Column(String)
    day = Column(Integer)
    month = Column(Integer)
    year = Column(Integer)
    time = Column(String)
    name = Column(String)
    car_brand = Column(String)
    vin = Column(String)
    phone_number = Column(String)


def get_db_session():
    if not os.path.exists('bot.db'):
        print("База данных не найдена, создание новой базы данных.")
    engine = create_engine('sqlite:///bot.db')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def hash_password(password: str) -> str:
    salt = "somesalt"  # Здесь вы можете использовать любую случайную строку в качестве соли
    hashed_password = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed_password

def check_password(password_hash: str, password: str) -> bool:
    salt = "somesalt"  # Здесь должна быть та же самая соль, которую вы использовали при хешировании пароля
    hashed_password = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed_password == password_hash

def find_user(chat_id):
    # Создание сессии для взаимодействия с базой данных
    session = get_db_session()
    
    # Поиск пользователя в базе данных по его chat_id
    user = session.query(User).filter_by(id=chat_id).first()
    
    # Логирование результата
    if user:
        print(f"Found user with id: {chat_id}")
    else:
        print(f"User with id {chat_id} not found")
    
    # Закрытие сессии после завершения взаимодействия с базой данных
    session.close()
    
    # Возвращение найденного объекта пользователя или None, если пользователь не найден
    return user


def add_user(chat_id, name, phone_number, email, password, car_country, car_brand, car_model, car_year, car_vin, bot):
    # Создание сессии для взаимодействия с базой данных
    session = get_db_session()
    
    # Поиск пользователя в базе данных по его chat_id
    existing_user = session.query(User).filter_by(id=chat_id).first()
    
    # Проверка, существует ли пользователь с указанным chat_id
    if existing_user:
        # Если пользователь с таким ID уже существует, отправить сообщение об ошибке
        error_message = "Данный пользователь по Вашему ID уже зарегистрирован. Если вы хотите произвести заново регистрацию, обратитесь к Администратору. Либо выполните Вход"
        bot.send_message(chat_id, error_message)
        session.close()
        return False
    
    # Хеширование пароля пользователя для безопасного хранения
    hashed_password = hash_password(password)
    
    # Создание нового объекта пользователя с указанными данными
    new_user = User(id=chat_id, 
                    name=name, 
                    phone_number=phone_number, 
                    email=email, 
                    password=hashed_password, 
                    car_country=car_country, 
                    car_brand=car_brand, 
                    car_model=car_model, 
                    car_year=car_year, 
                    car_vin=car_vin)
    
    # Добавление нового пользователя в базу данных
    session.add(new_user)
    session.commit()
    
    # Закрытие сессии после завершения взаимодействия с базой данных
    session.close()
    
    # Возвращение True, указывая на успешное добавление пользователя
    return True 





def add_termin(user_id, note, day, month, year, time, name, car_brand, vin, phone_number):
    session = get_db_session()
    termin = Termin(user_id=user_id, note=note, day=day, month=month, year=year, time=time, name=name, car_brand=car_brand, vin=vin, phone_number=phone_number)
    session.add(termin)
    session.commit()
    session.close()

def check_appointment_availability(year, month, day, time):
    session = get_db_session()
    appointment = session.query(Termin).filter(
        Termin.year == year,
        Termin.month == month,
        Termin.day == day,
        Termin.time == time
    ).first()

    session.close()

    if appointment:
        return False
    return True

def has_appointment(user_id):
    session = get_db_session()
    appointment = session.query(Termin).filter_by(user_id=user_id).first()
    session.close()
    return appointment is not None

def get_user_state(user_id):
    session = db.get_db_session()
    user = session.query(db.User).filter(db.User.id == user_id).first()
    if user:
        return user.state
    else:
        return None

def set_user_state(user_id, state):
    session = db.get_db_session()
    user = session.query(db.User).filter(db.User.id == user_id).first()
    if user:
        user.state = state
        session.commit()

def get_all_users():
    session = get_db_session()
    users = session.query(User).all()
    session.close()
    return [user.id for user in users]

