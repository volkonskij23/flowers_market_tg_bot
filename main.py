import asyncio
import sqlite3
import datetime
import pytz
import httplib2
import apiclient.discovery
import re

from emoji import emojize
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.filters.state import State, StatesGroup
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hlink
from aiogram import html
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials


# Блок работы с базой данных


def connect_db(db_name):
    sqlite_connection = sqlite3.connect(
        r"../db/" + db_name + ".db", check_same_thread=False
    )
    return sqlite_connection


def create_users_db(db_name):
    connect = sqlite3.connect(r"./db/{}.db".format(db_name), check_same_thread=False)
    cursor = connect.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS {}(
        id INTEGER PRIMARY KEY AUTOINCREMENT ,
        user_id,
        name TEXT,
        nickname TEXT
        )""".format(
            db_name
        )
    )
    return connect


def create_orders_db(db_name):
    connect = sqlite3.connect(r"./db/{}.db".format(db_name), check_same_thread=False)
    cursor = connect.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS {}(
        id INTEGER PRIMARY KEY AUTOINCREMENT ,
        user_id,
        date_of_creation TEXT,
        name TEXT, 
        nickname TEXT,
        fio TEXT,
        tel_number TEXT,
        date TEXT,
        description TEXT,
        callback_type TEXT
        )""".format(
            db_name
        )
    )
    return connect


def do_commit(connect):
    connect.commit()


def user_check(connect, db_name, user_id):
    cursor = connect.cursor()
    info = cursor.execute(
        """SELECT * FROM {} WHERE user_id = {}""".format(db_name, user_id)
    )
    if info.fetchone() is None:
        return True
    else:
        return False


def db_user_add(connect, db_name, user_id, name, nickname):
    cursor = connect.cursor()
    cursor.execute(
        """INSERT INTO {}(user_id,
                                     name, 
                                     nickname) VALUES(?,?,?);""".format(
            db_name
        ),
        [user_id, name, nickname],
    )
    do_commit(connect)


def db_order_add(
    connect,
    db_name,
    user_id,
    name,
    nickname,
    fio,
    tel_number,
    date,
    description,
    callback_type,
):

    now = datetime.datetime.now(pytz.timezone("Europe/Moscow")).strftime(
        "%d-%m-%Y %H:%M"
    )
    cursor = connect.cursor()
    cursor.execute(
        """INSERT INTO {}(user_id,
                                     date_of_creation,
                                     name, 
                                     nickname,
                                     fio, 
                                     tel_number, 
                                     date,
                                     description,
                                     callback_type) VALUES(?,?,?,?,?,?,?,?,?);""".format(
            db_name
        ),
        [
            user_id,
            now,
            name,
            nickname,
            fio,
            tel_number,
            date,
            description,
            callback_type,
        ],
    )
    do_commit(connect)


def update_user_order(connect, db_name, user_id, callback_type):
    cursor = connect.cursor()
    result = []
    for row in cursor.execute(
        "SELECT *  FROM {} WHERE user_id={} and callback_type='' and date<>'';".format(
            db_name, user_id
        )
    ):
        result.append(list(row))
    res = cursor.execute(
        "UPDATE {} SET callback_type=? WHERE user_id=? and callback_type='' and date<>'';".format(
            db_name
        ),
        [callback_type, user_id],
    )
    do_commit(connect)
    return result


def get_user_orders(connect, db_name, user_id):
    cursor = connect.cursor()
    result = []
    for row in cursor.execute(
        "SELECT *  FROM {} WHERE user_id={};".format(db_name, user_id)
    ):
        result.append(list(row))
    return result


class Form(StatesGroup):
    quant_order = State()
    quant_fio = State()
    quant_number = State()
    quant_date = State()
    quant_type = State()
    quant_add_type = State()
    quant_add_description = State()
    quant_description = State()


SAMPLE_SPREADSHEET_ID = ""


CREDENTIALS_FILE = "token.json"
creds = ServiceAccountCredentials.from_json_keyfile_name(
    CREDENTIALS_FILE, ["https://www.googleapis.com/auth/spreadsheets"]
)
httpAuth = creds.authorize(httplib2.Http())

service = apiclient.discovery.build("sheets", "v4", http=httpAuth)
sheet = service.spreadsheets()


db_name = "users"
db_orders_name = "orders"
connect_users = create_users_db(db_name)
connect_orders = create_orders_db(db_orders_name)


API_TOKEN = ""
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher()


