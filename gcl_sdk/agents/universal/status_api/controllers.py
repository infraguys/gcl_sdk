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
import uuid as sys_uuid

from restalchemy.api import resources
from restalchemy.api import controllers
from restalchemy.dm import filters as dm_filters

from gcl_sdk.agents.universal.status_api.dm import models


class KindController(controllers.BaseResourceController):
    """Controller for /v1/kind/ endpoint"""

    __resource__ = resources.ResourceByRAModel(
        model_class=models.KindModel,
        process_filters=True,
        convert_underscore=False,
    )


class ResourcesController(controllers.BaseNestedResourceController):
    """Controller for /v1/kind/<name>/resources/ endpoint"""

    __resource__ = resources.ResourceByRAModel(
        model_class=models.Resource,
        process_filters=True,
        convert_underscore=False,
    )

    def filter(
        self, parent_resource: models.KindModel, filters, order_by=None
    ):
        return models.Resource.objects.get_all(
            filters={
                "kind": dm_filters.EQ(parent_resource.kind),
            }
        )

    def get(
        self, uuid: sys_uuid.UUID, parent_resource: models.KindModel, **kwargs
    ):
        resource = models.Resource.objects.get_one(
            filters={
                "kind": dm_filters.EQ(parent_resource.kind),
                "uuid": dm_filters.EQ(str(uuid)),
            }
        )
        return resource


class UniversalAgentsController(controllers.BaseResourceController):
    """Controller for /v1/agents/ endpoint"""

    __resource__ = resources.ResourceByRAModel(
        model_class=models.UniversalAgent,
        process_filters=True,
        convert_underscore=False,
    )
