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

from restalchemy.dm import properties
from restalchemy.dm import types as ra_types
from restalchemy.dm import types_dynamic
from restalchemy.dm import models as ra_models
from restalchemy.dm import filters as dm_filters

from gcl_sdk.agents.universal.dm import models as ua_models
from gcl_sdk.infra import constants as pc


class Node(
    ra_models.ModelWithRequiredUUID,
    ra_models.ModelWithProject,
    ra_models.ModelWithNameDesc,
    ra_models.ModelWithTimestamp,
    ua_models.TargetResourceKindAwareMixin,
):
    """The model represents a node in Genesis Core infrastructure.

    The model represents a virtual machine or a physical machine with
    specified characteristics such as cores, ram, root disk size, image,
    node type, default network, etc.
    """

    __init_resource_status__ = pc.NodeStatus.NEW.value

    cores = properties.property(
        ra_types.Integer(min_value=1, max_value=4096), required=True
    )
    ram = properties.property(ra_types.Integer(min_value=1), required=True)
    root_disk_size = properties.property(
        ra_types.AllowNone(ra_types.Integer(min_value=1, max_value=1000000)),
        default=pc.DEF_ROOT_DISK_SIZE,
    )
    image = properties.property(ra_types.String(max_length=255), required=True)
    status = properties.property(
        ra_types.Enum([s.value for s in pc.NodeStatus]),
    )
    node_type = properties.property(
        ra_types.Enum([t.value for t in pc.NodeType]),
        default=pc.NodeType.VM.value,
    )
    default_network = properties.property(ra_types.Dict(), default=lambda: {})

    @classmethod
    def get_resource_kind(cls) -> str:
        """Return the resource kind."""
        return "node"

    def get_resource_target_fields(self) -> tp.Collection[str]:
        """Return the collection of target fields.

        Refer to the Resource model for more details about target fields.
        """
        return frozenset(
            (
                "uuid",
                "name",
                "cores",
                "ram",
                "root_disk_size",
                "node_type",
                "image",
                "project_id",
            )
        )


class NodeSet(
    ra_models.ModelWithRequiredUUID,
    ra_models.ModelWithProject,
    ra_models.ModelWithNameDesc,
    ra_models.ModelWithTimestamp,
    ua_models.TargetResourceKindAwareMixin,
):
    """The model represents a node set in Genesis Core infrastructure.

    The node set is a group of nodes with the same characteristics. See the
    `Node` model for more details about node characteristics. The key field of
    the node set model is `replicas`. The different `set_type` interpretate this
    field in different ways. The the simplest `set_type` is `SET` where the
    `replicas` field is the number of nodes in the set.
    """

    __init_resource_status__ = pc.NodeStatus.NEW.value

    replicas = properties.property(
        ra_types.Integer(min_value=0, max_value=4096), default=1
    )
    cores = properties.property(
        ra_types.Integer(min_value=1, max_value=4096), required=True
    )
    ram = properties.property(ra_types.Integer(min_value=1), required=True)
    root_disk_size = properties.property(
        ra_types.AllowNone(ra_types.Integer(min_value=1, max_value=1000000)),
        default=pc.DEF_ROOT_DISK_SIZE,
    )
    image = properties.property(ra_types.String(max_length=255), required=True)
    status = properties.property(
        ra_types.Enum([s.value for s in pc.NodeStatus]),
    )
    node_type = properties.property(
        ra_types.Enum([t.value for t in pc.NodeType]),
        default=pc.NodeType.VM.value,
    )
    default_network = properties.property(ra_types.Dict(), default=lambda: {})

    set_type = properties.property(
        ra_types.Enum([type_.value for type_ in pc.NodeSetType]),
        default=pc.NodeSetType.SET.value,
    )
    nodes = properties.property(ra_types.Dict(), default=lambda: {})

    @classmethod
    def get_resource_kind(cls) -> str:
        """Return the resource kind."""
        return "node_set"

    def get_resource_target_fields(self) -> tp.Collection[str]:
        """Return the collection of target fields.

        Refer to the Resource model for more details about target fields.
        """
        return frozenset(
            (
                "uuid",
                "name",
                "replicas",
                "cores",
                "ram",
                "root_disk_size",
                "node_type",
                "set_type",
                "image",
                "project_id",
            )
        )