priv = "Здравствуйте, "
starttext = (
    emojize(":sparkles:")
    + "\nРады приветствовать Вас в нашем боте!\nЧат-бот активирован.\n\nМы формируем систему лояльности для наших клиентов и предлагаем Вам заполнить анкету для начисления бонусов.\nЗаполнив анкету, вы также становитесь участником розыгрыша подарков!"
    + emojize(":backhand_index_pointing_down:")
)
kb_start = [
    [types.KeyboardButton(text=("Заполнить анкету" + emojize(":dollar_banknote:")))],
    # [types.KeyboardButton(text=("Показать текущие события" + emojize(":rose:")))]
]


@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    # start block
    await state.set_state(None)

    me = message.from_user
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    markup = types.ReplyKeyboardMarkup(keyboard=kb_start, resize_keyboard=True)
    await message.answer(
        priv + html.bold(html.quote(me.first_name)) + starttext, reply_markup=markup
    )


@dp.callback_query()
async def callback_start(query: types.CallbackQuery, state: FSMContext):
    await state.set_state(None)
    markup = types.ReplyKeyboardMarkup(keyboard=kb_start, resize_keyboard=True)
    await query.message.answer(
        "Выберите интересующую категорию" + emojize(":backhand_index_pointing_down:"),
        reply_markup=markup,
    )


@dp.message(
    lambda message: message.text == "Заполнить анкету" + emojize(":dollar_banknote:")
)
async def order(message: types.Message, state: FSMContext):
    kb_back = [
        [types.KeyboardButton(text=("Назад" + emojize(":right_arrow_curving_left:")))]
    ]
    markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)

    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    await message.answer("Введите свое имя и фамилию", reply_markup=markup)
    await state.set_state(Form.quant_order)


@dp.message(
    lambda message: message.text == "Назад" + emojize(":right_arrow_curving_left:")
)
async def start_menu(message: types.Message, state: FSMContext):

    await state.set_state(None)

    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    markup = types.ReplyKeyboardMarkup(keyboard=kb_start, resize_keyboard=True)
    await message.answer(
        "Выберите интересующую категорию" + emojize(":backhand_index_pointing_down:"),
        reply_markup=markup,
    )


@dp.message(Form.quant_order)
async def add_fio(message: types.Message, state: FSMContext):
    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    if re.search(r"[^а-яА-Яa-zA-Z\s]+", str(message.text.lower())):
        await message.answer(
            name
            + ", пожалуйста введите фамилию и имя без использования посторонних знаков"
            + emojize(":neutral_face:")
        )
        return

    else:
        fio = message.text
        await state.update_data(fio=fio)
        kb_back = [
            [
                types.KeyboardButton(
                    text=("Назад" + emojize(":right_arrow_curving_left:"))
                )
            ]
        ]
        markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)
        await message.answer(
            "Введите свой номер телефона (Только цифры, без кода страны, пробелов, плюсиков и любых других символов. Например: 9215467854)",
            reply_markup=markup,
        )
        await state.set_state(Form.quant_fio)


@dp.message(Form.quant_fio)
async def add_number(message: types.Message, state: FSMContext):
    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    if re.search(r"[\D]+", str(message.text.lower())):
        await message.answer(
            name
            + ", пожалуйста введите телефонный номер без использования посторонних знаков"
            + emojize(":neutral_face:")
        )
        return

    else:
        telephone = message.text
        await state.update_data(telephone=telephone)
        kb_back = [
            [
                types.KeyboardButton(
                    text=(
                        "Продолжить заполнение информации о событиях"
                        + emojize(":check_mark:")
                    )
                )
            ],
            [
                types.KeyboardButton(
                    text=("Завершить заполнение анкеты" + emojize(":cross_mark:"))
                )
            ],
        ]

        markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)

        await message.answer("Спасибо за представленную информацию!")
        await message.answer(
            "А еще вы можете воспользоваться услугой цветочный консьерж, оставьте информацию о событиях, когда вам может понадобиться наша помощь. Цветочный консьерж напомнит вам за три дня о памятной дате и мы организуем доставку цветов под ваше событие, начислим и спишем оплату частично бонусами.",
            reply_markup=markup,
        )
        await state.set_state(Form.quant_number)


@dp.message(
    Form.quant_number,
    lambda message: message.text
    == "Продолжить заполнение информации о событиях" + emojize(":check_mark:"),
)
async def pre_add_desc(message: types.Message, state: FSMContext):

    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    kb_back = [
        [types.KeyboardButton(text=("Назад " + emojize(":right_arrow_curving_left:")))]
    ]
    markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)
    await message.answer(
        "Введите описание события (например: годовщина свадьбы, день рождение жены, день матери и т.д.)",
        reply_markup=markup,
    )
    await state.set_state(Form.quant_add_description)


