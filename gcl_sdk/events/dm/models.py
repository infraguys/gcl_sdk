#    Copyright 2025 Genesis Corporation.
#
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc

from restalchemy.dm import models
from restalchemy.dm import properties
from restalchemy.dm import types
from restalchemy.dm import types_dynamic
from restalchemy.storage.sql import orm

from gcl_sdk.common import constants as sdk_c
from gcl_sdk.common import utils


class UserEvent(types_dynamic.AbstractKindModel):
    KIND = "UserEvent"

    user_id = properties.property(
        types.UUID(),
        required=True,
    )
    uuid = properties.property(
        types.UUID(),
        required=True,
    )


class AbstractEventPayload(types_dynamic.AbstractKindModel):

    @abc.abstractmethod
    def to_simple_dict(self):
        raise NotImplementedError(
            "Subclasses must implement to_simple_dict method"
        )


class DummyEventPayload(AbstractEventPayload):
    KIND = "DummyEventPayload"

    def to_simple_dict(self):
        return {}


class Event(
    models.ModelWithUUID,
    models.ModelWithTimestamp,
    orm.SQLStorableMixin,
):
    __tablename__ = "gcl_sdk_events"

    STATUS = sdk_c.EventStatus

    status = properties.property(
        types.Enum([status.value for status in STATUS]),
        default=STATUS.NEW.value,
    )
    event_type = properties.property(
        types_dynamic.KindModelSelectorType(
            types_dynamic.KindModelType(UserEvent),
        ),
        required=True,
    )
    event_data = properties.property(
        types_dynamic.KindModelSelectorType(
            *[
                types_dynamic.KindModelType(ept)
                for ept in utils.load_event_payload_map().values()
            ],
        ),
        required=True,
    )
