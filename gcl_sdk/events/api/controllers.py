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

from gcl_iam import controllers as iam_controllers
from restalchemy.api import controllers as ra_controllers
from restalchemy.api import resources as ra_resources

from gcl_sdk.events.dm import models


class EventController(
    iam_controllers.PolicyBasedControllerMixin,
    ra_controllers.BaseResourceControllerPaginated,
):
    __policy_service_name__ = "sdk"
    __policy_name__ = "event"

    __resource__ = ra_resources.ResourceByRAModel(
        model_class=models.Event,
        convert_underscore=False,
    )
