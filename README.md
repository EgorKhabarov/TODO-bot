<h1>Bot for organizing events by dates.</h1>
<i>Storing, adding, editing and deleting notes by date.
You can tag a note with an emoji.
Convenient search by emoji statuses and dates.
Birthdays and holidays are marked on the calendar (you need to set an emoji status).</i><br><br>
<i>Хранение, добавление, редактирование и удаление заметки по дате.
Можно пометить заметку эмодзи.
Удобный поиск по эмодзи статусам и датам.
Дни рождения и праздники помечаются на календаре (нужно поставить эмодзи статус).</i>

---

# [Commands](/lang.py#L453)
| Command          | Description en              |
|:-----------------|:----------------------------|
| /start           | Start                       |
| /calendar        | Calendar                    |
| /today           | Today's message             |
| /weather {city}  | Weather                     |
| /forecast {city} | Weather forecast for 5 days |
| /week_event_list | Weekly events               |
| /dice            | Roll the dice (randomizer)  |      
| /save_to_csv     | Save my data in csv         |     
| /help            | Help                        |                          
| /settings        | Settings                    |
| /search {query}  | Search                      |
| #{query}         | Search                      |

---

# [Limits](/func.py#L712)

| user_status | price | maximum characters/day | maximum events/day |
|:------------|:------|:-----------------------|:-------------------|
| normal      | 0     | 4000                   | 20                 |
| premium     | 🤷    | 8000                   | 40                 |
| admin       | -     | ∞                      | ∞                  |

---

# [DataBase](/func.py#L89)

* ### [root](/func.py#L97)
| name     | data type | default value |
|:---------|:----------|:--------------|
| event_id | INT       | _NULL_        |
| user_id  | INT       | _NULL_        |
| date     | TEXT      | _NULL_        |
| text     | TEXT      | _NULL_        |
| isdel    | INT       | 0             |
| status   | TEXT      | ⬜️            |

* ### [settings](/func.py#L111)
| name              | data type | default value |
|:------------------|:----------|:--------------|
| user_id           | INT       | _NULL_        |
| lang              | TEXT      | ru            |
| sub_urls          | INT       | 1             |
| city              | TEXT      | Москва        |
| timezone          | INT       | 3             |
| direction         | TEXT      | ⬇️            |
| user_status       | INT       | 0             |
| user_max_event_id | INT       | 1             |

---

# #TODO
* [ ] Прокомментировать код.
* [ ] Группы для статусов событий
* [ ] Возможность удалить из корзины.
* [ ] Изменение user_status для админов, добавить статус -1 это в бане (игнор сообщений).<br>
 Изменение списка команд для пользователя в зависимости от user_status
* [ ] В поиск добавить шаблоны<br>
 `#date=dd.mm.yyyy` or `#date=dd.mm` or `#date=mm.yyyy` or `#date=dd..yyyy`<br>
 `#day=00`<br>
 `#month=0`<br>
 `#year=0000`<br>
 `#status=⬜️`<br>
 `#id=0`<br>
 Например `#date=1.2023 status=🎧` для поиска всех событий со статусом музыки за январь 2023 года.<br>
 Добавить поддержку спецсимволов sql LIKE (%, _ и.т.д.).<br>
 Поиск <b><u>И</u></b> `#!query` только то, что в поиске без вариаций.
* [ ] Добавить возможность конвертировать валюты через api.
* [ ] Команда `/account`. Количество сообщений.<br>
 Как в гитхабе, график наличия событий цветными смайлами `⬜️(0) 🟩(1,3) 🟨(4,6) 🟧(7,9) 🟥(>=10)`


* [ ] Explorer (Подобие файловой системы)<br>
 Для хранения больших текстовых файлов или изображений (<u>admin only</u>).<br>
 <b>Возможно сделать через api гугл|яндекс диска</b>
* [ ] Когда добавляешь событие пусть если фото или файл прикреплено к сообщению то бот к тексту добавляет ссылку на файл, а текст берёт из `message.caption`.
* [ ] Когда удаляешь файл, то пусть все привязки к нему удаляются.

* [ ] Полноценные уведомления.


### #Already done
* [X] Добавить погоду на 5 дней `/forecast {city}`
* [X] SQL ORM с диапазонами.
* [X] Генерация сообщений по шаблону `"{template}"`.


### #Removed from TODO
* <s>_Убрать возможность пересылки обычных сообщений_</s>
* <s>Вставлять праздники за прошлые года</s>
* <s>Добавить возможностью делиться результатом через поиск</s>
* <s>Праздники на каждый день</s>

---

```
git clone https://github.com/EgorKhabarov/TODO-telegram-bot.git
```
