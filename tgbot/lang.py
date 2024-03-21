from typing import Any, Literal

# noinspection PyPackageRequirements
from telebot.types import BotCommand

from config import ts
from tgbot.request import request


def end(lang: str):
    def closure_ru(num_diff: int):
        num_diff = str(num_diff)
        if (
            num_diff[-2:] in ("11", "12", "13", "14")
            or num_diff[-1] == "0"
            or num_diff[-1] in ("5", "6", "7", "8", "9")
        ):
            return "дней"
        elif num_diff[-1] in ("2", "3", "4"):
            return "дня"
        elif num_diff[-1] == "1":
            return "день"

    def closure_en(num_diff: int):
        return "day" if num_diff == 1 else "days"

    if lang == "ru":
        return closure_ru
    else:
        return closure_en


translation = {
    "func": {
        "deldate": {
            "ru": lambda x: f"<b>{x} {end('ru')(x)} до удаления</b>",
            "en": lambda x: f"<b>{x} {end('en')(x)} before delete</b>",
        },
    },
    "arrays": {
        "relative_date_list": {
            "ru": (
                "Сегодня",
                "Завтра",
                "Послезавтра",
                "Вчера",
                "Позавчера",
                "Через",
                "назад",
                end("ru"),
            ),
            "en": (
                "Today",
                "Tomorrow",
                "Day after tomorrow",
                "Yesterday",
                "Day before yesterday",
                "After",
                "ago",
                end("en"),
            ),
        },
        "account": {
            "ru": (
                "Событий в день",
                "Символов в день",
                "Событий в месяц",
                "Символов в месяц",
                "Событий в год",
                "Символов в год",
                "Событий всего",
                "Символов всего",
            ),
            "en": (
                "Events per day",
                "Symbols per day",
                "Events per month",
                "Symbols per month",
                "Events per year",
                "Symbols per year",
                "Total events",
                "Total symbols",
            ),
        },
        "months_list": {
            "ru": (
                (("Январь", 1), ("Февраль", 2), ("Март", 3)),
                (("Апрель", 4), ("Май", 5), ("Июнь", 6)),
                (("Июль", 7), ("Август", 8), ("Сентябрь", 9)),
                (("Октябрь", 10), ("Ноябрь", 11), ("Декабрь", 12)),
            ),
            "en": (
                (("January", 1), ("February", 2), ("March", 3)),
                (("April", 4), ("May", 5), ("June", 6)),
                (("July", 7), ("August", 8), ("September", 9)),
                (("October", 10), ("November", 11), ("December", 12)),
            ),
        },
        "week_days_list": {
            "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
            "en": ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"),
        },
        "week_days_list_full": {
            "ru": (
                "Понедельник",
                "Вторник",
                "Среда",
                "Четверг",
                "Пятница",
                "Суббота",
                "Воскресенье",
            ),
            "en": (
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ),
        },
        "months_name": {
            "ru": (
                "Январь",
                "Февраль",
                "Март",
                "Апрель",
                "Май",
                "Июнь",
                "Июль",
                "Август",
                "Сентябрь",
                "Октябрь",
                "Ноябрь",
                "Декабрь",
            ),
            "en": (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ),
        },
        "months_name2": {
            "ru": (
                "Января",
                "Февраля",
                "Марта",
                "Апреля",
                "Мая",
                "Июня",
                "Июля",
                "Августа",
                "Сентября",
                "Октября",
                "Ноября",
                "Декабря",
            ),
            "en": (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ),
        },
    },
    "text": {
        "page": {
            "ru": "Страница",
            "en": "Page",
        },
        "add_bot_to_group": {
            "ru": "Добавить бота в группу",
            "en": "Add bot to group",
        },
        "restore_to_default": {
            "ru": "Настройки по умолчанию",
            "en": "Set default settings",
        },
        "migrate": {
            "ru": """
Группа (<code>{from_chat_id}</code>) обновилась до супергруппы (<code>{to_chat_id}</code>).
<b>Из-за особенностей телеграма все предыдущие сообщения бота устарели и больше не могут быть использованы для взаимодействий с вашим аккаунтом.
Вызовите новые сообщения командами.</b>
""",
            "en": """
The group (<code>{from_chat_id}</code>) migrate into a supergroup (<code>{to_chat_id}</code>)
<b>Due to the nature of Telegram, all previous bot messages are outdated and can no longer be used to interact with your account.
Please call up new messages using commands.</b>
""",
        },
        "account_has_been_deleted": {
            "ru": "Ваш аккаунт удалён.",
            "en": "Your account has been deleted.",
        },
        "command_list": {
            "ru": (
                """
/start - Старт
/menu - Меню
/calendar - Календарь
/today - События на сегодня
/weather {city} - Погода сейчас
/forecast {city} - Прогноз погоды
/week_event_list - Список событий на ближайшие 7 дней
/dice - Кинуть кубик
/export - Сохранить мои события в csv
/help - Помощь
/settings - Настройки
/search {...} - Поиск
/id - Получить свой Telegram id

/commands - Этот список
""",
                """
/version - Версия бота
/sqlite - Бекап базы данных
/SQL {...} - Выполнить sql запрос к базе данных
/clear_logs - Очистить логи
""",
            ),
            "en": (
                """
/start - Start
/menu - Menu
/calendar - Calendar
/today - Events for today
/weather {city} - Weather now
/forecast {city} - Weather forecast
/week_event_list - List of events for the next 7 days
/dice - Roll a die
/export - Save my events to csv
/help - Help
/settings - Settings
/search {...} - Search
/id - Get your Telegram id

/commands - This list
""",
                """
/version - Bot version
/sqlite - Database backup
/SQL {...} - Execute an sql query to the database
/clear_logs - Clear logs
""",
            ),
        },
        "recover": {
            "ru": "Восстановить",
            "en": "Recover",
        },
        "leap": {
            "ru": "Високосный",
            "en": "leap",
        },
        "not_leap": {
            "ru": "Невисокосный",
            "en": "non-leap",
        },
        "trash_bin": {
            "ru": "В корзину",
            "en": "To trash bin",
        },
        "delete_permanently": {
            "ru": "Удалить навсегда",
            "en": "Delete permanently",
        },
        "changes_saved": {
            "ru": "Изменения сохранены",
            "en": "Changes saved",
        },
        "event_about_info": {
            "ru": "Информация о событии",
            "en": "Information about event",
        },
        "clean_bin": {
            "ru": "Очистить корзину",
            "en": "Clear basket",
        },
        "send_event_text": {
            "ru": "Отправьте текст события",
            "en": "Send the text of the event",
        },
        "recurring_events": {
            "ru": "Повторяющиеся события",
            "en": "Recurring events",
        },
        "week_events": {
            "ru": "Cобытия в ближайшие 7 дней",
            "en": "Events in the next 7 days",
        },
        "are_you_sure_edit": {
            "ru": "Вы точно хотите изменить тест события на",
            "en": "Are you sure you want to change the event text to",
        },
    },
    "messages": {
        "start": {
            "ru": """
Приветствую вас! Я - ваш личный календарь-помощник.
Здесь вы можете легко создавать события и заметки, которые будут автоматически помещаться в календарь. Используйте специальные эмодзи, чтобы добавить эффекты или сделать поиск еще удобнее!

📅 Календарь: Пользуйтесь удобным календарем на месяц и легко перемещайтесь между днями и месяцами.

🔍 Поиск: Ищите события по дате или тексту, так что ни одно важное мероприятие не ускользнет от вас!

🔔 Уведомления: Никогда не пропустите важные моменты! Настройте уведомления на определенное время или отключите их, когда вам удобно.

☁️ Погода: Хотите знать прогноз погоды в вашем городе? Просто спросите меня, и я предоставлю вам актуальные данные.

👑 Преимущества премиум-пользователей: Лимиты увеличены, а также доступна удобная мусорная корзина для удалённых событий.

Пользуйтесь всеми преимуществами бота, чтобы упорядочить свою жизнь и не упустить ни одного важного момента! Если у вас возникли вопросы, введите команду /help. Приятного использования! 🌟
""",
            "en": """
Greetings! I am your personal calendar assistant.
Here you can easily create events and notes that will be automatically placed on the calendar. Just use special emoji to add effects or make your search even more convenient!

📅 Calendar: Use a convenient monthly calendar and easily move between days and months.

🔍 Search: Search for events by date or text so that no important event escapes you!

🔔 Notifications: Never miss important moments! Set notification for a specific time or turn them off at your convenience.

☁️ Weather: Want to know the weather forecast for your city? Just ask me and I will provide you with up-to-date data.

👑 Premium user benefits: Limits have been increased and a handy recycle bin is available for events that have been removed.

Use all the advantages of the bot to streamline your life and not miss a single important moment! If you have any questions, enter the /help command. Happy using! 🌟
""",
        },
        "settings": {
            "ru": """⚙️ Настройки ⚙️

[<u>Язык</u>]
<b>{}</b>

[<u>Уменьшать ссылки</u>]*
<b>{}</b> <i>(True рекомендуется)</i>

[<u>Город</u>]**
<b>{}</b> <i>(Москва по умолчанию)</i>

[<u>Часовой пояс</u>]
<b>{}</b> <i>(3 по умолчанию)</i> У вас сейчас <b>{}</b>?

[<u>Порядок событий в сообщении</u>]
<b>{}</b> <i>(⬇️ по умолчанию)</i>

[<u>Уведомления</u>]
<b>{} {}</b> <i>(🔕 по умолчанию)</i>

[<u>Тема</u>]***
<b>{}</b> <i>(⬜️ по умолчанию)</i>

*(<a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
>www.youtube.com</a> <i>вместо полной ссылки</i>)
**<i>Ответьте на это сообщение с названием города</i>
***<i>Изменяет тёмные эмодзи на светлые</i>""",
            "en": """⚙️ Settings ⚙️

[<u>Language</u>]
<b>{}</b>

[<u>Minify links</u>]
<b>{}</b> <i>(True recommended)</i>

[<u>City</u>]
<b>{}</b> <i>(Moscow by default)</i>

[<u>Timezone</u>]
<b>{}</b> <i>(3 by default)</i> Do you have <b>{}</b> now?

[<u>Order of events in a message</u>]
<b>{}</b> <i>(⬇️ by default)</i>

[<u>Notifications</u>]
<b>{} {}</b> <i>(🔕 by default)</i>

[<u>Theme</u>]***
<b>{}</b> <i>(⬜️ by default)</i>

*(<a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
>www.youtube.com</a> <i>instead of full link</i>)
**<i>Reply to this message with a city name</i>
***<i>Changes dark emojis to light ones</i>""",
        },
        "help": {
            "title": {
                "ru": "📚 Помощь 📚",
                "en": "📚 Help 📚",
            },
            "page 1": {
                "ru": [
                    """
Добро пожаловать в раздел помощи.
Ниже вы можете выбрать кнопку с темой, чтобы прочитать подробнее.
Кнопки с текстом помечаются эмодзи 📄. Папка для кнопок помечается 📁. Вернуться назад из папки можно нажав  🔙.
""",
                    [
                        [{k.ljust(60, ts): v}]
                        for k, v in {
                            "📄 События": "Events",
                            "📄 Статусы": "Statuses",
                            "📄 Лимиты": "Limits",
                            "📂 Виды сообщений": "page 2",
                            "🔙": "mnm",
                        }.items()
                    ],
                ],
                "en": [
                    """
Welcome to the help section.
Below you can select the topic button to read more.
Buttons with text are marked with a smiley 📄. The button folder is marked with 📁. You can go back from a folder by pressing 🔙.
""",
                    [
                        [{k.ljust(60, ts): v}]
                        for k, v in {
                            "📄 Events": "Events",
                            "📄 Statuses": "Statuses",
                            "📄 Limits": "Limits",
                            "📂 Types of messages": "page 2",
                            "🔙": "mnm",
                        }.items()
                    ],
                ],
            },
            "page 2": {
                "ru": [
                    """
В боте есть разные виды сообщений, каждый из которых имеет свои особенности и функции.
Выберите кнопку с темой, чтобы прочитать подробнее.
""",
                    [
                        [{k.ljust(60, ts): v}]
                        for k, v in {
                            "📄 Календарь": "Calendar",
                            "📄 1 день": "1_day",
                            "📄 7 дней": "7_days",
                            "📄 Настройки": "Settings",
                            "📄 Корзина": "Basket",
                            "📄 Поиск": "Search",
                            "📄 Уведомления": "Notifications",
                            "🔙": "page 1",
                        }.items()
                    ],
                ],
                "en": [
                    """
The bot has different types of messages, each of which has its own characteristics and functions.
Select a topic button to read more.
""",
                    [
                        [{k.ljust(60, ts): v}]
                        for k, v in {
                            "📄 Calendar": "Calendar",
                            "📄 1 day": "1_day",
                            "📄 7 days": "7_days",
                            "📄 Settings": "Settings",
                            "📄 Basket": "Basket",
                            "📄 Search": "Search",
                            "📄 Notifications": "Notifications",
                            "🔙": "page 1",
                        }.items()
                    ],
                ],
            },
            "Events": {
                "ru": """
<u><b>События</b></u>

Событие - это текстовая заметка на определенную дату. Каждое событие помечается уникальным номером (id) и может иметь свой статус. По умолчанию статус устанавливается как "⬜️". Статус можно изменить с помощью кнопки "🏷" в сообщении на день.

В сообщении на день есть кнопки для изменения или удаления событий. Если событий в сообщении несколько, то такие кнопки предлагают выбрать конкретное. <b>Если событие одно, то кнопки сразу выбирают его.</b>
""",
                "en": """
<u><b>Events</b></u>

An event is a textual note for a specific date. Each event is marked with a unique identifier (id) and can have its own status. By default, the status is set to "⬜️". The status can be changed using the "🏷" button in the message for a day.

The message for the day has buttons for changing or deleting events. If there are several events in the message, then such buttons offer to select a specific one. <b>If there is only one event, then the buttons select it immediately.</b>
""",
            },
            "Statuses": {
                "ru": """
<u><b>Статусы</b></u>

Статус - это один или несколько эмодзи для пометки события или добавления разных эффектов.
Статусы разделяются на три группы: "Важность", "Разное" и "Эффекты".

Важность
└─ Статусы для пометки важности или готовности события.

Разное
└─ Разные статусы.

Эффекты
└─ Статусы, добавляющие эффекты к событиям.


Статусы "🗒" (Список) и "🧮" (Нумерованный список) размечают каждую строку своими эмодзи.
Если поставить "-- " перед строкой, то на этой строке такая разметка применяться не будет.

<b>Событие может иметь максимум 5 статусов.</b>

Существуют несовместимые статусы.
Их нельзя поместить вместе на одном событии.
Если у вас стоит одно событие из пары, то поставить второе вы не сможете.
Вот полный список несовместимых статусов:
"🔗" (Ссылка) и "💻" (Код)
"🪞" (Скрыто) и "💻" (Код)
"🔗" (Ссылка) и "⛓" (Без сокращения ссылок)
"🧮" (Нумерованный список) и "🗒" (Список)

<b>Эффекты на статусах применяются только на отображении событий в сообщении.</b> Сам текст события не меняется.
""",
                "en": """
<u><b>Statuses</b></u>

Status - this is one or several emojis used to mark an event or add different effects.
Statuses are divided into three groups: "Importance," "Miscellaneous," and "Effects."

Importance
└─ Statuses for marking the importance or readiness of an event.

Miscellaneous
└─ Miscellaneous statuses.

Effects
└─ Statuses that add effects to the events.

The statuses "🗒" (List) and "🧮" (Numbered list) annotate each line with their emojis.
If you put "--" in front of a line, then this markup do not apply on this line.

<b>An event can have a maximum of 5 statuses.</b>

There are incompatible statuses.
They cannot be placed together on the same event.
If you have one event out of a pair, then you will not be able to put the second one.
Here is the complete list of incompatible statuses:
"🔗" (Link) and "💻" (Code)
"🪞" (Hidden) and "💻" (Code)
"🔗" (Link) and "⛓" (No link abbreviation)
"🧮" (Numbered list) and "🗒" (List)

<b>Effects on statuses are applied only on the display of events in the message.</b> The text of the event itself does not change.
""",
            },
            "Limits": {
                "ru": """
<u><b>Лимиты</b></u>

Для разных типов пользователей существуют различные лимиты на использование бота. Лимиты могут касаться как количества событий, так и количества символов.

По умолчанию у обычного пользователя доступны следующие лимиты:

<b>20</b> событий в день,
<b>4000</b> символов в день,
<b>75</b> событий в месяц,
<b>10000</b> символов в месяц,
<b>500</b> событий в год,
<b>80000</b> символов в год.
Максимальный <b>общий</b> лимит для обычного пользователя составляет <b>500</b> событий и <b>100000</b> символов.

Если вы превысите лимиты, вы не сможете добавлять новые события и добавлять новый текст к событиям. Чтобы освободить место под новые события, вы можете удалять старые события или сократить их текст.
""",
                "en": """
<u><b>Limits</b></u>

For different types of users, there are different limits on using the bot. These limits may apply to both the number of events and the number of characters.

By default, regular users have the following limits:

<b>20</b> events per day
<b>4000</b> characters per day
<b>75</b> events per month
<b>10000</b> characters per month
<b>500</b> events per year
<b>80000</b> characters per year
The maximum <b>general</b> limit for a normal user is <b>500</b> events and <b>100000</b> characters.

If you exceed the limits, you will not be able to add new events and add new text to events. To make a room for new events, you can delete old events or shorten their text.
""",
            },
            "Calendar": {
                "ru": """
<u>Виды сообщений > <b>Календарь</b></u>

Вы можете выбрать дату, нажав на кнопку с номером дня.
Кнопками внизу вы можете выбрать год и месяц.
Кнопкой "⟳" можно вернуться к текущей дате и выбрать текущий день.

При нажатии кнопки с датой в первом ряду вы попадете в список месяцев.
Там вы сможете выбрать месяц выбранного года.

В календаре существуют специальные обозначения для дней с событиями или с сегодняшним числом.
Вот значения символов обозначений:
"#" - Сегодняшний номер дня (отображается в любых месяцах).
"*" - В этот день есть события.
"!" - В этот день или в этот день другого года есть событие с повторяющимся статусом. Например, день рождения "🎉" или праздник "🎊".
""",
                "en": """
<u>Types of messages > <b>Calendar</b></u>

You can select a date by clicking on the day number button.
You can select the year and month using the buttons below.
With the "⟳" button, you can return to the current date and select the current day.

When you click on a date button in the first row, you will see the list of months.
There, you can choose a month within the selected year.

In the calendar, there are special symbols to indicate days with events or today's date.
Here are the meanings of the symbol notations:
"#" - Today's date (displayed in any month).
"*" - Events are scheduled for this day.
"!" - This day or the same date in a different year has a recurring event status. For example, a birthday "🎉" or a holiday "🎊".
""",
            },
            "1_day": {
                "ru": """
<u>Виды сообщений > <b>1 день</b></u>

Сообщение отображает события на один день.

Перед самим текстом события размещается строка с информацией о событии.
Например: <pre>1.3.⬜️</pre>
Тут 1 это порядковый номер события в сообщении, 3 это id события, а ⬜️ это статусы, перечисленные через запятую.

Если событий на эту дату становится больше 10, то остальные события размещаются на других страницах. Максимум 10 событий на одну страницу. Кнопки переключения страниц появляются под кнопками управления и пронумерованы номерами страниц.

Порядок расположения событий в сообщении можно изменить в настройках. По умолчанию события располагаются по возрастанию id (от малого к большему).

Кнопки управления:
➕ - Добавить событие.
📝 - Редактировать текст события.
🏷 - Изменить статус события.
🗑 - Удалить событие.
🔙 - Назад.
  &lt;   - Перелистнуть на один день назад.
  >   - Перелистнуть на один день вперёд.
🔄 - Обновить сообщение.
Если у вас есть события с повторяющимися статусами на этот день, то ниже основной клавиатуры и кнопок страниц появится кнопка "📅" для просмотра списка таких событий. Кнопка "↖️" позволяет открыть сообщение на дату этого события.

Для вызова сообщения, вы можете нажать кнопку в календаре или использовать команду /today.
""",
                "en": """
<u>Types of messages > <b>1 day</b></u>

The message displays events for a single day.

The line with information about the event is situated one line higher than the text of the event.
For example: <pre>1.3.⬜️</pre>
Here 1 is the index number of the events in the message, 3 is the event id, and ⬜️ are the statuses separated by commas.

If the number of events for this date exceeds 10, the remaining events are placed on other pages. There cannot be more than 10 events on one page. Page navigation buttons are displayed below the control buttons and are numbered accordingly.

The order of events in the message can be changed in the settings. By default, events are arranged in ascending order of their id (from small to large).

Control buttons:
➕ - Add an event.
📝 - Edit the event text.
🏷 - Change the event status.
🗑 - Delete an event.
🔙 - Go back.
  &lt;   - Navigate one day back.
  >   - Navigate one day forward.
🔄 - Refresh the message.
If you have events with recurring statuses on this day, below the main keyboard and page navigation buttons there will be a "📅" button to view a list of such events. The "↖️" button allows you to open the message for the date of that event.

To access the message, you can press the button in the calendar or use the command /today.
""",
            },
            "7_days": {
                "ru": """
<u>Виды сообщений > <b>7 дней</b></u>

Отображает события на ближайшие 7 дней.

Вызывается командой /week_event_list.
""",
                "en": """
<u>Types of messages > <b>7 days</b></u>

Displays events for the next 7 days.

Called by the command /week_event_list.
""",
            },
            "Settings": {
                "ru": """
<u>Виды сообщений > <b>Настройки</b></u>

Вызываются командой /settings.
Сообщение позволяет изменить настройки пользователя.

Чтобы изменить город, нужно ответить на сообщение с настройками от бота с названием города.
Город используется для запроса текущей погоды (/weather) и прогноза погоды (/forecast).

Часовой пояс используется для определения времени у пользователя.
""",
                "en": """
<u>Types of messages > <b>Settings</b></u>

Called by the command /settings.
This message allows users to modify their settings.

To change the city, you need to reply to the bots message containing the city name settings.
The city is used for requesting the current weather (/weather) and weather forecast (/forecast).

The time zone is used to determine the user's local time.
""",
            },
            "Basket": {
                "ru": """
<u>Виды сообщений > <b>Корзина</b></u>

Обычные пользователи могут только удалить своё событие навсегда.
Премиум-пользователям дополнительно доступна возможность переместить событие в корзину.
<b>События в корзине хранятся не более 30 дней!</b>

В корзине есть возможность восстановить событие на прежнюю дату.
""",
                "en": """
<u>Types of messages > <b>Basket</b></u>

Regular users can only delete their event permanently.
Premium users additionally have the option to move the event to the trash.
<b>Events in the trash are stored for no more than 30 days!</b>

In the trash basket, there is an option to restore the event to its original date.
""",
            },
            "Search": {
                "ru": """
<u>Виды сообщений > <b>Поиск</b></u>

Вы можете искать события, написав боту сообщение по следующему шаблону:
#&lt;поисковый запрос> или /search &lt;поисковый запрос>

<b>Обратите внимание, регистр поискового запроса важен!</b>

Бот ищет по вхождению слова в текст, дату и статус.
Он выдаёт все события, в которых есть совпадения.

Например, запрос <code>#03.05. Музыка</code> выдаст все события, в которых дата 3 мая и они содержат слово "Музыка".

# TODO Планируется расширение возможностей поисковых запросов.
""",
                "en": """
<u>Types of messages > <b>Search</b></u>

You can search for events by sending a message to the bot using the following template:
#&lt;search query> or /search &lt;search query>

<b>Please note that the search query is case-sensitive!</b>

The bot looks for occurrences of the word in the text, date and status.
It returns all events that have matches.

For example, the request <code>#03.05. Music</code> will return all events that have the date 3rd May and contain the word "Music".

# TODO Expanding the capabilities of search queries is planned.
""",
            },
            "Notifications": {
                "ru": """
<u>Виды сообщений > <b>Уведомления</b></u>

По умолчанию уведомления отключены.
Вы можете включить и изменить время уведомлений в настройках (/settings).
Бот уведомляет о важных "🟥" событиях, событиях с повторяющимся статусом ("📬", "📅", "🗞", "📆") и событиях со статусом "🔔".
""",
                "en": """
<u>Types of messages > <b>Notifications</b></u>

Notifications are disabled by default.
You can enable and customize the notification time in the settings (/settings).
The bot notifies about important "🟥" events, events with recurring status ("📬", "📅", "🗞", "📆"), and events with the status "🔔".
""",
            },
        },
        "weather": {
            "ru": """{} {} <u>{}</u>
Местное время <b>{}</b>
Измерения от ⠀<b>{}</b>
<b>{}°C</b>, ощущается как <b>{}°C</b>.
Ветер 💨 <b>{} м/с</b>, направление {} (<b>{}°</b>)
Восход <b>{}</b>
Закат⠀ <b>{}</b>
Видимость <b>{}</b>м""",
            "en": """{} {} <u>{}</u>
Local time <b>{}</b>
Measurements from⠀<b>{}</b>
<b>{}°C</b>, feels like <b>{}°C</b>.
Wind 💨 <b>{} m/s</b>, direction {} (<b>{}°</b>)
Sunrise <b>{}</b>
Sunset⠀<b>{}</b>
Visibility <b>{}</b>m""",
        },
        "search": {
            "ru": "Поиск",
            "en": "Search",
        },
        "basket": {
            "ru": "Корзина",
            "en": "Basket",
        },
        "reminder": {
            "ru": "Напоминание",
            "en": "Notification",
        },
        "menu": {
            "ru": (
                "Меню",
                "Помощь",
                "Календарь",
                "Аккаунт",
                "Группы",
                "7 дней",
                "Уведомления",
                "Настройки",
                "Корзина",
                "Админская",
            ),
            "en": (
                "Menu",
                "Help",
                "Calendar",
                "Account",
                "Groups",
                "7 days",
                "Notifications",
                "Settings",
                "Bin",
                "Admin",
            ),
        },
    },
    "buttons": {
        "commands": {
            "-1": {
                "user": {
                    "ru": [
                        BotCommand("_", "Вы забанены"),
                    ],
                    "en": [
                        BotCommand("_", "You are banned"),
                    ],
                },
                "group": {
                    "ru": [
                        BotCommand("_", "Вы забанены"),
                    ],
                    "en": [
                        BotCommand("_", "You are banned"),
                    ],
                },
            },
            "0": {
                "user": {
                    "ru": [
                        BotCommand("start", "Старт"),
                        BotCommand("menu", "Меню"),
                        BotCommand("calendar", "Календарь"),
                        BotCommand("today", "Вызвать сообщение с сегодняшним днём"),
                        BotCommand("weather", "{city} Погода"),
                        BotCommand("forecast", "{city} Прогноз погоды на 5 дней"),
                        BotCommand("week_event_list", "Cобытия в ближайшие 7 дней"),
                        BotCommand("dice", "Кинуть кубик"),
                        BotCommand(
                            "export",
                            "{format} Сохранить мои данные в формат. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Помощь"),
                        BotCommand("settings", "Настройки"),
                    ],
                    "en": [
                        BotCommand("start", "Start"),
                        BotCommand("menu", "Menu"),
                        BotCommand("calendar", "Calendar"),
                        BotCommand("today", "Today's message"),
                        BotCommand("weather", "{city} Weather"),
                        BotCommand("forecast", "{city} Weather forecast for 5 days"),
                        BotCommand("week_event_list", "Weekly events"),
                        BotCommand("dice", "Roll the dice (randomizer)"),
                        BotCommand(
                            "export",
                            "{format} Save my data in format. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Help"),
                        BotCommand("settings", "Settings"),
                    ],
                },
                "group": {
                    "ru": [
                        BotCommand("start", "Старт"),
                        BotCommand("menu", "Меню"),
                        BotCommand("calendar", "Календарь"),
                        BotCommand("today", "Вызвать сообщение с сегодняшним днём"),
                        BotCommand("weather", "{city} Погода"),
                        BotCommand("forecast", "{city} Прогноз погоды на 5 дней"),
                        BotCommand("week_event_list", "Cобытия в ближайшие 7 дней"),
                        BotCommand("dice", "Кинуть кубик"),
                        BotCommand(
                            "export",
                            "{format} Сохранить мои данные в формат. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Помощь"),
                        BotCommand("settings", "Настройки"),
                    ],
                    "en": [
                        BotCommand("start", "Start"),
                        BotCommand("menu", "Menu"),
                        BotCommand("calendar", "Calendar"),
                        BotCommand("today", "Today's message"),
                        BotCommand("weather", "{city} Weather"),
                        BotCommand("forecast", "{city} Weather forecast for 5 days"),
                        BotCommand("week_event_list", "Weekly events"),
                        BotCommand("dice", "Roll the dice (randomizer)"),
                        BotCommand(
                            "export",
                            "{format} Save my data in format. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Help"),
                        BotCommand("settings", "Settings"),
                    ],
                },
            },
            "1": {
                "user": {
                    "ru": [
                        BotCommand("start", "Старт"),
                        BotCommand("menu", "Меню"),
                        BotCommand("calendar", "Календарь"),
                        BotCommand("today", "Вызвать сообщение с сегодняшним днём"),
                        BotCommand("weather", "{city} Погода"),
                        BotCommand("forecast", "{city} Прогноз погоды на 5 дней"),
                        BotCommand("week_event_list", "Cобытия в ближайшие 7 дней"),
                        BotCommand("dice", "Кинуть кубик"),
                        BotCommand(
                            "export",
                            "{format} Сохранить мои данные в формат. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Помощь"),
                        BotCommand("settings", "Настройки"),
                    ],
                    "en": [
                        BotCommand("start", "Start"),
                        BotCommand("menu", "Menu"),
                        BotCommand("calendar", "Calendar"),
                        BotCommand("today", "Today's message"),
                        BotCommand("weather", "{city} Weather"),
                        BotCommand("forecast", "{city} Weather forecast for 5 days"),
                        BotCommand("week_event_list", "Weekly events"),
                        BotCommand("dice", "Roll the dice (randomizer)"),
                        BotCommand(
                            "export",
                            "{format} Save my data in format. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Help"),
                        BotCommand("settings", "Settings"),
                    ],
                },
                "group": {
                    "ru": [
                        BotCommand("start", "Старт"),
                        BotCommand("menu", "Меню"),
                        BotCommand("calendar", "Календарь"),
                        BotCommand("today", "Вызвать сообщение с сегодняшним днём"),
                        BotCommand("weather", "{city} Погода"),
                        BotCommand("forecast", "{city} Прогноз погоды на 5 дней"),
                        BotCommand("week_event_list", "Cобытия в ближайшие 7 дней"),
                        BotCommand("dice", "Кинуть кубик"),
                        BotCommand(
                            "export",
                            "{format} Сохранить мои данные в формат. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Помощь"),
                        BotCommand("settings", "Настройки"),
                    ],
                    "en": [
                        BotCommand("start", "Start"),
                        BotCommand("menu", "Menu"),
                        BotCommand("calendar", "Calendar"),
                        BotCommand("today", "Today's message"),
                        BotCommand("weather", "{city} Weather"),
                        BotCommand("forecast", "{city} Weather forecast for 5 days"),
                        BotCommand("week_event_list", "Weekly events"),
                        BotCommand("dice", "Roll the dice (randomizer)"),
                        BotCommand(
                            "export",
                            "{format} Save my data in format. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Help"),
                        BotCommand("settings", "Settings"),
                    ],
                },
            },
            "2": {
                "user": {
                    "ru": [
                        BotCommand("start", "Старт"),
                        BotCommand("menu", "Меню"),
                        BotCommand("calendar", "Календарь"),
                        BotCommand("today", "Вызвать сообщение с сегодняшним днём"),
                        BotCommand("weather", "{city} Погода"),
                        BotCommand("forecast", "{city} Прогноз погоды на 5 дней"),
                        BotCommand("week_event_list", "Cобытия в ближайшие 7 дней"),
                        BotCommand("dice", "Кинуть кубик"),
                        BotCommand(
                            "export",
                            "{format} Сохранить мои данные в формат. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Помощь"),
                        BotCommand("settings", "Настройки"),
                        BotCommand("commands", "Список команд"),
                    ],
                    "en": [
                        BotCommand("start", "Start"),
                        BotCommand("menu", "Menu"),
                        BotCommand("calendar", "Calendar"),
                        BotCommand("today", "Today's message"),
                        BotCommand("weather", "{city} Weather"),
                        BotCommand("forecast", "{city} Weather forecast for 5 days"),
                        BotCommand("week_event_list", "Weekly events"),
                        BotCommand("dice", "Roll the dice (randomizer)"),
                        BotCommand(
                            "export",
                            "{format} Save my data in format. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Help"),
                        BotCommand("settings", "Settings"),
                        BotCommand("commands", "Command list"),
                    ],
                },
                "group": {
                    "ru": [
                        BotCommand("start", "Старт"),
                        BotCommand("menu", "Меню"),
                        BotCommand("calendar", "Календарь"),
                        BotCommand("today", "Вызвать сообщение с сегодняшним днём"),
                        BotCommand("weather", "{city} Погода"),
                        BotCommand("forecast", "{city} Прогноз погоды на 5 дней"),
                        BotCommand("week_event_list", "Cобытия в ближайшие 7 дней"),
                        BotCommand("dice", "Кинуть кубик"),
                        BotCommand(
                            "export",
                            "{format} Сохранить мои данные в формат. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Помощь"),
                        BotCommand("settings", "Настройки"),
                        BotCommand("commands", "Список команд"),
                    ],
                    "en": [
                        BotCommand("start", "Start"),
                        BotCommand("menu", "Menu"),
                        BotCommand("calendar", "Calendar"),
                        BotCommand("today", "Today's message"),
                        BotCommand("weather", "{city} Weather"),
                        BotCommand("forecast", "{city} Weather forecast for 5 days"),
                        BotCommand("week_event_list", "Weekly events"),
                        BotCommand("dice", "Roll the dice (randomizer)"),
                        BotCommand(
                            "export",
                            "{format} Save my data in format. (csv, xml, json, jsonl)",
                        ),
                        BotCommand("help", "Help"),
                        BotCommand("settings", "Settings"),
                        BotCommand("commands", "Command list"),
                    ],
                },
            },
        },
        "status page": {
            "0": {
                "ru": (
                    (("🗂 Важность", "1"),),
                    (("🗂 Разное", "2"),),
                    (
                        ("🗂 Эффекты", "3"),
                        ("🗂 Кастомные", "4"),
                    ),
                ),
                "en": (
                    (("🗂 Importance", "1"),),
                    (("🗂 Miscellaneous", "2"),),
                    (
                        ("🗂 Effects", "3"),
                        ("🗂 Custom", "4"),
                    ),
                ),
            },
            "1": {
                "ru": (
                    (
                        "⬜️ Без статуса",
                        "✅ Сделано",
                    ),
                    (
                        "🟥 Важно",
                        "🟨 Сделано не полностью",
                    ),
                    (
                        "⭐️ Важно",
                        "🤨 Не уверен",
                    ),
                    (
                        "🟧 Важно но не так",
                        "💡 Идея",
                    ),
                ),
                "en": (
                    (
                        "⬜️ No Status",
                        "✅ Done",
                    ),
                    (
                        "🟥 Important",
                        "🟨 Not completely done",
                    ),
                    (
                        "⭐️ Important",
                        "🤨 Not sure",
                    ),
                    (
                        "🟧 Not so important",
                        "💡 Idea",
                    ),
                ),
            },
            "2": {
                "ru": (
                    (
                        "🎧 Музыка",
                        "📚 Книга",
                    ),
                    (
                        "🎬 Фильм",
                        "📺 Видео",
                    ),
                    (
                        "🖼 Фотография",
                        "🎮 Игра",
                    ),
                    (
                        "🎁 Подарок",
                        "❓ Вопрос",
                    ),
                    (
                        "🧾 Рецепт",
                        "📌 Закрепить",
                    ),
                    (
                        "🛒 План покупок",
                        "⏱ В процессе",
                    ),
                    (
                        "📋 План",
                        "🗺 Путешествия",
                    ),
                ),
                "en": (
                    (
                        "🎧 Music",
                        "📚 Book",
                    ),
                    (
                        "🎬 Movie",
                        "📺 Video",
                    ),
                    (
                        "🖼 Photography",
                        "🎮 Game",
                    ),
                    (
                        "🎁 Present",
                        "❓ Question",
                    ),
                    (
                        "🧾 Recipe",
                        "📌 Pin",
                    ),
                    (
                        "🛒 Shopping Plan",
                        "⏱ In Progress",
                    ),
                    (
                        "📋 Plan",
                        "🗺 Travel",
                    ),
                ),
            },
            "3": {
                "ru": (
                    (
                        "🗒 Cписок (ставит ▪️)",
                        "🧮 Порядковый список (1️⃣, 2️⃣ и т д)",
                    ),
                    (
                        "💻 Код⠀",
                        "🪞 Скрыто",
                        "💬 Цитата",
                    ),
                    (
                        "🎉 Дни рождения",
                        "🎊 Праздник",
                        "🪩 Один праздник",
                    ),
                    (
                        "🔗 Ссылка",
                        "⛓ Без сокращения ссылок",
                    ),
                    ("📆 Повторение каждый год",),
                    ("📅 Повторение каждый месяц",),
                    ("🗞 Повторение каждую неделю",),
                    ("📬 Повторение каждый день",),
                    ("🔕 Выключить уведомления",),
                ),
                "en": (
                    (
                        "🗒 List (puts ▪️)",
                        "🧮 Ordinal list (1️⃣, 2️⃣ etc)",
                    ),
                    (
                        "💻 Code",
                        "🪞 Hidden",
                        "💬 Quote",
                    ),
                    (
                        "🎉 Birthdays",
                        "🎊 Holiday",
                        "🪩 One feast",
                    ),
                    (
                        "🔗 Link",
                        "⛓ No link shortening",
                    ),
                    ("📆 Repeat every year",),
                    ("📅 Repeat every month",),
                    ("🗞 Repeat every week",),
                    ("📬 Repeat every day",),
                    ("🔕 Turn off notifications",),
                ),
            },
            "4": {
                "ru": (
                    (
                        "💻py Python",
                        "💻cpp C++",
                        "💻c C",
                    ),
                    (
                        "💻cs C#",
                        "💻html HTML",
                        "💻css CSS",
                    ),
                    (
                        "💻js JavaScript",
                        "💻ts TypeScript",
                    ),
                    (
                        "💻java Java",
                        "💻swift Swift",
                        "💻kt Kotlin",
                    ),
                    (
                        "💻go Go",
                        "💻rs Rust",
                        "💻rb Ruby",
                    ),
                    (
                        "💻sql SQL",
                        "💻re RegExp",
                        "💻sh Shell | Bash",
                    ),
                    (
                        "💻yaml YAML",
                        "💻json JSON",
                        "💻xml XML",
                    ),
                    (
                        "💻toml TOML",
                        "💻ini INI",
                        "💻csv CSV",
                    ),
                ),
                "en": (
                    (
                        "💻py Python",
                        "💻cpp C++",
                        "💻c C",
                        "💻cs C#",
                    ),
                    (
                        "💻js JavaScript",
                        "💻html HTML",
                        "💻css CSS",
                        "💻ts TypeScript",
                    ),
                    (
                        "💻java Java",
                        "💻swift Swift",
                        "💻kt Kotlin",
                    ),
                    (
                        "💻go Go",
                        "💻rs Rust",
                        "💻rb Ruby",
                    ),
                    (
                        "💻sql SQL",
                        "💻re RegExp",
                        "💻sh Shell | Bash",
                    ),
                    (
                        "💻yaml YAML",
                        "💻json JSON",
                        "💻xml XML",
                    ),
                    (
                        "💻toml TOML",
                        "💻ini INI",
                        "💻csv CSV",
                    ),
                ),
            },
        },
    },
    "errors": {
        "success": {
            "ru": "Успешно",
            "en": "Success",
        },
        "failure": {
            "ru": "Неудача",
            "en": "Failure",
        },
        "forbidden_to_log_account_in_group": {
            "ru": "В группе нельзя войти в аккаунт",
            "en": "You can't log into your account in a group.",
        },
        "no_account": {
            "ru": "Вы не вошли в аккаунт. Войдите\n<code>/login &lt;username&gt; &lt;password&gt;</code>\nили создайте аккаунт\n<code>/signup &lt;email&gt; &lt;username&gt; &lt;password&gt;</code>",
            "en": "You are not logged in to your account. Login\n<code>/login &lt;username&gt; &lt;password&gt;</code>\nor create an account\n<code>/signup &lt;email&gt; &lt;username&gt; &lt;password&gt;</code>",
        },
        "many_attempts": {
            "ru": "Извините, слишком много обращений. Пожалуйста, повторите попытку через {} секунд.",
            "en": "Sorry, too many requests. Please try again in {} seconds.",
        },
        "many_attempts_weather": {
            "ru": "Погоду запрашивали слишком часто. Повторите через {} секунд.",
            "en": "The weather was requested too often. Retry in {} seconds.",
        },
        "error": {
            "ru": "Произошла ошибка",
            "en": "An error has occurred",
        },
        "file_is_too_big": {
            "ru": "Возникла ошибка. Возможно файл слишком большой 🫤",
            "en": "An error has occurred. Maybe the file is too big 🫤",
        },
        "export": {
            "ru": "Нельзя так часто экспортировать данные\n"
            "Подождите ещё <b>{t} минут</b>",
            "en": "You can't export data so often\nPlease wait <b>{t} minutes</b>",
        },
        "export_format": {
            "ru": "Неверный формат. Выбери из (csv, xml, json, jsonl)",
            "en": "Wrong format. Choose from (csv, xml, json, jsonl)",
        },
        "deleted": {
            "ru": "Извините, вам эта команда не доступна",
            "en": "Sorry, this command is not available for you",
        },
        "no_events_to_interact": {
            "ru": "Нет событий для взаимодействия",
            "en": "No events to interact",
        },
        "already_on_this_page": {
            "ru": "Вы уже находитесь на этой странице",
            "en": "You are already on this page",
        },
        "status_already_posted": {
            "ru": "Cтатус уже стоит на событии",
            "en": "Status is already posted on event",
        },
        "more_5_statuses": {
            "ru": "Нельзя ставить больше 5 статусов",
            "en": "You can not put more than 5 statuses",
        },
        "conflict_statuses": {
            "ru": "Cтатусы конфликтуют друг с другом.",
            "en": "Statuses conflict with each other.",
        },
        "message_is_too_long": {
            "ru": "Сообщение слишком большое",
            "en": "Message is too long",
        },
        "exceeded_limit": {
            "ru": "Вы превысили дневной лимит.\n"
            "Уменьшите количество символов или удалите не нужные события.",
            "en": "You have exceeded the daily limit.\n"
            "Reduce the number of characters or remove unnecessary events.",
        },
        "limit_exceeded": {
            "ru": "Превышен лимит",
            "en": "Limit exceeded",
        },
        "message_empty": {
            "ru": "🕸  Здесь пусто🕷  🕸",
            "en": "🕸  It's empty here🕷  🕸",
        },
        "request_empty": {
            "ru": "Запрос пустой :/",
            "en": "Request is empty :/",
        },
        "nothing_found": {
            "ru": "🕸  Ничего не нашлось🕷  🕸",
            "en": "🕸  Nothing has found🕷  🕸",
        },
        "get_permission": {
            "ru": "Пожалуйста, выдайте боту <b>права удалять сообщения</b>, чтобы сохранять чат в чистоте",
            "en": "Please give the bot <b>permission to delete messages</b> to keep the chat clean",
        },
        "delete_messages_older_48_h": {
            "ru": "Из-за ограничений Telegram бот не может удалять сообщения <b>старше 48 часов</b>.",
            "en": "Due to Telegram restrictions, the bot cannot delete messages <b>older than 48 hours</b>.",
        },
        "weather_invalid_city_name": {
            "ru": "Ошибка. Несуществующее название города.\n"
            "Попробуйте ещё раз /weather {город}",
            "en": "Error. Invalid city name.\nTry again /weather {city}",
        },
        "forecast_invalid_city_name": {
            "ru": "Ошибка. Несуществующее название города.\n"
            "Попробуйте ещё раз /forecast {город}",
            "en": "Error. Invalid city name.\nTry again /forecast {city}",
        },
        "nodata": {
            "ru": "👀 На эту дату у вас нет событий",
            "en": "👀 You have no events for this date",
        },
        "invalid_date": {
            "ru": "Недействительная дата!",
            "en": "Invalid date!",
        },
    },
    "select": {
        "status_to_event": {
            "ru": "Выберите статус для события:",
            "en": "Select a status for the event:",
        },
        "notification_date": {
            "ru": "Выберите дату уведомления",
            "en": "Select notification date",
        },
        "event_to_open": {
            "ru": "Выберите событие для открытия",
            "en": "Select an event to open",
        },
        "event": {
            "ru": "Выберите событие",
            "en": "Choose an event",
        },
        "events": {
            "ru": "Выберите события",
            "en": "Choose an events",
        },
        "date": {
            "ru": "Выберите дату",
            "en": "Select a date",
        },
        "new_date": {
            "ru": "Выберите новую дату для события",
            "en": "Select a new date for the event",
        },
        "what_do_with_event": {
            "ru": "Выберите, что сделать с событием",
            "en": "Choose what to do with the event",
        },
        "what_do_with_events": {
            "ru": "Выберите, что сделать с событиями",
            "en": "Choose what to do with the events",
        },
    },
}


def get_translate(target: str, lang_iso: str | None = None) -> str | Any:
    """
    Взять перевод из файла lang.py c нужным языком
    """
    result: dict = translation
    for key in target.split("."):
        result = result[key]

    entity = request.entity
    lang_iso: str = lang_iso or (entity.settings.lang if entity else "en")
    try:
        return result[lang_iso]
    except KeyError:
        return result["en"]


def get_theme_emoji(target: Literal["back", "add", "del"]) -> str:
    """
    back

    add
    """
    theme: int = request.user.settings.theme
    match target:
        case "back":
            match theme:
                case 1:
                    return "⬅️"
                case _:
                    return "🔙"
        case "add":
            match theme:
                case 1:
                    return "🞣"
                case _:
                    return "➕"
        case "del":
            match theme:
                case 1:
                    return "✕"
                case _:
                    return "✖️"

    return ""
