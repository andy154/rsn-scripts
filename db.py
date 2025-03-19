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
print("Подключение успешно!")

# sql = "INSERT INTO calls (text, result) VALUES (%s, %s)"
# values = ("Alice", 25)
# cursor.execute(sql, values)
# conn.commit()  # Фиксируем изменения

