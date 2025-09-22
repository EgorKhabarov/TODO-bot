from tests.chat import Chat, setup_request

with Chat():
    from notes_bot.request import request
    from tests.mocks import callback_mock, message_mock
    from notes_bot.handlers import callback_handler

    # from notes_api.types import set_user_status
    from notes_api.exceptions import NotEnoughPermissions


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
        setup_request(callback_mock("mnh page main"))
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


# def test_bot_callback_mnb():
#     with Chat() as chat:
#         setup_request(callback_mock("mnb"))
#         callback_handler(request.query)
#         assert chat.comparer(
#             lambda m, u, k: (
#                 u.endswith("answerCallbackQuery")
#                 and k["params"]["callback_query_id"] == 100
#                 and k["params"]["text"]
#                 and k["params"]["show_alert"]
#             ),
#         )
#         set_user_status(request.entity.user_id, 2)
#         setup_request(callback_mock("mnb"))
#         callback_handler(request.query)
#         assert chat.comparer(
#             lambda m, u, k: (
#                 u.endswith("answerCallbackQuery")
#                 and k["params"]["callback_query_id"] == 100
#                 and k["params"]["text"]
#                 and k["params"]["show_alert"]
#             ),
#         )


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
            assert False, "not raised notes_api.exceptions.NotEnoughPermissions"

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
"""
sal_or_sbal
son_or_sbon
"""


def test_bot_callback_pd():
    with Chat() as chat:
        setup_request(callback_mock("pd 01.01.2000 0"))
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


def test_bot_callback_pr():
    with Chat() as chat:
        setup_request(callback_mock("pr 01.01.2000 0"))
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


def test_bot_callback_ps():
    with Chat() as chat:
        setup_request(callback_mock("ps 1"))
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


def test_bot_callback_pw():
    with Chat() as chat:
        setup_request(callback_mock("pw 0"))
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


def test_bot_callback_pb():
    with Chat() as chat:
        setup_request(callback_mock("pb 0"))
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


def test_bot_callback_pn():
    with Chat() as chat:
        setup_request(callback_mock("pn 01.01.2000 0"))
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


def test_bot_callback_cm():
    pass  # eval_=True


def test_bot_callback_cy():
    pass  # eval_=True


def test_bot_callback_ct():
    pass  # eval_=True


def test_bot_callback_us():
    with Chat() as chat:
        setup_request(callback_mock("us"))
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


def test_bot_callback_sfs():
    with Chat() as chat:
        setup_request(callback_mock("sfs", message_mock(1, "🔍 message: text")))
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


def test_bot_callback_sf():
    with Chat() as chat:
        setup_request(callback_mock("sf", message_mock(1, "🔍⚙️ message: text")))
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


def test_bot_callback_sfe():
    with Chat() as chat:
        setup_request(callback_mock("sfe", message_mock(1, "🔍 message: text")))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendChatAction")
                and k["params"]["chat_id"] == 1
                and k["params"]["action"] == "upload_document"
            ),
            lambda m, u, k: (
                u.endswith("sendDocument") and k["params"]["chat_id"] == 1
            ),
        )


def test_bot_callback_md():
    with Chat() as chat:
        setup_request(callback_mock("md"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("deleteMessage")
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
            ),
        )


def test_bot_callback_std():
    with Chat() as chat:
        setup_request(callback_mock("std"))
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


def test_bot_callback_stu():
    with Chat() as chat:
        setup_request(callback_mock("stu ('en', 1, 4, 0, '08:00', 0)"))
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


def test_bot_callback_sts():
    with Chat() as chat:
        setup_request(callback_mock("sts ('en', 1, 4, 0, '08:00', 0)"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (u.endswith("setMyCommands") and k["params"]["commands"]),
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
            ),
        )


def test_bot_callback_stl():
    with Chat() as chat:
        setup_request(callback_mock("stl ru"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("setMyCommands")
                and k["params"]["commands"]
                and k["params"]["scope"]
            ),
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
            ),
        )


# def test_bot_callback_bcl():
#     with Chat() as chat:
#         setup_request(callback_mock("bcl"))
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


def test_bot_callback_bem():
    with Chat() as chat:
        setup_request(callback_mock("bem 1"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["text"]
                and k["params"]["callback_query_id"] == 100
                and k["params"]["show_alert"]
            ),
        )


def test_bot_callback_bed():
    with Chat() as chat:
        setup_request(callback_mock("bed 1"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["text"]
                and k["params"]["callback_query_id"] == 100
            ),
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_callback_ber():
    with Chat() as chat:
        setup_request(callback_mock("ber 1 01.01.2000"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("answerCallbackQuery")
                and k["params"]["text"]
                and k["params"]["callback_query_id"] == 100
                and k["params"]["show_alert"]
            ),
        )


def test_bot_callback_bsm():
    pass  # {"id_list": "str"}


def test_bot_callback_bsd():
    pass  # {"id_list": "str"}


def test_bot_callback_bsr():
    pass  # {"id_list": "str", "date": "date"}


def test_bot_callback_logout():
    with Chat() as chat:
        setup_request(callback_mock("logout"))
        callback_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (u.endswith("setMyCommands") and k["params"]["commands"]),
            lambda m, u, k: (
                u.endswith("editMessageText")
                and k["params"]["text"]
                and k["params"]["chat_id"] == 1
                and k["params"]["message_id"] == 1
            ),
        )


def test_bot_callback_lm():
    pass  # {"date": "date"}


def test_bot_callback_grcr():
    pass


def test_bot_callback_gre():
    pass  # {"group_id": "str", "file_format": ("str", "csv")}


def test_bot_callback_grdb():
    pass  # {"group_id": "str", "mode": ("str", "al")}


def test_bot_callback_grd():
    pass  # {"group_id": "str", "mode": ("str", "al")}


def test_bot_callback_grlv():
    pass  # {"group_id": "str", "mode": ("str", "al")}


def test_bot_callback_grrgr():
    pass  # {"group_id": "str", "mode": ("str", "al")}


def test_bot_callback_get_premium():
    pass
