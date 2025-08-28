import datetime
import inspect

from restalchemy.common import contexts
from restalchemy.dm import models
from restalchemy.dm import properties
from restalchemy.dm import types
from restalchemy.storage.sql import orm

from gcl_sdk.audit import constants


class AuditRecord(
    models.ModelWithTimestamp,
    models.ModelWithUUID,
    orm.SQLStorableMixin,
):
    __tablename__ = "gcl_sdk_audit_logs"

    object_uuid = properties.property(
        types.UUID(),
        required=True,
        read_only=True,
    )
    object_type = properties.property(
        types.String(max_length=64),
        required=True,
        read_only=True,
    )
    user_uuid = properties.property(
        types.AllowNone(types.UUID()),
        default=None,
        read_only=True,
    )
    action = properties.property(
        types.String(max_length=64),
        required=True,
        read_only=True,
    )


class AuditLogSQLStorableMixin(orm.SQLStorableMixin):
    def insert(self, session=None, action: str = None, object_type=None):
        with self._get_engine().session_manager(session=session) as s:
            super().insert(session=s)
            self._write_audit_log(action, object_type, session=s)

    def update(
        self, session, force=False, action: str = None, object_type=None
    ):
        if force or self.is_dirty():
            with self._get_engine().session_manager(session=session) as s:
                super().update(session=s, force=force)
                self._write_audit_log(action, object_type, session=s)

    def delete(self, session, action: str = None, object_type=None):
        with self._get_engine().session_manager(session=session) as s:
            super().delete(session=s)
            self._write_audit_log(action, object_type, session=s)

    def _write_audit_log(
        self, action: str = None, object_type=None, session=None
    ):
        if action is None:
            action = inspect.stack()[1].function
            action = getattr(constants.Action, action, action)
        if object_type is None:
            object_type = self.get_table().name
        try:
            ctx = contexts.get_context()
            user_uuid = ctx.iam_context.token_info.user_uuid
        except (contexts.ContextIsNotExistsInStorage, AttributeError):
            user_uuid = None

        AuditRecord(
            object_uuid=getattr(self, "uuid", None),
            object_type=object_type,
            user_uuid=user_uuid,
            action=action,
        ).insert(session)
