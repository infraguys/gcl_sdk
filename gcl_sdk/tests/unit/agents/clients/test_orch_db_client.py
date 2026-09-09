#    Copyright 2026 Genesis Corporation.
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

from unittest import mock
import uuid as sys_uuid

from gcl_sdk.agents.universal import constants as c
from gcl_sdk.agents.universal.clients.orch import db as orch_db
from gcl_sdk.agents.universal.dm import models


class TestDatabaseOrchClientAgentsCreate:
    def test_agents_create_ignores_check_node_exists(self):
        # The node check guards the remote registration path only. This
        # client runs in-process with the service owning the database, and
        # that database is not necessarily the node registry - a downstream
        # service has no `ua_node_encryption_keys` row for its own host and
        # never will, so honouring the flag would make registration
        # impossible there.
        client = orch_db.DatabaseOrchClient()

        agent = models.UniversalAgent(
            uuid=sys_uuid.uuid4(),
            name="agent",
            node=sys_uuid.uuid4(),
            capabilities={"capabilities": ["pool"]},
            facts={"facts": []},
        )

        with mock.patch.object(agent, "insert", return_value=agent) as insert:
            result = client.agents_create(
                agent, check_node_exists=True, session=mock.MagicMock()
            )

        insert.assert_called_once()
        assert result is agent


class TestDatabaseOrchClientAgentsUpdate:
    def test_agents_update_activates_the_agent(self):
        # A re-registering agent (uuid already exists) goes through this
        # path - it must always end up ACTIVE. `status` is read-only over
        # the API (see UniversalAgentsController), but this client talks to
        # the DB directly, so it's the one responsible for activating it.
        client = orch_db.DatabaseOrchClient()
        agent_uuid = sys_uuid.uuid4()

        incoming = models.UniversalAgent(
            uuid=agent_uuid,
            name="new-name",
            node=sys_uuid.uuid4(),
            capabilities={"capabilities": ["pool"]},
            facts={"facts": []},
        )
        origin_agent = models.UniversalAgent(
            uuid=agent_uuid,
            name="old-name",
            node=sys_uuid.uuid4(),
            status=c.AgentStatus.NEW.value,
        )

        with (
            mock.patch.object(
                models.UniversalAgent._ObjectCollection,
                "get_one",
                return_value=origin_agent,
            ),
            mock.patch.object(origin_agent, "save"),
        ):
            result = client.agents_update(incoming, session=mock.MagicMock())

        assert result.status == c.AgentStatus.ACTIVE.value
