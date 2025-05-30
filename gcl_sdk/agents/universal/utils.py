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

import json
import hashlib
import typing as tp
import uuid as sys_uuid


def system_uuid(
    system_uuid_path: str = "/sys/class/dmi/id/product_uuid",
) -> sys_uuid.UUID:
    """Return system uuid"""
    with open(system_uuid_path) as f:
        return sys_uuid.UUID(f.read().strip())


def node_uuid() -> sys_uuid.UUID:
    """Return node uuid"""

    # FIXME(akremenetsky): Actually it's not correct for some baremetal cases.
    return system_uuid()


def calculate_hash(
    value: dict, hash_method: tp.Callable[[str], str] = hashlib.sha256
) -> str:
    m = hash_method()
    m.update(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )
    return m.hexdigest()
