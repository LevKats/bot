import telebot
from telebot import types
from telebot import apihelper

from db_requests import DBRequests
from db_requests import Task

from contextlib import closing
from functools import partial
import psycopg2
import re
import os


IS_LOCAL = os.environ['IS_LOCAL'] == 'True'
TOKEN = os.environ['TOKEN']

if IS_LOCAL:
    PROXIE_IP = os.environ['PROXIE_IP']
    PROXIE_PORT = os.environ['PROXIE_PORT']
    USE_PROXIE = os.environ['USE_PROXIE'] == 'True'
    DB_PASSWORD = os.environ['DB_PASSWORD']
    DB_USERNAME = os.environ['DB_USERNAME']
    DB_NAME = os.environ['DB_NAME']
    DB_URL = os.environ['DB_URL']
else:
    DB_URL = os.environ['DATABASE_URL']
    PROXIE_IP = None
    PROXIE_PORT = None
    DB_PASSWORD = None
    DB_USERNAME = None
    DB_NAME = None
    USE_PROXIE = False


if USE_PROXIE:
    apihelper.proxy = {
        'https': 'socks5h://{}:{}'.format(PROXIE_IP, PROXIE_PORT)
    }

bot = telebot.TeleBot(TOKEN)


def delete_keyboard(message):
    markup = types.ReplyKeyboardRemove(selective=False)
    bot.send_message(chat_id=message.chat.id, text="Deleting keyboard", reply_markup=markup)


def create_menu_keyboard(is_neady, is_helper):
    keyboard = telebot.types.ReplyKeyboardMarkup()
    col1 = ('Взять задачу', '') if not is_helper else ('Отказаться', 'Помог',)
    col2 = ('Помогите с задачей!', '') if not is_neady else ('Решилось само', '')
    keyboard.row(col1[0], col2[0], 'О боте')
    if col1[1] != '':
        keyboard.row(col1[1], 'Готовые проги')
    else
        keyboard.row('Готовые проги')
    return keyboard


def create_continue_menu():
    keyboard = telebot.types.ReplyKeyboardMarkup()
    keyboard.row('Ок')
    return keyboard


def start(person_id, chat_id):
    is_neady = db.get_task_id_to_needy(person_id) is not None
    is_helper = db.get_task_id_to_helper(person_id) is not None
    bot.send_message(chat_id, 'Что будем делать?',
                     reply_markup=create_menu_keyboard(is_neady, is_helper))


def start_mes(message):
    # print(message)
    # delete_keyboard(message)
    start(message.chat.id, message.chat.id)


@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, 'Привет!')
    start_mes(message)


def get_task_id_func():
    task_id = 0
    while True:
        yield task_id
        task_id += 1


def make_description(task, message):
    description = message.text
    bot.send_message(message.chat.id, "вставьте скриншот ошибки как картинку")
    bot.register_next_step_handler(message, partial(make_image, Task(
        id=task.id, asks=task.asks, helper=None, description=description, image=None, code=None
    )))


def make_image(task, message):
    if message.content_type == 'photo':
        file_id = message.json['photo'][-1]['file_id']
    else:
        bot.send_message(message.chat.id, "вставьте скриншот ошибки как картинку")
        bot.register_next_step_handler(message, partial(make_image, task))
        return
    image = file_id

    file_info = bot.get_file(file_id)
    ''' file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(TOKEN, file_info.file_path),
                        proxies=apihelper.proxy) '''
    file = bot.download_file(file_info.file_path)

    if db.load_image(image) is None:
        db.save_image(image, file)
    '''
    data = load_image(image)
    bot.send_photo(message.chat.id, data)
    '''

    bot.send_message(message.chat.id, "вставьте ссылку на https://pastebin.com/ с вашим кодом")
    bot.register_next_step_handler(message, partial(make_code, Task(
        id=task.id, asks=task.asks, helper=None, description=task.description, image=image, code=None
    )))


