import datetime
import inspect

from restalchemy.common.contexts import ContextIsNotExistsInStorage
from restalchemy.common.contexts import get_context
from restalchemy.dm import models
from restalchemy.dm import properties
from restalchemy.dm import types
from restalchemy.storage.sql import orm

from gcl_sdk.audit import constants


class AuditRecord(
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
    created_at = properties.property(
        types.UTCDateTimeZ(),
        read_only=True,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    action = properties.property(
        types.String(max_length=64),
        required=True,
        read_only=True,
    )


class AuditLogSQLStorableMixin(orm.SQLStorableMixin):
    def insert(self, session=None, force=False, action=None, object_type=None):
        if force or self.is_dirty():
            with self._get_engine().session_manager(session=session) as s:
                super().insert(session)
                self._write_audit_log(action, object_type)

    def update(self, session, force=False, action=None, object_type=None):
        if force or self.is_dirty():
            with self._get_engine().session_manager(session=session) as s:
                super().update(session)
                self._write_audit_log(action, object_type)

    def delete(self, session, action=None, object_type=None):
        with self._get_engine().session_manager(session=session) as s:
            super().delete(session)
            self._write_audit_log(action, object_type)

    def _write_audit_log(self, action=None, object_type=None):
        if action is None:
            action = inspect.stack()[1].function
            action = getattr(constants.Action, action, action)
        if object_type is None:
            object_type = self.get_table().name
        try:
            ctx = get_context()
            user_uuid = ctx.iam_context.token_info.user_uuid
        except (ContextIsNotExistsInStorage, AttributeError):
            user_uuid = None

        AuditRecord(
            object_uuid=getattr(self, "uuid", None),
            object_type=object_type,
            user_uuid=user_uuid,
            action=action,
        ).insert()
