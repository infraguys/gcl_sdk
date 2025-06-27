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
import datetime
import collections
import typing as tp
import uuid as sys_uuid

import xxhash
from restalchemy.dm import models
from restalchemy.dm import properties
from restalchemy.dm import relationships
from restalchemy.dm import filters as dm_filters
from restalchemy.dm import types
from restalchemy.storage.sql import engines
from restalchemy.storage.sql import orm

from gcl_sdk.agents.universal import utils
from gcl_sdk.agents.universal import constants as c


LOG = logging.getLogger(__name__)


class Payload(models.Model, models.SimpleViewMixin):
    """This model is used to represent the payload of the agent.

    The models is used as for control plane and data plane.
    The control plane payload is received from Orch API and it
    has be applied to the data plane, excepting `facts`.
    A data plane payload is a collected payload from the data.
    If CP and DP payloads are different from target values of
    resources that means we need to update something on the data plane.
    If CP and DP payloads are different from facts point of view,
    it means we need to update something in the Status API to save
    new facts.

    capabilities - a set of managed resources, for example, configuration,
        secrets and so on. An orchestrator sets which resources should be
        presented on the data plane. CP resources from the capabilities
        contains only managed fields. When these resources are gathered
        from the data plane they may have some additional fields,
        for instance, created time, updated time and so on. Only the
        managed fields are orchestrated.

    facts - opposite to the capabilities. These resources are gathered from
        the data plane independently from the orchestrator. In other words,
        they are not managed by the orchestrator. A simple example of facts
        are network interfaces.

    hash - a hash of the payload. The formula is described below:
        hash(
            hash(cap_resource0.hash),
            hash(cap_resource1.hash),
            ...
            hash(fact_resource0.full_hash),
            hash(fact_resource1.full_hash),
            ...
        )

    """

    capabilities = properties.property(types.Dict(), default=dict)
    facts = properties.property(types.Dict(), default=dict)
    hash = properties.property(types.String(max_length=256), default="")
    version = properties.property(
        types.Integer(min_value=0), default=0, required=True
    )

    def __hash__(self):
        return hash((self.hash, self.version))

    def __eq__(self, other: Payload) -> bool:
        return self.__hash__() == other.__hash__()

    def calculate_hash(
        self, hash_method: tp.Callable[[str | bytes], str] = xxhash.xxh3_64
    ) -> None:
        m = hash_method()
        caps_resources = self.caps_resources()
        facts_resources = self.facts_resources()
        caps_resources.sort(key=lambda r: r.hash)
        facts_resources.sort(key=lambda r: r.full_hash)
        hashes = [r.hash for r in caps_resources]
        hashes.extend([r.full_hash for r in facts_resources])
        m.update(
            json.dumps(hashes, separators=(",", ":"), sort_keys=True).encode(
                "utf-8"
            )
        )
        self.hash = m.hexdigest()

    def resources(self) -> list[Resource]:
        """Lists all resources by in the payload."""
        return self.caps_resources() + self.facts_resources()

    def caps_resources(self, capability: str | None = None) -> list[Resource]:
        """
        Lists all resources by capability or all resources if capability is None.
        """
        return self._resources(self.capabilities, capability)

    def add_caps_resource(
        self, resource: Resource, skip_fields: tuple[str, ...] = tuple()
    ) -> None:
        """Add a resource to the capabilities basket."""
        self._add_resource(self.capabilities, resource, skip_fields)

    def add_caps_resources(
        self, resources: list[Resource], skip_fields: tuple[str, ...] = tuple()
    ) -> None:
        """Add resources to the capabilities basket."""
        self._add_resources(self.capabilities, resources, skip_fields)

    def facts_resources(self, fact: str | None = None) -> list[Resource]:
        """
        Lists all resources by fact or all resources if fact is None.
        """
        return self._resources(self.facts, fact)

    def add_facts_resource(
        self, resource: Resource, skip_fields: tuple[str, ...] = tuple()
    ) -> None:
        """Add a resource to the facts basket."""
        self._add_resource(self.facts, resource, skip_fields)

    def add_facts_resources(
        self, resources: list[Resource], skip_fields: tuple[str, ...] = tuple()
    ) -> None:
        """Add resources to the facts basket."""
        self._add_resources(self.facts, resources, skip_fields)

    def save(self, payload_path: str) -> None:
        """Save the payload from the data plane."""
        self.calculate_hash()

        # Create missing directories
        payload_dir = os.path.dirname(payload_path)
        if not os.path.exists(payload_dir):
            os.makedirs(payload_dir)

        with open(payload_path, "w") as f:
            payload_data = self.dump_to_simple_view()
            json.dump(payload_data, f, indent=2)

    @classmethod
    def _resources(
        cls, source: dict, res_filter: str | None = None
    ) -> list[Resource]:
        """
        Lists all resources by capability/fact or all resources in the basket.
        """
        #  Lists all resources by capability
        if res_filter is not None:
            try:
                data = source[res_filter]["resources"]
            except KeyError:
                return []

            return [Resource.restore_from_simple_view(**r) for r in data]

        # Lists all resources
        resources = []
        for res_filter in source:
            resources.extend(cls._resources(source, res_filter))

        return resources

    @classmethod
    def _add_resource(
        cls,
        dest: dict,
        resource: Resource,
        skip_fields: tuple[str, ...] = tuple(),
    ) -> None:
        try:
            dest[resource.kind]["resources"].append(
                resource.dump_to_simple_view(skip=skip_fields)
            )
        except KeyError:
            dest[resource.kind] = {
                "resources": [resource.dump_to_simple_view(skip=skip_fields)]
            }

    @classmethod
    def _add_resources(
        cls,
        dest: dict,
        resources: list[Resource],
        skip_fields: tuple[str, ...] = tuple(),
    ) -> None:
        for resource in resources:
            cls._add_resource(dest, resource, skip_fields)

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
    """Universal Agent model.

    Unified agent that implements common logic of abstract resource and
    fact management.

    The models has helpful tools to APIs, resource, payload and other models.
    """

    __tablename__ = "ua_agents"

    capabilities = properties.property(types.Dict(), default=dict)
    facts = properties.property(types.Dict(), default=dict)
    node = properties.property(types.UUID(), required=True)
    status = properties.property(
        types.Enum([s.value for s in c.AgentStatus]),
        default=c.AgentStatus.NEW.value,
    )

    @property
    def list_capabilities(self) -> list[str]:
        return self.capabilities["capabilities"]

    @property
    def list_facts(self) -> list[str]:
        return self.facts["facts"]

    @classmethod
    def from_system_uuid(
        cls, capabilities: tp.Iterable[str], facts: tp.Iterable[str]
    ):
        uuid = utils.system_uuid()
        capabilities = {"capabilities": list(capabilities)}
        facts = {"facts": list(facts)}
        return cls(
            uuid=uuid,
            name=f"Universal Agent {str(uuid)[:8]}",
            status=c.AgentStatus.ACTIVE.value,
            capabilities=capabilities,
            facts=facts,
            # Actually it's won't be true for some cases. For instance,
            # baremetal nodes added by hands. We dont' have such cases
            # so keep it simple so far.
            node=uuid,
        )

    def get_payload(self, hash: str = "", version: int = 0) -> Payload:
        # Calculate hash of the target resources
        caps_resources = TargetResource.objects.get_all(
            filters={
                "agent": dm_filters.EQ(str(self.uuid)),
                "kind": dm_filters.In(self.list_capabilities),
            }
        )
        facts_resources = Resource.objects.get_all(
            filters={
                "node": dm_filters.EQ(str(self.node)),
            }
        )

        payload = Payload.empty()

        payload.add_caps_resources(
            caps_resources,
            skip_fields=("agent", "master", "tracked_at", "node"),
        )
        payload.add_facts_resources(
            facts_resources,
            skip_fields=("node",),
        )
        payload.calculate_hash()

        # TODO(akremenetsky): Add support for versions
        if payload.hash == hash:
            # Return the empty payload with the same hash and version.
            # That means the local value of the agent is correct.
            return Payload(hash=hash, version=version)

        # Fill the payload with data for capabilities with empty resources.
        # Seems all resources for these capabilities were deleted.
        for capability in self.list_capabilities:
            payload.capabilities.setdefault(capability, {"resources": []})

            # All gathered resources for capabilities are consideredas facts too.
            payload.facts.setdefault(capability, {"resources": []})

        for fact in self.list_facts:
            payload.facts.setdefault(fact, {"resources": []})

        LOG.debug(
            "Target and agents payloads are different. Agent %s", self.uuid
        )
        return payload

    @classmethod
    def have_capabilities(
        cls, capabilities: tp.Collection[str]
    ) -> dict[str, list["UniversalAgent"]]:
        if not capabilities:
            return {}

        caps_str = "'" + "','".join(capabilities) + "'"

        expression = (
            "SELECT * FROM ua_agents ua  "
            "WHERE ua.status = '{status}' AND "
            "      ua.capabilities->'capabilities' ?| "
            "  ARRAY[{caps}]; "
        ).format(status=c.AgentStatus.ACTIVE.value, caps=caps_str)

        engine = engines.engine_factory.get_engine()
        with engine.session_manager() as session:
            curs = session.execute(expression, tuple())
            response = curs.fetchall()

        if not response:
            return {}

        # Group agents by capabilities and return them as dict
        cap_map = collections.defaultdict(list)
        for data in response:
            # There is known issue with date format so we need
            # to handle it manually.
            if created_at := data.get("created_at"):
                data["created_at"] = created_at.replace(
                    tzinfo=datetime.timezone.utc
                )

            if updated_at := data.get("updated_at"):
                data["updated_at"] = updated_at.replace(
                    tzinfo=datetime.timezone.utc
                )

            agent = cls(**data)
            caps = set(agent.list_capabilities) & set(capabilities)
            for capability in caps:
                cap_map[capability].append(agent)

        return cap_map


