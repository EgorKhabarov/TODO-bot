class ApiError(Exception):
    pass


class Forbidden(Exception):
    pass


class NotEnoughPermissions(Exception):
    pass


class UserNotFound(Exception):
    pass


class GroupNotFound(Exception):
    pass


class NotGroupMember(Exception):
    pass


class EventNotFound(Exception):
    pass


class MediaNotFound(Exception):
    pass


class LimitExceeded(Exception):
    pass


class TextIsTooBig(Exception):
    pass


class WrongDate(Exception):
    pass


class StatusConflict(Exception):
    pass


class StatusLengthExceeded(Exception):
    pass


class StatusRepeats(Exception):
    pass
