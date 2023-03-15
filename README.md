# Bot for organizing events by dates
#### Allows you to store, add, edit and delete notes by date


# Commands:
| Command          | Description en             |
|:-----------------|:---------------------------|
| /start           | Start                      |
| /calendar        | Calendar                   |
| /today           | Today's message            |
| /weather {city}  | Weather                    |
| /week_event_list | Weekly events              |
| /dice            | Roll the dice (randomizer) |      
| /save_to_csv     | Save my data in csv        |     
| /help            | Help                       |                          
| /settings        | Settings                   |
| /search {query}  | Search                     |
| #{query}         | Search                     |

# Limits:
###### (_func.limits_)
| user_status | price | maximum characters/day | maximum events/day |
|:------------|:------|:-----------------------|:-------------------|
| normal      | 0     | 4000                   | 20                 |
| premium     | 🤷    | 8000                   | 40                 |
| admin       | 🤷    | 999999                 | 999                |

# DataBase
* ### root  
  ###### (_func.create_tables()_)
| name     | data type | default value |
|:---------|:----------|:--------------|
| event_id | INT       | _NULL_        |
| user_id  | INT       | _NULL_        |
| date     | TEXT      | _NULL_        |
| text     | TEXT      | _NULL_        |
| isdel    | INT       | 0             |
| status   | TEXT      | ⬜️            |

* ### settings
  ###### (_func.create_tables()_)
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




## #TODO
* [ ] Прокомментировать код
* [ ] Генерация сообщений по шаблону %
* [ ] Праздники на каждый день
* [ ] Вставлять праздники за прошлые года
* [ ] Убрать возможность пересылки обычных сообщений
* [ ] Добавить погоду на 2, 3, 4, 5 дней (`/weather5 {city}`)
* [ ] Добавить возможностью делиться результатом через поиск
* [ ] Изменение user_status для админов, добавить статус -1 это в бане (игнор сообщений)
* [ ] Добавить возможность конвертировать валюты через api


* [ ] Explorer (Подобие файловой системы) для хранения больших текстовых файлов или изображений
* [ ] Когда добавляешь событие пусть если фото к боту прикреплено или файл то бот к тексту добавляет ссылку на файл, а текст берёт из _капчи_
* [ ] Когда удаляешь файл то пусть все привязки к нему удаляются



```
git clone https://github.com/EgorKhabarov/TODO-telegram-bot.git
```