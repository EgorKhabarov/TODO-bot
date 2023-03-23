# Bot for organizing events by dates
#### Allows you to store, add, edit and delete notes by date


# Commands:
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

# Limits:
(_func.limits_)

| user_status | price | maximum characters/day | maximum events/day |
|:------------|:------|:-----------------------|:-------------------|
| normal      | 0     | 4000                   | 20                 |
| premium     | 🤷    | 8000                   | 40                 |
| admin       | 🤷    | 999999                 | 999                |

# DataBase
* ### root  
(_func.create_tables()_)

| name     | data type | default value |
|:---------|:----------|:--------------|
| event_id | INT       | _NULL_        |
| user_id  | INT       | _NULL_        |
| date     | TEXT      | _NULL_        |
| text     | TEXT      | _NULL_        |
| isdel    | INT       | 0             |
| status   | TEXT      | ⬜️            |

* ### settings
(_func.create_tables()_)

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




# #TODO
* [ ] Прокомментировать код.
* [ ] Генерация сообщений по шаблону `"{template}"`.
* [ ] Возможность удалить из корзины.
* [ ] SQL ORM с диапазонами.
* [ ] В поиск добавить шаблоны<br>`#date=dd.mm.yyyy` or `#date=dd.mm` or `#date=mm.yyyy` or `#date=dd..yyyy`<br>`#day=00`<br>`#month=0`<br>`#year=0000`<br>`#status=⬜️`<br>`#id=0`<br>Например `#date=1.2023 status=🎧` для поиска всех событий со статусом музыки за январь 2023 года.<br>Добавить поддержку спецсимволов sql LIKE (%, _ и.т.д.).
* [ ] Изменение user_status для админов, добавить статус -1 это в бане (игнор сообщений).
* [ ] Добавить возможность конвертировать валюты через api.


* [ ] Explorer (Подобие файловой системы) для хранения больших текстовых файлов или изображений (<u>admin only</u>).
* [ ] Когда добавляешь событие пусть если фото или файл прикреплено к сообщению то бот к тексту добавляет ссылку на файл, а текст берёт из `message.caption`.
* [ ] Когда удаляешь файл то пусть все привязки к нему удаляются.


### #Already done
* [X] Добавить погоду на 5 дней `/forecast {city}`


### #Removed from TODO
* <s>_Убрать возможность пересылки обычных сообщений_</s>
* <s>Вставлять праздники за прошлые года</s>
* <s>Добавить возможностью делиться результатом через поиск</s>
* <s>Праздники на каждый день</s>


```
git clone https://github.com/EgorKhabarov/TODO-telegram-bot.git
```