class Resource(
    models.ModelWithID,
    models.ModelWithTimestamp,
    models.SimpleViewMixin,
    orm.SQLStorableMixin,
):
    """This model is represent an abstract resource for the Universal Agent.

    This model is mostly used as an actual resource, for instance, gathered
    from the data plane. In this case the `value` dict contains a real object
    from the data plane in dict format.

    kind - resource kind, for instance, "config", "secret", ...
    value - resource value in dict format.
    hash - hash value only for the target fields.
    full_hash - hash value for the whole value (all fields).
    status - resource status, for instance, "ACTIVE", "NEW", ...

    Some explanation for the `hash` and `full_hash`. Let's assume we have
    the following target node resource:
    {
        "uuid": "a1b2c3d4-e5f6-7890-a1b2-c3d4e5f67890",
        "name": "vm",
        "project_id": "12345678-c625-4fee-81d5-f691897b8142",
        "root_disk_size": 15,
        "cores": 1,
        "ram": 1024,
        "image": "http://10.20.0.1:8080/genesis-base.raw"
    }
    All these fields are considered as target fields and they are used
    to calculate `hash`.

    After node creation we have the the follwing:
    {
        "uuid": "a1b2c3d4-e5f6-7890-a1b2-c3d4e5f67890",
        "name": "vm",
        "project_id": "12345678-c625-4fee-81d5-f691897b8142",
        "root_disk_size": 15,
        "cores": 1,
        "ram": 1024,
        "image": "http://10.20.0.1:8080/genesis-base.raw",

        // Not target fields below
        "created_at": "2022-01-01T00:00:00+00:00",
        "updated_at": "2022-01-01T00:00:00+00:00",
        "default_network": {}
    }

    For hash calculation only the target fields are used as discussed
    above. `full_hash` is calculated for all fields.
    """

    __tablename__ = "ua_actual_resources"

    # Should be the same as `uuid` of internal object that the
    # resource is holding. Therefore isn't unique since we can have
    # the same `uuid` but different `kind`. The simplest example is
    # any resource is created by the Element Manager. We will have
    # two objects with the same `uuid` but different `kind`.
    # - (<uuid_foo>, em_core_object) (EM resource)
    # - (<uuid_foo>, object) (A particular service resource)
    uuid = properties.property(
        types.UUID(),
        read_only=True,
        default=lambda: sys_uuid.uuid4(),
    )
    kind = properties.property(types.String(max_length=64), required=True)
    value = properties.property(types.Dict())
    hash = properties.property(types.String(max_length=256), default="")
    full_hash = properties.property(types.String(max_length=256), default="")
    status = properties.property(types.String(max_length=32), default="ACTIVE")
    node = properties.property(types.AllowNone(types.UUID()), default=None)

    # The `uuid` field isn't unique, since it's possible to have several
    # resource with the same `uuid` but different `kind`. Therefore the
    # primary key is `res_uuid`. it's useful to have a single unique
    # identifier and it can be any unique UUID but it's recommended to
    # use `uuid5(uuid, kind)`.
    res_uuid = properties.property(
        types.UUID(),
        id_property=True,
        required=True,
        default=lambda: sys_uuid.uuid4(),
    )

    def __eq__(self, other: Resource):
        if isinstance(other, self.__class__):
            return self.uuid == other.uuid and self.kind == other.kind
        return False

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.uuid, self.kind))

    def calculate_hash(self) -> None:
        self.hash = utils.calculate_hash(self.value)

    def replace_value(
        self,
        value: dict[str, tp.Any],
        target_fields: frozenset[str] | None = None,
        extract_status: bool = True,
    ) -> Resource:
        """Return a new resource with replaced value and hashes."""
        if target_fields is None:
            hash = self.hash
        else:
            hash = utils.calculate_hash({k: value[k] for k in target_fields})

        if extract_status:
            status = value.get("status", self.status)
        else:
            status = self.status

        return Resource(
            uuid=self.uuid,
            kind=self.kind,
            res_uuid=self.res_uuid,
            value=value,
            hash=hash,
            full_hash=utils.calculate_hash(value),
            status=status,
            node=self.node,
        )

    @classmethod
    def gen_res_uuid(cls, uuid: sys_uuid.UUID, kind: str) -> sys_uuid.UUID:
        return sys_uuid.uuid5(uuid, kind)

    @classmethod
    def from_value(
        cls,
        value: dict[str, tp.Any],
        kind: str,
        target_fields: frozenset[str] | None = None,
    ) -> Resource:
        status = value.get("status", "ACTIVE")
        uuid = sys_uuid.UUID(value["uuid"])

        if target_fields is None:
            hash = ""
        else:
            hash = utils.calculate_hash({k: value[k] for k in target_fields})

        return cls(
            uuid=uuid,
            kind=kind,
            res_uuid=cls.gen_res_uuid(uuid, kind),
            value=value,
            hash=hash,
            full_hash=utils.calculate_hash(value),
            status=status,
        )


