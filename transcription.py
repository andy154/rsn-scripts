import os
import time
import asyncio

import logging
import yaml

import requests
from ratelimit import limits, sleep_and_retry

import whisperx

# Настройка логирования
logging_file = os.path.join("logs", f"{time.strftime('%Y-%m-%d_%H-%M', time.localtime())}.log")
logging.basicConfig(
    level=logging.INFO,  # Уровень логов
    format="%(asctime)s [%(levelname)s] %(message)s",  # Формат сообщений
    handlers=[
        logging.FileHandler(logging_file, encoding="utf-8"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)

# Настройка запросов
@sleep_and_retry
@limits(calls=3, period=1)
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


async def main():
    logging.info("Скрипт транскрибации запущен")
    
    # Загрузка файла конфигурации
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)
        logging.info("Файл конфигурации успешно прочитан")

asyncio.run(main())