import enum


class Action(str, enum.Enum):
    insert = "create"
    update = "update"
    delete = "delete"
