import os
import time
import asyncio
import traceback

import whisperx

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
from ratelimit import limits, sleep_and_retry
@sleep_and_retry
@limits(calls=config['api_calls_per_second'], period=1)
def _limit_sync():  # вспомогательная функция, используется в async-коде
    pass

async def call_api_async(url):
    try:
        _limit_sync()
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
    
# Уведолмения в ТГ
def send_tg_message(text):
    call_api(f"https://api.telegram.org/bot6425454857:AAEQOtr6P5VRlfcYZmIxrC4yMWQD0oG1HM0/sendMessage?chat_id=636481977&text=СКРИПТ ТРАНСКРИБАЦИИ ЗВОНКОВ:\n{text}")

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

# ARS
calls_duration = 0
calls_count = 0
logging.info("Загрузка whisper...")
whisper_version = 'whisperx'
whisper_model = 'large-v3'
import whisperx
model = whisperx.load_model(whisper_model, device="cuda", language="ru", compute_type="float16")
transcribe_semaphore = asyncio.Semaphore(3)

# Загрузка списка компаний
def get_companies():
    logging.info("Происходит загрузка компаний...")
    start_time = time.time()
    try:
        response = call_api(f"https://novomir.pro/amo/rossuvenir/amo/getCompanies.php?limit={config['companys_count_load_limit']}")
        if response.status_code == 200:
            json = response.json()
            companys = json['companies']
            logging.info("Загружено " + str(len(companys)) + " компаний за " + str((time.time() - start_time).__round__(2)) + " секунд" + "\n")
        else:
            error = f"Произошла ошибка при загрузке компаний, код ответа сервера: {response.status_code}"
            logging.error(f"{error}\n")
        return companys
    except Exception as e:
        error = f"Произошла ошибка при загрузке компаний: {e}"
        logging.error(f"{error}\n")

def get_handled_companys():
    cursor.execute("SELECT company_id FROM calls WHERE model=%s GROUP BY company_id", (f"{whisper_version}_{whisper_model}",))
    companys = cursor.fetchall()
    companys = [company['company_id'] for company in companys]
    return companys

async def get_company_calls(company):
    try:
        response = await call_api_async("https://novomir.pro/amo/rossuvenir/amo/getCompaniesCalls.php?id=" + str(company['id']))
        if response.status_code == 200:
            json = response.json()
            if not json:
                print("\tУ компании нет звонков\n")
                write_to_db(company['id'], None, None, None, None, "Нет звонков")
                return []
            else :
                print(f"Загружено звонков: {str(len(json))}")
                return list(json.items())
        else:
            error = f"\t\tПроизошла ошибка при загрузке звонков: {e}"
            logging.error(f"{error}\n")
            return None
    except Exception as e:
        error = f"\t\tПроизошла ошибка при загрузке звонков: {e}"
        logging.error(f"{error}\n")
        return None

async def call_handler(company, call):
    if not call.get('link'):
        return None
    
    # Проверка наличия транскрибации в БД
    cursor.execute("SELECT call_id FROM calls WHERE call_id = %s AND model = %s", (call['call_id'], f"{whisper_version}_{whisper_model}"))
    handle_count = len(cursor.fetchall())
    if handle_count > 0:
        return None

    filename = f"audio/temp_{call['call_id']}.mp3"
    downloaded = await download_audio_stream(call['link'], filename)
    
    if downloaded > 400:
        write_to_db(company['id'], call['call_id'], call['link'], call['duration'], "", "Ссылка на звонок недействительна")
    elif downloaded:
        if os.path.exists(filename) and os.path.getsize(filename) < 1024:
            write_to_db(company['id'], call['call_id'], call['link'], call['duration'], "", "Файл поврежден")
            os.remove(filename)
            logging.error(f"Файл {filename} слишком маленький, возможно, повреждён.")
            return None
        
        text = await get_text(filename)
        
        write_to_db(company['id'], call['call_id'], call['link'], call['duration'], text)
        os.remove(filename)

        global calls_duration
        global calls_count

        calls_duration += int(call['duration'])
        calls_count += 1