class AbstractTarget(
    types_dynamic.AbstractKindModel, ra_models.SimpleViewMixin
):

    def target_nodes(self) -> tp.List[sys_uuid.UUID]:
        """Returns list of target nodes where config should be deployed."""
        return []

    def owners(self) -> tp.List[sys_uuid.UUID]:
        """Return list of owners objects where config bind to.

        For instance, the simplest case if an ordinary node config.
        In that case, the owner and target is the node itself.
        A more complex case is when a config is bound to a node set.
        In this case the owner is the set and the targets are all nodes
        in this set.
        """
        return []

    def are_owners_alive(self) -> bool:
        raise NotImplementedError()


class AbstractContentor(
    types_dynamic.AbstractKindModel, ra_models.SimpleViewMixin
):

    def render(self) -> str:
        return ""


class NodeTarget(AbstractTarget):
    KIND = "node"

    node = properties.property(ra_types.UUID(), required=True)

    @classmethod
    def from_node(cls, node: sys_uuid.UUID) -> "NodeTarget":
        return cls(node=node)

    def target_nodes(self) -> tp.List[sys_uuid.UUID]:
        return [self.node]

    def owners(self) -> tp.List[sys_uuid.UUID]:
        """It's the simplest case with an ordinary node config.

        In that case, the owner and target is the node itself.
        If owners are deleted, the config will be deleted as well.
        """
        return [self.node]


class TextBodyConfig(AbstractContentor):
    KIND = "text"

    content = properties.property(ra_types.String(), required=True, default="")

    @classmethod
    def from_text(cls, text: str) -> "TextBodyConfig":
        return cls(content=text)

    def render(self) -> str:
        return self.content


class TemplateBodyConfig(AbstractContentor):
    KIND = "template"

    template = properties.property(
        ra_types.String(), required=True, default=""
    )
    variables = properties.property(ra_types.Dict(), default=dict)

    def render(self) -> str:
        # TODO(akremenetsky): Will be added later
        raise NotImplementedError()


class OnChangeNoAction(
    types_dynamic.AbstractKindModel, ra_models.SimpleViewMixin
):
    KIND = "no_action"


class OnChangeShell(
    types_dynamic.AbstractKindModel, ra_models.SimpleViewMixin
):
    KIND = "shell"

    command = properties.property(
        ra_types.String(max_length=262144), required=True, default=""
    )

    @classmethod
    def from_command(cls, command: str) -> "OnChangeShell":
        return cls(command=command)


class Config(
    ra_models.ModelWithRequiredUUID,
    ra_models.ModelWithProject,
    ra_models.ModelWithNameDesc,
    ra_models.ModelWithTimestamp,
    ua_models.TargetResourceKindAwareMixin,
):
    __init_resource_status__ = pc.NodeStatus.NEW.value

    path = properties.property(
        ra_types.String(min_length=1, max_length=255),
        required=True,
    )
    status = properties.property(
        ra_types.Enum([s.value for s in pc.InstanceStatus]),
    )
    target = properties.property(
        types_dynamic.KindModelSelectorType(
            types_dynamic.KindModelType(NodeTarget),
        ),
        required=True,
    )
    body = properties.property(
        types_dynamic.KindModelSelectorType(
            types_dynamic.KindModelType(TextBodyConfig),
            types_dynamic.KindModelType(TemplateBodyConfig),
        ),
        required=True,
    )
    on_change = properties.property(
        types_dynamic.KindModelSelectorType(
            types_dynamic.KindModelType(OnChangeNoAction),
            types_dynamic.KindModelType(OnChangeShell),
        ),
        default=OnChangeNoAction,
    )
    mode = properties.property(ra_types.String(max_length=4), default="0600")
    owner = properties.property(
        ra_types.String(max_length=128),
        default="root",
    )
    group = properties.property(
        ra_types.String(max_length=128),
        default="root",
    )

    @classmethod
    def get_resource_kind(cls) -> str:
        """Return the resource kind."""
        return "config"

    def get_resource_target_fields(self) -> tp.Collection[str]:
        """Return the collection of target fields.

        Refer to the Resource model for more details about target fields.
        """
        return frozenset(
            (
                "uuid",
                "name",
                "path",
                "target",
                "body",
                "on_change",
                "mode",
                "owner",
                "group",
                "project_id",
            )
        )
