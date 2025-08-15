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

import os
import json
import logging
from pathlib import Path
import threading
import uuid as sys_uuid

from restalchemy.dm import properties
from restalchemy.dm import types
from restalchemy.dm import models as ra_models

from gcl_sdk.agents.universal.drivers import base
from gcl_sdk.agents.universal.drivers import exceptions as driver_exc
from gcl_sdk.agents.universal.dm import models


LOG = logging.getLogger(__name__)


class MetaDataPlaneModel(
    ra_models.ModelWithRequiredUUID, models.ResourceMixin
):
    """A base model for using in MetaFileStorageAgentDriver.

    Child models should implement methods to work with data plane.
    """

    # Store the resource target fields
    target_fields = properties.property(
        types.TypedList(types.String()), default=list
    )

    @classmethod
    def from_ua_resource(
        cls, resource: models.Resource
    ) -> "MetaDataPlaneModel":
        target_fields = list(resource.value.keys())
        return cls.restore_from_simple_view(
            target_fields=target_fields, **resource.value
        )

    def get_resource_target_fields(self) -> list[str]:
        """Return the list of target fields.

        Refer to the Resource model for more details about target fields.
        """
        return self.target_fields

    def get_resource_ignore_fields(self) -> list[str]:
        """Return fields that should not belong to the resource."""
        return ["target_fields"]

    def get_meta_fields(self) -> set[str] | None:
        """Return a list of meta fields or None.

        Similar to `get_meta_model_fields` but adds addtional service fields.
        """
        fields = self.get_meta_model_fields()
        if fields is None:
            return None
        fields.add("target_fields")
        return fields

    def get_meta_model_fields(self) -> set[str] | None:
        """Return a list of meta fields or None.

        Meta fields are the fields that cannot be fetched from
        the data plane or we just want to save them into the meta file.

        `None` means all fields are meta fields but it doesn't mean they
        won't be updated from the data plane.
        """
        return None

    def dump_to_dp(self) -> None:
        """Save the resource to the data plane."""

    def restore_from_dp(self) -> None:
        """Load the resource from the data plane."""

    def delete_from_dp(self) -> None:
        """Delete the resource from the data plane."""

    def update_on_dp(self) -> None:
        """Update the resource on the data plane."""


class MetaFileStorageSingleton(dict):
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, meta_file: str):
        if meta_file not in cls._instances:
            with cls._lock:
                if meta_file not in cls._instances:
                    cls._instances[meta_file] = super(
                        MetaFileStorageSingleton, cls
                    ).__new__(cls)
        return cls._instances[meta_file]

    def __init__(self, meta_file: str):
        self._meta_file = Path(meta_file)

        super().__init__()
        self.load()

    def load(self) -> None:
        if not os.path.exists(self._meta_file):
            self.clear()
            return

        with open(self._meta_file) as f:
            data = json.load(f)
            self.clear()
            self.update(data)

    def persist(self) -> None:
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(self._meta_file), exist_ok=True)

        # Save the new data
        tmp_file = self._meta_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            json.dump(self, f, indent=2)
        os.replace(tmp_file, self._meta_file)


