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

import glob
import os
import pwd
import grp
import logging
import subprocess
import uuid as sys_uuid


from restalchemy.dm import models
from restalchemy.dm import properties
from restalchemy.dm import types as ra_types
from restalchemy.dm import types_dynamic as ra_types_dyn

from gcl_sdk.agents.universal.drivers import meta
from gcl_sdk.agents.universal.drivers import exceptions
from gcl_sdk.agents.universal import constants as c
from gcl_sdk.infra import constants as ic


LOG = logging.getLogger(__name__)
SERVICE_TARGET_KIND = "service_agent_node"
SERVICES_DIR = "/etc/systemd/system/"
NAME_PREFIX = "g_em_"

SERVICE_TEMPLATE = """\
[Unit]
Description=Genesis Core: EM dynamic service
After=network.target

[Service]
Type={service_type}
Restart={restart}
ExecStart=/usr/bin/bash -c '{command}'
User={user}
{pre}
{post}

[Install]
WantedBy=multi-user.target
"""

TYPES_MAPPING = {"simple": "simple", "oneshot": "oneshot"}


class ServiceTypeSimple(
    ra_types_dyn.AbstractKindModel, models.SimpleViewMixin
):
    KIND = "simple"

    count = properties.property(
        ra_types.Integer(min_value=1, max_value=1000), required=True, default=1
    )


class ServiceTypeOneshot(
    ra_types_dyn.AbstractKindModel, models.SimpleViewMixin
):
    KIND = "oneshot"


# TODO: get service name here!
class ServiceTarget(ra_types_dyn.AbstractKindModel, models.SimpleViewMixin):
    KIND = "service"

    service = properties.property(ra_types.UUID(), required=True)

    @classmethod
    def from_service(cls, service: sys_uuid.UUID) -> "ServiceTarget":
        return cls(service=service)

    def target_services(self) -> tp.List[sys_uuid.UUID]:
        return [self.service]

    def owners(self) -> tp.List[sys_uuid.UUID]:
        """It's the simplest case with an ordinary service target.

        In that case, the owner and target is the service itself.
        If owners are deleted, the service will be deleted as well.
        """
        return [self.service]

    def _fetch_services(self) -> tp.List["Service"]:
        return Service.objects.get_all(filters={"uuid": str(self.service)})

    def are_owners_alive(self) -> bool:
        return bool(self._fetch_services())


class CmdShell(ra_types_dyn.AbstractKindModel, models.SimpleViewMixin):
    KIND = "shell"

    command = properties.property(
        ra_types.String(max_length=262144), required=True, default=""
    )

    @classmethod
    def from_command(cls, command: str) -> "CmdShell":
        return cls(command=command)


class Service(meta.MetaDataPlaneModel):
    """Service model."""

    status = properties.property(
        ra_types.Enum([s.value for s in ic.InstanceStatus]),
        default=ic.InstanceStatus.NEW.value,
    )
    path = properties.property(
        ra_types.String(min_length=1, max_length=255),
        required=True,
    )
    user = properties.property(
        ra_types.String(min_length=1, max_length=255),
        required=True,
        default="root",
    )
    service_type = properties.property(
        ra_types_dyn.KindModelSelectorType(
            ra_types_dyn.KindModelType(ServiceTypeSimple),
            ra_types_dyn.KindModelType(ServiceTypeOneshot),
        ),
        required=True,
    )
    before = properties.property(
        ra_types.TypedList(
            ra_types_dyn.KindModelSelectorType(
                ra_types_dyn.KindModelType(CmdShell),
                ra_types_dyn.KindModelType(ServiceTarget),
            ),
        ),
        required=True,
        default=[],
    )
    after = properties.property(
        ra_types.TypedList(
            ra_types_dyn.KindModelSelectorType(
                ra_types_dyn.KindModelType(CmdShell),
                ra_types_dyn.KindModelType(ServiceTarget),
            ),
        ),
        required=True,
        default=[],
    )

    # For scheduling only
    node = properties.property(ra_types.UUID())

    def get_service_name(self):
        return f"{NAME_PREFIX}{self.uuid}.service"

    def get_meta_model_fields(self) -> set[str] | None:
        """Return a list of meta fields or None.

        Meta fields are the fields that cannot be fetched from
        the data plane or we just want to save them into the meta file.

        `None` means all fields are meta fields but it doesn't mean they
        won't be updated from the data plane.
        """

        # Keep all fields as meta fields for simplicity
        return {"uuid", "path", "user", "service_type", "before", "after"}

    def _parse_conditions(self, conditions, prefix):
        res = []
        for cond in conditions:
            if cond.kind == "service":
                # TODO: support services deps
                continue
            res.append(
                f"{prefix}=+/usr/bin/bash -c '{cond.command.replace("'", "\\'")}'"
            )
        return res

    def dump_to_dp(self) -> None:
        with open(f"{SERVICES_DIR}{self.get_service_name()}", "w") as f:
            f.write(
                SERVICE_TEMPLATE.format(
                    service_type=TYPES_MAPPING[self.service_type.kind],
                    restart=(
                        "always"
                        if self.service_type.kind != "oneshot"
                        else "on-failure"
                    ),
                    command=self.path.replace("'", "\\'"),
                    user=self.user or "root",
                    pre="\n".join(self._parse_conditions(self.before, "ExecStartPre")),
                    post="\n".join(self._parse_conditions(self.before, "ExecStartPost")),
                )
            )

        subprocess.check_call(["systemctl", "daemon-reload"])
        subprocess.check_call(["systemctl", "enable", "--now", self.get_service_name()])
        self.status = ic.InstanceStatus.ACTIVE.value

    def restore_from_dp(self) -> None:
        try:
            subprocess.check_call(["systemctl", "status", self.get_service_name()])
            self.status = ic.InstanceStatus.ACTIVE.value
        except subprocess.CalledProcessError:
            self.status = ic.InstanceStatus.ERROR.value

    def delete_from_dp(self) -> None:
        subprocess.check_call(
            ["systemctl", "disable", "--now", self.get_service_name()]
        )
        os.remove(f"{SERVICES_DIR}{self.get_service_name()}")

    def update_on_dp(self) -> None:
        """Update the resource on the data plane."""
        # The simplest implementation, just recreate.
        self.delete_from_dp()
        self.dump_to_dp()


class ServiceCapabilityDriver(meta.MetaFileStorageAgentDriver):
    SERVICE_META_PATH = os.path.join(c.WORK_DIR, "service_meta.json")

    __model_map__ = {SERVICE_TARGET_KIND: Service}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, meta_file=self.SERVICE_META_PATH, **kwargs)
