import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from aiogram import Bot, types, Dispatcher
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

app = Flask(__name__)
bot = Bot(token="7898468859:AAED-74SLqvJLWQl_7RazW0jdDdCu7_6tLo")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Конфигурация
DOMAIN = "vipvdom.ru"
ADMIN_ID = 850188889  # Замените на ваш Telegram ID
CONTACTS = """Агентство 'Максимум'
📞 Тел: +79676633355, +79676633377
🌐 Сайт: https://maximum-an.ru"""

# Инициализация БД
conn = sqlite3.connect('ads.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS ads
             (id INTEGER PRIMARY KEY,
             transaction_type TEXT,
             property_type TEXT,
             price INTEGER,
             rooms INTEGER,
             area REAL,
             address TEXT,
             description TEXT,
             status TEXT DEFAULT 'draft',
             created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS photos
             (id INTEGER PRIMARY KEY,
             ad_id INTEGER,
             file_path TEXT,
             FOREIGN KEY(ad_id) REFERENCES ads(id))''')

c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY,
             telegram_id INTEGER UNIQUE,
             role TEXT CHECK(role IN ('admin', 'agent', 'user')),
             registered_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

# States
class CreateAd(StatesGroup):
    TRANSACTION_TYPE = State()
    PROPERTY_TYPE = State()
    PRICE = State()
    ROOMS = State()
    AREA = State()
    ADDRESS = State()
    DESCRIPTION = State()
    PHOTOS = State()

class AuthStates(StatesGroup):
    WAITING_PASSWORD = State()

# ================= Telegram Handlers =================
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    
    c.execute("SELECT role FROM users WHERE telegram_id=?", (user_id,))
    user = c.fetchone()
    
    if user:
        if user[0] == 'admin':
            await admin_panel(message)
        else:
            await show_user_menu(message)
    else:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔑 Войти как сотрудник", callback_data="agent_login"))
        await message.answer(
            "Добро пожаловать в агентство 'Максимум'!\n\n"
            "Выберите действие:",
            reply_markup=keyboard
        )

@dp.callback_query_handler(lambda c: c.data == 'agent_login')
async def request_password(callback_query: types.CallbackQuery):
    await AuthStates.WAITING_PASSWORD.set()
    await bot.send_message(
        callback_query.from_user.id,
        "Введите пароль сотрудника:",
        reply_markup=types.ForceReply(selective=True)
    )

@dp.message_handler(state=AuthStates.WAITING_PASSWORD)
async def check_password(message: types.Message, state: FSMContext):
    if message.text == "Max2024!":
        try:
            c.execute("INSERT INTO users (telegram_id, role) VALUES (?, 'agent')", 
                     (message.from_user.id,))
            conn.commit()
            await message.answer("✅ Вы успешно авторизованы как сотрудник!")
            await show_agent_menu(message)
        except sqlite3.IntegrityError:
            await message.answer("⚠️ Вы уже зарегистрированы!")
    else:
        await message.answer("❌ Неверный пароль! Попробуйте еще раз.")
    
    await state.finish()

async def show_agent_menu(message: types.Message):
    await message.answer(
        "Меню сотрудника:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("➕ Новое объявление", callback_data="create_ad"),
            InlineKeyboardButton("📊 Мои объявления", callback_data="my_ads")
        )
    )

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    c.execute("SELECT role FROM users WHERE telegram_id=?", (message.from_user.id,))
    user = c.fetchone()
    
    if user and user[0] == 'admin':
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("➕ Новое объявление", callback_data="create_ad"))
        await message.answer("🏠 Админ-панель:", reply_markup=keyboard)
    else:
        await message.answer("⛔ У вас нет доступа к этой команде!")

# ... (остальные обработчики создания объявлений из предыдущего ответа)

# ================= Web Routes =================
@app.route('/')
def index():
    return render_template_string(INDEX_HTML.replace("{{CONTACTS}}", CONTACTS))

@app.route('/ad/<int:ad_id>')
def view_ad(ad_id):
    c.execute("SELECT * FROM ads WHERE id=?", (ad_id,))
    ad = c.fetchone()
    
    c.execute("SELECT file_path FROM photos WHERE ad_id=?", (ad_id,))
    photos = [row[0] for row in c.fetchall()]
    
    return render_template_string(AD_HTML, 
                               ad=ad,
                               photos=photos,
                               CONTACTS=CONTACTS,
                               transaction_type='Продажа' if ad[1] == 'sell' else 'Аренда',
                               property_type='Квартира' if ad[2] == 'flat' else 'Дом' if ad[2] == 'house' else 'Коммерческая',
                               price=f"{ad[3]:,}".replace(",", " "))

# ... (остальные HTML-шаблоны из предыдущего ответа)

if __name__ == '__main__':
    os.makedirs('static/photos', exist_ok=True)
    executor.start_webhook(
        dispatcher=dp,
        webhook_path='/webhook',
        on_startup=lambda _: bot.set_webhook(f"https://{DOMAIN}/webhook"),
        host='0.0.0.0',
        port=5000
    )