def make_code(task, message):
    code = message.text
    if re.match(r'^https://pastebin.com/\w+$', code) is None:
        bot.send_message(message.chat.id, "вставьте ссылку на https://pastebin.com/ с вашим кодом")
        bot.register_next_step_handler(message, partial(make_code, task))
        return

    bot.send_message(message.chat.id, "Ожидайте")
    task = Task(id=task.id, asks=task.asks, helper=None,
                description=task.description, image=task.image, code=code)
    db.ask_help(task)
    bot.send_message(message.chat.id, 'Продолжаем',
                     reply_markup=create_continue_menu())
    bot.register_next_step_handler(message, start_mes)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def text(message):
    is_neady = db.get_task_id_to_needy(message.chat.id) is not None
    is_helper = db.get_task_id_to_helper(message.chat.id) is not None
    if message.text == 'Взять задачу' and not is_helper:
        task = db.get_next_task_to_helper()
        if task is not None:
            db.take_task_by_helper(task.id, message.chat.id)
            try:
                name = bot.get_chat_member(task.asks, task.asks).user.username
            except Exception:
                name = "ошибка"
            bot.send_message(message.chat.id, "Тебе нужно помочь @{}".format(name))
            bot.send_message(message.chat.id, '''
            Описание проблемы:
            {}
            Код:
            {}
            '''.format(task.description, task.code))
            bot.send_photo(message.chat.id, db.load_image(task.image))
        else:
            bot.send_message(message.chat.id, "Пока нет задач")
        bot.send_message(message.chat.id, 'Продолжаем',
                         reply_markup=create_continue_menu())
        bot.register_next_step_handler(message, start_mes)
    elif message.text == 'Отказаться' and is_helper:
        db.helper_drop_task(message.chat.id)
        bot.send_message(message.chat.id, 'Продолжаем',
                         reply_markup=create_continue_menu())
        bot.register_next_step_handler(message, start_mes)
    elif message.text == 'Помог' and is_helper:
        db.remove_task(db.get_task(db.get_task_id_to_helper(message.chat.id)))
        bot.send_message(message.chat.id, 'Продолжаем',
                         reply_markup=create_continue_menu())
        bot.register_next_step_handler(message, start_mes)
    elif message.text == 'Решилось само' and is_neady:
        db.needy_drop_task(message.chat.id)
        bot.send_message(message.chat.id, 'Продолжаем',
                         reply_markup=create_continue_menu())
        bot.register_next_step_handler(message, start_mes)
    elif message.text == 'Помогите с задачей!' and not is_neady:
        delete_keyboard(message)
        task_id = get_task_id_func().__next__()
        bot.send_message(message.chat.id, "Опишите проблему")
        bot.register_next_step_handler(message, partial(make_description, Task(
            id=task_id, asks=message.chat.id, helper=None, description=None, image=None, code=None
        )))
    elif message.text == 'О боте':
        bot.send_message(message.chat.id, """
        Бот создан @LevKats, кидать тяжелые и не очень предметы в него
        Количество решаемых сейчас задач {}
        Количество оставшихся задач {}
        """.format(str(db.get_number_of_being_solved()), str(db.get_number_of_unsolved())))
        bot.send_message(message.chat.id, 'Продолжаем',
                         reply_markup=create_continue_menu())
        bot.register_next_step_handler(message, start_mes)
    elif message.text == 'Готовые проги':
        bot.send_message(message.chat.id, """
                Возможно, готовые задачи будут появляться здесь https://cloud.mail.ru/public/2vHt/3RRNy3nuz
                """.format(str(db.get_number_of_being_solved()), str(db.get_number_of_unsolved())))
        bot.send_message(message.chat.id, 'Продолжаем',
                         reply_markup=create_continue_menu())
        bot.register_next_step_handler(message, start_mes)
    else:
        bot.send_message(message.chat.id, "Проблема с командой")
        bot.send_message(message.chat.id, 'Продолжаем',
                         reply_markup=create_continue_menu())
        bot.register_next_step_handler(message, start_mes)


if __name__ == "__main__":
    with closing(
            psycopg2.connect(dbname=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD, host=DB_URL) if IS_LOCAL
            else psycopg2.connect(DB_URL, sslmode='require')

    ) as conn:
        with conn.cursor() as cursor:
            db = DBRequests(connection=conn, cursor=cursor)
            bot.polling(none_stop=True, interval=0)
