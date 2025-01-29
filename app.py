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
ADMIN_ID = 123456789  # Замените на ваш Telegram ID
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

# ================= Telegram Handlers =================
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("➕ Новое объявление", callback_data="create_ad"))
    await message.answer("🏠 Админ-панель:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'create_ad')
async def start_ad_creation(callback_query: types.CallbackQuery):
    await CreateAd.TRANSACTION_TYPE.set()
    await bot.send_message(
        callback_query.from_user.id,
        "🔹 Выберите тип операции:",
        reply_markup=InlineKeyboardMarkup().row(
            InlineKeyboardButton("Продажа", callback_data="sell"),
            InlineKeyboardButton("Аренда", callback_data="rent"),
            InlineKeyboardButton("Покупка", callback_data="buy")
        )
    )

@dp.callback_query_handler(state=CreateAd.TRANSACTION_TYPE)
async def process_transaction_type(callback_query: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['transaction_type'] = callback_query.data
    await CreateAd.next()
    await bot.send_message(
        callback_query.from_user.id,
        "🏘 Выберите тип недвижимости:",
        reply_markup=InlineKeyboardMarkup().row(
            InlineKeyboardButton("Квартира", callback_data="flat"),
            InlineKeyboardButton("Дом", callback_data="house"),
            InlineKeyboardButton("Коммерческая", callback_data="commercial")
        )
    )

@dp.callback_query_handler(state=CreateAd.PROPERTY_TYPE)
async def process_property_type(callback_query: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['property_type'] = callback_query.data
    await CreateAd.next()
    await bot.send_message(callback_query.from_user.id, "💰 Введите цену (только цифры):")

@dp.message_handler(state=CreateAd.PRICE)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        async with state.proxy() as data:
            data['price'] = price
        await CreateAd.next()
        await message.answer("🚪 Количество комнат:")
    except:
        await message.answer("❌ Некорректная цена! Введите число:")

@dp.message_handler(state=CreateAd.ROOMS)
async def process_rooms(message: types.Message, state: FSMContext):
    try:
        rooms = int(message.text)
        async with state.proxy() as data:
            data['rooms'] = rooms
        await CreateAd.next()
        await message.answer("📏 Площадь (м²):")
    except:
        await message.answer("❌ Некорректное значение! Введите число:")

@dp.message_handler(state=CreateAd.AREA)
async def process_area(message: types.Message, state: FSMContext):
    try:
        area = float(message.text)
        async with state.proxy() as data:
            data['area'] = area
        await CreateAd.next()
        await message.answer("📍 Адрес объекта:")
    except:
        await message.answer("❌ Некорректное значение! Введите число:")

@dp.message_handler(state=CreateAd.ADDRESS)
async def process_address(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['address'] = message.text
    await CreateAd.next()
    await message.answer("📝 Описание объекта:")

@dp.message_handler(state=CreateAd.DESCRIPTION)
async def process_description(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['description'] = message.text
    await CreateAd.next()
    await message.answer("📸 Отправьте фотографии объекта (макс. 10):")

@dp.message_handler(state=CreateAd.PHOTOS, content_types=types.ContentType.PHOTO)
async def process_photos(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if 'photos' not in data:
            data['photos'] = []
        
        photo = message.photo[-1]
        file_id = photo.file_id
        file_path = f"static/photos/{file_id}.jpg"
        
        await photo.download(destination_file=file_path)
        data['photos'].append(file_path)

    await message.answer("✅ Фото добавлено! Отправьте ещё или нажмите 'Готово'",
                       reply_markup=InlineKeyboardMarkup().add(
                           InlineKeyboardButton("✅ Готово", callback_data="finish_photos")))

@dp.callback_query_handler(lambda c: c.data == 'finish_photos', state=CreateAd.PHOTOS)
async def finish_ad_creation(callback_query: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        # Сохранение в БД
        c.execute('''INSERT INTO ads 
                    (transaction_type, property_type, price, rooms, area, address, description)
                    VALUES (?,?,?,?,?,?,?)''',
                 (data['transaction_type'], data['property_type'], data['price'],
                  data['rooms'], data['area'], data['address'], data['description']))
        ad_id = c.lastrowid
        
        for path in data.get('photos', []):
            c.execute("INSERT INTO photos (ad_id, file_path) VALUES (?,?)", (ad_id, path))
        
        conn.commit()
    
    await state.finish()
    await bot.send_message(callback_query.from_user.id, "✅ Объявление успешно создано!")
    await publish_to_channel(ad_id)

async def publish_to_channel(ad_id):
    c.execute("SELECT * FROM ads WHERE id=?", (ad_id,))
    ad = c.fetchone()
    
    c.execute("SELECT file_path FROM photos WHERE ad_id=?", (ad_id,))
    photos = [types.InputMediaPhoto(open(row[0], 'rb')) for row in c.fetchall()[:10]]
    
    text = f'''🏠 *{ad[3]}* | {'Продажа' if ad[1] == 'sell' else 'Аренда'} 

📌 Тип: {'Квартира' if ad[2] == 'flat' else 'Дом' if ad[2] == 'house' else 'Коммерческая'}
💰 Цена: *{ad[3]:,} ₽*
🚪 Комнат: {ad[4]}
📏 Площадь: {ad[5]} м²
📍 Адрес: {ad[6]}

📝 {ad[7]}

{CONTACTS}

[Подробнее на сайте](https://{DOMAIN}/ad/{ad_id})'''
    
    if photos:
        photos[0].caption = text
        photos[0].parse_mode = "Markdown"
        await bot.send_media_group(chat_id="@rent_vipvdom", media=photos)
    else:
        await bot.send_message(chat_id="@rent_vipvdom", text=text, parse_mode="Markdown")

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

INDEX_HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>Максимум - Недвижимость</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto; }
        .ad-card { border: 2px solid #2ECC71; border-radius: 10px; padding: 15px; margin: 20px 0; }
        .gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; }
        img { width: 100%; height: 200px; object-fit: cover; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Агентство недвижимости "Максимум"</h1>
    <div class="gallery">
        {% for ad in ads %}
        <div class="ad-card">
            <h3>{{ ad.title }}</h3>
            <p>Цена: {{ ad.price }} ₽</p>
            <p>{{ ad.description }}</p>
            <pre>{{ CONTACTS }}</pre>
        </div>
        {% endfor %}
    </div>
</body>
</html>'''

AD_HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>{{ ad[3] }}</title>
    <style>
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; }
        .info { margin-top: 20px; background: #f8f9fa; padding: 20px; border-radius: 10px; }
        .price { color: #2ECC71; font-size: 24px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ ad[3] }}</h1>
        <div class="gallery">
            {% for photo in photos %}
            <img src="/{{ photo }}" alt="Фото объекта">
            {% endfor %}
        </div>
        
        <div class="info">
            <p><span class="price">{{ price }} ₽</span></p>
            <p>🔹 Тип операции: {{ transaction_type }}</p>
            <p>🏠 Тип объекта: {{ property_type }}</p>
            <p>🚪 Комнат: {{ ad[4] }}</p>
            <p>📏 Площадь: {{ ad[5] }} м²</p>
            <p>📍 Адрес: {{ ad[6] }}</p>
            <p>{{ ad[7] }}</p>
        </div>

        <h3>Контакты:</h3>
        <pre>{{ CONTACTS }}</pre>
    </div>
</body>
</html>'''

if __name__ == '__main__':
    os.makedirs('static/photos', exist_ok=True)
    executor.start_webhook(
        dispatcher=dp,
        webhook_path='/webhook',
        on_startup=lambda _: bot.set_webhook(f"https://{DOMAIN}/webhook"),
        host='0.0.0.0',
        port=5000
    )