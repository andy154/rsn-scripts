import os
import time
import asyncio
import traceback

# Настройка логирования
import logging
logging_file = os.path.join("logs", f"{time.strftime('%Y-%m-%d_%H-%M', time.localtime())}.log")
logging.basicConfig(
    level=logging.INFO,  # Уровень логов
    format="%(asctime)s [%(levelname)s] %(message)s",  # Формат сообщений
    handlers=[
        logging.FileHandler(logging_file, encoding="utf-8"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)

# Загрузка файла конфигурации
import yaml
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)
    logging.info("Файл конфигурации успешно прочитан")

# Настройка запросов
import requests
import httpx

async def call_api_async(url):
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url)
            return response
    except httpx.TimeoutException:
        logging.error(f"Таймаут запроса: {url}")
        return None
    except httpx.RequestError as e:
        logging.error(f"Ошибка запроса: {url}\n{e}")
        return None
    
def call_api(url):
    try:
        response = requests.get(url, timeout=60)
        return response
    except requests.exceptions.Timeout:
        logging.error(f"Таймаут запроса: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка запроса: {url}\n{e}")
        return None

# Подключение к БД
import mysql.connector

    # Параметры подключения
conn = mysql.connector.connect(
    host=config['db_host'],
    user=config['db_user'],
    password=config['db_password'],
    database=config['db_name']
)

    # Создаём курсор для выполнения запросов
cursor = conn.cursor(dictionary=True)
logging.info("Подключение к базе данных успешно.")

# ИИ
from openai import OpenAI

client = OpenAI(api_key=config['openai_api_key'])

response = client.chat.completions.create(
    model="gpt-4o mini",  # или "gpt-4", "gpt-3.5-turbo"
    messages=[
        {"role": "system", "content": "Ты помощник."},
        {"role": "user", "content": "Привет! Это тестовый запрос. Какая ты модель ИИ?"}
    ]
)

print(response.choices[0].message.content)