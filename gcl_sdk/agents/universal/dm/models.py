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
import logging
import hashlib
import typing as tp

from restalchemy.dm import models
from restalchemy.dm import properties
from restalchemy.dm import relationships
from restalchemy.dm import filters as dm_filters
from restalchemy.dm import types
from restalchemy.storage.sql import orm

from gcl_sdk.agents.universal import utils
from gcl_sdk.agents.universal import constants as c


LOG = logging.getLogger(__name__)


class Payload(models.Model, models.SimpleViewMixin):
    capabilities = properties.property(types.Dict(), default=dict)
    hash = properties.property(types.String(max_length=256), default="")
    version = properties.property(
        types.Integer(min_value=0), default=0, required=True
    )

    def calculate_hash(
        self, hash_method: tp.Callable[[str | bytes], str] = hashlib.sha256
    ) -> None:
        m = hash_method()
        resources = self.resources()
        resources.sort(key=lambda r: r.full_hash)
        hashes = [r.full_hash for r in resources]
        m.update(
            json.dumps(hashes, separators=(",", ":"), sort_keys=True).encode(
                "utf-8"
            )
        )
        self.hash = m.hexdigest()

    def resources(self, capability: str | None = None) -> list[Resource]:
        """
        Lists all resources by capability or all resources if capability is None.
        """
        #  Lists all resources by capability
        if capability is not None:
            try:
                data = self.capabilities[capability]["resources"]
            except KeyError:
                return []

            return [Resource.restore_from_simple_view(**r) for r in data]

        # Lists all resources
        resources = []
        for capability in self.capabilities:
            resources.extend(self.resources(capability))

        return resources

    def add_resource(self, resource: Resource) -> None:
        try:
            self.capabilities[resource.kind]["resources"].append(
                resource.dump_to_simple_view()
            )
        except KeyError:
            self.capabilities[resource.kind] = {
                "resources": [resource.dump_to_simple_view()]
            }

    def add_resources(self, resources: list[Resource]) -> None:
        for resource in resources:
            self.add_resource(resource)

    def save(self, payload_path: str) -> None:
        """Save the payload from the data plane."""
        self.calculate_hash()

        # Create missing directories
        payload_dir = os.path.dirname(payload_path)
        if not os.path.exists(payload_dir):
            os.makedirs(payload_dir)

        with open(payload_path, "w") as f:
            payload_data = self.dump_to_simple_view()
            LOG.debug("Saving payload: %s", payload_data)
            json.dump(payload_data, f, indent=2)

    @classmethod
    def empty(cls):
        return cls()

    @classmethod
    def load(cls, payload_path: str) -> Payload:
        """Load the saved payload from the file."""
        if not os.path.exists(payload_path):
            return cls.empty()

        # Load base from the payload file
        with open(payload_path) as f:
            payload_data = json.load(f)
            payload: Payload = Payload.restore_from_simple_view(**payload_data)

        return payload


class UniversalAgent(
    models.ModelWithRequiredUUID,
    models.ModelWithRequiredNameDesc,
    models.ModelWithTimestamp,
    models.SimpleViewMixin,
    orm.SQLStorableMixin,
):
    __tablename__ = "ua_agents"

    capabilities = properties.property(
        types.TypedList(types.String()), default=list
    )
    node = properties.property(types.UUID())
    status = properties.property(
        types.Enum([s.value for s in c.AgentStatus]),
        default=c.AgentStatus.NEW.value,
    )

    @classmethod
    def from_system_uuid(cls, capabilities: tp.Iterable[str]):
        uuid = utils.system_uuid()
        return cls(
            uuid=uuid,
            name=f"Universal Agent {str(uuid)[:8]}",
            status=c.AgentStatus.ACTIVE.value,
            capabilities=list(capabilities),
            # Actually it's won't be true for some cases. For instance,
            # baremetal nodes added by hands. We dont' have such cases
            # so keep it simple so far.
            node=uuid,
        )

    def get_payload(self, hash: str = "", version: int = 0) -> Payload:
        # Calculate hash of the target resources
        resources = TargetResource.objects.get_all(
            filters={"agent": dm_filters.EQ(self)}
        )
        payload = Payload.empty()
        payload.add_resources(resources)
        payload.calculate_hash()

        # TODO(akremenetsky): Add support for versions
        if payload.hash == hash:
            # Return the empty payload with the same hash and version.
            # That means the local value of the agent is correct.
            return Payload(hash=hash, version=version)

        LOG.debug(
            "Target and agents payloads are different. Agent %s", self.uuid
        )
        return payload


class Resource(
    models.ModelWithRequiredUUID, models.SimpleViewMixin, orm.SQLStorableMixin
):
    __tablename__ = "ua_agent_resources"

    kind = properties.property(types.String(max_length=64), required=True)
    value = properties.property(types.Dict())
    hash = properties.property(types.String(max_length=256), default="")
    full_hash = properties.property(types.String(max_length=256), default="")

    def eq_hash(self, other: "Resource") -> bool:
        return self.hash == other.hash and self.full_hash == other.full_hash


class TargetResource(Resource):
    __tablename__ = "ua_target_resources"

    agent = relationships.relationship(UniversalAgent, prefetch=True)
