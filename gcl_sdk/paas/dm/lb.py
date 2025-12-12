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

from restalchemy.dm import models
from restalchemy.dm import properties
from restalchemy.dm import types as ra_types

from gcl_sdk.infra import constants as ic


class LB(models.ModelWithRequiredUUID):
    status = properties.property(
        ra_types.Enum([s.value for s in ic.InstanceStatus]),
        default=ic.InstanceStatus.NEW.value,
    )
    vhosts = properties.property(ra_types.List())
    backend_pools = properties.property(ra_types.Dict())
