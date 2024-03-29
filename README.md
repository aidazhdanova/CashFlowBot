Телеграм-бот для учёта финансов

## Описание бота

Телеграм-бот представляет собой инструмент для учета финансовых операций пользователей.
Бот использует базу данных для хранения информации о пользователях, доходах, расходах, категориях расходов 
и других необходимых данных. Он поддерживает логирование событий для отслеживания возможных ошибок.

## Технологии

- Telebot (python-telegram-bot)
- SQLAlchemy
- APScheduler

## Развертывание проекта локально
1. Клонируем репозиторий в нужную директорию:
- git clone https://github.com/aidazhdanova/CashFlowBot.git

2. Создаём виртуальное окружение:
- Для Mac:
  ```
  python3 -m venv venv
  ```

4. Активируем виртуальное окружение:
- Для Mac:
  ```
  source venv/bin/activate
  ```

4. Устанавливаем зависимости:
- pip install -r requirements.txt

5. Создаём файл .env и добавляем переменные окружения, включая токен Telegram бота.

6. Запускаем программу в терминале:
- main.py
