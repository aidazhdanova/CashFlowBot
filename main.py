from functools import wraps
import telebot
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine
import os
import sys
import logging
from dotenv import load_dotenv
from models import Expense, ExpenseCategory, Income, User, UserData
from telebot import types

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

load_dotenv()

logging.FileHandler('logg.log')

logging.basicConfig(
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO
                    )
logger = logging.getLogger(__name__)

database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

token = os.getenv('TOKEN')
bot = telebot.TeleBot(token)


commands = ['Доход', 'Расход', 'Информация']
commands_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                              row_width=2)
for command in commands:
    commands_keyboard.add(types.KeyboardButton(command))


def cached(func):
    cache = {}

    @wraps(func)
    def wrapper(*args):
        if args in cache:
            return cache[args]
        result = func(*args)
        cache[args] = result
        return result
    return wrapper


@cached
def get_user(telegram_id):
    try:
        return session.query(User).get(telegram_id)
    except NoResultFound:
        return None


@bot.message_handler(commands=['menu'])
def menu_handler(message):
    bot.send_message(
                    message.chat.id, 'Выбери команду.',
                    reply_markup=commands_keyboard)


@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        user = session.query(User).filter_by(telegram_id=message.chat.id).first()

        if user is None:
            user = User(telegram_id=message.chat.id)
            session.add(user)
            session.commit()
            user.user_data = UserData(telegram_id=message.chat.id)
            session.commit()
            bot.send_message(message.chat.id,
                             'Привет! Я помогу тебе вести учёт финансов. '
                             'Введи /menu, чтобы узнать все доступные команды.')
        else:
            bot.send_message(message.chat.id,
                             'Ты уже зарегистрирован. '
                             'Напиши /info, чтобы узнать свой баланс или /menu, '
                             'чтобы узнать все доступные команды.')
    except SQLAlchemyError:
        bot.send_message(message.chat.id,
                         'Кажется, что-то пошло не так. Попробуй позже.')
        logger.error(f'Ошибка при обработке команды start {e}.')


@bot.message_handler(func=lambda message: message.text == 'Доход')
def income_handler(message):
    bot.send_message(message.chat.id, 'Введи сумму дохода.')
    bot.register_next_step_handler(message, income_amount_handler)


def income_amount_handler(message):
    try:
        amount = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректная сумма. Введи число.')
        return
    bot.send_message(message.chat.id,
                     'Введи дату дохода в формате ГГГГ-ММ-ДД.')
    bot.register_next_step_handler(message, income_date_handler, amount)


def income_date_handler(message, amount):
    try:
        date = message.text
        bot.send_message(message.chat.id, 'Введи описание дохода.')
        bot.register_next_step_handler(message, income_description_handler,
                                       amount, date)
    except Exception as e:
        bot.send_message(message.chat.id, 
                         'Произошла ошибка при добавлении описания дохода. '
                         'Попробуй еще раз.')
        logger.error(f'Ошибка при обработке описания дохода: {e}')


def income_description_handler(message, amount, date):
    try:
        description = message.text
        user = session.query(User).filter_by(telegram_id=message.chat.id).first()
        income = Income(user=user, amount=amount,
                        date=date, description=description)
        session.add(income)
        session.commit()
        bot.send_message(message.chat.id, f'Доход на сумму {amount} добавлен.')
    except Exception as e:
        bot.send_message(message.chat.id, 'Произошла ошибка при добавлении дохода. '
                         'Попробуй еще раз.')
        logger.error(f'Ошибка при добавлении дохода: {e}')


@bot.message_handler(func=lambda message: message.text == 'Расход')
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
    amount_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    amount_keyboard.add('Назад')

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
                     'Введи сумму расхода:', 
                     reply_markup=amount_keyboard)
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
    category_name = message.text
    if category_name == 'Назад':
        menu_handler(message)
    else:
        category = session.query(ExpenseCategory).filter_by(name=category_name).first()
        if category is None:
            bot.send_message(message.chat.id, 
                             'Введи название новой категории.')
            bot.register_next_step_handler(message, new_category_name_handler)
        else:
            add_expense_category(message, category.name)


def expense_amount_handler(message, category):
    amount = float(message.text)
    bot.send_message(message.chat.id,
                     'Введи дату расхода в формате ГГГГ-ММ-ДД.')
    bot.register_next_step_handler(message, expense_date_handler,
                                   category, amount)


def expense_date_handler(message, category, amount):
    try:
        date = message.text
        bot.send_message(message.chat.id, 'Введи описание расхода.')
        bot.register_next_step_handler(message, expense_description_handler, 
                                       category, amount, date)
    except Exception as e:
        bot.send_message(message.chat.id, 
                         'Произошла ошибка при обработке даты расхода. '
                         'Попробуй еще раз.')
        logger.error(f'Ошибка в обработчике даты расхода: {e}')


def expense_description_handler(message, category, amount, date):
    description = message.text
    user = session.query(User).filter_by(telegram_id=message.chat.id).first()
    expense = Expense(user=user, category=category,
                      amount=amount, date=date, description=description)
    session.add(expense)
    session.commit()
    bot.send_message(message.chat.id, 
                     f'Расход на сумму {amount} для категории "{category.name}" добавлен.')


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
