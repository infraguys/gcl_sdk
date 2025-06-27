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
import uuid as sys_uuid

import bazooka

from gcl_sdk.agents.universal.dm import models
from gcl_sdk.clients.http import base


class UniversalAgentsClient(base.StaticCollectionBaseModelClient):
    __collection_path__ = "/v1/agents/"
    __model__ = models.UniversalAgent

    def get_payload(
        self, uuid: sys_uuid.UUID, last_payload: models.Payload
    ) -> models.Payload:
        payload_data = self.do_action(
            "get_payload",
            uuid,
            hash=last_payload.hash,
            version=last_payload.version,
        )
        cp_payload = models.Payload.restore_from_simple_view(**payload_data)

        # Choose the target payload. If the payloads are equal, the CP returns
        # light payload without capabilities so use the last payload
        # in this case.
        return last_payload if last_payload == cp_payload else cp_payload


class OrchAPI:
    def __init__(
        self,
        base_url: str,
        http_client: bazooka.Client | None = None,
    ) -> None:
        http_client = http_client or bazooka.Client()

        self._http_client = http_client
        self._agents_client = UniversalAgentsClient(base_url, http_client)

    @property
    def agents(self):
        return self._agents_client
