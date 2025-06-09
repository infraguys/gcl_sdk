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
from __future__ import annotations

import typing as tp
import uuid as sys_uuid

from bazooka import exceptions as bazooka_exc

from gcl_sdk.agents.universal.dm import models
from gcl_sdk.agents.universal.clients.http import base as http
from gcl_sdk.agents.universal.clients.backend import base
from gcl_sdk.agents.universal.clients.backend import exceptions


class GCRestApiBackendClient(base.AbstractBackendClient):
    """Genesis Core Rest API backend client."""

    def __init__(
        self,
        http_client: http.CollectionBaseClient,
        collection_map: dict[str:str],
        project_id: sys_uuid.UUID,
    ) -> None:
        self._client = http_client
        self._collection_map = collection_map
        self._project_id = str(project_id)

    def get(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Get the resource value in dictionary format."""
        collection_url = self._collection_map[resource.kind]

        try:
            return self._client.get(collection_url, resource.uuid)
        except bazooka_exc.NotFoundError:
            raise exceptions.ResourceNotFound(resource=resource)

    def create(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Creates the resource. Returns the created resource."""
        collection_url = self._collection_map[resource.kind]

        # Inject mandatory fields
        resource.value["uuid"] = str(resource.uuid)

        # Simple validation for project_id. Only one project is supported.
        res_project_id = resource.value.get("project_id", None)
        if res_project_id and res_project_id != self._project_id:
            raise exceptions.ResourceProjectMismatch(resource=resource)

        try:
            return self._client.create(collection_url, resource.value)
        except bazooka_exc.ConflictError:
            raise exceptions.ResourceAlreadyExists(resource=resource)

    def update(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Update the resource. Returns the updated resource."""
        collection_url = self._collection_map[resource.kind]

        # FIXME(akremenetsky): Not the best implementation
        # Remove popential RO fields
        value = resource.value.copy()
        value.pop("created_at", None)
        value.pop("updated_at", None)
        value.pop("project_id", None)
        value.pop("uuid", None)

        try:
            return self._client.update(collection_url, resource.uuid, **value)
        except bazooka_exc.NotFoundError:
            raise exceptions.ResourceNotFound(resource=resource)

    def list(self, kind: str) -> list[dict[str, tp.Any]]:
        """Lists all resources by kind."""
        collection_url = self._collection_map[kind]

        # TODO(akremenetsky): Use a project prefix to filter resources
        return self._client.filter(collection_url, project_id=self._project_id)

    def delete(self, resource: models.Resource) -> None:
        """Delete the resource."""
        collection_url = self._collection_map[resource.kind]

        try:
            self._client.delete(collection_url, resource.uuid)
        except bazooka_exc.NotFoundError:
            raise exceptions.ResourceNotFound(resource=resource)