async def get_text(filename):

    audio = whisperx.load_audio(filename)

    async with transcribe_semaphore:
        print(calls_duration)
        result = model.transcribe(audio, batch_size=config['batch_size'])

    text = "".join([segment["text"] for segment in result["segments"]])

    return text

async def download_audio_stream(url, save_path):
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    return response.status_code

                with open(save_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
        return True

    except httpx.HTTPError as e:
        logging.error(f"Произошла HTTP-ошибка при загрузке звонка: {e}")
        return False
    except Exception as e:
        logging.error(f"Другая ошибка при загрузке звонка: {e}")
        return False

def write_to_db(company_id, call_id, call_link, call_duration, text, result = ""):
    sql = "INSERT INTO calls (company_id, call_id, link, duration, text, result, model) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    values = (company_id, call_id, call_link, call_duration, text, result, f"{whisper_version}_{whisper_model}")
    cursor.execute(sql, values)
    conn.commit()  # Фиксируем изменения
    print(f"Данные успешно записаны в БД [call_id = {call_id}]")

async def main():
    
    logging.info("---------- Скрипт транскрибации запущен ----------")
    start_time = time.time()

    # Загрузка списка немаркерованных компаний
    companys = get_companies()
    handled_companys = get_handled_companys()

    # print('всего ', len(companys))
    # print('обработанные', len(handled_companys))
    # print("Уникальных company_id в обработанных:", len(set(handled_companys)))

    handling_companys = [company for company in companys if company['id'] not in handled_companys]
    handling_companys = handling_companys[:config['companys_count_handle_limit']]
    # print('к обработке', len(handling_companys))

    logging.info(f'В обработке {len(handling_companys)} компаний из {len(companys)} загруженных')

    for company in handling_companys:
            calls = await get_company_calls(company)
            if calls:
                tasks = [
                    call_handler(company, call_data)
                    for _, call_data in calls
                ]
                await asyncio.gather(*tasks)

    logging.info("---------- Скрипт транскрибации завершен ----------")
    end_time = time.time()
    script_duration = end_time - start_time

    logging.info(f"ВРЕМЯ РАБОТЫ СКРИПТА: {script_duration.__round__(2)} сек. ({(script_duration/60).__round__(0)} мин.)")
    logging.info(f"ДЛИТЕЛЬНОСТЬ ЗАПИСЕЙ ОБРАБОТАННЫХ ЗВОНКОВ: {calls_duration.__round__(2)} сек. ({(calls_duration/60).__round__(0)} мин.)")
    logging.info(f"СКОРОСТЬ ОБРАБОТКИ 1 СЕК: {(calls_duration/script_duration).__round__(2)}")
    logging.info(f"КОЛИЧЕСТВО ЗВОНКОВ: {calls_count}")
    logging.info(f"СРЕДНЕЕ ВРЕМЯ ОБРАБОТКИ 1 ЗВОНКА: {(calls_duration/calls_count).__round__(2)} сек.")
    send_tg_message(f"""Скрипт закончил работу

ВРЕМЯ РАБОТЫ СКРИПТА: {script_duration.__round__(2)} сек. ({(script_duration/60).__round__(0)} мин.)
ДЛИТЕЛЬНОСТЬ ЗАПИСЕЙ ОБРАБОТАННЫХ ЗВОНКОВ: {calls_duration.__round__(2)} сек. ({(calls_duration/60).__round__(0)} мин.)
СКОРОСТЬ ОБРАБОТКИ 1 СЕК: {(calls_duration/script_duration).__round__(2)}
КОЛИЧЕСТВО ЗВОНКОВ: {calls_count}
СРЕДНЕЕ ВРЕМЯ ОБРАБОТКИ 1 ЗВОНКА: {(calls_duration/calls_count).__round__(2)} сек.""")
try:
    asyncio.run(main())
except Exception as e:
    logging.error(traceback.format_exc())
finally:
    # Закрытие соединения с БД
    cursor.close()
    conn.close()