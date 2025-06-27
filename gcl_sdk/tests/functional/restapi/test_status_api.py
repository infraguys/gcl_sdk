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

from urllib.parse import urljoin
import uuid as sys_uuid

import pytest
import requests
from oslo_config import cfg

from gcl_sdk.agents.universal.dm import models
from gcl_sdk.tests.functional import utils as test_utils
from gcl_sdk.tests.functional import conftest


CONF = cfg.CONF


class TestUAStatusApi:
    @pytest.fixture(scope="class")
    def status_api_service(self, status_api_wsgi_app):
        class ApiRestService(test_utils.RestServiceTestCase):
            __FIRST_MIGRATION__ = conftest.FIRST_MIGRATION
            __APP__ = status_api_wsgi_app

        rest_service = ApiRestService()
        rest_service.setup_class()

        yield rest_service

        rest_service.teardown_class()

    @pytest.fixture()
    def status_api(self, status_api_service: test_utils.RestServiceTestCase):
        status_api_service.setup_method()

        yield status_api_service

        status_api_service.teardown_method()

    def test_agent_no_agents(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        url = urljoin(status_api.base_url, "agents/")

        response = requests.get(url)

        assert response.status_code == 200

    def test_agent_list(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        uuid_a = sys_uuid.uuid4()
        agent_a = models.UniversalAgent(
            name="Agent A", uuid=uuid_a, node=uuid_a
        )
        uuid_b = sys_uuid.uuid4()
        agent_b = models.UniversalAgent(
            name="Agent B", uuid=uuid_b, node=uuid_b
        )
        agent_a.insert()
        agent_b.insert()

        url = urljoin(status_api.base_url, "agents/")

        response = requests.get(url)
        output = response.json()

        assert response.status_code == 200
        assert len(output) == 2
        assert {a["uuid"] for a in output} == {str(uuid_a), str(uuid_b)}

    def test_agent_register(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        uuid = sys_uuid.uuid4()
        agent = models.UniversalAgent(
            name="Agent A",
            uuid=uuid,
            node=uuid,
            capabilities={"capabilities": ["foo"]},
            facts={"facts": ["bar"]},
        )

        view = agent.dump_to_simple_view()

        url = urljoin(status_api.base_url, "agents/")

        response = requests.post(url, json=view)
        output = response.json()

        assert response.status_code == 201
        assert output["uuid"] == str(uuid)

    def test_resources_no_kind(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        url = urljoin(status_api.base_url, "kind/")

        response = requests.get(url)
        output = response.json()

        assert response.status_code == 200
        assert output == []

    def test_resources_empty_kind(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        url = urljoin(status_api.base_url, "kind/foo/resources/")

        response = requests.get(url)
        output = response.json()

        assert response.status_code == 200
        assert output == []

    def test_resources_add_resource(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(
            uuid=uuid,
            name="foo-name",
            project_id=uuid,
        ).to_ua_resource(kind="/v1/kind/foo")
        view = resource.dump_to_simple_view()

        url = urljoin(status_api.base_url, "kind/foo/resources/")

        response = requests.post(url, json=view)
        output = response.json()

        assert response.status_code == 201
        assert output["uuid"] == str(uuid)

    def test_resources_update_resource(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(
            uuid=uuid,
            name="foo-name",
            project_id=uuid,
        ).to_ua_resource(kind="/v1/kind/foo")
        view = resource.dump_to_simple_view()

        url = urljoin(status_api.base_url, "kind/foo/resources/")

        response = requests.post(url, json=view)
        output = response.json()

        assert response.status_code == 201
        assert output["uuid"] == str(uuid)

        view["value"]["name"] = "foo-name-updated"
        view.pop("uuid")
        view.pop("res_uuid")
        view.pop("created_at")
        view.pop("updated_at")

        url = urljoin(status_api.base_url, f"kind/foo/resources/{uuid}")

        response = requests.put(url, json=view)
        output = response.json()

        assert response.status_code == 200
        assert output["value"]["name"] == "foo-name-updated"

    def test_resources_delete_resource(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(
            uuid=uuid,
            name="foo-name",
            project_id=uuid,
        ).to_ua_resource(kind="/v1/kind/foo")
        view = resource.dump_to_simple_view()

        url = urljoin(status_api.base_url, "kind/foo/resources/")

        response = requests.post(url, json=view)
        output = response.json()

        assert response.status_code == 201
        assert output["uuid"] == str(uuid)

        url = urljoin(status_api.base_url, f"kind/foo/resources/{uuid}")

        response = requests.delete(url)

        assert response.status_code == 204

    def test_resources_add_resource_dynamic_kind(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(
            uuid=uuid,
            name="foo-name",
            project_id=uuid,
        ).to_ua_resource(kind="/v1/kind/foo")
        view = resource.dump_to_simple_view()

        url = urljoin(status_api.base_url, "kind/foo/resources/")

        response = requests.post(url, json=view)
        assert response.status_code == 201

        url = urljoin(status_api.base_url, "kind/")

        response = requests.get(url)
        output = response.json()

        assert response.status_code == 200
        assert output == ["foo"]

    def test_resources_list_kind(
        self,
        status_api: test_utils.RestServiceTestCase,
    ):
        uuid = sys_uuid.uuid4()
        resource = conftest.FooResource(
            uuid=uuid,
            name="foo-name",
            project_id=uuid,
        ).to_ua_resource(kind="/v1/kind/foo")
        view = resource.dump_to_simple_view()

        url = urljoin(status_api.base_url, "kind/foo/resources/")

        response = requests.post(url, json=view)
        assert response.status_code == 201

        response = requests.get(url)
        output = response.json()

        assert response.status_code == 200
        assert len(output) == 1
        assert output[0]["uuid"] == str(uuid)
