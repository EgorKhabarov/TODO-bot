<table>
    <td><a href="/README.md">EN</a></td>  <!-- <img src="https://www.megaflag.ru/sites/default/files/images/shop/products/flag_velikobritanija_new.jpg" width="30" alt="EN"> -->
    <td><a href="/README_ru.md">RU</a></td>  <!-- <img src="https://www.megaflag.ru/sites/default/files/images/shop/products/flag_rf_enl.jpg"           width="30" alt="RU"> -->
</table>

<h1>Bot for organizing notes by dates.</h1>
<i>Storing, adding, editing and deleting notes by date.
You can tag a note with an emoji.
Convenient search by emoji statuses and dates.
Birthdays and holidays are marked on the calendar (you need to set an emoji status).</i>

---

The `/calendar` command gives you access to the calendar.
You can immediately select a date or scroll to another month or year using the `<` `>` and `<<` `>>` buttons, respectively.<br>
The `⟳` button returns the calendar to the current date if it is on another, otherwise it goes one step down the menu and eventually opens a message with the current date.<br>
By pressing the topmost button with the name of the month and information about the year, you can open a list of months.

<img alt="calendar.png" src="images/calendar.png" style="border-radius: 17px;">

There are several symbols on the calendar.

| Sign | Meaning                                                                                                                                                                                                                  |
|:----:|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `#`  | Today's day number (shown in any months)                                                                                                                                                                                 |
| `*`  | There are events on this day                                                                                                                                                                                             |
| `!`  | On this day or on this day of another year there is an event with the status or a birthday `🎉`<br>or a holiday `🎊`<br/> <details><summary>More</summary>It helps not to forget, that someone has a birthday.</details> |


<img alt="calendar.png" src="images/calendar_elements.png" style="border-radius: 10px;">

When you click on the button in the calendar with the date, today's date opens.

| Button  | Action                           |
|:-------:|:---------------------------------|
|   `➕`   | Add event                        |
|  `📝`   | Edit event                       |
|  `🚩`   | Set status for event             |
|  `🗑`   | Delete event                     |
|  `🔙`   | Back                             |
| `<` `>` | 1 day ahead or back              |
|   `✖`   | Delete this message from the bot |


<img alt="calendar.png" src="images/date.png" style="border-radius: 16px;">

# [Limits](/func.py#L771&L775)

The bot has limits for different user groups.

| user_status | price | maximum characters/day | maximum events/day |
|:------------|:------|:-----------------------|:-------------------|
| default     | 0     | 4000                   | 20                 |
| premium     | 🤷    | 8000                   | 40                 |
| admin       | -     | ∞                      | ∞                  |

# [Поиск](/func.py#L684&L704)

The bot has a search by events. You can search with `#query` or `/search query` commands.
This search tries to find all matches.<br>
The query `#1 2` searches for all events that contain the digits 1 <b>OR</b> 2 (`t1ext`, `tex2t`, `2te1xt`)<br>
There is also a search for <b>AND</b>. It searches only for those events in which all conditions are exactly the same. You can search with such a search with the `#!query` command or `/search! query`.<br>
The `#!1 2` request will return only those events that have 1 <b>AND</b> 2 (`text12`, `te2xt1`).

You can use wildcards in your search query

| What to look for | template/s                                                             |
|:-----------------|:-----------------------------------------------------------------------|
| Date             | `date=dd.mm.yyyy`<br>`date=dd.mm`<br>`date=mm.yyyy`<br>`date=dd..yyyy` |
| Day number       | `day=00`                                                               |
| Month number     | `mon=0`<br>`month=0`                                                   |
| Year             | `year=0000`                                                            |
| Event Status     | `status=⬜️`                                                            |
| event id         | `id=0`                                                                 |

For example `#date=1.2023 status=🎧 youtube.com` to search for all events with music status for January 2023 that have a link to YouTube.




<details>
<summary>Commands</summary>

# [Commands](/lang.py#L472)
| Command          | Description                 |
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

</details>

<details>
<summary>DataBase</summary>

# [DataBase](/func.py#L93&L125)

* ### [root](/func.py#L102&L109)
| name     | data type | default value |
|:---------|:----------|:--------------|
| event_id | INT       | _NULL_        |
| user_id  | INT       | _NULL_        |
| date     | TEXT      | _NULL_        |
| text     | TEXT      | _NULL_        |
| isdel    | INT       | 0             |
| status   | TEXT      | ⬜️            |

* ### [settings](/func.py#L115&L125)
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

</details>

# #TODO
* [ ] Ability to view _recurring events_ in the `/week_event_list` command.
* [ ] When trying to create files, immediately update the initial set of commands for all users
* [ ] If there are no events for a specific day now, but there were earlier, and they remained in the old message, then process the error and update the message.<br>Instead of parsing from the message, make a database query
* [ ] Comment and clean up the code.
* [ ] Groups for event statuses.
* [ ] Sort in week_event_list by date
* [ ] Ability to search by the date of the selected event
* [ ] Add templates to search<br>
  `#date=dd.mm.yyyy` or `#date=dd.mm` or `#date=mm.yyyy` or `#date=dd..yyyy`<br>
  `#day=00`<br>
  `#month=0`<br>
  `#year=0000`<br>
  `#status=⬜️`<br>
  `#id=0`<br>
  For example `#date=1.2023 status=🎧` to search for all events with music status for January 2023.<br>
  Add support for special characters sql LIKE (%, _ etc.).<br>
  Search <b><u>AND</u></b> `#!query` only what is in the search without variations.
* [ ] Add the ability to convert currencies via api.


* [ ] Explorer (Similar file system)<br>
  For storing large text files or images (<u>admin only</u>).<br>
  <b>Can be done via Google|Yandex drive api</b>
* [ ] When you add an event, let if a photo or a file is attached to the message, then the bot adds a link to the file to the text, and takes the text from `message.caption`.
* [ ] When you delete a file, then let all bindings to it be deleted.

* [ ] Full notifications.


# Already done
* [X] Schedule statuses. Repeat every week and year. Similar to birthday status.
* [X] Ability to remove from cart.
* [X] Ability to restore an event from the trash.
* [X] Add weather for 5 days `/forecast {city}`
* [X] SQL ORM with ranges.
* [X] Generation of messages according to the template `"{template}"`.
* [X] Change user_status for admins, add status -1 it's banned (ignore messages).<br>
  Changing the list of commands for a user depending on user_status


# Removed from TODO
* <s>The `/account` command. Number of messages.<br>
  As in GitHub, a graph of the presence of events with colored emoticons `⬜️(0) 🟩(1,3) 🟨(4,6) 🟧(7,9) 🟥(>=10)`</s>
* <s>_Remove the ability to forward regular messages_</s>
* <s>Insert holidays for previous years</s>
* <s>Add the ability to share results via search</s>
* <s>Holidays for every day</s>

---

```
git clone https://github.com/EgorKhabarov/TODO-telegram-bot.git
```
