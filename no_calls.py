from ratelimit import limits, sleep_and_retry
import requests
import logging
import traceback
import time

limit = 'all'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,  # Уровень логов
    format="%(asctime)s [%(levelname)s] %(message)s",  # Формат сообщений
    handlers=[
        logging.FileHandler(f"{time.time()}.log", encoding="utf-8"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)

def send_tg_message(text):
    call_api(f"https://api.telegram.org/bot6425454857:AAEQOtr6P5VRlfcYZmIxrC4yMWQD0oG1HM0/sendMessage?chat_id=636481977&text=СКРИПТ ТРАНСКРИБАЦИИ ЗВОНКОВ:\n{text}")

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
    
def get_companies():
    logging.info("Происходит загрузка компаний...")
    start_time = time.time()
    try:
        response = call_api(f"https://novomir.pro/amo/rossuvenir/amo/getCompanies.php?limit={limit}")
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

def get_calls(company):
    logging.info("------------------------------------------------------------------")
    logging.info(f"Происходит загрузка звонков компании '{company['name']}' ({company['id']})")
    start_time = time.time()
    response = call_api("https://novomir.pro/amo/rossuvenir/amo/getCompaniesCalls.php?id=" + str(company['id']))
    if response:
        json = response.json()
        if not json:
            logging.info("Компания '" + company['name'] + "' не имеет звонков\n")
            return

        logging.info("Количество звонков: " + str(len(json)))
        logging.info("Время загрузки: " + str((time.time() - start_time).__round__(2)) + " сек.\n")
        return json.items()
    else:
        error = f"\t\tПроизошла ошибка при загрузке звонков: {e}"
        logging.error(f"{error}\nTraceback: {traceback.format_exc()}")
        send_tg_message(error)

try:
    logging.info("Скрипт запущен")

    start_time = time.time()

    companys = get_companies()
    companys_count = len(companys)

    no_calls = 0

    for company in companys:
        logging.info(f"Прогресс: {companys.index(company) + 1} из {companys_count} компаний ({((companys.index(company) + 1)/companys_count).__round__(2)*100}%)")
        calls = get_calls(company)
        if calls:
            if len(calls) > 0:
                logging.info(f"Результат обработки компании '{company['name']}' ({company['id']}) не был изменен\n")
            else:
                set_company_result(company, "Нет звонков")       
                no_calls += 1         
        else:
            set_company_result(company, "Нет звонков")
            no_calls += 1

    logging.info(f"Скрипт завершил работу за {(time.time() - start_time).__round__()} сек.")
    logging.info(f"Время обработки 1 компании {(time.time() - start_time).__round__() / companys_count} сек.")
    logging.info(f"Без звонков / ВСЕГО: {no_calls} / {companys_count}")

except Exception as e:
    error = f"Произошла непредвиденная ошибка: {e}"
    logging.error(f"\t\t{error}\n")
    send_tg_message(error)
    logging.info(f"Скрипт завершил работу за {(time.time() - start_time).__round__()} сек.")
    logging.info(f"Время обработки 1 компании {(time.time() - start_time).__round__() / companys_count} сек.")
    logging.info(f"Без звонков / ВСЕГО: {no_calls} / {companys_count}")