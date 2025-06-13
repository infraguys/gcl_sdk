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

import os
import json
import typing as tp
import uuid as sys_uuid

from gcl_sdk.agents.universal.dm import models
from gcl_sdk.agents.universal.storage import base
from gcl_sdk.agents.universal.storage import exceptions as se


class FileAgentStorage(base.AbstractAgentStorage):
    """Rest API backend client."""

    DEFAULT_STORAGE_NAME = "ua_driver_storage.json"

    def __init__(self, work_dir: str, storage_name: str | None = None) -> None:
        self._storage_name = storage_name or self.DEFAULT_STORAGE_NAME
        self._storage_path = os.path.join(work_dir, self._storage_name)

    def _load(self, kind: str) -> list[dict[str, tp.Any]]:
        if not os.path.exists(self._storage_path):
            return []

        try:
            with open(self._storage_path) as f:
                return json.load(f)[kind]
        except KeyError:
            return []

    def _delete(self, kind: str, uuid: sys_uuid.UUID) -> None:
        """Remove the resource from the meta file."""
        if not os.path.exists(self._storage_path):
            return

        uuid = str(uuid)

        with open(self._storage_path, "r+") as f:
            data = json.load(f)
            data[kind] = [r for r in data[kind] if r["uuid"] != uuid]
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, indent=2)

    def _add(self, kind: str, item: dict[str, tp.Any]) -> None:
        """Add the resource from the meta file."""
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)

        # Create the file if it doesn't exist
        if not os.path.exists(self._storage_path):
            with open(self._storage_path, "w") as f:
                json.dump({kind: []}, f, indent=2)

        # Save the new meta object
        with open(self._storage_path, "r+") as f:
            data = json.load(f)
            if kind not in data:
                data[kind] = []
            data[kind].append(item)
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, indent=2)

    def get(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Get the resource  item from the storage."""
        uuid = str(resource.uuid)

        for item in self._load(resource.kind):
            if item["uuid"] == uuid:
                return item

        raise se.ResourceNotFound(resource=resource)

    def create(
        self,
        resource: models.Resource,
        item: dict[str, tp.Any],
        force: bool = False,
    ) -> dict[str, tp.Any]:
        """Creates the resource item in the storage."""
        try:
            self.get(resource)
        except se.ResourceNotFound:
            # Desirable behavior, the resource should not exist
            pass
        else:
            if not force:
                raise se.ResourceAlreadyExists(resource)
            self._delete(resource.kind, resource.uuid)

        self._add(resource.kind, item)
        return item

    def update(
        self, resource: models.Resource, item: dict[str, tp.Any]
    ) -> dict[str, tp.Any]:
        """Update the resource item in the storage."""
        self.delete(resource)
        self.create(resource, item)
        return item

    def list(self, kind: str) -> list[dict[str, tp.Any]]:
        """Lists all resource items by kind."""
        return self._load(kind)

    def delete(self, resource: models.Resource, force: bool = False) -> None:
        """Delete the resource item from the storage."""
        try:
            self.get(resource)
        except se.ResourceNotFound:
            if not force:
                raise

        self._delete(resource.kind, resource.uuid)
