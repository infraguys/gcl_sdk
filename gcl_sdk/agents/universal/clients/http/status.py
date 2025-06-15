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
import bazooka

from gcl_sdk.agents.universal.dm import models
from gcl_sdk.clients.http import base


class UniversalAgentsClient(base.CollectionBaseModelClient):
    __collection_url__ = "/v1/agents/"
    __model__ = models.UniversalAgent


class ResourcesClient(base.CollectionBaseModelClient):
    __collection_url__ = "/v1/resources/"
    __model__ = models.Resource


class StatusAPI:
    def __init__(
        self,
        base_url: str,
        http_client: bazooka.Client | None = None,
    ) -> None:
        http_client = http_client or bazooka.Client()

        self._http_client = http_client
        self._agents_client = UniversalAgentsClient(base_url, http_client)
        self._resources_client = ResourcesClient(base_url, http_client)

    @property
    def agents(self):
        return self._agents_client

    @property
    def resources(self):
        return self._resources_client
