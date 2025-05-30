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

import logging

from gcl_looper.services import basic as looper_basic
from bazooka import exceptions as baz_exc

from gcl_sdk.agents.universal import driver as driver_base
from gcl_sdk.agents.universal import exceptions as driver_exc
from gcl_sdk.agents.universal.dm import models
from gcl_sdk.agents.universal.clients import status as status_clients
from gcl_sdk.agents.universal.clients import orch as orch_clients
from gcl_sdk.agents.universal import constants as c
from gcl_sdk.agents.universal import utils


LOG = logging.getLogger(__name__)


class UniversalAgentService(looper_basic.BasicService):

    def __init__(
        self,
        drivers: list[driver_base.AbstractAgentDriver],
        orch_api: orch_clients.OrchAPI,
        status_api: status_clients.StatusAPI,
        payload_path: str = c.PAYLOAD_PATH,
        iter_min_period=3,
        iter_pause=0.1,
    ):
        super().__init__(iter_min_period, iter_pause)
        self._system_uuid = utils.system_uuid()
        self._orch_api = orch_api
        self._status_api = status_api
        self._payload_path = payload_path

        # Make driver map by capability:
        # For instance, {"config": ConfigDriver, "service": ServiceDriver}
        self._driver_map = {}
        for d in drivers:
            for capability in d.get_capabilities():
                self._driver_map[capability] = d

    def _wipe_collected_payload(self):
        self._collected_payload = models.Payload()

    def _register_agent(self) -> None:
        capabilities = self._driver_map.keys()
        agent = models.UniversalAgent.from_system_uuid(capabilities)
        try:
            self._status_api.agents.create(agent)
            LOG.info("Agent registered: %s", agent.uuid)
        except baz_exc.ConflictError:
            LOG.warning("Agent already registered: %s", agent.uuid)

    def _create_resource(
        self,
        driver: driver_base.AbstractAgentDriver,
        resource: models.Resource,
    ) -> None:
        try:
            dp_resource = driver.create(resource)
        except driver_exc.ResourceAlreadyExists:
            LOG.warning("The resource already exists: %s", resource.uuid)
            dp_resource = driver.get(resource)

        self._status_api.resources.create(dp_resource)
        return dp_resource

    def _delete_resource(
        self,
        driver: driver_base.AbstractAgentDriver,
        resource: models.Resource,
    ) -> None:
        try:
            driver.delete(resource)
        except driver_exc.ResourceNotFound:
            LOG.warning("The resource does not exist: %s", resource.uuid)

        self._status_api.resources.delete(resource)

    def _update_resource(
        self,
        driver: driver_base.AbstractAgentDriver,
        resource: models.Resource,
    ) -> None:
        dp_resource = driver.update(resource)
        self._status_api.resources.update(
            resource.uuid, **dp_resource.dump_to_simple_view()
        )
        return dp_resource

    def _actualize_resources(
        self,
        driver: driver_base.AbstractAgentDriver,
        capability: str,
        resources: list[models.Resource],
    ) -> list[models.Resource]:
        """
        Actualize resources and return a list of resources from data plane.
        """
        target_resources = {r: r for r in resources}
        actual_resources = {r: r for r in driver.list(capability)}

        # A list of resources to be collected from the data plane
        # for this capability
        collected_resources = []

        # Create all new resources
        for r in target_resources.keys() - actual_resources.keys():
            try:
                resource = self._create_resource(driver, r)
                collected_resources.append(resource)
            except Exception:
                LOG.exception("Error creating resource %s", r.uuid)

        # Delete outdated resources
        for r in actual_resources.keys() - target_resources.keys():
            try:
                self._delete_resource(driver, r)
            except Exception:
                # The resource wasn't deleted so add it back
                collected_resources.append(r)
                LOG.exception("Error deleting resource %s", r.uuid)

        for r in target_resources.keys() & actual_resources.keys():
            # We need to get exactly target resource, not actual
            target_resource = target_resources[r]
            actual_resource = actual_resources[r]

            # Nothing to do if the resources are the same
            if target_resource.eq_hash(actual_resource):
                collected_resources.append(actual_resource)
                continue

            try:
                resource = self._update_resource(driver, target_resource)
                collected_resources.append(resource)
            except Exception:
                LOG.exception("Error updating resource %s", r.uuid)

        return collected_resources

    def _iteration(self):
        # The payload is collected every iteration from the data plane.
        # At the end of the iteration the payload hash is calculated
        # and it is saved
        collected_payload = models.Payload.empty()

        # Last successfully saved payload. Use it to compare with CP payload.
        last_payload = models.Payload.load(self._payload_path)

        # Check if the agent is registered
        try:
            cp_payload = self._orch_api.agents.get_payload(
                self._system_uuid, last_payload
            )
        except baz_exc.NotFoundError:
            # Auto discovery mechanism
            self._register_agent()
            return

        # TODO(akremenetsky): Need to overthink this moment
        payload = last_payload if last_payload == cp_payload else cp_payload

        # TODO(akremenetsky): Implement actions

        for capability, driver in self._driver_map.items():
            # Skip capabilities that are not in the payload
            if capability not in payload.capabilities:
                continue

            target_resources = payload.resources(capability)

            try:
                collected_resources = self._actualize_resources(
                    driver, capability, target_resources
                )
                collected_payload.add_resources(collected_resources)
            except Exception:
                LOG.exception("Error actualizing resources for %s", capability)

        # Save the collected payload after actualization
        collected_payload.save(self._payload_path)
