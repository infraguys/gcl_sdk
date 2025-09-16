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
import typing as tp
import uuid as sys_uuid

from restalchemy.dm import filters as dm_filters
from restalchemy.storage import exceptions as ra_exc
from restalchemy.storage import base as ra_storage
from gcl_sdk.agents.universal.clients.backend import base
from gcl_sdk.agents.universal.clients.backend import exceptions as client_exc
from gcl_sdk.agents.universal.dm import models


LOG = logging.getLogger(__name__)


class ModelSpec(tp.NamedTuple):
    model: tp.Type[ra_storage.AbstractStorableMixin]
    kind: str

    # TODO(akremenetsky): Actually we can do filtering more flexibly
    # by using any filters from restalchemy and not using the project_id.
    project_id: sys_uuid.UUID

    @classmethod
    def from_collection(
        cls,
        collection: tp.Collection[tuple[tp.Type, str]],
        project_id: sys_uuid.UUID,
    ) -> tuple[ModelSpec, ...]:
        return tuple(
            cls(
                model=model,
                kind=kind,
                project_id=project_id,
            )
            for model, kind in collection
        )


class DatabaseBackendClient(base.AbstractBackendClient):
    """Database backend client."""

    def __init__(
        self,
        model_specs: tp.Collection[ModelSpec],
        session: tp.Any | None = None,
    ):
        super().__init__()
        self._session = session
        self._model_spec_map = {m.kind: m for m in model_specs}

    def set_session(self, session: tp.Any) -> None:
        """Set the session to be used by the client."""
        self._session = session

    def clear_session(self) -> None:
        """Clear the session."""
        self._session = None

    def get(self, resource: models.Resource) -> models.ResourceMixin:
        """Find and return a resource by uuid and kind."""
        model_spec = self._model_spec_map[resource.kind]

        try:
            return model_spec.model.objects.get_one(
                session=self._session,
                filters={
                    "uuid": dm_filters.EQ(str(resource.uuid)),
                    "project_id": dm_filters.EQ(str(model_spec.project_id)),
                },
            )
        except ra_exc.RecordNotFound:
            LOG.exception(
                "Unable to find %s %s", str(model_spec), resource.uuid
            )
            raise client_exc.ResourceNotFound(resource=resource)

    def list(self, capability: str) -> list[models.ResourceMixin]:
        """Lists all resources by capability."""
        model_spec = self._model_spec_map[capability]

        # Get all objects for the project from the database
        return model_spec.model.objects.get_all(
            session=self._session,
            filters={
                "project_id": dm_filters.EQ(str(model_spec.project_id)),
            },
        )

    def create(self, resource: models.Resource) -> models.ResourceMixin:
        """Creates a resource."""
        model_spec = self._model_spec_map[resource.kind]

        # Check if the resource already exists
        # We need to do this check since PG does not correctly handle
        # the case when the resource already exists and fails the transaction
        obj = model_spec.model.objects.get_one_or_none(
            session=self._session,
            filters={
                "uuid": dm_filters.EQ(str(resource.uuid)),
                "project_id": dm_filters.EQ(str(model_spec.project_id)),
            },
        )
        if obj is not None:
            LOG.warning("The resource already exists: %s", resource.uuid)
            raise client_exc.ResourceAlreadyExists(resource=resource)

        # Save to db
        obj = model_spec.model.from_ua_resource(resource)
        obj.insert(session=self._session)

        return obj

    def update(self, resource: models.Resource) -> models.ResourceMixin:
        """Update the resource."""
        model_spec = self._model_spec_map[resource.kind]

        # Check if the resource already exists
        obj = model_spec.model.objects.get_one_or_none(
            session=self._session,
            filters={
                "uuid": dm_filters.EQ(str(resource.uuid)),
                "project_id": dm_filters.EQ(str(model_spec.project_id)),
            },
        )
        if obj is None:
            LOG.warning("The resource does not exist: %s", resource.uuid)
            raise client_exc.ResourceNotFound(resource=resource)

        updated_obj = model_spec.model.from_ua_resource(resource)

        # Update the object
        for field_name in resource.value.keys():
            prop = obj.properties.get(field_name)
            if not prop or prop.is_read_only():
                continue
            setattr(obj, field_name, getattr(updated_obj, field_name))
        obj.update(session=self._session)

        return obj

    def delete(self, resource: models.Resource) -> None:
        """Delete the resource."""
        model_spec = self._model_spec_map[resource.kind]

        try:
            obj = model_spec.model.objects.get_one(
                session=self._session,
                filters={
                    "uuid": dm_filters.EQ(str(resource.uuid)),
                    "project_id": dm_filters.EQ(str(model_spec.project_id)),
                },
            )
            obj.delete(session=self._session)
            LOG.debug("Deleted resource: %s", resource.uuid)
        except ra_exc.RecordNotFound:
            LOG.warning("The resource is already deleted: %s", resource.uuid)
