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

import os
import tempfile
import uuid as sys_uuid
from unittest import mock

from bazooka import exceptions as bazooka_exc
from restalchemy.dm import models as ra_models
from restalchemy.dm import properties
from restalchemy.dm import types as ra_types

from gcl_sdk.agents.universal import utils
from gcl_sdk.agents.universal.dm import models
from gcl_sdk.agents.universal.drivers import base
from gcl_sdk.agents.universal.services import agent as agent_svc
from gcl_sdk.tests.functional import conftest

MACHINE_UUID = sys_uuid.UUID("44b5857b-c15d-47f2-bed1-00fecd137208")


class FooCapDriver(base.AbstractCapabilityDriver):
    create_called = False
    delete_called = False
    update_called = False
    list_called = False
    get_called = False

    def get_capabilities(self) -> list[str]:
        return ["foo"]

    def get(self, resource: models.Resource) -> models.Resource:
        self.__class__.get_called = True
        return resource

    def create(self, resource: models.Resource) -> models.Resource:
        self.__class__.create_called = True
        return resource

    def update(self, resource: models.Resource) -> models.Resource:
        self.__class__.update_called = True
        return resource

    def list(self, capability: str) -> list[models.Resource]:
        self.__class__.list_called = True
        return []

    def delete(self, resource: models.Resource) -> None:
        self.__class__.delete_called = True
        pass


class FooFactDriver(base.AbstractFactDriver):
    get_called = False
    list_called = False

    def get_facts(self) -> list[str]:
        return ["foo"]

    def get(self, resource: models.Resource) -> models.Resource:
        self.__class__.get_called = True
        return resource

    def list(self, fact: str) -> list[models.Resource]:
        self.__class__.list_called = True
        return []


