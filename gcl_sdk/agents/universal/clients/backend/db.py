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
    filters: dict[str, dm_filters.AbstractClause]

    # Inject filter fields into the model if the model does not have them
    # This is used to be able to filter resources on the list method
    inject_filter_fields: bool = True

    @classmethod
    def from_collection(
        cls,
        collection: tp.Collection[tuple[tp.Type, str]],
        filters: dict[str, dm_filters.AbstractClause],
    ) -> tuple[ModelSpec, ...]:
        return tuple(
            cls(
                model=model,
                kind=kind,
                filters=filters,
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

    def _get_resource_filters(
        self, resource: models.Resource
    ) -> dict[str, dm_filters.AbstractClause]:
        model_spec = self._model_spec_map[resource.kind]
        filters = {"uuid": dm_filters.EQ(str(resource.uuid))}
        filters.update(model_spec.filters)
        return filters

    def set_session(self, session: tp.Any) -> None:
        """Set the session to be used by the client."""
        self._session = session

    def clear_session(self) -> None:
        """Clear the session."""
        self._session = None

    def get(self, resource: models.Resource) -> models.ResourceMixin:
        """Find and return a resource by uuid and kind."""
        model_spec = self._model_spec_map[resource.kind]
        filters = self._get_resource_filters(resource)

        try:
            return model_spec.model.objects.get_one(
                session=self._session,
                filters=filters,
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
            filters=model_spec.filters,
        )

    def create(self, resource: models.Resource) -> models.ResourceMixin:
        """Creates a resource."""
        model_spec = self._model_spec_map[resource.kind]
        filters = self._get_resource_filters(resource)

        # Check if the resource already exists
        # We need to do this check since PG does not correctly handle
        # the case when the resource already exists and fails the transaction
        obj = model_spec.model.objects.get_one_or_none(
            session=self._session,
            filters=filters,
        )
        if obj is not None:
            LOG.warning("The resource already exists: %s", resource.uuid)
            raise client_exc.ResourceAlreadyExists(resource=resource)

        # Inject filter fields into the resource value if they are not present
        if model_spec.inject_filter_fields:
            value = resource.value.copy()
            for field, _filter in model_spec.filters.items():
                if field not in value:
                    value[field] = _filter.value
                else:
                    LOG.warning(
                        "The filter field %s is already present in "
                        "the resource value: %s",
                        field,
                        resource.uuid,
                    )
            obj = model_spec.model.restore_from_simple_view(**value)
        else:
            obj = model_spec.model.from_ua_resource(resource)

        # Save to db
        obj.insert(session=self._session)

        return obj

    def update(self, resource: models.Resource) -> models.ResourceMixin:
        """Update the resource."""
        model_spec = self._model_spec_map[resource.kind]
        filters = self._get_resource_filters(resource)

        # Check if the resource already exists
        obj = model_spec.model.objects.get_one_or_none(
            session=self._session,
            filters=filters,
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
        filters = self._get_resource_filters(resource)

        try:
            obj = model_spec.model.objects.get_one(
                session=self._session,
                filters=filters,
            )
            obj.delete(session=self._session)
            LOG.debug("Deleted resource: %s", resource.uuid)
        except ra_exc.RecordNotFound:
            LOG.warning("The resource is already deleted: %s", resource.uuid)