class TargetResource(Resource):
    """This model is represent an abstract resource for the Universal Agent.

    Almost the same as `Resource` but it's used as a target resource.
    """

    __tablename__ = "ua_target_resources"

    agent = properties.property(types.AllowNone(types.UUID()), default=None)
    master = properties.property(types.AllowNone(types.UUID()), default=None)
    tracked_at = properties.property(
        types.UTCDateTimeZ(),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def update_value(self, other: TargetResource) -> None:
        """Update the resource value."""
        self.hash = other.hash
        self.value = other.value
        self.status = other.status


class ResourceMixin(models.SimpleViewMixin):
    """A helpful mixin to convert models to the resource model."""

    def get_resource_uuid(self) -> sys_uuid.UUID:
        """Get resource uuid."""
        return self.uuid

    def get_resource_target_fields(self) -> tp.Collection[str]:
        """Return the collection of target fields.

        Refer to the Resource model for more details about target fields.
        """
        return set()

    def get_resource_ignore_fields(self) -> tp.Collection[str]:
        """Return fields that should not belong to the resource."""
        return set()

    def to_ua_resource(self, kind: str) -> Resource:
        # It's considered as a data plane values
        value = self.dump_to_simple_view(
            skip=self.get_resource_ignore_fields()
        )

        # Need to get only target fields with values to calculate hash
        target_fields = self.get_resource_target_fields()

        if target_fields:
            target_data = {
                k: v for k, v in value.items() if k in target_fields
            }
        else:
            target_data = value

        return Resource(
            uuid=self.get_resource_uuid(),
            kind=kind,
            res_uuid=Resource.gen_res_uuid(self.get_resource_uuid(), kind),
            value=value,
            hash=utils.calculate_hash(target_data),
            full_hash=utils.calculate_hash(value),
        )

    @classmethod
    def from_ua_resource(cls, resource: Resource) -> "ResourceMixin":
        return cls.restore_from_simple_view(**resource.value)


class TargetResourceMixin(ResourceMixin):
    """A helpful mixin to convert models to the resource model.

    The same as ResourceMixin but it's used as a target resource.
    """

    def to_ua_resource(
        self,
        kind: str,
        master: sys_uuid.UUID | None = None,
        tracked_at: datetime.datetime | None = None,
    ) -> TargetResource:
        tracked_at = tracked_at or datetime.datetime.now(datetime.timezone.utc)
        value = self.dump_to_simple_view(
            skip=self.get_resource_ignore_fields()
        )

        # Need to get only target fields with values to calculate hash
        target_fields = self.get_resource_target_fields()

        if target_fields:
            target_data = {
                k: v for k, v in value.items() if k in target_fields
            }
        else:
            target_data = value

        return TargetResource(
            uuid=self.get_resource_uuid(),
            kind=kind,
            res_uuid=TargetResource.gen_res_uuid(
                self.get_resource_uuid(), kind
            ),
            value=target_data,
            hash=utils.calculate_hash(target_data),
            full_hash="",
            master=master,
            tracked_at=tracked_at,
        )


class TargetResourceSQLStorableMixin:

    @classmethod
    def _execute_expression(
        cls, expression: str, params: tp.Collection, session=None
    ) -> list[dict[str, tp.Any]]:
        if session is None:
            engine = engines.engine_factory.get_engine()
            with engine.session_manager() as session:
                curs = session.execute(expression, params)
                response = curs.fetchall()
        else:
            curs = session.execute(expression, params)
            response = curs.fetchall()

        return response

    @classmethod
    def get_new_entities(
        cls, table: str, kind: str, limit: int = 100, session=None
    ) -> list["TargetResourceSQLStorableMixin"]:
        expression = (
            "SELECT "
            "    {table}.uuid as uuid "
            "FROM {table} LEFT JOIN "
            "( "
            "    SELECT "
            "        uuid "
            "    FROM ua_target_resources "
            "    WHERE kind = %s "
            ") AS ua_target_resources_by_kind "
            "ON {table}.uuid = ua_target_resources_by_kind.uuid "
            "WHERE ua_target_resources_by_kind.uuid is NULL "
            "LIMIT %s;"
        ).format(table=table)
        params = (kind, limit)

        response = cls._execute_expression(expression, params, session)
        if not response:
            return []

        return cls.objects.get_all(
            filters={"uuid": dm_filters.In(str(r["uuid"]) for r in response)},
        )

    @classmethod
    def get_updated_entities(
        cls, table: str, kind: str, limit: int = 100, session=None
    ) -> list["TargetResourceSQLStorableMixin"]:
        expression = (
            "SELECT "
            "    {table}.uuid as uuid "
            "FROM {table} INNER JOIN ua_target_resources ON  "
            "    {table}.uuid = ua_target_resources.uuid "
            "WHERE {table}.updated_at != ua_target_resources.tracked_at "
            "AND ua_target_resources.kind = %s "
            "LIMIT %s;"
        ).format(table=table)
        params = (kind, limit)

        response = cls._execute_expression(expression, params, session)
        if not response:
            return []

        return cls.objects.get_all(
            filters={"uuid": dm_filters.In(str(r["uuid"]) for r in response)},
        )

    @classmethod
    def get_deleted_target_resources(
        cls, table: str, kind: str, limit: int = 100, session=None
    ) -> list[TargetResource]:
        expression = (
            "SELECT "
            "    ua_target_resources.uuid as uuid "
            "FROM ua_target_resources LEFT JOIN {table} ON  "
            "    ua_target_resources.uuid = {table}.uuid  "
            "WHERE ua_target_resources.kind = %s "
            "    AND {table}.uuid is NULL "
            "LIMIT %s;"
        ).format(table=table)
        params = (
            kind,
            limit,
        )

        response = cls._execute_expression(expression, params, session)
        if not response:
            return []

        return TargetResource.objects.get_all(
            filters={"uuid": dm_filters.In(str(r["uuid"]) for r in response)},
        )


class OutdatedResource(models.ModelWithUUID, orm.SQLStorableMixin):
    __tablename__ = "ua_outdated_resources_view"

    kind = properties.property(types.String(max_length=64), required=True)
    target_resource = relationships.relationship(
        TargetResource,
        prefetch=True,
        required=True,
    )
    actual_resource = relationships.relationship(
        Resource,
        prefetch=True,
        required=True,
    )
