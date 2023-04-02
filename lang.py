from telebot.types import BotCommand

def end(lang: str):
    def closure_ru(num_diff: int):
        num_diff = str(num_diff)
        if num_diff[-2:] in ('11', '12', '13', '14'): return 'дней'
        if num_diff[-1] == '0': return 'дней'
        if num_diff[-1] == '1': return 'день'
        if num_diff[-1] in ('2', '3', '4'): return 'дня'
        if num_diff[-1] in ('5', '6', '7', '8', '9'): return 'дней'

    def closure_en(num_diff: int):
        return "day" if num_diff == 1 else "days"
    if lang == "ru":
        return closure_ru
    else:
        return closure_en

translation = {
    "months_list": {
        "ru": ((("Январь", 1), ("Февраль", 2), ("Март", 3)),
               (("Апрель", 4), ("Май", 5), ("Июнь", 6)),
               (("Июль", 7), ("Август", 8), ("Сентябрь", 9)),
               (("Октябрь", 10), ("Ноябрь", 11), ("Декабрь", 12))),
        "en": ((("January", 1), ("February", 2), ("March", 3)),
               (("April", 4), ("May", 5), ("June", 6)),
               (("July", 7), ("August", 8), ("September", 9)),
               (("October", 10), ("November", 11), ("December", 12)))
    },
    "leap": {
        "ru": "Високосный",
        "en": "leap"
    },
    "not_leap": {
        "ru": "Невисокосный",
        "en": "non-leap"
    },
    "week_days_list": {
        "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
        "en": ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
    },
    "week_days_list_full": {
        "ru": ("Понедельник", "Вторник", " Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"),
        "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    },
    "months_name": {
        "ru": ("Январь", "Февраль", "Март",
               "Апрель", "Май", "Июнь",
               "Июль", "Август", "Сентябрь",
               "Октябрь", "Ноябрь", "Декабрь"),
        "en": ("January", "February", "March",
               "April", "May", "June",
               "July", "August", "September",
               "October", "November", "December")
    },
    "months_name2": {
        "ru": ("Января", "Февраля", "Марта",
               "Апреля", "Мая", "Июня",
               "Июля", "Августа", "Сентября",
               "Октября", "Ноября", "Декабря"),
        "en": ("January", "February", "March",
               "April", "May", "June",
               "July", "August", "September",
               "October", "November", "December")
    },
    "start": {
        "ru": """&lt;   -1 месяц
&gt;   +1 месяц
⟳   Поставить текущую дату
&lt;&lt;   -1 год
&gt;&gt;   +1 год
➕   Добавить событие
🗑   Удалить событие
🔙   Вернуться назад
✖   Удалить это сообщение
#... or /search... - Поиск
/event_list - Cписок событий на 7 дней
/weather {"город"} - Погода
🚩 - поставить статус

<b>Подробнее /help</b>

Напишите /calendar или нажмите на кнопку ниже""",
        "en": """&lt;   -1 month
&gt;   +1 month
⟳   Put current date
&lt;&lt;   -1 year
&gt;&gt;   +1 year
➕   Add event
🗑   Delete event
🔙   Go back
✖   Delete this message
#... or /search... - Search
/event_list - List of events for 7 days
/weather {"city"} - Weather
🚩 - set status

<b>More /help</b>

Write /calendar or click on the button below"""
    },
    "help": {
        "ru": """Обозначения
| перед каждым событием есть пометка например 1.34.✅
| из этого
| 1 это порядковый номер события в конкретном сообщении
| 34 это порядковый номер события в базе данных
| (она общая но каждому доступны только его события)
| ✅ это статус события
| (по нему можно помечать события и искать поиском
| (# или /search) и ставить уведомления (⏰)(!не стабильно!))

КНОПКИ
| Календарь
| <  Убавить 1 месяц
| >  Добавить 1 месяц
| ⟳ Поставить текущую дату
| << Убавить 1 год
| >> Добавить 1 год
|
| Основное окно
| ➕ Добавить событие
| 📝 Редактировать событие
| 🗑 Удалить событие
| 🚩 Изменить статус
| 🔙 Вернуться назад
|  < Убавить 1 день
|  > Добавить 1 день
| ✖️ Удалить сообщение бота

СТАТУСЫ
| ⬜️ Без статуса
| 🟥 Важно
| 🟧 Важно но не так
| 🟨 Сделано но не полностью
| ✅ Сделано
| 💡 Идея
| 🤨 Не уверен
| 🎉 Дни рождения
| 🎊 Праздник
| 🛒 План покупок
| 🧾 Рецепт
| 🖼 Фотография
| 🗺 Путешествия
| 💻 Код
| 🔗 Ссылка
| 📋 План
| 🗒 Cписок (Заменяет переносы строки на ▪️)
| 🎧 Музыка
| 🪞 Скрыто
| ❓ Вопрос
| ⏱ В процессе
| ⏰ Включить уведомление

Поиск
Искать можно по дате по тексту (Регистр важен!), событиям, дате и id события
Например если нужно искать события только за Август то можно написать #.09.
8 января #08.09
Все события с статусом дней рождения #🎉""",
        "en": """
*Notation*
| before each event there is a note for example 1.34.✅
| from this
| 1 is the sequence number of the event in a particular message
| 34 is the sequence number of the event in the database
| (it is general but only its events are available to everyone)
| ✅ this is the status of the event
| (on it you can mark events and search by search
| (# or /search) and set notifications (⏰)(!not stable!))

*BUTTONS*
| Calendar
| < Subtract 1 month
| > Add 1 month
| ⟳ Put current date
| << Subtract 1 year
| >> Add 1 year
|
| Main window
| ➕ Add event
| 📝 Edit event
| 🗑 Delete event
| 🚩 Change status
| 🔙 Go back
| < Subtract 1 day
| > Add 1 day
| ✖️ Delete bot message

*STATUSES*
| ⬜️ No Status
| 🟥 Important
| 🟧 Important but not so
| 🟨 Done but not complete
| ✅ Done
| 💡 Idea
| 🤨 Not sure
| 🎉 Birthdays
| 🎊 Holiday
| 🛒 Shopping plan
| 🧾 Recipe
| 🖼 Photography
| 🗺 Travel
| 💻 Code
| 🔗 Link
| 📋 Plan
| 🗒 List (Replaces line breaks with ▪️)
| 🎧 Music
| 🪞 Hidden
| ❓ Question
| ⏱ In progress
| ⏰ Enable notification

*Search*
You can search by date in the text (Case is important!), events, date and event id
For example, if you need to search for events only for August, then you can write #.09.
January 8 #08.09
All events with birthday status #🎉
"""
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
<b>{}</b> <i>(3 по умолчанию)</i>

[<u>Порядок событий в сообщении</u>]
<b>{}</b> <i>(⬇️ по умолчанию)</i>

*(<a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">https://www.youtube.com</a> <i>вместо полной ссылки</i>)
**<i>Ответьте на это сообщение с названием города</i>""",
        "en": """⚙️ Settings ⚙️

[<u>Language</u>]
<b>{}</b>

<u>Minify links</u>]
<b>{}</b> <i>(True recommended)</i>

[<u>City</u>]
<b>{}</b> <i>(Moscow by default)</i>

[<u>Timezone</u>]
<b>{}</b> <i>(3 by default)</i>

[<u>Order of events in a message</u>]
<b>{}</b> <i>(⬇️ by default)</i>

*(<a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">https://www.youtube.com</a> <i>instead of full link</i>)
**<i>Reply to this message with a city name</i>"""
    },
    "message_empty": {
        "ru": "🕸  Здесь пусто🕷  🕸",
        "en": "🕸  It's empty here🕷  🕸"
    },
    "request_empty": {
        "ru": "Запрос пустой :/",
        "en": "Request is empty :/"
    },
    "nothing_found": {
        "ru": "🕸  Ничего не нашлось🕷  🕸",
        "en": "🕸  Nothing found🕷  🕸"
    },
    "week_events": {
        "ru": "📆 Cобытия в ближайшие 7 дней:",
        "en": "📆 Events in the next 7 days:"
    },
    "search": {
        "ru": "🔍 Поиск",
        "en": "🔍 Search"
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
Visibility <b>{}</b>m"""
    },
    "weather_invalid_city_name": {
        "ru": "Ошибка. Несуществующее название города.\nПопробуйте ещё раз /weather {город}",
        "en": "Error. Invalid city name.\nTry again /weather {city}"
    },
    "forecast_invalid_city_name": {
        "ru": "Ошибка. Несуществующее название города.\nПопробуйте ещё раз /forecast {город}",
        "en": "Error. Invalid city name.\nTry again /forecast {city}"
    },
    "basket": {
        "ru": "🗑 Корзина 🗑",
        "en": "🗑 Basket 🗑"
    },
    "nodata": {
        "ru": "👀 На эту дату у вас нет событий",
        "en": "👀 You have no events for this date"
    },
    "get_admin_rules": {
        "ru": "Пожалуйста, выдайте боту права администратора, чтобы сохранять чат в чистоте",
        "en": "Please give the bot admin rights to keep the chat clean"
    },
    "relative_date_list": {
        "ru": (
            "Сегодня",
            "Завтра",
            "Послезавтра",
            "Вчера",
            "Позавчера",
            "Через",
            "назад",
            end("ru")
        ),
        "en": (
            "Today",
            "Tomorrow",
            "Day after tomorrow",
            "Yesterday",
            "Day before yesterday",
            "After",
            "ago",
            end("en")
        )
    },
    "alarm": {
        "ru": ("Будильник", "Скоро праздник!"),
        "en": ("Alarm", "Holiday coming soon!")
    },
    "exceeded_limit": {
        "ru": """Вы превысили дневной лимит.
Уменьшите количество символов или удалите не нужные события.""",
        "en": """You have exceeded the daily limit.
Reduce the number of characters or remove unnecessary events."""
    },
    "message_is_too_long": {
        "ru": "Сообщение слишком большое",
        "en": "Message is too long"
    },
    "send_event_text": {
        "ru": "Отправьте текст события",
        "en": "Send the text of the event"
    },
    "already_on_this_page": {
        "ru": "Вы уже находитесь на этой странице",
        "en": "You are already on this page"
    },
    "select_event_to_edit": {
        "ru": "Выберите событие для редактирования",
        "en": "Select an event to edit"
    },
    "select_event_to_change_status": {
        "ru": "Выберите событие для изменения статуса",
        "en": "Select an event to change status"
    },
    "select_status_to_event": {
        "ru": "Выберите статус для события",
        "en": "Select a status for the event"
    },
    "select_event_to_delete": {
        "ru": "Выберите событие для удаления",
        "en": "Select an event to delete"
    },
    "choose_event": {
        "ru": "Выберите событие",
        "en": "Choose an event"
    },
    "choose_date": {
        "ru": "Выберите дату",
        "en": "Select a date"
    },
    "status_list": {
        "ru": (
            ('⬜️ Без статуса                        ', '📋 План                               '),
            ('✅ Сделано                            ', '🗒 Cписок (ставит ▪️)                   '),
            ('🟨 Сделано не полностью               ', '🧮 Порядковый список                  '),
            ('🤨 Не уверен                          ', '📌 Закрепить                          '),
            ('🟧 Важно но не так                    ', '🎁 Подарок                            '),
            ('🟥 Важно                              ', '🧾 Рецепт                             '),
            ('💡 Идея                                ', '🔗 Ссылка                             '),
            ('🎉 Дни рождения                       ', '🎬 Фильмы                             '),
            ('🎊 Праздник                           ', '🖼 Фотография                         '),
            ('🗺 Путешествия                        ', '💻 Код                                '),
            ('🎧 Музыка                             ', '🪞 Скрыто                              '),
            ('⏱ В процессе                         ', '🛒 План покупок                       '),
            ('⏰ Включить уведомление (не работает) ', '❓ Вопрос                             ')),
        "en": (
            ('⬜️ No Status                          ', '📋 Plan                                '),
            ('✅ Done                               ', '🗒 List (puts ▪️)                       '),
            ('🟨 Not completely done                ', '🧮 Ordinal list                       '),
            ('🤨 Not sure                           ', '📌 Pin                                '),
            ('🟧 Important but not so               ', '🎁 Present                             '),
            ('🟥 Important                          ', '🧾 Recipe                              '),
            ('💡 Idea                                ', '🔗 Link                               '),
            ('🎉 Birthdays                          ', '🎬 Movies                              '),
            ('🎊 Holiday                            ', '🖼 Photography                         '),
            ('🗺 Travel                             ', '💻 Code                                '),
            ('🎧 Music                              ', '🪞 Hidden                               '),
            ('⏱ In Progress                        ', '🛒 Shopping Plan                       '),
            ('⏰ Enable notification (not working)  ', '❓ Question                            ')),
    },
    "are_you_sure": {
        "ru": "Вы уверены что хотите удалить",
        "en": "Are you sure you want to delete"
    },
    "/deleted": {
        "ru": "<b>Чтобы посмотреть удалённые напишите /deleted</b>",
        "en": "<b>To see deleted write /deleted</b>"
    },
    "are_you_sure_edit": {
        "ru": "Вы точно хотите изменить тест события на: ",
        "en": "You want to change the event test to:"
    },
    "error": {
        "ru": "Произошла ошибка :/",
        "en": "An error has occurred :/"
    },
    "file_is_too_big": {
        "ru": "Возникла ошибка. Возможно файл слишком большой 🫤",
        "en": "An error has occurred. Maybe the file is too big 🫤"
    },
    "export_csv": {
        "ru": "Нельзя так часто экспортировать данные\nПодождите ещё <b>{t} минут</b>",
        "en": "You can't export data that often\nPlease wait another <b>{t} minutes</b>"
    },
    "deleted": {
        "ru": "Извините, вам эта команда не доступна",
        "en": "Sorry, this command is not available to you"
    },
    "game_bot": {
        "ru": "Другой бот с разными играми",
        "en": "Another bot with different games"
    },
    "add_bot_to_group": {
        "ru": "Добавить бота в группу",
        "en": "Add a bot to a group"
    },
    "defaultcommandlist": {
        "ru": [
            BotCommand("start",           "Старт"),
            BotCommand("calendar",        "Календарь"),
            BotCommand("today",           "Вызвать сообщение с сегодняшним днём"),
            BotCommand("weather",         "{city} Погода"),
            BotCommand("forecast",        "{city} Прогноз погоды на 5 дней"),
            BotCommand("week_event_list", "Cобытия в ближайшие 7 дней"),
            BotCommand("dice",            "Кинуть кубик"),
            BotCommand("save_to_csv",     "Сохранить мои данные в csv"),
            BotCommand("help",            "Помощь"),
            BotCommand("settings",        "Настройки")],
        "en": [
            BotCommand("start",           "Start"),
            BotCommand("calendar",        "Calendar"),
            BotCommand("today",           "Today's message"),
            BotCommand("weather",         "{city} Weather"),
            BotCommand("forecast",        "{city} Weather forecast for 5 days"),
            BotCommand("week_event_list", "Weekly events"),
            BotCommand("dice",            "Roll the dice (randomizer)"),
            BotCommand("save_to_csv",     "Save my data in csv"),
            BotCommand("help",            "Help"),
            BotCommand("settings",        "Settings")]
    },
    "premiumcommandlist": {
        "ru": [
            BotCommand("start",           "Старт"),
            BotCommand("calendar",        "Календарь"),
            BotCommand("today",           "Вызвать сообщение с сегодняшним днём"),
            BotCommand("weather",         "{city} Погода"),
            BotCommand("forecast",        "{city} Прогноз погоды на 5 дней"),
            BotCommand("week_event_list", "Cобытия в ближайшие 7 дней"),
            BotCommand("deleted",         "Корзина"),
            BotCommand("dice",            "Кинуть кубик"),
            BotCommand("save_to_csv",     "Сохранить мои данные в csv"),
            BotCommand("help",            "Помощь"),
            BotCommand("settings",        "Настройки")],
        "en": [
            BotCommand("start",           "Start"),
            BotCommand("calendar",        "Calendar"),
            BotCommand("today",           "Today's message"),
            BotCommand("weather",         "{city} Weather"),
            BotCommand("forecast",        "{city} Weather forecast for 5 days"),
            BotCommand("week_event_list", "Weekly events"),
            BotCommand("deleted",         "Trash bin"),
            BotCommand("dice",            "Roll the dice (randomizer)"),
            BotCommand("save_to_csv",     "Save my data in csv"),
            BotCommand("help",            "Help"),
            BotCommand("settings",        "Settings")]
    },
    "": {
        "ru": "",
        "en": ""
    },
    "": {
        "ru": "",
        "en": ""
    },
    "": {
        "ru": "",
        "en": ""
    },
    "": {
        "ru": "",
        "en": ""
    }
}