class MetaFileStorageAgentDriver(base.AbstractCapabilityDriver):
    """Meta driver. Handles models that partly are placed into the metafile.

    It's not possible to get all necessary information from the data plane
    pretty often. For instance, configuration files. There are hundreds or
    thousands of them in the system. How to know which files should be handled
    by the driver? A `meta file` may be used for this purpose. This file
    contains some meta information such path, uuid and so on but this file
    does not contain the information that can be fetched from the data plane.

    Particular models should be derived from `MetaDataPlaneModel` to work
    properly with the driver.
    """

    __model_map__ = {"model": MetaDataPlaneModel}

    def __init__(self, *args, meta_file: str, **kwargs):
        super().__init__()
        self._meta_file = meta_file
        self._storage = MetaFileStorageSingleton(self._meta_file)

        # Check the model map is in the correct format
        for cap_models in self.__model_map__.values():
            if not issubclass(cap_models, MetaDataPlaneModel):
                raise TypeError(
                    f"Model {cap_models} is not a MetaDataPlaneModel"
                )

    def persist_storage(self):
        self._storage.persist()

    def _load_from_meta(self, capability: str) -> list[MetaDataPlaneModel]:
        """Load the resources from the meta file.

        It loads only the `meta` part that cannot be fetched from the data plane
        or lightweight models.
        """

        if (
            capability not in self._storage
            # Reset storage with new format
            or "resources" not in self._storage.get(capability, {})
        ):
            self._storage[capability] = {"resources": {}}
        capstor = self._storage[capability]["resources"]

        cap_model = self.__model_map__[capability]
        return [
            cap_model.restore_from_simple_view(**r) for r in capstor.values()
        ]

    def _delete_from_meta(self, kind: str, uuid: sys_uuid.UUID) -> None:
        """Remove the resource from the meta file."""

        uuid = str(uuid)

        self._storage[kind]["resources"].pop(uuid)
        LOG.debug("Deleted meta resource %s", uuid)

    def _add_to_meta(
        self, capability: str, meta_object: MetaDataPlaneModel
    ) -> None:
        """Add the resource from the meta file."""

        view = meta_object.dump_to_simple_view()

        # Save only meta fields
        # TODO(akremenetsky): Handle an empty meta fields list.
        # Actually it means no fields are saved.
        if meta_fields := meta_object.get_meta_fields():
            for k in tuple(view.keys()):
                if k not in meta_fields:
                    view.pop(k)

        self._storage[capability]["resources"][str(meta_object.uuid)] = view
        LOG.debug("Saved meta resource: %s", view)

    def get_capabilities(self) -> list[str]:
        """Returns a list of capabilities supported by the driver."""
        return list(self.__model_map__.keys())

    def get(self, resource: models.Resource) -> models.Resource:
        """Find and return a resource by uuid and kind.

        It returns the resource from the data plane.
        """
        if resource.kind not in self.__model_map__:
            raise TypeError(f"The resource is not {self.__model_map__.keys()}")

        # Check the resource exists
        for r in self._load_from_meta(resource.kind):
            # Find the corresponding resource
            if r.uuid == resource.uuid:
                meta_resource = r
                break
        else:
            raise driver_exc.ResourceNotFound(resource=resource)

        meta_resource.restore_from_dp()
        return meta_resource.to_ua_resource(resource.kind)

    def list(self, capability: str) -> list[models.Resource]:
        """Lists all resources by capability."""
        if capability not in self.__model_map__:
            raise TypeError(f"The resource is not {self.__model_map__.keys()}")

        dp_objects = []
        for obj in self._load_from_meta(capability):
            try:
                obj.restore_from_dp()
                dp_objects.append(obj)
            except driver_exc.ResourceNotFound:
                LOG.error("Resource %s not found on the data plane", obj.uuid)

        return [obj.to_ua_resource(capability) for obj in dp_objects]

    def create(self, resource: models.Resource) -> models.Resource:
        """Creates a resource."""
        if resource.kind not in self.__model_map__:
            raise TypeError(f"The resource is not {self.__model_map__.keys()}")

        # Check the resource does not exist
        try:
            self.get(resource)
        except driver_exc.ResourceNotFound:
            # Desirable behavior, the resource should not exist
            pass
        else:
            raise driver_exc.ResourceAlreadyExists(resource=resource)

        # Restore object from the resource
        cap_model = self.__model_map__[resource.kind]

        # The object is lightweight since it is not stored in the data plane
        meta_obj = cap_model.from_ua_resource(resource)

        meta_obj.dump_to_dp()
        self._add_to_meta(resource.kind, meta_obj)
        return meta_obj.to_ua_resource(resource.kind)

    def update(self, resource: models.Resource) -> models.Resource:
        """Update the resource.

        The simplest implementation. Updating through recreating the resource.
        """
        if resource.kind not in self.__model_map__:
            raise TypeError(f"The resource is not {self.__model_map__.keys()}")

        for meta_obj in self._load_from_meta(resource.kind):
            if meta_obj.uuid == resource.uuid:
                break
        else:
            raise driver_exc.ResourceNotFound(resource=resource)

        meta_obj = self.__model_map__[resource.kind].from_ua_resource(resource)
        meta_obj.update_on_dp()

        # The simplest implementation, just recreate.
        self._delete_from_meta(resource.kind, resource.uuid)
        self._add_to_meta(resource.kind, meta_obj)

        new_resource = meta_obj.to_ua_resource(resource.kind)
        LOG.debug("Updated resource: %s", new_resource.uuid)
        return new_resource

    def delete(self, resource: models.Resource) -> None:
        """Delete the resource."""
        if resource.kind not in self.__model_map__:
            raise TypeError(f"The resource is not {self.__model_map__.keys()}")

        try:
            self.get(resource)
        except driver_exc.ResourceNotFound:
            # Nothing to do, the resource does not exist
            pass

        # Restore object from the resource
        cap_model = self.__model_map__[resource.kind]
        meta_obj = cap_model.from_ua_resource(resource)

        meta_obj.delete_from_dp()
        self._delete_from_meta(resource.kind, resource.uuid)
        LOG.debug("Deleted resource: %s", resource.uuid)
