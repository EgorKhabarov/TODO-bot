<table>
    <tr>
        <td>Название метода</td>
        <td>Описание</td>
        <td>Параметры</td>
        <td>Текст ошибки</td>
        <td>Описание ошибки</td>
    </tr>
    <tr>
        <td>check_event</td>
        <td>Проверить наличие события.<br>Возвращает `true` или `false`.</td>
        <td>event_id: int - id события.<br>in_wastebasket: bool - искать в корзине.</td>
        <td>_</td>
        <td>_</td>
    </tr>
    <tr>
        <td>check_user</td>
        <td>Проверить наличие пользователя.</td>
        <td>user_id: int - id пользователя.</td>
        <td>_</td>
        <td>_</td>
    </tr>
    <tr>
        <td>get_limits</td>
        <td>Возвращает список процентов заполнения лимитов.</td>
        <td>date: str | None = None - Дата</td>
        <td>_</td>
        <td>_</td>
    </tr>
    <tr>
        <td rowspan="2">check_limit</td>
        <td rowspan="2">Проверить лимит на добавление событий или символов.</td>
        <td rowspan="2">date: str | None = None - Дата<br>event_count: int = 0 - Количество добавленных событий<br>symbol_count: int = 0 - Количество добавленных символов</td>
        <td>"Invalid Date Format"</td>
        <td>Формат даты неверный.</td>
    </tr>
    <tr>
        <td>"Wrong Date"</td>
        <td>Неверная дата.</td>
    </tr>
    <tr>
        <td rowspan="3">get_event</td>
        <td rowspan="3">Возвращает одно событие.</td>
        <td rowspan="3">event_id: int - id события.<br>in_wastebasket: bool = False - искать в корзине.</td>
        <td>"Неверный id"</td>
        <td>Неверный id.</td>
    </tr>
    <tr>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td>"Events Not Found"</td>
        <td>Событие не найдено.</td>
    </tr>
    <tr>
        <td rowspan="2">get_events</td>
        <td rowspan="2">Возвращает события по списку id.</td>
        <td rowspan="2">events_id: list | tuple[int, ...] - Список из id.<br>direction: Literal[-1, 1, "DESC", "ASC"] = -1 - Направление сортировки.</td>
        <td>'direction must be in [-1, 1, "DESC", "ASC"]'</td>
        <td>Неверный direction.</td>
    </tr>
    <tr>
        <td>"SQL Error"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td>get_settings</td>
        <td>_</td>
        <td>_</td>
        <td>_</td>
        <td>_</td>
    </tr>
    <tr>
        <td rowspan="5">add_event</td>
        <td rowspan="5">Добавить событие.</td>
        <td rowspan="5">date: str - Дата.<br>text: str - Текст.</td>
        <td>"Text Is Too Big"</td>
        <td>Текст слишком большой.</td>
    </tr>
    <tr>
        <td>"Invalid Date Format"</td>
        <td>Формат даты неверный.</td>
    </tr>
    <tr>
        <td>"Wrong Date"</td>
        <td>Неверная дата.</td>
    </tr>
    <tr>
        <td>"Limit Exceeded"</td>
        <td>Лимит превышен.</td>
    </tr>
    <tr>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td rowspan="4">edit_event</td>
        <td rowspan="4">Изменить текст события.</td>
        <td rowspan="4">event_id: int - id событий.<br>text: str - Текст.</td>
        <td>"Text Is Too Big"</td>
        <td>Текст слишком большой.</td>
    </tr>
    <tr>
        <td>"Event Not Found"</td>
        <td>Событие не найдено.</td>
    </tr>
    <tr>
        <td>"Limit Exceeded"</td>
        <td>Лимит превышен.</td>
    </tr>
    <tr>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td rowspan="2">delete_event</td>
        <td rowspan="2">Удалить событие.</td>
        <td rowspan="2">event_id: int - id события.<br>to_bin: bool = False - Удалить в корзину.</td>
        <td>"Event Not Found"</td>
        <td>Событие не найдено.</td>
    </tr>
    <tr>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td rowspan="5">edit_event_date</td>
        <td rowspan="5">Изменить дату.</td>
        <td rowspan="5">event_id: int - id события.<br>date: str - Дата.</td>
        <td>"Invalid Date Format"</td>
        <td>Формат даты неверный.</td>
    </tr>
    <tr>
        <td>"Wrong Date"</td>
        <td>Неверная дата.</td>
    </tr>
    <tr>
        <td>"Event Not Found"</td>
        <td>Событие не найдено.</td>
    </tr>
    <tr>
        <td>"Limit Exceeded"</td>
        <td>Лимит превышен.</td>
    </tr>
    <tr>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td rowspan="2">recover_event</td>
        <td rowspan="2">Восстановить событие из корзины.</td>
        <td rowspan="2">event_id: int - id события.</td>
        <td>"Event Not Found"</td>
        <td>Событие не найдено.</td>
    </tr>
    <tr>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td rowspan="5">set_status</td>
        <td rowspan="5">Поставить статус.</td>
        <td rowspan="5">event_id: int - id события.<br>status: str = "⬜️" - Статус.</td>
        <td>"Event Not Found"</td>
        <td>Событие не было найдено.</td>
    </tr>
    <tr>
        <td>"Status Conflict"</td>
        <td>В статусах есть конфликты.</td>
    </tr>
    <tr>
        <td>"Status Length Exceeded"</td>
        <td>Статус слишком большой.</td>
    </tr>
    <tr>
        <td>"Status Repeats"</td>
        <td>Статусы повторяются.</td>
    </tr>
    <tr>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td>clear_basket</td>
        <td>Очистить корзину.</td>
        <td>_</td>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
    <tr>
        <td rowspan="2">export_data</td>
        <td rowspan="2">Экспортировать в csv.</td>
        <td rowspan="2">file_name: str - Имя файла<br>file_format: str = "csv" - Формат файла</td>
        <td>"Format Is Not Valid"</td>
        <td>Невалидный формат.</td>
    </tr>
    <tr>
        <td>"Wait x min"</td>
        <td>Слишком часто запрашивали, ждите x минут.</td>
    </tr>
    <tr>
        <td rowspan="8">set_settings</td>
        <td rowspan="8">Установить настройку.</td>
        <td rowspan="8">lang: Literal["ru", "en"] = None = Язык.<br>sub_urls: Literal[0, 1] = None - Сокращать ли url в сообщениях.<br>city: str = None - Название города.<br>timezone: int = None - Часовой пояс.<br>direction: Literal["DESC", "ASC"] = None - Направление сортировки.<br>user_status: Literal[-1, 0, 1, 2] = None - Статус пользователя.<br>notifications: Literal[0, 1] = None - Включены ли уведомления.<br>notifications_time: str = None - Время уведомления.</td>
        <td>'lang must be in ["ru", "en"]'</td>
        <td></td>
    </tr>
    <tr>
        <td>"sub_urls must be in [0, 1]"</td>
        <td></td>
    </tr>
    <tr>
        <td>"timezone must be -12 and less 12"</td>
        <td></td>
    </tr>
    <tr>
        <td>'direction must be in ["DESC", "ASC"]'</td>
        <td></td>
    </tr>
    <tr>
        <td>"user_status must be in [-1, 0, 1, 2]"</td>
        <td></td>
    </tr>
    <tr>
        <td>"notifications must be in [0, 1]"</td>
        <td></td>
    </tr>
    <tr>
        <td>"hour must be more -1 and less 13"</td>
        <td></td>
    </tr>
    <tr>
        <td>"minute must be in [0, 10, 20, 30, 40, 50]"</td>
        <td></td>
    </tr>
    <tr>
        <td rowspan="5">delete_user</td>
        <td rowspan="5">Удалить все данные пользователя.</td>
        <td rowspan="5">user_id: int = None - id пользователя.</td>
        <td>"User Not Exist"</td>
        <td>Пользователь не существует.</td>
    </tr>
    <tr>
        <td>"Not Enough Authority"</td>
        <td>Недостаточно прав.</td>
    </tr>
    <tr>
        <td>"Unable To Remove Administrator"</td>
        <td>Нельзя удалить администратора.</td>
    </tr>
    <tr>
        <td>"Error"</td>
        <td>Не получилось получить csv файл.</td>
    </tr>
    <tr>
        <td>("SQL Error {}", csv_file)</td>
        <td>Ошибка при удалении.</td>
    </tr>
    <tr>
        <td rowspan="5">set_user_status</td>
        <td rowspan="5">Поставить статус пользователю.</td>
        <td rowspan="5">user_id: int = None - id пользователя.<br>status: Literal[-1, 0, 1, 2] = 0 - Статус.</td>
        <td>"User Not Exist"</td>
        <td>Пользователь не существует.</td>
    </tr>
    <tr>
        <td>"Not Enough Authority"</td>
        <td>Недостаточно прав.</td>
    </tr>
    <tr>
        <td>"Invalid status"</td>
        <td>Неверный статус.</td>
    </tr>
    <tr>
        <td>"Cannot be reduced in admin rights"</td>
        <td>Нельзя понизить администратора.</td>
    </tr>
    <tr>
        <td>"SQL Error {}"</td>
        <td>Ошибка sql.</td>
    </tr>
</table>
