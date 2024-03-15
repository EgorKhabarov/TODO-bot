class ApiError(Exception):
    pass

class UserNotFound(Exception):
    pass

class NotEnoughPermissions(Exception):
    pass

class GroupNotFound(Exception):
    pass

class NotGroupMember(Exception):
    pass

class EventNotFound(Exception):
    pass

class LimitExceeded(Exception):
    pass

class TextIsTooBig(Exception):
    pass
