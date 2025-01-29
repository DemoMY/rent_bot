#!/bin/bash

# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y python3.12 python3.12-venv nginx certbot python3-certbot-nginx tmux

# Настройка проекта
mkdir -p ~/rent_bot/static/photos
cd ~/rent_bot

# Виртуальное окружение
python3.12 -m venv venv
source venv/bin/activate

# Установка Python зависимостей
pip install --upgrade pip
pip install -r requirements.txt

# Настройка Nginx
sudo cp nginx.conf /etc/nginx/sites-enabled/rent_bot.conf
sudo nginx -t && sudo systemctl reload nginx

# Получение SSL
sudo certbot --nginx -d vipvdom.ru --non-interactive --agree-tos -m admin@vipvdom.ru

# Systemd сервис
sudo cp rent_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rent_bot
sudo systemctl start rent_bot

echo "Установка завершена! Сервис доступен по https://vipvdom.ru"