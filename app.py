import os
import sqlite3
from flask import Flask, request, render_template_string
from aiogram import Bot, types, Dispatcher
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext, filters
from aiogram.dispatcher.filters.state import State, StatesGroup

app = Flask(__name__)
bot = Bot(token="7898468859:AAED-74SLqvJLWQl_7RazW0jdDdCu7_6tLo")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Конфигурация
DOMAIN = "vipvdom.ru"
ADMIN_ID = 850188889  # Замените на ваш ID
CONTACTS = """Агентство 'Максимум'
📞 Тел: +79676633355, +79676633377
🌐 Сайт: https://maximum-an.ru"""

# Инициализация БД
def init_db():
    conn = sqlite3.connect('ads.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS ads
                (id INTEGER PRIMARY KEY,
                title TEXT,
                price TEXT,
                description TEXT,
                photos TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                role TEXT CHECK(role IN ('admin', 'agent', 'user')) DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

class CreateAd(StatesGroup):
    TITLE = State()
    PRICE = State()
    DESCRIPTION = State()
    PHOTOS = State()

# Telegram Handlers
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    web_app = WebAppInfo(url=f"https://{DOMAIN}/")
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📝 Создать объявление", web_app=web_app)
    )
    
    await message.answer(
        "Добро пожаловать в агентство недвижимости!\n"
        "Нажмите кнопку ниже чтобы создать объявление:",
        reply_markup=keyboard
    )

# Web Routes
@app.route('/')
def index():
    conn = sqlite3.connect('ads.db')
    c = conn.cursor()
    c.execute("SELECT * FROM ads WHERE status='approved'")
    ads = c.fetchall()
    conn.close()
    
    return render_template_string(INDEX_HTML, ads=ads, CONTACTS=CONTACTS)

INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Агентство "Максимум"</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }
        .ad-form { background: #f5f5f5; padding: 20px; border-radius: 10px; }
        input, textarea { width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ddd; }
        button { background: #2ECC71; color: white; border: none; padding: 10px 20px; cursor: pointer; }
        .ad-card { border: 2px solid #2ECC71; border-radius: 10px; padding: 15px; margin: 10px 0; }
        .photos { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
        .photos img { width: 100%; height: 150px; object-fit: cover; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="ad-form">
        <h2>Добавить объявление</h2>
        <form id="adForm" onsubmit="return submitForm(event)">
            <input type="text" name="title" placeholder="Заголовок" required>
            <input type="text" name="price" placeholder="Цена" required>
            <textarea name="description" placeholder="Описание"></textarea>
            <input type="file" name="photos" multiple accept="image/*">
            <button type="submit">Опубликовать</button>
        </form>
    </div>

    <h3>Активные объявления:</h3>
    <div id="adsList">
        {% for ad in ads %}
        <div class="ad-card">
            <h3>{{ ad[1] }}</h3>
            <p>Цена: {{ ad[2] }}</p>
            <p>{{ ad[3] }}</p>
            <div class="photos">
                {% for photo in ad[4].split(',') %}
                <img src="/static/photos/{{ photo }}" alt="Фото">
                {% endfor %}
            </div>
            <pre>{{ CONTACTS }}</pre>
        </div>
        {% endfor %}
    </div>

    <script>
        async function submitForm(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            
            const response = await fetch('/add_ad', {
                method: 'POST',
                body: formData
            });
            
            if(response.ok) {
                alert('Объявление отправлено на модерацию!');
                location.reload();
            }
        }
    </script>
</body>
</html>
'''

@app.route('/add_ad', methods=['POST'])
def add_ad():
    conn = sqlite3.connect('ads.db')
    c = conn.cursor()
    
    photos = request.files.getlist('photos')
    photo_names = []
    
    os.makedirs('static/photos', exist_ok=True)
    
    for photo in photos:
        filename = f"{os.urandom(8).hex()}.jpg"
        photo.save(os.path.join('static/photos', filename))
        photo_names.append(filename)
    
    c.execute('''INSERT INTO ads (title, price, description, photos)
                VALUES (?, ?, ?, ?)''',
             (request.form['title'], 
              request.form['price'],
              request.form['description'],
              ','.join(photo_names)))
    
    conn.commit()
    conn.close()
    
    return '', 204

if __name__ == '__main__':
    os.makedirs('static/photos', exist_ok=True)
    executor.start_webhook(
        dispatcher=dp,
        webhook_path='/webhook',
        on_startup=lambda _: bot.set_webhook(f"https://{DOMAIN}/webhook"),
        host='0.0.0.0',
        port=5000
    )