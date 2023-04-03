import datetime
import re
import telebot
import os
import sys
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, func
from dotenv import load_dotenv
from models import Expense, ExpenseCategory, Income, User, UserData
from telebot import types
from functools import lru_cache

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

load_dotenv()

log_filename = 'mylogfile.log'

handler = logging.FileHandler(log_filename)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[handler]
)

logger = logging.getLogger()

database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

token = os.getenv('TOKEN')
bot = telebot.TeleBot(token)


commands = ['Добавить доход', 'Добавить расход', 'Информация', 'Посмотреть сумму расходов и доходов за период']
commands_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                              row_width=2)
for command in commands:
    commands_keyboard.add(types.KeyboardButton(command))


@lru_cache(maxsize=20)
def get_user(telegram_id):
    try:
        return session.query(User).get(telegram_id)
    except NoResultFound:
        return None


def is_valid_date(date_string):
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    return re.match(pattern, date_string) is not None


@bot.message_handler(commands=['menu'])
def menu_handler(message):
    user = get_or_create_user(message)
    bot.send_message(
                    message.chat.id, 'Выбери команду.',
                    reply_markup=commands_keyboard)


@bot.message_handler(commands=['start'])
def start_handler(message):
    user = get_or_create_user(message)
    if user is not None:
        bot.send_message(message.chat.id,
                         'Ты уже зарегистрирован. '
                         'Введи /menu, чтобы узнать все доступные команды.')
    else:
        bot.send_message(message.chat.id,
                         'Привет! Я помогу тебе вести учёт финансов. '
                         'Введи /menu, чтобы узнать все доступные команды.')


def get_or_create_user(message):
    try:
        user = session.query(User).filter_by(telegram_id=message.chat.id).first()

        if user is None:
            user = User(telegram_id=message.chat.id)
            session.add(user)
            session.commit()
            user.user_data = UserData(telegram_id=message.chat.id)
            session.commit()
        return user
    except SQLAlchemyError as e:
        bot.send_message(message.chat.id,
                         'Кажется, что-то пошло не так. Попробуй позже.')
        logger.error(f'Ошибка при обработке команды start {e}.')


@bot.message_handler(func=lambda message: message.text == 'Добавить доход')
def income_handler(message):
    bot.send_message(message.chat.id, 'Введи сумму дохода.')
    bot.register_next_step_handler(message, income_amount_handler)


def income_amount_handler(message):
    amount = message.text
    try:
        amount_float = float(amount)
    except ValueError:
        bot.send_message(message.chat.id, 'Сумма дохода должна быть числом. '
                         'Попробуй ещё раз.')
        bot.register_next_step_handler(message, income_amount_handler)
        return
    bot.send_message(message.chat.id,
                     'Введи дату дохода в формате ГГГГ-ММ-ДД.')
    bot.register_next_step_handler(message, income_date_handler, amount_float)


def income_date_handler(message, amount):
    date = message.text
    if not is_valid_date(date):
        bot.send_message(message.chat.id,
                         'Некорректный формат даты. '
                         'Введи дату в формате ГГГГ-ММ-ДД.')
        bot.register_next_step_handler(message, income_date_handler, amount)
        return
    bot.send_message(message.chat.id, 'Введи описание дохода.')
    bot.register_next_step_handler(message, income_description_handler,
                                   amount, date)



def income_description_handler(message, amount, date):
    try:
        description = message.text
        user = session.query(User).filter_by(telegram_id=message.chat.id).first()
        income = Income(user=user, amount=amount,
                        date=date, description=description)
        session.add(income)
        session.commit()
        bot.send_message(message.chat.id, f'Доход на сумму {amount} добавлен.')
        menu_handler(message)
    except Exception as e:
        bot.send_message(message.chat.id, 
                         'Произошла ошибка при добавлении дохода. '
                         'Попробуй еще раз.')
        logger.error(f'Ошибка при добавлении дохода: {e}')


@bot.message_handler(func=lambda message: message.text == 'Добавить расход')
def expense_handler(message):
    try:
        categories = session.query(ExpenseCategory).all()
        keyboard = telebot.types.ReplyKeyboardMarkup(row_width=2)
        for category in categories:
            keyboard.add(category.name)
        keyboard.add('Добавить новую категорию')
        bot.send_message(message.chat.id, 
                         'Выбери категорию расхода или добавь новую.',
                         reply_markup=keyboard)
        bot.register_next_step_handler(message, expense_category_handler)
    except Exception as e:
        bot.send_message(message.chat.id, f'Произошла ошибка: {e}')
        logger.error(f'Ошибка при выборе категории расхода: {e}')


def add_expense_category(message, category_name):
    if category_name == 'Добавить новую категорию':
        bot.send_message(message.chat.id, 'Введи название новой категории.')
        bot.register_next_step_handler(message, new_category_name_handler)
        return

    category = session.query(ExpenseCategory).filter_by(name=category_name).first()
    if category is None:
        bot.send_message(message.chat.id,
                         'Категория не найдена. Попробуй еще раз.')
        return
    bot.send_message(message.chat.id,
                     'Введи сумму расхода:')
    bot.register_next_step_handler(message, expense_amount_handler, category)


@bot.message_handler(commands=['new_category'])
def expense_category_handler(message):
    category_name = message.text
    add_expense_category(message, category_name)


