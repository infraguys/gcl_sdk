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

from gcl_sdk.agents.universal.drivers import exceptions as driver_exc
from gcl_sdk.agents.universal.drivers import meta
from gcl_sdk.agents.universal import constants as c
from gcl_sdk.infra import constants as ic
from gcl_sdk.paas.dm import lb as lb_models


LOG = logging.getLogger(__name__)

LB_TARGET_KIND = "paas_lb_node"


class LB(lb_models.LB, meta.MetaDataPlaneModel):

    def get_meta_model_fields(self) -> set[str] | None:
        """Return a list of meta fields or None.

        Meta fields are the fields that cannot be fetched from
        the data plane or we just want to save them into the meta file.

        `None` means all fields are meta fields but it doesn't mean they
        won't be updated from the data plane.
        """

        # Keep all fields as meta fields for simplicity
        return {
            "uuid",
            "vhosts",
            "backends",
        }

    def dump_to_dp(self) -> None:
        return
        with open(f"{SERVICES_DIR}{self.get_my_name()}", "w") as f:
            f.write(self._gen_file_content())

        subprocess.check_call(["systemctl", "daemon-reload"])
        if self.target_status == "enabled":
            subprocess.check_call(
                ["systemctl", "enable", "--now", self.get_my_name()]
            )
        else:
            subprocess.check_call(
                ["systemctl", "disable", "--now", self.get_my_name()]
            )
        self.status = ic.InstanceStatus.ACTIVE.value

    def restore_from_dp(self) -> None:
        return
        try:
            subprocess.check_output(
                ["systemctl", "is-active", self.get_my_name()]
            )
            self.status = ic.InstanceStatus.ACTIVE.value
        except subprocess.CalledProcessError as e:
            # It's ok that oneshot is already finished and inactive
            if self.service_type.kind.endswith("oneshot"):
                if e.output == b"inactive\n":
                    self.status = ic.InstanceStatus.ACTIVE.value
            else:
                raise driver_exc.InvalidDataPlaneObjectError(
                    obj={"uuid": str(self.uuid)}
                )

        # Force file validation
        try:
            with open(f"{SERVICES_DIR}{self.get_my_name()}", "r") as f:
                if self._gen_file_content() != f.read():
                    raise driver_exc.InvalidDataPlaneObjectError(
                        obj={"uuid": str(self.uuid)}
                    )
        except FileNotFoundError:
            raise driver_exc.InvalidDataPlaneObjectError(
                obj={"uuid": str(self.uuid)}
            )

    def delete_from_dp(self) -> None:
        return
        subprocess.check_call(
            ["systemctl", "disable", "--now", self.get_my_name()]
        )
        try:
            os.remove(f"{SERVICES_DIR}{self.get_my_name()}")
        except FileNotFoundError:
            pass
        subprocess.check_call(["systemctl", "daemon-reload"])

    def update_on_dp(self) -> None:
        return
        """Update the resource on the data plane."""
        # The simplest implementation, just recreate.
        self.delete_from_dp()
        self.dump_to_dp()


class LBCapabilityDriver(meta.MetaFileStorageAgentDriver):
    META_PATH = os.path.join(c.WORK_DIR, "lb_meta.json")

    __model_map__ = {LB_TARGET_KIND: LB}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, meta_file=self.META_PATH, **kwargs)
