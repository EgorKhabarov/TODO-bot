<table>
    <td><a href="/README.md">EN</a></td>
    <td><a href="/README_ru.md">RU</a></td>
</table>

<h1>Bot for organizing notes by dates.</h1>
<i>Storing, adding, editing and deleting notes by date.
You can tag a note with an emoji.
Convenient search by emoji statuses and dates.
Birthdays and holidays are marked on the calendar (you need to set an emoji status).</i>

[Installation instructions](/setup.md)

---

# Commands
  * [/start](#start)
  * [/menu](#menu)
    * [/help](#help)
    * [/calendar](#calendar)
    * [account](#account)
    * [groups](#groups)
    * [/week_event_list](#week_event_list)
    * [notifications](#notifications)
    * [/settings](#settings)
    * [trash](#trash)
    * [admin](#admin)
  * [/calendar](#calendar)
  * [/today](#today)
  * [/weather](#weather)
  * [/forecast](#forecast)
  * [/week_event_list](#week_event_list)
  * [/export](#export)


## start

Greets the user

| Buttons                  | Actions                                     |
|:-------------------------|---------------------------------------------|
| [/menu](#menu)           | Same as /menu command                       |
| [/calendar](#calendar)   | Same as /calendar command                   |
| [Add a bot to a group]() | Calls up a dialog box for selecting a group |


## menu

Navigation through bot functions

| Buttons          | Actions                                               |
|:-----------------|-------------------------------------------------------|
| 📚 Help          | Same as /help                                         |
| 📆Calendar       | Same as /calendar                                     |
| 👤 Account       | Personal account and data export                      |
| 👥 Groups        | Group settings                                        |
| 📆 7 days        | Events in the next 7 days                             |
| 🔔 Notifications | View events that will be included in the notification |
| ⚙️Settings       | Same as /settings                                     |
| 🗑 Cart          | Recycle bin with deleted events (premium)             |
| 😎 Admin         | Admin panel (admin)                                   |

## help

Gives access to information about the bot's capabilities

## calendar

Calendar

<table>
    <tr><th colspan="7">January (1.2000) (Leap 🐲) (52-5)</th></tr>
    <tr><th>  Mo </th><th> Tu! </th><th> We </th><th> Th </th><th> Fr </th><th> Sa </th><th> Su </th></tr>
    <tr><th>     </th><th>     </th><th>    </th><th>    </th><th>    </th><th> #1 </th><th>  2 </th></tr>
    <tr><th>   3 </th><th> 4!* </th><th>  5 </th><th> 6* </th><th>  7 </th><th>  8 </th><th>  9 </th></tr>
    <tr><th> 10! </th><th>  11 </th><th> 12 </th><th> 13 </th><th> 14 </th><th> 15 </th><th> 16 </th></tr>
    <tr><th>  17 </th><th>  18 </th><th> 19 </th><th> 20 </th><th> 21 </th><th> 22 </th><th> 23 </th></tr>
    <tr><th>  24 </th><th>  25 </th><th> 26 </th><th> 27 </th><th> 28 </th><th> 29 </th><th> 30 </th></tr>
    <tr><th>  31 </th><th>     </th><th>    </th><th>    </th><th>    </th><th>    </th><th>    </th></tr>
    <tr><th colspan="2"><<</th><th><</th><th>⟳</th><th>></th><th colspan="2">>></th></tr>
</table>

### Designations

#### First button

When pressed, a yearly calendar appears.

| Designation | Meaning                                       |
|-------------|-----------------------------------------------|
| January     | Names of the month                            |
| (1.2000)    | Month and year numbers                        |
| (Leap 🐲)   | Is it a leap year and the animal of this year |
| (52-5)      | Numbers of the first and last week            |

#### Days of the week

When pressed, they do nothing.
The text on the button may end with the `!` character.
This means that on this day of the week there are repeating events with an interval of a week ([more about statuses](#Event-statuses)).

#### Button for the day

When pressed, it calls up [message for one day](#message-for-one-day)

| Sign | Designation                                                                                                                              |
|:----:|------------------------------------------------------------------------------------------------------------------------------------------|
| `#`  | Today                                                                                                                                    |
| `*`  | There are events on this day<br>If there are less than 10 events then it will consist of degree icons<br>indicating the number of events |
| `!`  | There is an important event on this day<br>For example, with the status birthday `🎉` or holiday `🎊`                                    |

#### Navigation buttons

| Sign | Designation                          |
|------|--------------------------------------|
| `<<` | Show calendar for **one year ago**   |
| `<`  | Show calendar for **one month ago**  |
| `⟳`  | Show calendar for **current date**   |
| `>`  | Show calendar **one month ahead**    |
| `>>` | Show calendar for **one year ahead** |

## account


## groups

## week_event_list

Message with events in the next 7 days.

## notifications

Message with events for today, tomorrow, after tomorrow, after after tomorrow and in a week.

## settings

Message with settings.

<table>
    <tr>
        <th>🗣 ru </th>
        <th>🔗 True </th>
        <th>⬆️ </th>
        <th>🔕 </th>
        <th>⬛️ </th>
    </tr>
    <tr>
        <th>-3 </th>
        <th>-1 </th>
        <th>3 🌍 </th>
        <th>+1 </th>
        <th>+3 </th>
    </tr>
    <tr>
        <th>-1h </th>
        <th>-10m </th>
        <th>08:00 ⏰ </th>
        <th>+10m </th>
        <th>+1h </th>
    </tr>
    <tr><th colspan="5">Default settings</th></tr>
</table>

|    Sign     | Designation                                                                                                                     |
|:-----------:|:--------------------------------------------------------------------------------------------------------------------------------|
|     🗣      | Language (default `ru`)                                                                                                         |
|    `🔗`     | Should I shorten links (https://en.wikipedia.org/wiki/Hyperlink -> [en.wikipedia.org](https://en.wikipedia.org/wiki/Hyperlink)) |
| `⬇️` / `⬆️` | Event sort order                                                                                                                | |
|    `🔕`     | Whether to enable notifications (disabled by default)                                                                           |
| `⬜️` / `⬛️` | Bot theme (replaces dark emoticons with light ones)                                                                             |
|     🌍      | Your time zone                                                                                                                  |
|      ⏰      | Notification Time                                                                                                               |


## trash

List of deleted events.

| 🔼 | ↕️ |
|----|----|
| 🧹 | 🔄 |

| Sign | Designation            |
|------|------------------------|
| 🔼   | Select one event       |
| ↕️   | Select multiple events |
| 🧹   | Empty Trash            |
| 🔄   | Update cart            |

## admin

## today

| ➕  | 🔼 | ↕️   | Menu |
|----|----|------|------|
| 🔙 | <  | &gt; | 🔄   |

| Sign   | Designation                |
|--------|----------------------------|
| `➕`    | Add event                  |
| `🔼`   | Select one event           |
| `↕️`   | Select multiple events     |
| `Menu` | Return to menu             |
| `🔙`   | Return to calendar         |
| `<`    | Show message for yesterday |
| `>`    | Show message for tomorrow  |
| `🔄`   | Update message             |

## weather

## forecast

## export

Export events in different file formats `csv`, `xml`, `json`, `jsonl`.

## Message for one day

<table>
    <tr><th>📝</th><th><code>🏷</code> / <code>🚩</code></th><th>🗑</th></tr>
    <tr><th colspan="3">📅 Change date</th></tr>
    <tr><th>🔙</th><th>ℹ️</th><th>🔄</th></tr>
</table>

When you click on a button in the calendar with a date, today's date opens.

|   Button    | Action                        |
|:-----------:|:------------------------------|
|    `📝`     | Edit event text               |
| `🏷` / `🚩` | Add status to event           |
|    `🗑`     | Delete event                  |
|    `📅`     | Change event date             |
|    `🔙`     | Return to message for the day |
|    `ℹ️`     | Event Information             |
|    `🔄`     | Update message                |

## Event statuses

A status is one or more emoji to mark an event or add different effects.
**An event can have a maximum of 5 statuses.**

There are incompatible statuses.
They cannot be placed together in the same event.
If you have one event from a pair, then you will not be able to place the second one.

| Incompatible statuses                    |
|------------------------------------------|
| `🔗` (Link) and `💻` (Code)              |
| `🪞` (Hidden) and `💻` (Code)            |
| `🔗` (Link) and `⛓` (No link shortening) |
| `🧮` (Numbered List) and `🗒` (List)     |

Effects on statuses are applied only when displaying events in a message. The event text itself does not change in the database.

## Limits

There are limits for different user groups

### Maximum possible values

| user_status | event<br>day | symbol<br>day | event<br>month | symbol<br>month | event<br>year | symbol<br>year | event<br>all | symbol<br>all |
|:------------|--------------|---------------|----------------|-----------------|---------------|----------------|--------------|---------------|
| default     | 20           | 4000          | 75             | 10000           | 500           | 80000          | 500          | 100000        |
| premium     | 40           | 8000          | 100            | 15000           | 750           | 100000         | 900          | 150000        |
| admin       | 60           | 20000         | 200            | 65000           | 1000          | 120000         | 2000         | 200000        |

## Search

The bot has a search by events. You can search using the commands `#query` or `/search query`.
This search attempts to find all matches.<br>
Query `#1 2` searches for all events that contain the numbers 1 <b>OR</b> 2 (`t1ext`, `tex2t`, `2te1xt`)<br>
There is also a search for <b>AND</b>. It searches only for those events in which all conditions completely match. You can search with this search using the command `#!query` or `/search! query`.<br>
The `#!1 2` request will return only those events that contain 1 <b>AND</b> 2 (`text12`, `te2xt1`).

You can use templates in your search query

| What to look for | template/s                                                             |
|:-----------------|:-----------------------------------------------------------------------|
| Date             | `date=dd.mm.yyyy`<br>`date=dd.mm`<br>`date=mm.yyyy`<br>`date=dd..yyyy` |
| Day number       | `day=00`                                                               |
| Month number     | `mon=0`<br>`month=0`                                                   |
| Year             | `year=0000`                                                            |
| Event Status     | `status=⬜️`                                                            |
| event id         | `id=0`                                                                 |

For example, `#date=1.2023 status=🎧 youtube.com` to search for all events with music status for January 2023 that have a link to youtube.

# TODO

* [ ] Add action when select more
* [ ] Make a closure for the argument parser
* [ ] DB schema
* [ ] Transfer event IDs directly to buttons
* [ ] Your own condition language parser for effective search
* [ ] Make webhooks and test so that requests when falling asleep are not repeated twice
* [ ] Set up custom autodeploy
