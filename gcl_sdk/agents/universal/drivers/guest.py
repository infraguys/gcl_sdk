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
import logging
import subprocess

from restalchemy.dm import properties
from restalchemy.dm import types
from restalchemy.dm import types_network

from gcl_sdk.agents.universal.drivers import meta
from gcl_sdk.agents.universal import constants as c


LOG = logging.getLogger(__name__)
GUEST_MACHINE_KIND = "guest_machine"


class GuestMachineMetaModel(meta.MetaDataPlaneModel):
    """Guest machine meta model."""

    image = properties.property(types.String(), required=True)
    boot = properties.property(types.String(), required=True)
    hostname = properties.property(
        types.AllowNone(types_network.Hostname()), default=None
    )
    block_devices = properties.property(types.Dict(), default=dict)
    net_devices = properties.property(types.Dict(), default=dict)
    pci_devices = properties.property(types.Dict(), default=dict)

    status = properties.property(
        types.Enum([s.value for s in c.InstanceStatus]),
        default=c.InstanceStatus.ACTIVE.value,
    )

    def _set_hostname(self, hostname: str) -> None:
        """Set hostname in the system."""
        subprocess.check_call(["hostnamectl", "hostname", hostname])

    def _get_hostname(self) -> str:
        """Return hostname from the system."""
        return (
            subprocess.check_output(["hostnamectl", "hostname"])
            .decode("utf-8")
            .strip()
        )

    def get_meta_model_fields(self) -> set[str] | None:
        """Return a list of meta fields or None.

        Meta fields are the fields that cannot be fetched from
        the data plane or we just want to save them into the meta file.

        `None` means all fields are meta fields but it doesn't mean they
        won't be updated from the data plane.
        """
        return {"uuid", "image", "boot", "hostname"}

    def dump_to_dp(self) -> None:
        """Apply the guest settings to the data plane."""
        if self.hostname:
            self._set_hostname(self.hostname)

    def restore_from_dp(self) -> None:
        """Load the guest settings from the data plane."""
        # If no hostname specified, use the one from the system
        if self.hostname:
            self.hostname = self._get_hostname()

    def delete_from_dp(self) -> None:
        """It's not applicable for the guest machine."""
        # Just do nothing.
        pass

    def update_on_dp(self) -> None:
        """Update the resource on the data plane."""
        # The simplest implementation, just recreate.
        self.dump_to_dp()


class GuestMachineCapabilityDriver(meta.MetaFileStorageAgentDriver):
    GUEST_META_PATH = os.path.join(c.WORK_DIR, "guest_meta.json")

    __model_map__ = {GUEST_MACHINE_KIND: GuestMachineMetaModel}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, meta_file=self.GUEST_META_PATH, **kwargs)
