from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base


engine = create_engine('sqlite:///finance_bot.db')
Session = sessionmaker(bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer)
    first_name = Column(String)
    last_name = Column(String)
    income = relationship('Income', back_populates='user')
    expense = relationship('Expense', back_populates='user')
    user_data = relationship('UserData', uselist=False, back_populates='user')


class UserData(Base):
    __tablename__ = 'user_data'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer)
    current_category_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', back_populates='user_data')
Base.metadata.create_all(engine)


class Income(Base):
    __tablename__ = 'incomes'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    amount = Column(Float)
    date = Column(String)
    description = Column(String)
    user = relationship('User', back_populates='income')


class ExpenseCategory(Base):
    __tablename__ = 'expense_categories'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    expenses = relationship('Expense', back_populates='category')


class Expense(Base):
    __tablename__ = 'expenses'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    category_id = Column(Integer, ForeignKey('expense_categories.id'))
    amount = Column(Float)
    date = Column(String)
    description = Column(String)
    user = relationship('User', back_populates='expense')
    category = relationship('ExpenseCategory', back_populates='expenses')  

Base.metadata.create_all(engine)
