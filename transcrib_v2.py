import whisperx
import asyncio
import time
import os
import requests
from duck_chat import DuckChat
import logging
import os
import traceback
import yaml
from ratelimit import limits, sleep_and_retry
import warnings
warnings.simplefilter("ignore", category=FutureWarning)

# Настройка логирования
logging_file = os.path.join("logs", f"{time.strftime('%Y-%m-%d_%H-%M', time.localtime())}.log")
logging.basicConfig(
    level=logging.INFO,  # Уровень логов
    format="%(asctime)s [%(levelname)s] %(message)s",  # Формат сообщений
    handlers=[
        # logging.FileHandler(logging_file, encoding="utf-8"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)

logging.info("Скрипт запущен!")

script_start_time = 0
companys_count = 0
calls_count = 0
calls_count_duration_yes = 0
calls_count_no_results = 0
calls_count_handled = 0

calls_duration = 0
calls_duration_no_handled = 0
calls_duration_handled = 0

transcrib_duration = 0
calls_handler_duration = 0
calls_download_duration = 0

calls_errors = 0

with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)
prompt = config["prompt"]
response_prompt = '\nДАЙ ОТВЕТ ОПРЕДЕЛЕННО ТОЛЬКО "ДА" или "НЕТ", НИКАКИХ ОБЪЯСНЕНИЙ!!! ТОЛЬКО "ДА" ИЛИ "НЕТ"!!!'

logging.info("Загрузка whisper...")
whisper_version = "whisperX"
whisper_model = "large-v3"
model = whisperx.load_model(whisper_model, device="cuda", language="ru", compute_type="float16")

import mysql.connector

# Параметры подключения
conn = mysql.connector.connect(
    host="vip139.hosting.reg.ru",      # Адрес сервера (или IP)
    user="u0966977_amo",           # Имя пользователя MySQL
    password="nI1hL5cM9jnC5sT5",   # Пароль от MySQL
    database="u0966977_amo"     # Название базы данных
)

# Создаём курсор для выполнения запросов
cursor = conn.cursor()
logging.info("Подключение к базе данных успешно!")

def write_to_db(company_id, call_id, call_link, call_duration, text, result = ""):
    sql = "INSERT INTO calls (company_id, call_id, link, duration, text, result, model) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    values = (company_id, call_id, call_link, call_duration,  text, result, f"{whisper_version}_{whisper_model}")
    cursor.execute(sql, values)
    conn.commit()  # Фиксируем изменения
    logging.info("Данные успешно записаны в БД")

@sleep_and_retry
@limits(calls=7, period=1)
def call_api(url):
    try:
        response = requests.get(url, timeout=60)  # Добавляем таймаут в 10 секунд
        return response
    except requests.exceptions.Timeout:
        logging.error(f"Таймаут запроса: {url}")
        send_tg_message(f"Ошибка: Таймаут запроса {url}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка запроса: {url}\n{e}")
        send_tg_message(f"Ошибка: {e}")
        return None

def send_tg_message(text):
    call_api(f"https://api.telegram.org/bot6425454857:AAEQOtr6P5VRlfcYZmIxrC4yMWQD0oG1HM0/sendMessage?chat_id=636481977&text=СКРИПТ ТРАНСКРИБАЦИИ ЗВОНКОВ:\n{text}")

def get_companies():
    logging.info("Происходит загрузка компаний...")
    start_time = time.time()
    try:
        response = call_api(f"https://novomir.pro/amo/rossuvenir/amo/getCompanies.php?limit={config['company_counts_limit']}")
        if response.status_code == 200:
            json = response.json()
            companys = json['companies']
            logging.info("Загружено " + str(len(companys)) + " компаний за " + str((time.time() - start_time).__round__(2)) + " секунд" + "\n")
        else:
            error = f"Произошла ошибка при загрузке компаний, код ответа сервера: {response.status_code}"
            logging.error(f"{error}\n")
            send_tg_message(error)
        return companys
    except Exception as e:
        error = f"Произошла ошибка при загрузке компаний: {e}"
        logging.error(f"{error}\nTraceback: {traceback.format_exc()}")
        send_tg_message(error)

def get_calls(company):
    logging.info("------------------------------------------------------------------")
    logging.info(f"Происходит загрузка звонков компании '{company['name']}' ({company['id']})")
    start_time = time.time()
    response = call_api("https://novomir.pro/amo/rossuvenir/amo/getCompaniesCalls.php?id=" + str(company['id']))
    if response:
        if response.status_code == 200:
            json = response.json()
            if not json:
                logging.info("Компания '" + company['name'] + "' не имеет звонков\n")
                return []

            logging.info("Количество звонков: " + str(len(json)))
            logging.info("Время загрузки: " + str((time.time() - start_time).__round__(2)) + " сек.\n")
            return json.items()
        else:
            error = f"\t\tПроизошла ошибка при загрузке звонков: {e}"
            logging.error(f"{error}\nTraceback: {traceback.format_exc()}")
            send_tg_message(error)
    else:
        return None
    
def download_file(url, local_filename):
    global calls_download_duration

    start_time = time.time()
    logging.info("\t\tПроисходит загрузка звонка...")
    try:
        response = requests.get(url, stream=True)
        with open(local_filename, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        download_duration = time.time() - start_time
        calls_download_duration += int(download_duration)
        logging.info("\t\tВремя загрузки: " + str(download_duration.__round__(2)) + " сек.\n")

        return local_filename
    except Exception as e:
        error = f"\t\tПроизошла ошибка при загрузке файла: {e}"
        logging.error(f"{error}\nTraceback: {traceback.format_exc()}")
        send_tg_message(error)

def get_text(file_url):
    global transcrib_duration

    local_filename = "temp_audio.mp3"  # Временный файл
    download_file(file_url, local_filename)

    logging.info("\t\tПроисходит транскрибация звонка...")
    try:
        start_time = time.time()

        batch_size = 16
        audio = whisperx.load_audio(local_filename)
        result = model.transcribe(audio, batch_size=batch_size)
        text = ""
        for segment in result["segments"]:
            text += segment["text"]

        os.remove(local_filename)  # Удаляем временный файл после обработки

        end_time = time.time()
        transcrib_duration_local = end_time - start_time
        transcrib_duration += (end_time - start_time)

        logging.info("\t\tВремя транскрибации: " + str(transcrib_duration_local.__round__(2)) + " сек.\n")
        logging.info("\t\tРЕЗУЛЬТАТ: " + text)
        
        return text
    except Exception as e:
        error = f"Произошла ошибка при транскрибации: {e}"
        logging.error(f"\t\t{error}\n")

async def get_answer(company, call, text):
    global calls_handler_duration

    start_time = time.time()
    logging.info("\t\tПроисходит обработка содержимого разговора...")
    try:
        async with DuckChat() as chat:
            # response_detail = await chat.ask_question(f"{prompt}\nРасшифровка звонка:\n{text}")
            # response_strong = await chat.ask_question(f"Вот результат обработки разговора:\n{response_detail}\n{response_prompt}\n")
            response = await chat.ask_question(f"{prompt}\nРасшифровка звонка:\n{text}")
            write_to_db(company['id'], call['call_id'], call['link'], call['duration'], text, response)

            end_time = time.time()
            duration = end_time - start_time
            calls_handler_duration += int(duration)

            # logging.info(f"\t\tРезультат обработки разговора: {response_detail}")
            # logging.info("\t\tРЕЗУЛЬТАТ: " + str(response_strong))
            logging.info("\t\tРЕЗУЛЬТАТ: " + str(response))
            logging.info("\t\tВремя обработки ИИ: " + str(duration.__round__(2)) + " сек.\n")

            return response
    except Exception as e:
        write_to_db(company['id'], call['call_id'], call['link'], call['duration'], text)
        error = f"Произошла ошибка при обработке ИИ(кол-во символов в запросе = {len(text)}): {e}"
        logging.error(f"\t\t{error}\n")
        # send_tg_message(error)
        return None

def call_handler(company, call):
    global calls_duration
    global calls_duration_no_handled
    global calls_duration_handled
    global calls_count_duration_yes
    global calls_count_handled
    global calls_count_no_results

    start_time = time.time()
    duration = int(call[1]['duration']) if call[1]['duration'] is not None else 0
    calls_duration += duration
    
    logging.info("\tОбработка звонка")
    logging.info("\tДлительность: " + str(duration) + " сек.")
    logging.info("\tСсылка: " + str(call[1]['link']) + "\n")

    if duration > config['yes_duration']:
        logging.info(f"\t\tПродолжительность звонка более {config['yes_duration']} сек., по этому в качестве результата принимаем, что есть интерес")
        calls_count_duration_yes += 1
        calls_duration_no_handled += int(duration)
        return "ДА"
    elif call[1]['link']:    
        text = get_text(call[1]['link'])
        if not text:
            logging.info("\t\tПроизошла ошибка при транскрибации звонка\n")
            return None
        result = asyncio.run(get_answer(company, call[1], text))

        logging.info("\t\tВсего времени на обработку звонка: " + str((time.time() - start_time).__round__(2)) + " сек.\n")
        calls_count_handled += 1
        calls_duration_handled += int(duration)
        return result
    else:
        calls_count_no_results += 1
        return -1

def set_company_result(company, result):
    logging.info("Происходит отправка результата обработки компании...")

    try:
        response = call_api(f"https://novomir.pro/amo/rossuvenir/amo/sendCompaniesCheck.php?id={str(company['id'])}&result={str(result)}")
        if response.status_code == 200:
            logging.info(f"Результат обработки компании '{company['name']}' ({company['id']}) установлен '{result}'\n")
        else:
            error = f"Произошла ошибка при отправке результата обработки компаний, код ответа сервера: {response.status_code}"
            logging.error(f"{error}\n")
            send_tg_message(error)
    except Exception as e:
        error = f"Произошла ошибка при отправке результата обработки компаний: {e}\nTraceback: {traceback.format_exc()}"
        logging.error(f"{error}\n")
        send_tg_message(error)


def print_stats():
    logging.info("------------------------------------------------------------------")
    logging.info("Скрипт завершил работу!\n")

    script_duration = time.time() - script_start_time
    logging.info("Время работы скрипта: " + str(script_duration.__round__(2)) + " сек.")
    logging.info("Количество обработанных компаний: " + str(companys_count) + "\n")

    logging.info("Количество звонков (всего): " + str(calls_count))
    logging.info(f"Количество звонков (с длительностью более {config['yes_duration']} сек.): {calls_count_duration_yes}")
    logging.info(f"Количество звонков (не обработано): {calls_count_no_results}")
    logging.info(f"Количество звонков (обработано): {calls_count_handled}\n")

    logging.info(f"Длительность звонков (всего): {calls_duration} сек.")
    logging.info(f"Длительность звонков (с длительностью более {config['yes_duration']} сек.): {calls_duration_no_handled} сек.")
    logging.info(f"Длительность звонков (обработано): {calls_duration_handled} сек.")

    logging.info(f"Общее время транскрибации: {transcrib_duration.__round__()} сек.")
    logging.info(f"Общее время обработки звонков: {calls_handler_duration.__round__()} сек.")
    logging.info(f"Общее время загрузки звонков: {calls_download_duration.__round__()} сек.\n")

    logging.info(f"Среднее время обработки 1 компании: {(script_duration/companys_count).__round__()} сек.")
    logging.info(f"Среднее время обработки 1 звонка: {(script_duration/calls_count_handled).__round__()} сек.")
    logging.info(f"Среднее время обработки 1 сек. записи: {(script_duration/calls_duration_handled).__round__(2)} сек.\n")

    logging.info(f"Коэффициент скорости обработки звонков(общее время): {(calls_duration_handled/script_duration).__round__(2)}")
    logging.info(f"Коэффициент скорости обработки звонков(транскрибация): {(calls_duration_handled/transcrib_duration).__round__(2)}")

    send_tg_message(f"""
    Скрипт успешно завершил работу!
    Время работы скрипта: {str(script_duration.__round__(2))} сек.
    Коэффициент скорости обработки звонков(общее время): {(calls_duration_handled/script_duration).__round__(2)}
    Коэффициент скорости обработки звонков(транскрибация): {(calls_duration_handled/transcrib_duration).__round__(2)}
""")
    

def main():
    
    global companys_count
    global calls_count
    global script_start_time

    script_start_time = time.time()
    
    companys = get_companies()
    companys_count = len(companys)

    for company in companys:
        logging.info(f"Прогресс: {companys.index(company) + 1} из {companys_count} компаний ({((companys.index(company) + 1)/companys_count).__round__(2)*100}%)")
        start_time = time.time()

        calls = get_calls(company)
        result = None
        no_calls = None

        if calls != None:
            if (len(calls) == 0):
                result = "Нет звонков"
            
            for call in calls:
                calls_count += 1
                call_result = call_handler(company, call)

                if call_result == "ДА":
                    result = "Есть интерес"
                    break
                elif call_result == "НЕТ":
                    result = "Нет интереса"
                elif call_result == -1:
                    no_calls = True

        if result: 
            set_company_result(company, result)
        elif no_calls:
            set_company_result(company, "Нет звонков")
        else:
            logging.info(f"Результат обработки компании '{company['name']}' ({company['id']}) не изменен\n")

        logging.info("Всего времени на обработку компании: " + str((time.time() - start_time).__round__(2)) + " сек.\n")

    print_stats()

try:
    main()
except Exception as e:
    error = f"Произошла непредвиденная ошибка: {e}\nTraceback: {traceback.format_exc()}"
    logging.error(f"{error}\n")
    print_stats()
    send_tg_message(error)