@dp.message(Form.quant_add_description)
async def add_desc(message: types.Message, state: FSMContext):
    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    if message.text == "Назад " + emojize(":right_arrow_curving_left:"):
        await state.set_state(Form.quant_number)
        kb_back = [
            [
                types.KeyboardButton(
                    text=(
                        "Продолжить заполнение информации о событиях"
                        + emojize(":check_mark:")
                    )
                )
            ],
            [
                types.KeyboardButton(
                    text=("Завершить заполнение анкеты" + emojize(":cross_mark:"))
                )
            ],
        ]

        markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)

        await message.answer(
            "Желаете продолжить?" + emojize(":backhand_index_pointing_down:"),
            reply_markup=markup,
        )

    else:
        delivery_description = message.text
        await state.update_data(delivery_description=delivery_description)
        await state.update_data(flag="True")

        kb_back = [
            [
                types.KeyboardButton(
                    text=("Назад " + emojize(":right_arrow_curving_left:"))
                )
            ]
        ]
        markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)
        await message.answer(
            "Укажите дату события в формате ДД.ММ", reply_markup=markup
        )
        await state.set_state(Form.quant_date)


@dp.message(
    Form.quant_date,
    lambda message: message.text == "Назад " + emojize(":right_arrow_curving_left:"),
)
async def back_2(message: types.Message, state: FSMContext):

    await state.set_state(Form.quant_number)

    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    kb_back = [
        [
            types.KeyboardButton(
                text=(
                    "Продолжить заполнение информации о событиях"
                    + emojize(":check_mark:")
                )
            )
        ],
        [
            types.KeyboardButton(
                text=("Завершить заполнение анкеты" + emojize(":cross_mark:"))
            )
        ],
    ]

    markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)

    await message.answer(
        "Желаете продолжить?" + emojize(":backhand_index_pointing_down:"),
        reply_markup=markup,
    )


@dp.message(Form.quant_date)
async def add_date(message: types.Message, state: FSMContext):
    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    if re.search(r"\d\d\.\d\d", str(message.text.lower())) is None:
        await message.answer(
            name
            + ", пожалуйста введите корректную дату в формате ДД.ММ (например 08.03)"
            + emojize(":neutral_face:")
        )
        return

    else:
        day = message.text.split(".")[0]
        month = message.text.split(".")[1]
        month_days = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        if int(month) not in range(1, 13):
            await message.answer(
                name
                + ", указанного месяца не существует. Введите корректную дату в формате ДД.ММ (например 08.03)"
                + emojize(":neutral_face:")
            )
            return

        if int(day) == 0 or int(day) > month_days[int(month) - 1]:
            day_name = "дней" if month_days[int(month) - 1] != 31 else "день"
            await message.answer(
                name
                + ", в указанном месяце {} {}. Введите корректную дату в формате ДД.ММ (например 08.03)".format(
                    month_days[int(month) - 1], day_name
                )
                + emojize(":neutral_face:")
            )
            return
        delivery_date = message.text
        await state.update_data(delivery_date=delivery_date)
        data = await state.get_data()
        db_order_add(
            connect_orders,
            db_orders_name,
            user_id,
            user_name,
            nickname,
            data["fio"],
            data["telephone"],
            data["delivery_date"],
            data["delivery_description"],
            "",
        )

        kb_back = [
            [
                types.KeyboardButton(
                    text=(
                        "Продолжить заполнение информации о событиях"
                        + emojize(":check_mark:")
                    )
                )
            ],
            [
                types.KeyboardButton(
                    text=("Завершить заполнение анкеты" + emojize(":cross_mark:"))
                )
            ],
        ]
        markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)
        await message.answer(
            "Событие добавлено!\n\nЖелаете продолжить?", reply_markup=markup
        )
        await state.set_state(Form.quant_type)


@dp.message(
    Form.quant_type,
    lambda message: message.text
    == "Завершить заполнение анкеты" + emojize(":cross_mark:"),
)
async def pre_add_callback_type(message: types.Message, state: FSMContext):
    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)
    kb_back = [
        [types.KeyboardButton(text=("Telegram" + emojize(":blue_circle:")))],
        [types.KeyboardButton(text=("WhatsApp" + emojize(":green_circle:")))],
    ]

    markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)
    await message.answer(
        "Выберите удобный способ связи для напоминания о событии", reply_markup=markup
    )
    await state.set_state(Form.quant_add_type)


