import os
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, render_template_string, send_from_directory, session, redirect, url_for
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, Message
from config import DOMAIN, BOT_TOKEN, ADMIN_ID, CONTACTS

app = Flask(__name__)
app.secret_key = os.urandom(24)
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Инициализация БД
def init_db():
    conn = sqlite3.connect('ads.db')
    c = conn.cursor()
    
    # Таблица объявлений
    c.execute('''CREATE TABLE IF NOT EXISTS ads
                (id INTEGER PRIMARY KEY,
                title TEXT,
                price TEXT,
                description TEXT,
                location TEXT,
                amenities TEXT,
                photos TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY,
                tg_id INTEGER UNIQUE,
                full_name TEXT,
                phone TEXT,
                role TEXT DEFAULT 'user',
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица аналитики
    c.execute('''CREATE TABLE IF NOT EXISTS analytics
                (id INTEGER PRIMARY KEY,
                user_id INTEGER,
                ad_id INTEGER,
                ip TEXT,
                visited_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

# Логирование
logging.basicConfig(level=logging.INFO)

# Генерация SEO-тегов
def generate_seo_tags(ad):
    return f"""
    <meta name="description" content="Аренда {ad['title']} в {ad['location']}. {ad['description']}">
    <meta property="og:title" content="{ad['title']}">
    <meta property="og:description" content="{ad['description']}">
    <meta property="og:image" content="https://{DOMAIN}/static/photos/{ad['photos'].split(',')[0]}">
    """

# Красивый шаблон карточки
AD_CARD_TEMPLATE = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ ad.title }}</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&family=Roboto:wght@300;400&display=swap');
        .rental-card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .image-container { position: relative; height: 400px; background: linear-gradient(rgba(0,0,0,0) 60%, rgba(0,0,0,0.7)); }
        .price-tag { position: absolute; top: 20px; right: 20px; background: #E74C3C; color: white; padding: 8px 16px; border-radius: 8px; }
    </style>
    {{ seo_tags|safe }}
</head>
<body class="p-4">
    <div class="max-w-4xl mx-auto rental-card">
        <div class="image-container">
            <img src="/static/photos/{{ ad.photos.split(',')[0] }}" alt="{{ ad.title }}">
            <div class="price-tag">{{ ad.price }} ₽/мес</div>
        </div>
        <div class="p-6">
            <h1 class="text-2xl font-bold mb-2">{{ ad.title }}</h1>
            <div class="text-gray-600 mb-4">📍 {{ ad.location }}</div>
            <div class="grid md:grid-cols-2 gap-6 mb-6">
                <div class="bg-gray-50 p-4 rounded-lg">
                    <h2 class="font-bold mb-3">Описание</h2>
                    <p>{{ ad.description }}</p>
                </div>
                <div class="bg-gray-50 p-4 rounded-lg">
                    <h2 class="font-bold mb-3">Удобства</h2>
                    <div class="grid grid-cols-2 gap-2">
                        {% for amenity in ad.amenities.split(',') %}
                        <div>✓ {{ amenity }}</div>
                        {% endfor %}
                    </div>
                </div>
            </div>
            <div class="border-t pt-6">
                {{ CONTACTS|safe }}
            </div>
        </div>
    </div>
</body>
</html>'''

# Главная страница
INDEX_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>Агентство недвижимости "Максимум"</title>
    <meta name="description" content="Лучшие предложения по аренде недвижимости">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold mb-8">Актуальные предложения</h1>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {% for ad in ads %}
            <a href="/ad/{{ ad.id }}" class="rental-card">
                <div class="image-container">
                    <img src="/static/photos/{{ ad.photos.split(',')[0] }}" alt="{{ ad.title }}">
                    <div class="price-tag">{{ ad.price }} ₽/мес</div>
                </div>
                <div class="p-4">
                    <h3 class="font-bold text-lg">{{ ad.title }}</h3>
                    <p class="text-gray-600">{{ ad.location }}</p>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</body>
</html>'''

# Система авторизации
@app.route('/login')
def login():
    user_data = request.args.get('user')
    if user_data:
        user = json.loads(user_data)
        conn = sqlite3.connect('ads.db')
        c = conn.cursor()
        
        try:
            c.execute('INSERT OR IGNORE INTO users (tg_id, full_name) VALUES (?, ?)', 
                     (user['id'], user['first_name']))
            conn.commit()
            
            # Отправка уведомления админу
            await bot.send_message(
                ADMIN_ID,
                f"🎉 Новый пользователь!\n"
                f"ID: {user['id']}\n"
                f"Имя: {user['first_name']}\n"
                f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
        except Exception as e:
            logging.error(f"Ошибка регистрации: {e}")
        
        finally:
            conn.close()
            
        session['user_id'] = user['id']
        return redirect(url_for('index'))
    
    return "Ошибка авторизации", 401

# Остальные обработчики и логика из предыдущей версии...

# Аналитика
@app.after_request
def track_analytics(response):
    if request.path.startswith('/ad/'):
        conn = sqlite3.connect('ads.db')
        c = conn.cursor()
        
        try:
            ad_id = request.path.split('/')[-1]
            c.execute('INSERT INTO analytics (user_id, ad_id, ip) VALUES (?, ?, ?)',
                     (session.get('user_id'), ad_id, request.remote_addr))
            conn.commit()
        except Exception as e:
            logging.error(f"Ошибка аналитики: {e}")
        finally:
            conn.close()
    
    return response

if __name__ == '__main__':
    # Инициализация вебхуков и запуск
    from aiogram.webhook.aiohttp_server import setup_application
    from aiohttp import web
    
    app_web = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dp=dp, bot=bot)
    webhook_requests_handler.register(app_web, path='/webhook')
    setup_application(app_web, dp=dp, bot=bot)
    
    web.run_app(app_web, host='0.0.0.0', port=5000)