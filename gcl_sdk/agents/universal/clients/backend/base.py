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


class AbstractBackendClient(abc.ABC):
    """Abstract backend client.

    An interface for clients to communicate with a backend side.
    """

    @abc.abstractmethod
    def get(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Get the resource value in dictionary format."""

    @abc.abstractmethod
    def create(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Creates the resource. Returns the created resource."""

    @abc.abstractmethod
    def update(self, resource: models.Resource) -> dict[str, tp.Any]:
        """Update the resource. Returns the updated resource."""

    @abc.abstractmethod
    def list(self, kind: str, **kwargs) -> list[dict[str, tp.Any]]:
        """Lists all resources by kind."""

    @abc.abstractmethod
    def delete(self, resource: models.Resource) -> None:
        """Delete the resource."""
