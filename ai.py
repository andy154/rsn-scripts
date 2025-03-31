import os
import time
import asyncio

# Настройка логирования
import logging
logging_file = os.path.join("logs", f"{time.strftime('%Y-%m-%d_%H-%M', time.localtime())}.log")
logging.basicConfig(
    level=logging.INFO,  # Уровень логов
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

# Настройка запросов
import requests
from ratelimit import limits, sleep_and_retry
@sleep_and_retry
@limits(calls=config['api_calls_per_second'], period=1)
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
logging.info("Модуль запросов успешно настроен.")

# ИИ
import ollama
ai_model = 'deepseek-r1:7b'
llm_handle_version = 'test'
ai_system_prompt = """Ты — аналитик по транскриптам звонков в отдел продаж. 
Отвечай строго на русском языке. Пиши кратко и по делу.
Твоя задача — на основе текста разговора определить, подходит ли собеседник под критерии потенциального клиента. 
Не пиши лишнего. Не извиняйся. Не предлагай помощь."""

def get_result(text):
    start_time = time.time()
    response = ollama.chat(
        model=ai_model,
        messages=[
            {'role': 'system', 'content': ai_system_prompt},
            {'role': 'system', 'content': config['prompt']},
        {'role': 'user', 'content': f'''
Транскрипция звонка: [{text}]
Дай ответ с пояснением, есть у отвечающего интерес в целом к нашей продукции.
''' }
        ]
    )
    end_time = time.time()
    print(f"Время выполнения: {(end_time - start_time).__round__(2)} секунд")
    return response['message']['content']


logging.info("Модуль ИИ успешно импортирован.")
def get_not_handled_calls():
    logging.info("Происходит загрузка звонков из БД...")
    cursor.execute("SELECT * FROM calls WHERE result='' LIMIT 10")

    # Получаем все строки
    calls = cursor.fetchall()
    logging.info(f"Загружено {len(calls)} звонков из БД.")
    return calls


async def main():
    calls = get_not_handled_calls()
    for call in calls:
        result = get_result(call['text'])
        print(call['text'], result)
        if result == "ДА":
            result = True
        elif result == "Нет":
            result = False
        else:
            result = None

        # if result != None:
        #     cursor.execute("UPDATE calls SET llm_result=%s, llm_model=%s, llm_handle_vesion=%s WHERE id=%s", (result, ai_model, llm_handle_version, call['id']))
        #     conn.commit()

try:
    asyncio.run(main())
except Exception as e:
    logging.error(e)
finally:
    # Закрытие соединения с БД
    cursor.close()
    conn.close()