@dp.message(
    Form.quant_type,
    lambda message: message.text
    == "Продолжить заполнение информации о событиях" + emojize(":check_mark:"),
)
async def post_add_callback_type(message: types.Message, state: FSMContext):
    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    kb_back = [
        [types.KeyboardButton(text=("Назад " + emojize(":right_arrow_curving_left:")))]
    ]
    markup = types.ReplyKeyboardMarkup(keyboard=kb_back, resize_keyboard=True)
    await message.answer(
        "Введите описание события (например: годовщина свадьбы, день рождение жены, день матери и т.д.)",
        reply_markup=markup,
    )
    await state.set_state(Form.quant_add_description)


@dp.message(Form.quant_add_type)
async def add_callback_type(message: types.Message, state: FSMContext):
    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    if message.text == "Telegram" + emojize(":blue_circle:"):
        callback_type = "Telegram"
    else:
        callback_type = "WhatsApp"

    await state.update_data(flag="True")

    google_values = []
    now = datetime.datetime.now(pytz.timezone("Europe/Moscow")).strftime(
        "%d-%m-%Y %H:%M"
    )
    for row in update_user_order(
        connect_orders, db_orders_name, user_id, callback_type
    ):
        google_values.append(
            [user_id, nickname, now, row[5], row[6], row[7], row[8], callback_type]
        )

    resp = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range="A1:J")
        .execute()
    )
    index = (
        len(resp["values"]) + 1
        if len(resp["values"][1][0]) != ""
        else len(resp["values"])
    )
    rozigrish_date = resp["values"][1][-1]
    body = {"values": google_values}
    SAMPLE_RANGE_NAME = "A{}:H".format(index)

    service.spreadsheets().values().update(
        spreadsheetId=SAMPLE_SPREADSHEET_ID,
        range=SAMPLE_RANGE_NAME,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()

    await state.update_data(callback_type=callback_type)
    markup = types.ReplyKeyboardMarkup(keyboard=kb_start, resize_keyboard=True)
    await message.answer(
        html.bold(html.quote(name))
        + ", благодарим Вас за заполненную анкету!\n"
        + "Напоминаем, что розыгрыш состоится {} в прямой трансляции в наших социальных сетях: ".format(
            rozigrish_date
        )
        + html.link("наш инстаграм", "https://instagram.com/kgarden_msk")
        + "*. Рекомендуем подписаться, чтобы не пропустить.\n\n* Соцсеть Инстаграм принадлежат компании Мета, которая признана экстремистской организацией. Её деятельность запрещена в России.",
        reply_markup=markup,
    )
    await state.set_state(None)


@dp.message(
    Form.quant_number,
    lambda message: message.text
    == "Завершить заполнение анкеты" + emojize(":cross_mark:"),
)
async def add_result(message: types.Message, state: FSMContext):
    name = message.from_user.first_name
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    nickname = message.from_user.username
    if user_check(connect_users, db_name, user_id):
        db_user_add(connect_users, db_name, user_id, user_name, nickname)

    data = await state.get_data()
    now = datetime.datetime.now(pytz.timezone("Europe/Moscow")).strftime(
        "%d-%m-%Y %H:%M"
    )
    resp = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range="A1:J")
        .execute()
    )
    index = (
        len(resp["values"]) + 1
        if len(resp["values"][1][0]) != 0
        else len(resp["values"])
    )
    rozigrish_date = resp["values"][1][-1]

    if "flag" not in data.keys():
        db_order_add(
            connect_orders,
            db_orders_name,
            user_id,
            user_name,
            nickname,
            data["fio"],
            data["telephone"],
            "",
            "",
            "",
        )

        body = {
            "values": [
                [user_id, nickname, now, data["fio"], data["telephone"], "", "", ""],
            ]
        }
        SAMPLE_RANGE_NAME = "A{}:H".format(index)

        service.spreadsheets().values().update(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            range=SAMPLE_RANGE_NAME,
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

    markup = types.ReplyKeyboardMarkup(keyboard=kb_start, resize_keyboard=True)
    await message.answer(
        html.bold(html.quote(name))
        + ", благодарим Вас за заполненную анкету!\n"
        + "Напоминаем, что розыгрыш состоится {} в прямой трансляции в наших социальных сетях: ".format(
            rozigrish_date
        )
        + html.link("наш инстаграм", "https://instagram.com/kgarden_msk")
        + "*. Рекомендуем подписаться, чтобы не пропустить.\n\n* Соцсеть Инстаграм принадлежат компании Мета, которая признана экстремистской организацией. Её деятельность запрещена в России.",
        reply_markup=markup,
    )

    await state.set_state(None)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.get_event_loop().run_until_complete(main())
