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
import itertools
import typing as tp
import uuid as sys_uuid

from restalchemy.common import contexts
from restalchemy.dm import filters as dm_filters
from gcl_looper.services import basic as looper_basic

from gcl_sdk.common import constants as c

# from gcl_sdk.infra import constants as pc
from gcl_sdk.agents.universal.dm import models
from gcl_sdk.agents.universal import constants as ua_c

LOG = logging.getLogger(__name__)


class UniversalBuilderService(looper_basic.BasicService):

    def __init__(
        self,
        instance_model: type[models.InstanceMixin],
        iter_min_period: float = 3,
        iter_pause: float = 0.1,
    ):
        super().__init__(iter_min_period, iter_pause)
        self._instance_model = instance_model

    # Builder interface

    def pre_create_instance_resource(
        self, instance: models.InstanceMixin
    ) -> None:
        """The hook is performed before creating instance resource.

        The hook is called only for new instances.
        """
        pass

    def create_instance_derivatives(
        self, instance: models.InstanceMixin
    ) -> tp.Collection[models.TargetResourceKindAwareMixin]:
        """Create the instance.

        The result is a collection of derivative objects that are
        required for the instance. For example, the main instance is a
        `Config` so the derivative objects for the the config is a list
        of `Render`. The result is a tuple/list/set/... of render objects.
        The derivative objects should inherit from the `TargetResourceMixin`.

        The hook is called only for new instances.
        """
        return tuple()

    def post_create_instance_resource(
        self,
        instance: models.InstanceMixin,
        resource: models.TargetResource,
        derivatives: tp.Collection[models.TargetResource] = tuple(),
    ) -> None:
        """The hook is performed after saving instance resource.

        The hook is called only for new instances.
        """
        instance.status = ua_c.InstanceStatus.IN_PROGRESS.value

    def pre_update_instance_resource(
        self, instance: models.InstanceMixin
    ) -> None:
        """The hook is performed before updating instance resource."""
        pass

    def update_instance_derivatives(
        self,
        instance: models.InstanceWithDerivativesMixin,
        resource: models.TargetResourceKindAwareMixin,
        derivative_pairs: tp.Collection[
            tuple[
                models.TargetResourceKindAwareMixin,  # The target resource
                models.TargetResourceKindAwareMixin
                | None,  # The actual resource
            ]
        ],
    ) -> tp.Collection[models.TargetResourceKindAwareMixin]:
        """The hook to update instance derivatives.

        The hook is called when an initiator of updating is an user or
        software from control plane side.
        The default behavior is to send the same list as on instance creation.
        """
        return self.create_instance_derivatives(instance)

    def post_update_instance_resource(
        self,
        instance: models.InstanceMixin,
        resource: models.TargetResource,
        derivatives: tp.Collection[models.TargetResource] = tuple(),
    ) -> None:
        """The hook is performed after updating instance resource."""
        pass

    def actualize_outdated_instance(
        self,
        current_instance: models.InstanceMixin,
        actual_instance: models.InstanceMixin,
    ) -> None:
        """Actualize outdated instance.

        It means some changes occurred on the data plane and the instance
        is outdated now. For example, the instance `Password` has field
        `value` that is stored in the secret storage. If the value is changed
        or created on the data plane, the instance is outdated and this method
        is called to reactualize the instance.

        Args:
            current_instance: The current instance.
            actual_instance: The actual instance.
        """
        pass

    def actualize_outdated_instance_derivatives(
        self,
        instance: models.InstanceMixin,
        derivative_pairs: tp.Collection[
            tuple[
                models.TargetResourceKindAwareMixin,  # The target resource
                models.TargetResourceKindAwareMixin
                | None,  # The actual resource
            ]
        ],
    ) -> tp.Collection[models.TargetResourceKindAwareMixin]:
        """Actualize outdated instance with derivatives.

        It means some changes occurred on the data plane and the instance
        is outdated now. For example, the instance `Config` has derivative
        `Render`. Single `Config` may have multiple `Render` derivatives.
        If any of the derivatives is outdated, this method is called to
        reactualize the derivatives. The method returns the list of `updated`
        derivatives. If nothing needs to be updated, the method returns the
        same list of target derivatives as it received. Otherwise, the method
        should return the list of updated derivatives. It also can add new or
        remove old derivatives.
        Depends on the `fetch_all_derivatives_on_outdate` the behavior of the
        method is different:

        fetch_all_derivatives_on_outdate == True:
        The method receives the list of all derivatives currently available
        for the instance even though the derivatives aren't outdated.

        fetch_all_derivatives_on_outdate == False:
        The method receives the list only changed derivatives from the last
        actualization. For example, a config has two renders. Only one of
        them is outdated. The method receives the list of only one outdated
        render.

        Args:
            instance: The instance to actualize.
            derivative_pairs: Changed or all derivatives of the instance.
        """
        return tuple(p[0] for p in derivative_pairs)

    def pre_delete_instance_resource(
        self, resource: models.TargetResource
    ) -> None:
        """The hook is performed before deleting instance resource."""
        pass

    def track_outdated_master_hash_instances(self) -> bool:
        """Track outdated master hash instances."""
        return False

    def track_outdated_master_full_hash_instances(self) -> bool:
        """Track outdated master full hash instances."""
        return False

    def actualize_outdated_master_hash_instance(
        self,
        instance: models.InstanceMixin,
        master_instance: models.InstanceMixin,
        derivatives: tp.Collection[
            tuple[
                models.TargetResourceKindAwareMixin,  # The target resource
                models.TargetResourceKindAwareMixin
                | None,  # The actual resource
            ]
        ],
    ) -> tp.Collection[models.TargetResourceKindAwareMixin]:
        """Actualize outdated master hash instance.

        The logic is quite similar to `actualize_outdated_instance_derivatives`.
        But the reason when this method is called is different. The
        `actualize_outdated_instance_derivatives` allows to track changes on the
        data plane but this method allows to track changes on a related master
        instance. For example, the instance model is `Database`, the related master
        for this instance is `NodeSet`. If the `NodeSet` is updated, this method
        is called for all `Database` instances that are related to this `NodeSet`
        to reactualize them.
        This method tracks changes for target fields of the master instance.

        Args:
            instance: The instance to actualize.
            master_instance: The master instance.
            derivatives: All derivatives of the instance.
        """
        return tuple(p[0] for p in derivatives)

    def actualize_outdated_master_full_hash_instance(
        self,
        instance: models.InstanceMixin,
        master_instance: models.InstanceMixin,
        derivatives: tp.Collection[
            tuple[
                models.TargetResourceKindAwareMixin,  # The target resource
                models.TargetResourceKindAwareMixin
                | None,  # The actual resource
            ]
        ],
    ) -> tp.Collection[models.TargetResourceKindAwareMixin]:
        """Actualize outdated master full hash instance.

        The logic is quite similar to `actualize_outdated_instance_derivatives`.
        But the reason when this method is called is different. The
        `actualize_outdated_instance_derivatives` allows to track changes on the
        data plane but this method allows to track changes on a related master
        instance. For example, the instance model is `Database`, the related master
        for this instance is `NodeSet`. If the `NodeSet` is updated, this method
        is called for all `Database` instances that are related to this `NodeSet`
        to reactualize them.
        This method tracks changes for all fields of the master instance.

        Args:
            instance: The instance to actualize.
            master_instance: The master instance.
            derivatives: All derivatives of the instance.
        """
        return tuple(p[0] for p in derivatives)

    # Internal methods

    def _are_target_resources_equal(
        self,
        resources_left: tp.Collection[models.TargetResource],
        resources_right: tp.Collection[models.TargetResource],
    ) -> bool:
        """Compare two collections of target resources."""
        left_hash = hash(frozenset(r.hash for r in resources_left))
        right_hash = hash(frozenset(r.hash for r in resources_right))
        return left_hash == right_hash

    def _actualize_resource_hash_status(
        self,
        target_resource: models.TargetResource,
        actual_resource: models.Resource,
        active_status: str = ua_c.InstanceStatus.ACTIVE.value,
    ) -> None:
        """Actualize resource hash and status."""
        target_resource.full_hash = actual_resource.full_hash

        # `ACTIVE` only if the hash is the same
        if (
            actual_resource.status == active_status
            and target_resource.hash == actual_resource.hash
        ):
            target_resource.status = actual_resource.status
        elif (
            actual_resource.status != active_status
            and target_resource.status != actual_resource.status
        ):
            target_resource.status = actual_resource.status
        target_resource.update()
        LOG.debug("Outdated resource %s actualized", target_resource.uuid)

    def _actualize_derivative_resources_hash_status(
        self,
        derivatives: tp.Collection[
            tuple[models.TargetResource, models.Resource]
        ],
        active_status: str = ua_c.InstanceStatus.ACTIVE.value,
    ) -> None:
        """Actualize derivative resources hash and status."""
        # Update target derivatives with actual information from the DP.
        for target_derivative, actual_derivative in derivatives:
            self._actualize_resource_hash_status(
                target_derivative,
                actual_derivative,
                active_status,
            )

    def _actualize_derivative_target_resources(
        self,
        new_target_resources: frozenset[models.TargetResource],
        current_target_resources: frozenset[models.TargetResource],
    ) -> tp.Collection[models.TargetResource]:
        """Actualize derivative target resources.

        A new collection of target resources is generated by some reason.
        This method compares the new collection with the current collection
        and actualizes the target resources.

        Returns a collection of actualized target resources.
        """
        # Compare if the resources are the same
        if self._are_target_resources_equal(
            new_target_resources, current_target_resources
        ):
            return current_target_resources

        target_resources = []

        # Create new target resources
        for resource in new_target_resources - current_target_resources:
            resource.insert()
            target_resources.append(resource)
            LOG.debug(
                "New target resource(%s) %s created",
                resource.kind,
                resource.uuid,
            )

        # Delete outdated target resources
        for resource in current_target_resources - new_target_resources:
            resource.delete()
            LOG.debug(
                "Outdated target resource(%s) %s deleted",
                resource.kind,
                resource.uuid,
            )

        # Update target resources
        # FIXME(akremenetsky): Both collections are expected to be small.
        # So we can use nested loop here.
        for new_resource in new_target_resources:
            for current_resource in current_target_resources:
                # The resource has been changed
                # We need to recreate it.
                if (
                    new_resource == current_resource
                    and new_resource.hash != current_resource.hash
                ):
                    current_resource.update_value(new_resource)
                    current_resource.update()
                    target_resources.append(current_resource)
                    LOG.debug(
                        "Target resource(%s) %s recreated",
                        new_resource.kind,
                        new_resource.uuid,
                    )

        return target_resources

    # `Outdated` actualization methods

    def _actualize_outdated_instance(
        self,
        instance: models.InstanceMixin,
        target_resource: models.TargetResource,
        actual_resource: models.Resource,
        active_status: str = ua_c.InstanceStatus.ACTIVE.value,
    ) -> None:
        """Actualize outdated instance.

        It means some changes occurred on the data plane and the instance
        is outdated now. For example, its status is incorrect.
        Usually, this method has to update status and full_hash of the instance.

        Args:
            instance: The instance to actualize.
            target_resource: The target resource of the instance.
            actual_resource: The actual resource of the instance.
        """
        actual_instance = self._instance_model.from_ua_resource(
            actual_resource
        )

        # Hook to actualize instance. For example, for `Password` instance
        # we need to update its value, saved into the secret storage.
        self.actualize_outdated_instance(instance, actual_instance)

        self._actualize_resource_hash_status(
            target_resource,
            actual_resource,
            active_status,
        )

        # Save the instance if some changes occurred.
        instance.save()

        # Commit the tracked_at timestamp
        target_resource.tracked_at = instance.updated_at
        target_resource.status = actual_resource.status
        target_resource.update()

        LOG.info(
            "Instance(%s) resource %s actualized",
            instance.get_resource_kind(),
            target_resource.uuid,
        )

    def _actualize_outdated_instance_derivatives(
        self,
        instance: models.InstanceWithDerivativesMixin,
        target_resource: models.TargetResource,
        actual_resource: models.Resource | None = None,
        changed_derivatives: tp.Collection[
            tuple[models.TargetResource, models.Resource]
        ] = tuple(),
        active_status: str | None = ua_c.InstanceStatus.ACTIVE.value,
    ) -> None:
        """Actualize outdated instance.

        It means some changes occurred on the data plane and the instance
        is outdated now. For example, its status is incorrect. Usually, this
        method has to update status and full_hash of the instance and
        derivatives. This method accepts only changed derivatives.
        So if you need to fetch all derivatives both changed and not changed
        use `actualize_outdated_instance_all_derivatives`.

        Args:
            instance: The instance to actualize.
            target_resource: The target resource of the instance.
            actual_resource: The actual resource of the instance.
            changed_derivatives: The changed derivatives of the instance.
        """
        if len(changed_derivatives) == 0:
            return

        # Convert derivatives to actual models
        derivatives = [
            (
                self._instance_model.derivative_model(t.kind).from_ua_resource(
                    t
                ),
                self._instance_model.derivative_model(a.kind).from_ua_resource(
                    a
                ),
            )
            for t, a in changed_derivatives
        ]

        # Hook to actualize instance.
        # Pay attention. This derivatives collection is only a subset of the
        # derivatives of the instance. It means that some derivatives may
        # be not changed. So all operation below are applied to the subset
        # of derivatives.
        new_derivatives = self.actualize_outdated_instance_derivatives(
            instance, derivatives
        )

        # Actualize hash and status of the target resources
        if actual_resource is not None:
            self._actualize_resource_hash_status(
                target_resource,
                actual_resource,
                active_status,
            )
        self._actualize_derivative_resources_hash_status(changed_derivatives)

        new_target_resources = frozenset(
            d.to_ua_resource(master=target_resource.uuid)
            for d in new_derivatives
        )
        # Actualize derivative target resources if they are changed
        self._actualize_derivative_target_resources(
            new_target_resources, frozenset(d for d, _ in changed_derivatives)
        )

        # Commit the tracked_at timestamp
        instance.update()
        target_resource.tracked_at = instance.updated_at
        target_resource.status = instance.status
        if actual_resource is not None:
            target_resource.full_hash = actual_resource.full_hash
        target_resource.update()

    def _actualize_outdated_instance_all_derivatives(
        self,
        instance: models.InstanceWithDerivativesMixin,
        target_resource: models.TargetResource,
        actual_resource: models.Resource | None = None,
        changed_derivatives: tp.Collection[
            tuple[models.TargetResource, models.Resource]
        ] = tuple(),
        all_derivatives: tp.Collection[
            tuple[models.TargetResource, models.Resource | None]
        ] = tuple(),
        active_status: str | None = ua_c.InstanceStatus.ACTIVE.value,
    ) -> None:
        """Actualize outdated instance.

        It means some changes occurred on the data plane and the instance
        is outdated now. For example, its status is incorrect. Usually, this
        method has to update status and full_hash of the instance and
        derivatives. This method accepts all derivatives both changed and
        not changed. So if you need to fetch only changed derivatives use
        `actualize_outdated_instance_derivatives`.

        Args:
            instance: The instance to actualize.
            target_resource: The target resource of the instance.
            actual_resource: The actual resource of the instance.
            changed_derivatives: The changed derivatives of the instance.
            all_derivatives: The all derivatives of the instance.
        """
        if len(changed_derivatives) == 0:
            return

        # Convert derivatives to actual models
        derivatives = [
            (
                self._instance_model.derivative_model(t.kind).from_ua_resource(
                    t
                ),
                (
                    self._instance_model.derivative_model(
                        a.kind
                    ).from_ua_resource(a)
                    if a is not None
                    else None
                ),
            )
            for t, a in all_derivatives
        ]

        # Hook to actualize instance.
        # Look at the docstring of the method for more details.
        new_derivatives = self.actualize_outdated_instance_derivatives(
            instance, derivatives
        )

        # Actualize hash and status of the target resources
        if actual_resource is not None:
            self._actualize_resource_hash_status(
                target_resource,
                actual_resource,
                active_status,
            )
        self._actualize_derivative_resources_hash_status(changed_derivatives)

        new_target_resources = frozenset(
            d.to_ua_resource(master=target_resource.uuid)
            for d in new_derivatives
        )

        # Actualize derivative target resources if they are changed
        self._actualize_derivative_target_resources(
            new_target_resources, frozenset(d for d, _ in all_derivatives)
        )

        # Commit the tracked_at timestamp
        instance.update()
        target_resource.tracked_at = instance.updated_at
        target_resource.status = getattr(
            instance, "status", ua_c.InstanceStatus.ACTIVE.value
        )
        if actual_resource is not None:
            target_resource.full_hash = actual_resource.full_hash
        target_resource.update()

    def _actualize_new_instance(self, instance: models.InstanceMixin) -> None:
        """Actualize the new PaaS instance."""
        # Perform some additional actions before creating
        # resource and derivatives
        self.pre_create_instance_resource(instance)

        # Create nessary derivatives for the instance
        if self._instance_model._has_model_derivatives():
            derivative_objects = self.create_instance_derivatives(instance)
        else:
            derivative_objects = tuple()

        # Convert instance to resource
        instance_resource = instance.to_ua_resource()
        instance_resource.insert()

        # Save the derivative objects
        derivative_resources = []
        for derivative_object in derivative_objects:
            derivative_resource = derivative_object.to_ua_resource(
                master=instance_resource.uuid
            )
            derivative_resources.append(derivative_resource)
            derivative_resource.save()

        self.post_create_instance_resource(
            instance, instance_resource, derivative_resources
        )
        for derivative_resource in derivative_resources:
            derivative_resource.update()

        instance.save()

        # Commit tracked_at ts
        instance_resource.tracked_at = instance.updated_at
        instance_resource.status = instance.status

        instance_resource.update()

        LOG.info("Instance resource %s created", instance_resource.uuid)

    def _actualize_new_instances(
        self, instances: tp.Collection[models.InstanceMixin] = tuple()
    ) -> None:
        """Actualize new PaaS instances."""
        instances = instances or self._instance_model.get_new_instances()

        if len(instances) == 0:
            return

        # Create resources for new instances
        for instance in instances:
            try:
                self._actualize_new_instance(instance)
            except Exception:
                LOG.exception(
                    "Error creating instance resource %s", instance.uuid
                )

    # `Updated` actualization methods

    def _actualize_updated_instance(
        self,
        instance: models.InstanceMixin,
        resource: models.TargetResource,
        derivatives: tp.Collection[
            tuple[models.TargetResource, models.Resource | None]
        ] = tuple(),
    ) -> None:
        """Actualize updated instance by user."""
        # Perform some additional actions before updating
        # resource and derivatives
        self.pre_update_instance_resource(instance)

        new_resource = instance.to_ua_resource()

        # Update the original resource
        resource.update_value(new_resource)

        # NOTE(akremenetsky): The default implementation of the method
        # `update_instance_derivatives` may be dangerous in cases if the
        # derivatives are changed in live cycle of the instance. For instance,
        # if new derivatives are added after the instance was created, they
        # will be dropped in the default implementation of the method.
        if self._instance_model._has_model_derivatives():
            # Convert derivative resources to actual models
            current_derivatives = tuple(
                (
                    self._instance_model.derivative_model(
                        t.kind
                    ).from_ua_resource(t),
                    (
                        self._instance_model.derivative_model(
                            a.kind
                        ).from_ua_resource(a)
                        if a is not None
                        else None
                    ),
                )
                for t, a in derivatives
            )

            # Create nessary derivatives for the updated instance
            new_derivatives = self.update_instance_derivatives(
                instance, resource, current_derivatives
            )
            new_target_resources = frozenset(
                d.to_ua_resource(master=resource.uuid) for d in new_derivatives
            )

            # Actualize derivative target resources if they are changed
            target_resources = self._actualize_derivative_target_resources(
                new_target_resources, frozenset(d for d, _ in derivatives)
            )
        else:
            target_resources = tuple()

        self.post_update_instance_resource(
            instance, resource, target_resources
        )

        instance.save()

        # Commit the tracked_at timestamp
        resource.tracked_at = instance.updated_at
        resource.status = instance.status
        resource.update()

        LOG.info(
            "Instance(%s) resource %s updated",
            instance.get_resource_kind(),
            resource.uuid,
        )

    def _actualize_updated_instances(self) -> None:
        """Actualize updated instances changed by user."""
        updated_instances = self._instance_model.get_updated_instances()

        if len(updated_instances) == 0:
            return

        instance_resources = models.TargetResource.objects.get_all(
            filters={
                "uuid": dm_filters.In(str(i.uuid) for i in updated_instances),
                "kind": dm_filters.EQ(
                    self._instance_model.get_resource_kind()
                ),
            }
        )

        # Derivatives resources if the model class has derivatives
        if updated_instances[0]._has_model_derivatives():
            resource_derivative_map = self._get_resources_by_masters(
                tuple(r.uuid for r in instance_resources)
            )
        else:
            resource_derivative_map = {}

        resource_map = {i.uuid: i for i in instance_resources}

        # Update every resource in accordance with the new secret
        for instance in updated_instances:
            resource = resource_map[instance.uuid]
            derivatives = resource_derivative_map.get(resource.uuid, tuple())

            try:
                self._actualize_updated_instance(
                    instance, resource, derivatives
                )
            except Exception:
                LOG.exception(
                    "Error updating instance(%s) resource %s",
                    instance.get_resource_kind(),
                    resource.uuid,
                )

    def _get_outdated_instance_resources(
        self,
        limit: int = c.DEF_SQL_LIMIT,
    ) -> dict[
        sys_uuid.UUID,  # Resource UUID
        tuple[models.TargetResource, models.Resource],
    ]:
        kind = self._instance_model.get_resource_kind()
        outdated = models.OutdatedResource.objects.get_all(
            filters={"kind": dm_filters.EQ(kind)},
            limit=limit,
        )
        return {
            pair.target_resource.uuid: (
                pair.target_resource,
                pair.actual_resource,
            )
            for pair in outdated
        }

    def _actualize_outdated_instances_no_derivatives(self) -> None:
        """Actualize outdated instances.

        It means some changes occurred on the data plane and the instances
        are outdated now. For instance, their status is incorrect.

        This method is only used when the model class doesn't have
        derivatives.
        """
        kind = self._instance_model.get_resource_kind()

        # Check if there are outdated instance resources
        resource_map = self._get_outdated_instance_resources()

        if len(resource_map) == 0:
            return

        instances = self._instance_model.objects.get_all(
            filters={
                "uuid": dm_filters.In(str(u) for u in resource_map.keys()),
            },
        )

        # Actualize outdated instances. At least need to check
        # the status and full_hash
        for instance in instances:
            target, actual = resource_map[instance.uuid]
            try:
                self._actualize_outdated_instance(instance, target, actual)
                LOG.debug("Instance(%s) %s actualized", kind, instance.uuid)
            except Exception:
                LOG.exception(
                    "Error actualizing instance(%s) %s", kind, instance.uuid
                )

    def _get_outdated_derivative_resources(
        self,
        limit: int = c.DEF_SQL_LIMIT,
    ) -> dict[
        sys_uuid.UUID,  # Master UUID
        list[tuple[models.TargetResource, models.Resource]],
    ]:
        outdated = models.OutdatedResource.objects.get_all(
            filters={
                "kind": dm_filters.In(self._instance_model.derivative_kinds())
            },
            limit=limit,
        )
        key_map = {}
        for pair in outdated:
            key_map.setdefault(pair.target_resource.master, []).append(
                (pair.target_resource, pair.actual_resource)
            )

        return key_map

    def _get_outdated_instances_by_masters(
        self,
        masters: tp.Collection[sys_uuid.UUID],
    ) -> list[tuple[models.InstanceMixin, models.TargetResource]]:
        kind = self._instance_model.get_resource_kind()
        resources = models.TargetResource.objects.get_all(
            filters={
                "uuid": dm_filters.In(m for m in masters),
                "kind": dm_filters.EQ(kind),
            },
            order_by={"uuid": "asc"},
        )

        instances = self._instance_model.objects.get_all(
            filters={
                "uuid": dm_filters.In(m for m in masters),
            },
            order_by={"uuid": "asc"},
        )

        if len(instances) != len(resources):
            raise RuntimeError("Number of instances and resources not equal")

        return list(zip(instances, resources))

    def _get_resources_by_masters(
        self,
        masters: tp.Collection[sys_uuid.UUID],
    ) -> dict[
        sys_uuid.UUID,  # Master UUID
        list[tuple[models.TargetResource, models.Resource | None]],
    ]:
        kinds = self._instance_model.derivative_kinds()
        target_resources = models.TargetResource.objects.get_all(
            filters={
                "master": dm_filters.In(m for m in masters),
                "kind": dm_filters.In(kinds),
            },
            order_by={"uuid": "asc"},
        )

        # Prepare actual resources map
        actual_resources = {
            (r.uuid, r.kind): r
            for r in models.Resource.objects.get_all(
                filters={
                    "uuid": dm_filters.In(r.uuid for r in target_resources),
                    "kind": dm_filters.In(kinds),
                },
                order_by={"uuid": "asc"},
            )
        }

        # Prepare pairs of target and actual resources
        resource_map = {}
        for target_resource in target_resources:
            actual_resource = actual_resources.get(
                (target_resource.uuid, target_resource.kind)
            )
            resource_map.setdefault(target_resource.master, []).append(
                (target_resource, actual_resource)
            )

        return resource_map

    def _actualize_outdated_instances_have_derivatives(self) -> None:
        """Actualize outdated instances.

        It means some changes occurred on the data plane and the instances
        are outdated now. For instance, their status is incorrect.

        This method is only used when the model class has derivatives.
        For example, `Config` has derivatives `Render`.
        """
        changed_resource_map = self._get_outdated_derivative_resources()

        # Nothing to actualize if no changed resources
        if len(changed_resource_map) == 0:
            return

        need_all = self._instance_model.fetch_all_derivatives_on_outdate()

        # Get all instances related to changed resources
        instances = self._get_outdated_instances_by_masters(
            tuple(changed_resource_map.keys())
        )

        # Also fetch all derivatives if needed
        if need_all:
            all_resource_map = self._get_resources_by_masters(
                tuple(changed_resource_map.keys())
            )

        for instance, resource in instances:
            changed_derivatives = changed_resource_map[resource.uuid]

            try:
                # Actualize instance with all derivatives
                if need_all:
                    all_derivatives = all_resource_map[resource.uuid]
                    self._actualize_outdated_instance_all_derivatives(
                        instance,
                        resource,
                        changed_derivatives=changed_derivatives,
                        all_derivatives=all_derivatives,
                    )
                else:
                    # Actualize instance with only changed derivatives
                    self._actualize_outdated_instance_derivatives(
                        instance,
                        resource,
                        changed_derivatives=changed_derivatives,
                    )
            except Exception:
                LOG.exception(
                    "Error actualizing outdated instance %s", instance.uuid
                )

    def _actualize_outdated_instances(self) -> None:
        """Actualize outdated instances.

        It means some changes occurred on the data plane and the instances
        are outdated now. For instance, their status is incorrect.
        """
        if self._instance_model._has_model_derivatives():
            self._actualize_outdated_instances_have_derivatives()
        else:
            self._actualize_outdated_instances_no_derivatives()

    # `Deleted` actualization methods

    def _actualize_deleted_instances(self) -> None:
        """Actualize deleted instances."""
        deleted_instance_resources = (
            self._instance_model.get_deleted_instances()
        )

        if len(deleted_instance_resources) == 0:
            return

        if self._instance_model._has_model_derivatives():
            derivative_resources = models.TargetResource.objects.get_all(
                filters={
                    "master": dm_filters.In(
                        str(m.uuid) for m in deleted_instance_resources
                    ),
                }
            )
        else:
            derivative_resources = tuple()

        # Delete all outdated resources
        for resource in itertools.chain(
            deleted_instance_resources, derivative_resources
        ):
            try:
                self.pre_delete_instance_resource(resource)
                resource.delete()
                LOG.info(
                    "Outdated resource(%s) %s deleted",
                    resource.kind,
                    resource.uuid,
                )
            except Exception:
                LOG.exception("Error deleting resource %s", resource.uuid)

    # Outdated master hash (full hash) instances

    def _get_outdated_master_hash_resources(
        self,
        limit: int = c.DEF_SQL_LIMIT,
    ) -> tuple[tuple[models.TargetResource, models.TargetResource], ...]:
        kind = self._instance_model.get_resource_kind()
        outdated = models.OutdatedMasterHashResource.objects.get_all(
            filters={"kind": dm_filters.EQ(kind)},
            limit=limit,
        )
        return tuple(
            (
                pair.target_resource,
                pair.master,
            )
            for pair in outdated
        )

    def _get_outdated_master_full_hash_resources(
        self,
        limit: int = c.DEF_SQL_LIMIT,
    ) -> tuple[tuple[models.TargetResource, models.TargetResource], ...]:
        kind = self._instance_model.get_resource_kind()
        outdated = models.OutdatedMasterFullHashResource.objects.get_all(
            filters={"kind": dm_filters.EQ(kind)},
            limit=limit,
        )
        return tuple(
            (
                pair.target_resource,
                pair.master,
            )
            for pair in outdated
        )

    def _actualize_outdated_master_hash_instance(
        self,
        target_resource: models.TargetResource,
        master: models.TargetResource,
        derivatives: tp.Collection[
            tuple[models.TargetResource, models.Resource | None]
        ],
        tracked_field: tp.Literal["hash", "full_hash"] = "hash",
    ) -> None:
        """Actualize outdated master hash instance."""
        instance = self._instance_model.from_ua_resource(target_resource)

        if self._instance_model.__master_model__ is None:
            raise ValueError("The master model is not initialized.")

        master_instance = (
            self._instance_model.__master_model__.from_ua_resource(master)
        )

        converted_derivatives = [
            (
                self._instance_model.derivative_model(t.kind).from_ua_resource(
                    t
                ),
                (
                    self._instance_model.derivative_model(
                        a.kind
                    ).from_ua_resource(a)
                    if a is not None
                    else None
                ),
            )
            for t, a in derivatives
        ]

        # Hook to actualize instance.
        # Look at the docstring of the method for more details.
        if tracked_field == "hash":
            new_derivatives = self.actualize_outdated_master_hash_instance(
                instance, master_instance, converted_derivatives
            )
        else:
            new_derivatives = (
                self.actualize_outdated_master_full_hash_instance(
                    instance, master_instance, converted_derivatives
                )
            )

        new_target_resources = frozenset(
            d.to_ua_resource(master=target_resource.uuid)
            for d in new_derivatives
        )

        # Actualize derivative target resources if they are changed
        self._actualize_derivative_target_resources(
            new_target_resources, frozenset(d for d, _ in derivatives)
        )

        # Commit the master hash
        if tracked_field == "hash":
            target_resource.master_hash = master.hash
        else:
            target_resource.master_full_hash = master.full_hash
        target_resource.save()

    def _actualize_outdated_master_instances(
        self,
        resources: tuple[
            tuple[models.TargetResource, models.TargetResource], ...
        ],
        tracked_field: tp.Literal["hash", "full_hash"] = "hash",
    ) -> None:
        """Actualize outdated master hash instances.

        Track changes for the related master instances.
        Look at `actualize_outdated_master_hash_instance` for more details.
        """
        if len(resources) == 0:
            return

        # Get all derivatives related to the instances.
        # We need to be clear here. Masters for this call are instances
        # (resources) and not masters of the instances.
        # For example, our instance model is `Database`. The master of the
        # instance is `NodeSet` but for the call we pass `Database` as
        # master to get their derivatives and not derivatives of the
        # `NodeSet`.
        derivative_map = self._get_resources_by_masters(
            tuple(r.uuid for r, _ in resources)
        )

        for target_resource, master in resources:
            derivatives = derivative_map[target_resource.uuid]
            try:
                self._actualize_outdated_master_hash_instance(
                    target_resource,
                    master,
                    derivatives=derivatives,
                    tracked_field=tracked_field,
                )
            except Exception:
                LOG.exception(
                    "Error actualizing outdated master hash instance %s",
                    target_resource.uuid,
                )

    def _actualize_outdated_master_hash_instances(self) -> None:
        """Actualize outdated master hash instances."""

        resources = self._get_outdated_master_hash_resources()
        self._actualize_outdated_master_instances(
            resources, tracked_field="hash"
        )

    def _actualize_outdated_master_full_hash_instances(self) -> None:
        """Actualize outdated master full hash instances."""

        resources = self._get_outdated_master_full_hash_resources()
        self._actualize_outdated_master_instances(
            resources, tracked_field="full_hash"
        )

    # Misc methods

    def _iteration(self) -> None:
        with contexts.Context().session_manager():
            try:
                self._actualize_new_instances()
            except Exception:
                LOG.exception("Error actualizing new instances")

            try:
                self._actualize_deleted_instances()
            except Exception:
                LOG.exception("Error actualizing deleted instances")

            try:
                self._actualize_updated_instances()
            except Exception:
                LOG.exception("Error actualizing updated instances")

            try:
                self._actualize_outdated_instances()
            except Exception:
                LOG.exception("Error actualizing outdated instances")

            if self.track_outdated_master_hash_instances():
                try:
                    self._actualize_outdated_master_hash_instances()
                except Exception:
                    LOG.exception(
                        "Error actualizing outdated master hash instances"
                    )

            if self.track_outdated_master_full_hash_instances():
                try:
                    self._actualize_outdated_master_full_hash_instances()
                except Exception:
                    LOG.exception(
                        "Error actualizing outdated master full hash instances"
                    )
