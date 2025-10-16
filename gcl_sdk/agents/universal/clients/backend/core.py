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

import re
import typing as tp
import uuid as sys_uuid

from gcl_sdk.agents.universal.dm import models
from gcl_sdk.clients.http import base as http
from gcl_sdk.agents.universal.clients.backend import rest
from gcl_sdk.agents.universal.clients.backend import exceptions
from gcl_sdk.agents.universal.storage import base as storage_base


class ResourceProjectMismatch(exceptions.BackendClientException):
    __template__ = "The resource project mismatch: {resource}"
    resource: models.Resource


class GCRestApiBackendClient(rest.RestApiBackendClient):
    """Genesis Core Rest API backend client."""

    def __init__(
        self,
        http_client: http.CollectionBaseClient,
        collection_map: dict[str, str],
        project_id: sys_uuid.UUID | None = None,
        tf_storage: storage_base.AbstractTargetFieldsStorage | None = None,
    ) -> None:
        super().__init__(
            http_client=http_client, collection_map=collection_map
        )
        self._project_id = project_id
        self._tf_storage = tf_storage

    def _get_filters(self, kind: str) -> dict[str, str]:
        """Get filters for the kind.

        If the project_id is set, return it.
        Otherwise, construct filters from the target fields
        from the storage.
        """
        if self._project_id is not None:
            return {"project_id": str(self._project_id)}

        # Construct filters from the target fields
        target_fields: dict = self._tf_storage.storage()
        if kind not in target_fields or not target_fields[kind]:
            return {}

        uuids = tuple(target_fields[kind].keys())
        if len(uuids) == 1:
            return {"uuid": str(uuids[0])}

        filter_str = "&".join(f"uuid={str(u)}" for u in uuids)

        # Remove "uuid=" prefix
        return {"uuid": filter_str[5:]}

    def create(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Creates the resource. Returns the created resource."""
        # Inject mandatory fields
        resource.value["uuid"] = str(resource.uuid)

        # Simple validation for project_id. Only one project is supported.
        if self._project_id is not None:
            res_project_id = resource.value.get("project_id", None)
            if res_project_id and res_project_id != str(self._project_id):
                raise ResourceProjectMismatch(resource=resource)

        return super().create(resource)

    def update(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Update the resource. Returns the updated resource."""
        # FIXME(akremenetsky): Not the best implementation
        # Remove popential RO fields
        value = resource.value.copy()
        resource.value.pop("created_at", None)
        resource.value.pop("updated_at", None)
        resource.value.pop("project_id", None)
        resource.value.pop("uuid", None)

        try:
            result = super().update(resource)
        finally:
            resource.value = value

        return result

    def list(self, kind: str) -> list[dict[str, tp.Any]]:
        """Lists all resources by kind."""
        return super().list(kind, **self._get_filters(kind))
