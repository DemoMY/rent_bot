#!/bin/bash

# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y python3.12 python3.12-venv nginx certbot python3-certbot-nginx tmux

# Создание структуры папок
mkdir -p ~/rent_bot/static/photos
chmod -R 755 ~/rent_bot/static

# Настройка виртуального окружения
cd ~/rent_bot
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Настройка Nginx
sudo cp nginx.conf /etc/nginx/sites-enabled/rent_bot.conf
sudo nginx -t && sudo systemctl reload nginx

# Получение SSL сертификата
sudo certbot --nginx -d vipvdom.ru --non-interactive --agree-tos -m admin@vipvdom.ru

# Создание systemd сервиса
sudo cp rent_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rent_bot
sudo systemctl start rent_bot

echo "Установка завершена! Сервис доступен по https://vipvdom.ru"