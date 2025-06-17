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

import abc
import typing as tp

from gcl_sdk.agents.universal.dm import models


class AbstractAgentStorage(abc.ABC):
    """Abstract agent storage."""

    @abc.abstractmethod
    def get(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Get the resource  item from the storage."""

    @abc.abstractmethod
    def create(
        self,
        resource: models.Resource,
        item: dict[str, tp.Any],
        force: bool = False,
    ) -> dict[str, tp.Any]:
        """Creates the resource item in the storage."""

    @abc.abstractmethod
    def update(
        self, resource: models.Resource, item: dict[str, tp.Any]
    ) -> dict[str, tp.Any]:
        """Update the resource item in the storage."""

    @abc.abstractmethod
    def list(self, kind: str) -> list[dict[str, tp.Any]]:
        """Lists all resource items by kind."""

    @abc.abstractmethod
    def delete(self, resource: models.Resource, force: bool = False) -> None:
        """Delete the resource item from the storage."""