@mock.patch.object(
    utils,
    "system_uuid",
    lambda: MACHINE_UUID,
)
class TestUniversalAgent:
    PAYLOAD_PATH = os.path.join(tempfile.gettempdir(), "___payload___.json")

    def setup_method(self) -> None:
        # Run service
        self.orch_api = mock.MagicMock()
        self.status_api = mock.MagicMock()

    def teardown_method(self) -> None:
        if os.path.exists(self.PAYLOAD_PATH):
            os.remove(self.PAYLOAD_PATH)

    def test_agent_registration(self):
        cause = mock.MagicMock()
        cause.response.status_code = 404
        self.orch_api.agents.get_payload = mock.MagicMock(
            side_effect=bazooka_exc.NotFoundError(cause)
        )

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[],
            facts_drivers=[],
            orch_api=self.orch_api,
            status_api=self.status_api,
        )

        agent._iteration()

        self.status_api.agents.create.assert_called_once()

    def test_agent_new_capability(self):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(uuid=uuid)
        payload = models.Payload.empty()
        payload.add_caps_resource(resource.to_ua_resource(kind="foo"))
        payload.calculate_hash()

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class CapDriver(FooCapDriver):

            def create(self, resource):
                assert resource.uuid == uuid
                return super().create(resource)

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[CapDriver()],
            facts_drivers=[],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        assert CapDriver.create_called
        assert not CapDriver.delete_called
        assert not CapDriver.update_called
        self.orch_api.agents.get_payload.assert_called_once()
        self.status_api.resources("foo").create.assert_called_once_with(
            resource.to_ua_resource(kind="foo")
        )
        self.status_api.resources("foo").update.assert_not_called()
        self.status_api.resources("foo").delete.assert_not_called()

    def test_agent_update_capability(self):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(uuid=uuid)
        payload = models.Payload.empty()
        payload.add_caps_resource(resource.to_ua_resource(kind="foo"))
        payload.add_facts_resource(resource.to_ua_resource(kind="foo"))
        payload.calculate_hash()

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class CapDriver(FooCapDriver):
            def list(self, capability):
                res = resource.dump_to_simple_view()
                res["name"] = "foo-name-updated"
                res = conftest.FooResource.restore_from_simple_view(**res)
                return [res.to_ua_resource(kind="foo")]

            def update(self, resource):
                assert resource.uuid == uuid
                return super().update(resource)

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[CapDriver()],
            facts_drivers=[],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        assert CapDriver.update_called
        assert not CapDriver.delete_called
        assert not CapDriver.create_called
        self.orch_api.agents.get_payload.assert_called_once()
        self.status_api.resources("foo").create.assert_not_called()
        self.status_api.resources("foo").update.assert_not_called()
        self.status_api.resources("foo").delete.assert_not_called()

    def test_agent_delete_capability(self):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(uuid=uuid)
        payload = models.Payload.empty()
        payload.capabilities = {"foo": {"resources": []}}
        payload.add_facts_resource(resource.to_ua_resource(kind="foo"))
        payload.calculate_hash()

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class CapDriver(FooCapDriver):
            def list(self, capability):
                return [resource.to_ua_resource(kind="foo")]

            def delete(self, resource):
                assert resource.uuid == uuid
                return super().delete(resource)

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[CapDriver()],
            facts_drivers=[],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        assert CapDriver.delete_called
        assert not CapDriver.update_called
        assert not CapDriver.create_called
        self.orch_api.agents.get_payload.assert_called_once()
        self.status_api.resources("foo").create.assert_not_called()
        self.status_api.resources("foo").update.assert_not_called()
        self.status_api.resources("foo").delete.assert_called_once_with(
            str(uuid)
        )

    def test_agent_new_capabilities(self):
        uuid_a = sys_uuid.uuid4()
        uuid_b = sys_uuid.uuid4()
        resource_a = conftest.FooResource(uuid=uuid_a)
        resource_b = conftest.FooResource(uuid=uuid_b)
        payload = models.Payload.empty()
        payload.add_caps_resource(resource_a.to_ua_resource(kind="foo"))
        payload.add_caps_resource(resource_b.to_ua_resource(kind="foo"))
        payload.calculate_hash()

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class CapDriver(FooCapDriver):

            def create(self, resource):
                assert resource.uuid in {uuid_a, uuid_b}
                return super().create(resource)

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[CapDriver()],
            facts_drivers=[],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        self.orch_api.agents.get_payload.assert_called_once()
        assert self.status_api.resources("foo").create.call_count == 2
        self.status_api.resources("foo").update.assert_not_called()
        self.status_api.resources("foo").delete.assert_not_called()

    def test_agent_mix_capability_actions(self):
        uuid_a = sys_uuid.uuid4()
        uuid_b = sys_uuid.uuid4()
        uuid_c = sys_uuid.uuid4()
        resource_a = conftest.FooResource(uuid=uuid_a)
        resource_b = conftest.FooResource(uuid=uuid_b)
        resource_c = conftest.FooResource(uuid=uuid_c)
        payload = models.Payload.empty()
        payload.add_caps_resource(resource_a.to_ua_resource(kind="foo"))
        payload.add_caps_resource(resource_b.to_ua_resource(kind="foo"))
        payload.add_facts_resource(resource_b.to_ua_resource(kind="foo"))
        payload.add_facts_resource(resource_c.to_ua_resource(kind="foo"))
        payload.calculate_hash()

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class CapDriver(FooCapDriver):

            def list(self, capability):
                res = resource_b.dump_to_simple_view()
                res["name"] = "foo-name-updated"
                res = conftest.FooResource.restore_from_simple_view(**res)
                return [
                    res.to_ua_resource(kind="foo"),
                    resource_c.to_ua_resource(kind="foo"),
                ]

            def create(self, resource):
                assert resource.uuid == uuid_a
                return super().create(resource)

            def delete(self, resource):
                assert resource.uuid == uuid_c
                return super().delete(resource)

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[CapDriver()],
            facts_drivers=[],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        self.status_api.resources("foo").create.assert_called_once_with(
            resource_a.to_ua_resource(kind="foo")
        )
        self.status_api.resources("foo").update.assert_not_called()
        self.status_api.resources("foo").delete.assert_called_once_with(
            str(uuid_c)
        )

    def test_agent_new_fact(self):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(uuid=uuid)
        payload = models.Payload.empty()
        payload.facts = {"foo": {"resources": []}}
        payload.calculate_hash()

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class FactDriver(FooFactDriver):

            def list(self, fact):
                super().list(fact)
                return [resource.to_ua_resource(kind="foo")]

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[],
            facts_drivers=[FactDriver()],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        self.orch_api.agents.get_payload.assert_called_once()
        self.status_api.resources("foo").create.assert_called_once_with(
            resource.to_ua_resource(kind="foo")
        )
        self.status_api.resources("foo").update.assert_not_called()
        self.status_api.resources("foo").delete.assert_not_called()

    def test_agent_update_fact(self):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(uuid=uuid)
        payload = models.Payload.empty()
        payload.add_facts_resource(resource.to_ua_resource(kind="foo"))
        payload.calculate_hash()

        res = resource.dump_to_simple_view()
        res["name"] = "foo-name-updated"
        res = conftest.FooResource.restore_from_simple_view(**res)

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class FactDriver(FooFactDriver):

            def list(self, fact):
                super().list(fact)
                return [res.to_ua_resource(kind="foo")]

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[],
            facts_drivers=[FactDriver()],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        self.orch_api.agents.get_payload.assert_called_once()
        self.status_api.resources("foo").create.assert_not_called()
        self.status_api.resources("foo").delete.assert_not_called()

        data = res.to_ua_resource(kind="foo").dump_to_simple_view()
        data.pop("created_at", None)
        data.pop("updated_at", None)
        data.pop("res_uuid", None)
        data.pop("node", None)
        self.status_api.resources("foo").update.assert_called_once_with(**data)

    def test_agent_delete_fact(self):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(uuid=uuid)
        payload = models.Payload.empty()
        payload.add_facts_resource(resource.to_ua_resource(kind="foo"))
        payload.calculate_hash()

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class FactDriver(FooFactDriver):
            pass

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[],
            facts_drivers=[FactDriver()],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        self.orch_api.agents.get_payload.assert_called_once()
        self.status_api.resources("foo").create.assert_not_called()
        self.status_api.resources("foo").update.assert_not_called()
        self.status_api.resources("foo").delete.assert_called_once_with(
            str(uuid)
        )

    def test_agent_new_facts(self):
        uuid_a = sys_uuid.uuid4()
        uuid_b = sys_uuid.uuid4()
        resource_a = conftest.FooResource(uuid=uuid_a)
        resource_b = conftest.FooResource(uuid=uuid_b)
        payload = models.Payload.empty()
        payload.facts = {"foo": {"resources": []}}
        payload.calculate_hash()

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class FactDriver(FooFactDriver):

            def list(self, fact):
                super().list(fact)
                return [
                    resource_a.to_ua_resource(kind="foo"),
                    resource_b.to_ua_resource(kind="foo"),
                ]

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[],
            facts_drivers=[FactDriver()],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        self.orch_api.agents.get_payload.assert_called_once()
        assert self.status_api.resources("foo").create.call_count == 2
        self.status_api.resources("foo").update.assert_not_called()
        self.status_api.resources("foo").delete.assert_not_called()

    def test_agent_mix_fact_actions(self):
        uuid_a = sys_uuid.uuid4()
        uuid_b = sys_uuid.uuid4()
        uuid_c = sys_uuid.uuid4()
        resource_a = conftest.FooResource(uuid=uuid_a)
        resource_b = conftest.FooResource(uuid=uuid_b)
        resource_c = conftest.FooResource(uuid=uuid_c)
        payload = models.Payload.empty()
        payload.add_facts_resource(resource_b.to_ua_resource(kind="foo"))
        payload.add_facts_resource(resource_c.to_ua_resource(kind="foo"))
        payload.calculate_hash()

        res = resource_b.dump_to_simple_view()
        res["name"] = "foo-name-updated"
        res = conftest.FooResource.restore_from_simple_view(**res)

        self.orch_api.agents.get_payload = mock.MagicMock(return_value=payload)

        class FactDriver(FooFactDriver):

            def list(self, fact):
                super().list(fact)
                return [
                    resource_a.to_ua_resource(kind="foo"),
                    res.to_ua_resource(kind="foo"),
                ]

        agent = agent_svc.UniversalAgentService(
            caps_drivers=[],
            facts_drivers=[FactDriver()],
            orch_api=self.orch_api,
            status_api=self.status_api,
            payload_path=self.PAYLOAD_PATH,
        )

        agent._iteration()

        self.orch_api.agents.get_payload.assert_called_once()
        self.status_api.resources("foo").create.assert_called_once_with(
            resource_a.to_ua_resource(kind="foo")
        )
        self.status_api.resources("foo").delete.assert_called_once_with(
            str(uuid_c)
        )

        data = res.to_ua_resource(kind="foo").dump_to_simple_view()
        data.pop("created_at", None)
        data.pop("updated_at", None)
        data.pop("res_uuid", None)
        data.pop("node", None)
        self.status_api.resources("foo").update.assert_called_once_with(**data)