def new_category_name_handler(message):
    try:
        name = message.text
        category = session.query(ExpenseCategory).filter_by(name=name).first()
        if category is not None:
            bot.send_message(message.chat.id, 'Такая категория уже существует. '
                                              'Введи другое название:')
            bot.register_next_step_handler(message, new_category_name_handler)
        else:
            category = ExpenseCategory(name=name)
            session.add(category)
            session.commit()
            bot.send_message(message.chat.id, f'Категория "{name}" добавлена.')
            add_expense_category(message, name)
    except Exception as e:
        bot.send_message(message.chat.id, f'Произошла ошибка: {e}')
        logger.error(f'Произошла ошибка при добавлении категории расходов: {e}')


def expense_category_or_new_handler(message):
    category = session.query(ExpenseCategory).filter_by(name=category_name).first()
    if category is None:
        bot.send_message(message.chat.id,
                         'Введи название новой категории.')
        bot.register_next_step_handler(message, new_category_name_handler)
    else:
        add_expense_category(message, category.name)


def expense_amount_handler(message, category):
    amount = message.text
    try:
        amount_float = float(amount)
    except ValueError:
        bot.send_message(message.chat.id, 'Сумма расхода должна быть числом. '
                         'Попробуй ещё раз.')
        bot.register_next_step_handler(message, expense_amount_handler, 
                                       category)
        return

    bot.send_message(message.chat.id, 'Введи дату расхода в формате ГГГГ-ММ-ДД.')
    bot.register_next_step_handler(message, expense_date_handler, 
                                   category, amount_float)


def expense_date_handler(message, category, amount):
    date = message.text
    if not is_valid_date(date):
        bot.send_message(message.chat.id,
                         'Некорректный формат даты. Введи дату в формате ГГГГ-ММ-ДД.')
        bot.clear_step_handler_by_chat_id(message.chat.id)
        bot.register_next_step_handler(message, expense_date_handler, 
                                       category, amount)
        return
    bot.send_message(message.chat.id, 'Введи описание расхода.')
    bot.clear_step_handler_by_chat_id(message.chat.id)
    bot.register_next_step_handler(message, expense_description_handler, 
                                   category, amount, date)


def expense_description_handler(message, category, amount, date):
    description = message.text
    user = session.query(User).filter_by(telegram_id=message.chat.id).first()
    expense = Expense(user=user, category=category,
                      amount=amount, date=date, description=description)
    session.add(expense)
    session.commit()
    bot.send_message(message.chat.id, 
                     f'Расход на сумму {amount} для категории "{category.name}" добавлен.')
    menu_handler(message)


@bot.message_handler(func=lambda message: message.text == 'Посмотреть сумму расходов и доходов за период')
def balance_handler(message):
    bot.send_message(message.chat.id,
                     'Введи дату начала периода в формате ГГГГ-ММ-ДД.')
    bot.register_next_step_handler(message, balance_start_date_handler)


def balance_start_date_handler(message):
    if is_valid_date(message.text):
        start_date = datetime.datetime.strptime(message.text, '%Y-%m-%d')
        bot.send_message(message.chat.id, 
                         'Введи дату конца периода в формате ГГГГ-ММ-ДД.')
        bot.register_next_step_handler(message,
                                       balance_end_date_handler, start_date)
    else:
        bot.send_message(message.chat.id,
                         'Некорректная дата. '
                         'Попробуй ввести снова в формате ГГГГ-ММ-ДД.')
        bot.register_next_step_handler(message, balance_start_date_handler)


def balance_end_date_handler(message, start_date):
    if is_valid_date(message.text):
        end_date = datetime.datetime.strptime(message.text, '%Y-%m-%d')
        if end_date < start_date:
            bot.send_message(message.chat.id,
                             'Дата конца периода должна '
                             'быть больше даты начала периода. Попробуй снова.')
            bot.register_next_step_handler(message,
                                           balance_end_date_handler, start_date)
        else:
            user = get_or_create_user(message)
            income_sum = session.query(func.sum(Income.amount)).filter(Income.user == user, Income.date.between(start_date, end_date)).scalar() or 0
            expense_sum = session.query(func.sum(Expense.amount)).filter(Expense.user == user, Expense.date.between(start_date, end_date)).scalar() or 0
            balance = income_sum - expense_sum
            bot.send_message(message.chat.id,
                             f'Сумма доходов за период: {income_sum}\n'
                             f'Сумма расходов за период: {expense_sum}\n'
                             f'Баланс за период: {balance}')
            menu_handler(message)
            return
    bot.send_message(message.chat.id, 'Некорректная дата. ' 
                     'Попробуй ввести снова в формате ГГГГ-ММ-ДД.')
    bot.register_next_step_handler(message, balance_start_date_handler)


@bot.message_handler(func=lambda message: message.text == 'Информация')
def info_handler(message):
    user = session.query(User).filter_by(telegram_id=message.chat.id).first()
    expenses = session.query(Expense).filter_by(user=user).all()
    incomes = session.query(Income).filter_by(user=user).all()
    total_income = sum([income.amount for income in incomes])
    total_expense = sum([expense.amount for expense in expenses])
    balance = total_income - total_expense
    info_text = f'Общий доход: {total_income:.2f}\nОбщий расход: {total_expense:.2f}\nБаланс: {balance:.2f}'
    bot.send_message(message.chat.id, info_text)


bot.polling()
