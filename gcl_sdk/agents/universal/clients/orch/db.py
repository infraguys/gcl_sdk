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

import contextlib
import logging
import typing as tp
import uuid as sys_uuid

from restalchemy.common import contexts
from restalchemy.dm import filters as dm_filters
from restalchemy.storage import exceptions as ra_exc

from gcl_sdk.agents.universal import constants as c
from gcl_sdk.agents.universal.clients.orch import base
from gcl_sdk.agents.universal.clients.orch import exceptions
from gcl_sdk.agents.universal.dm import models

LOG = logging.getLogger(__name__)


class DatabaseOrchClient(base.AbstractOrchClient):
    """Database Orchestrator client.

    An interface for clients to communicate with an orchestrator.
    """

    @contextlib.contextmanager
    def _session_context(self, session: tp.Any | None = None) -> tp.Any:
        if session:
            yield session
        else:
            with contexts.Context().session_manager() as session:
                yield session

    def agents_create(
        self,
        agent: models.UniversalAgent,
        check_node_exists: bool = False,
        session: tp.Any = None,
    ) -> models.UniversalAgent:
        """Create an instance of Universal agent.

        `check_node_exists` is accepted for interface compatibility with
        the HTTP client but is never acted on here. That check guards the
        remote registration path: an agent on some node asks the
        orchestrator's API to register it, and the orchestrator refuses
        unless it already knows the node (it holds the node's encryption
        key). This client has no such gap to guard - it is constructed
        in-process by the service that owns the database, so registering
        an agent is that service registering itself.

        Worse, honouring the flag here checks the wrong database.
        `ua_node_encryption_keys` lives in whichever service embeds this
        client, and only the node registry (Exordos Core) provisions rows
        in its own copy. A downstream service running an agent against
        its own database has no row for the host it runs on and never
        will, so the check could only ever fail.
        """
        try:
            with self._session_context(session=session) as s:
                return agent.insert(session=s)
        except ra_exc.ConflictRecords:
            raise exceptions.AgentAlreadyExists(uuid=agent.uuid)

    def agents_update(
        self,
        agent: models.UniversalAgent,
        session: tp.Any = None,
    ) -> models.UniversalAgent:
        """Update an instance of Universal agent."""
        try:
            with self._session_context(session=session):
                # Fetch the origin agent
                origin_agent = models.UniversalAgent.objects.get_one(
                    filters={
                        "uuid": dm_filters.EQ(str(agent.uuid)),
                    }
                )

                # Update fields
                origin_agent.capabilities = agent.capabilities
                origin_agent.facts = agent.facts
                origin_agent.name = agent.name

                # `status` is read-only over the API (see
                # UniversalAgentsController) - this client talks to the DB
                # directly, so it activates the agent itself the same way.
                origin_agent.status = c.AgentStatus.ACTIVE.value

                origin_agent.save()

                return origin_agent
        except ra_exc.RecordNotFound:
            raise exceptions.AgentNotFound(uuid=agent.uuid)

    def agents_get_payload(
        self,
        uuid: sys_uuid.UUID,
        payload: models.Payload | None,
        session: tp.Any = None,
    ) -> models.Payload:
        """Get payload for of the Universal agent."""
        if payload is None:
            payload = models.Payload.empty()

        with self._session_context(session=session):
            try:
                agent = models.UniversalAgent.objects.get_one(
                    filters={
                        "uuid": dm_filters.EQ(str(uuid)),
                    }
                )
            except ra_exc.RecordNotFound:
                raise exceptions.AgentNotFound(uuid=uuid)

            return agent.get_payload(hash=payload.hash, version=payload.version)

    def resources_create(
        self,
        resource: models.Resource,
        session: tp.Any = None,
    ) -> models.Resource:
        """Create a resource."""
        try:
            with self._session_context(session=session) as s:
                return resource.insert(session=s)
        except ra_exc.ConflictRecords:
            raise exceptions.ResourceAlreadyExists(uuid=resource.uuid)

    def resources_get(
        self, kind: str, uuid: sys_uuid.UUID, session: tp.Any = None
    ) -> models.Resource:
        """Get the resource."""
        try:
            with self._session_context(session=session):
                return models.Resource.objects.get_one(
                    filters={
                        "uuid": dm_filters.EQ(str(uuid)),
                        "kind": dm_filters.EQ(kind),
                    }
                )
        except ra_exc.RecordNotFound:
            raise exceptions.ResourceNotFound(uuid=uuid)

    def resources_update(
        self,
        kind: str,
        uuid: sys_uuid.UUID,
        session: tp.Any = None,
        **kwargs: tp.Any,
    ) -> models.Resource:
        """Update the resource."""
        with self._session_context(session=session) as s:
            resource = self.resources_get(kind, uuid, session=s)
            view = resource.dump_to_simple_view()
            view.update(**kwargs)
            resource = models.Resource.restore_from_simple_view(**view)
            return resource.update(session=s, force=True)

    def resources_delete(
        self, resource: models.Resource, session: tp.Any = None
    ) -> None:
        """Delete the resource."""
        with self._session_context(session=session) as s:
            resource = self.resources_get(resource.kind, resource.uuid, session=s)
            resource.delete(session=s)
