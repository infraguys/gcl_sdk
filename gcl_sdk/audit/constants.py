import enum


class Action(str, enum.Enum):
    INSERT = "create"
    UPDATE = "update"
    DELETE = "delete"
