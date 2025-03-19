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
print("Подключение к базе данных успешно!")

# def write_to_db(company, call, text, result = ""):
#     sql = "INSERT INTO calls (company_id, call_id, link, duration, text, result) VALUES (%s, %s, %s, %s, %s, %s)"
#     values = (111111, 2222222, "http://.....", 66,  "TEXTTEXTTEXTTEXTTEXT", "ДА")
#     cursor.execute(sql, values)
#     conn.commit()  # Фиксируем изменения

