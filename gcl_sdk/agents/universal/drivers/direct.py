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

import logging
import uuid as sys_uuid

from gcl_sdk.agents.universal.drivers import base
from gcl_sdk.agents.universal.drivers import exceptions as driver_exc
from gcl_sdk.agents.universal.dm import models
from gcl_sdk.agents.universal.clients.backend import base as client_base
from gcl_sdk.agents.universal.clients.backend import exceptions as client_exc
from gcl_sdk.agents.universal.storage import base as storage_base

LOG = logging.getLogger(__name__)


class DirectAgentDriver(base.AbstractCapabilityDriver):
    """Direct driver. Directly gets all data from the backend.

    The key feature of this driver it's able to get all
    data from the data plane without using any additional
    information like meta files.
    """

    def __init__(
        self,
        client: client_base.AbstractBackendClient,
        storage: storage_base.AbstractAgentStorage,
    ):
        super().__init__()
        self._client = client
        self._storage = storage

    def _create_storage_item(
        self, uuid: sys_uuid.UUID, target_fields: frozenset[str]
    ):
        return {"uuid": str(uuid), "target_fields": list(target_fields)}

    def _validate(self, resource: models.Resource) -> None:
        """Validate the resource."""
        if resource.kind not in self.get_capabilities():
            raise TypeError(f"Unsupported capability {resource.kind}")

    def get(self, resource: models.Resource) -> models.Resource:
        """Find and return a resource by uuid and kind.

        It returns the resource from the backend.
        """
        self._validate(resource)

        try:
            value = self._client.get(resource)
        except client_exc.ResourceNotFound:
            LOG.error("Unable to find resource on backend %s", resource.uuid)
            raise driver_exc.ResourceNotFound(resource=resource)

        # Figure out the target fields to correct hash calculation
        target_fields = frozenset(resource.value.keys())

        return resource.replace_value(value, target_fields)

    def list(self, capability: str) -> list[models.Resource]:
        """Lists all resources by capability."""
        if capability not in self.get_capabilities():
            raise TypeError(f"Unsupported capability {capability}")

        # Collect all resources in convient format
        resources = []
        storage_items = {i["uuid"]: i for i in self._storage.list(capability)}
        values = {i["uuid"]: i for i in self._client.list(capability)}

        # If storage item or value is missing, consider it as
        # a missing resource
        for uuid in storage_items.keys() & values.keys():
            value = values[uuid]
            item = storage_items[uuid]
            target_fields = frozenset(item["target_fields"])
            res = models.Resource.from_value(value, capability, target_fields)
            resources.append(res)

        return resources

    def create(self, resource: models.Resource) -> models.Resource:
        """Creates a resource."""
        self._validate(resource)

        # Figure out the target fields to correct hash calculation
        target_fields = frozenset(resource.value.keys())

        item = self._create_storage_item(resource.uuid, target_fields)

        try:
            value = self._client.create(resource)
            LOG.debug("Created resource: %s", resource.uuid)
        except client_exc.ResourceAlreadyExists:
            self._storage.create(resource, item, force=True)
            LOG.error("The resource already exists: %s", resource.uuid)
            raise driver_exc.ResourceAlreadyExists(resource=resource)

        self._storage.create(resource, item, force=True)
        return resource.replace_value(value, target_fields)

    def update(self, resource: models.Resource) -> models.Resource:
        """Update the resource."""
        self._validate(resource)

        try:
            value = self._client.update(resource)
            LOG.debug("Updated resource: %s", resource.uuid)
        except client_exc.ResourceNotFound:
            LOG.error("The resource does not exist: %s", resource.uuid)
            raise driver_exc.ResourceNotFound(resource=resource)

        # Figure out the target fields to correct hash calculation
        target_fields = frozenset(resource.value.keys())

        item = self._create_storage_item(resource.uuid, target_fields)
        self._storage.create(resource, item, force=True)

        return resource.replace_value(value, target_fields)

    def delete(self, resource: models.Resource) -> None:
        """Delete the resource."""
        self._validate(resource)

        try:
            self._client.delete(resource)
            LOG.debug("Deleted resource: %s", resource.uuid)
        except client_exc.ResourceNotFound:
            self._storage.delete(resource, force=True)
            LOG.debug("The resource is already deleted: %s", resource.uuid)

        self._storage.delete(resource, force=True)
