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

from gcl_sdk.agents.universal.dm import models


class AbstractAgentDriver(abc.ABC):

    @abc.abstractmethod
    def get_capabilities(self) -> list[str]:
        """Returns a list of capabilities supported by the driver."""

    @abc.abstractmethod
    def get(self, resource: models.Resource) -> models.Resource:
        """Find and return a resource by uuid and kind.

        It returns the resource from the data plane.
        """

    @abc.abstractmethod
    def create(self, resource: models.Resource) -> models.Resource:
        """Creates a resource."""

    @abc.abstractmethod
    def update(self, resource: models.Resource) -> models.Resource:
        """Update the resource.

        The simplest implementation. The driver should detect which
        fields were changed itself.
        """

    @abc.abstractmethod
    def list(self, capability: str) -> list[models.Resource]:
        """Lists all resources by capability."""

    @abc.abstractmethod
    def delete(self, resource: models.Resource) -> None:
        """Delete the resource."""
