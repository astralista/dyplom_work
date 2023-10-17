# Используем официальный образ Python
FROM python:3.11

# Устанавливаем переменную среды для Python, чтобы вывод был более читаемым
ENV PYTHONUNBUFFERED 1

# Создаем и устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем requirements.txt в контейнер и устанавливаем зависимости
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы из текущей директории в контейнер
COPY . /app/

# Создаем и применяем миграции при старте контейнера
CMD ["python", "manage.py", "migrate"]

# Запускаем сервер Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]