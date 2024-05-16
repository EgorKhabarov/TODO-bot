from tests.chat import Chat, setup_request

with Chat():
    from tgbot.request import request
    from tests.mocks import callback_mock
    from tgbot.handlers import callback_handler
    from todoapi.exceptions import NotEnoughPermissions


def test_bot_callback_mnm():
    with Chat() as chat:
        setup_request(callback_mock("mnm"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mns():
    with Chat() as chat:
        setup_request(callback_mock("mns"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mnw():
    with Chat() as chat:
        setup_request(callback_mock("mnw"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mngrs():
    with Chat() as chat:
        setup_request(callback_mock("mngrs al 1"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mngr():
    with Chat() as chat:
        group_id = request.entity.create_group("GROUP_NAME")
        setup_request(callback_mock(f"mngr {group_id} al"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mna():
    with Chat() as chat:
        setup_request(callback_mock("mna"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mnc():
    with Chat() as chat:
        setup_request(callback_mock("mnc ('now',)"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mnh():
    with Chat() as chat:
        setup_request(callback_mock("mnh page 1"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mnb():
    with Chat() as chat:
        setup_request(callback_mock("mnb"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["text"]
                and k["params"]["show_alert"]
            ),
        )


def test_bot_callback_mnn():
    with Chat() as chat:
        setup_request(callback_mock("mnn"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_mnsr():
    with Chat() as chat:
        setup_request(callback_mock("mnsr"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_dl():
    with Chat() as chat:
        setup_request(callback_mock("dl 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )

        chat.clear()
        request.entity.create_event("01.01.2000", "event text")
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_em():
    with Chat() as chat:
        setup_request(callback_mock("em 1"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["show_alert"]
            ),
        )

        chat.clear()
        event_id = request.entity.create_event("01.01.2000", "event text")
        setup_request(callback_mock(f"em {event_id}"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_ea():
    with Chat() as chat:
        setup_request(callback_mock("ea 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["text"]
            ),
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_es():
    with Chat() as chat:
        # TODO 'NoneType' object has no attribute '_status'
        """
        generated.event._status = json.dumps(statuses_list[-5:], ensure_ascii=False)
        'NoneType' object has no attribute '_status'
        """
        request.entity.create_event("01.01.2000", "event text")
        setup_request(callback_mock("es ⬜ 1 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_ess():
    with Chat() as chat:
        setup_request(callback_mock("ess 1 01.01.2000 ✅"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_eet():
    with Chat() as chat:
        setup_request(callback_mock("eet 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["text"]
                and k["params"]["show_alert"]
            ),
        )


def test_bot_callback_eds():
    with Chat() as chat:
        request.entity.create_event("01.01.2000", "event text")
        setup_request(callback_mock("eds 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["text"]
            ),
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_ed():
    with Chat() as chat:
        setup_request(callback_mock("ed 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["text"]
            ),
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_edb():
    with Chat() as chat:
        setup_request(callback_mock("edb 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["text"]
            ),
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_esdt():
    with Chat() as chat:
        setup_request(callback_mock("esdt 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_ebd():
    with Chat() as chat:
        setup_request(callback_mock("ebd 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_eab():
    with Chat() as chat:
        setup_request(callback_mock("eab 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_esh():
    with Chat() as chat:
        setup_request(callback_mock("esh 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_eh():
    with Chat() as chat:
        setup_request(callback_mock("eh 1 01.01.2000 1"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_esm():
    with Chat() as chat:
        setup_request(callback_mock("esm 0"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_esbd():
    with Chat() as chat:
        setup_request(callback_mock("esbd 0"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_essd():
    with Chat() as chat:
        setup_request(callback_mock("essd 0"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_esd():
    with Chat() as chat:
        setup_request(callback_mock("esd 0 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["text"]
            ),
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_esdb():
    with Chat() as chat:
        setup_request(callback_mock("esdb 0 01.01.2000"))
        try:
            callback_handler(request.query)
        except NotEnoughPermissions:
            pass
        else:
            assert False, "not raised todoapi.exceptions.NotEnoughPermissions"

        # Change user status
        chat.clear()
        # callback_handler(request.query)
        # assert chat.comparer(
        #     lambda m, u, k: (
        #         u.endswith("editMessageText")
        #         and k["params"]["text"]
        #         and k["params"]["chat_id"] == 1
        #         and k["params"]["message_id"] == 1
        #         and k["params"]["reply_markup"]
        #     ),
        # )


def test_bot_callback_esds():
    with Chat() as chat:
        setup_request(callback_mock("esds 0 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["callback_query_id"] == 100
                and k["params"]["text"]
                and k["params"]["show_alert"]
            ),
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


# def test_bot_callback_se():
#     with Chat() as chat:
#         setup_request(callback_mock("se"))
#         callback_handler(request.query)
#         assert chat.comparer(
#             lambda m, u, k: (
#                 u.endswith("editMessageText")
#                 and k["params"]["text"]
#                 and k["params"]["chat_id"] == 1
#                 and k["params"]["message_id"] == 1
#                 and k["params"]["reply_markup"]
#             ),
#         )
#
#
# def test_bot_callback_ses():
#     with Chat() as chat:
#         setup_request(callback_mock("ses"))
#         callback_handler(request.query)
#         assert chat.comparer(
#             lambda m, u, k: (
#                 u.endswith("editMessageText")
#                 and k["params"]["text"]
#                 and k["params"]["chat_id"] == 1
#                 and k["params"]["message_id"] == 1
#                 and k["params"]["reply_markup"]
#             ),
#         )
