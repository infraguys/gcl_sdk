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

from gcl_sdk.agents.universal.dm import models as ua_models
from gcl_sdk.agents.universal.services import builder


LOG = logging.getLogger(__name__)


class InfraResourcePair(tp.NamedTuple):
    target: ua_models.TargetResourceKindAwareMixin
    actual: ua_models.TargetResourceKindAwareMixin | None


class InfraCollection(tp.NamedTuple):
    infra_objects: tp.Collection[InfraResourcePair]

    def targets(self) -> tuple[ua_models.TargetResourceKindAwareMixin, ...]:
        return tuple(p.target for p in self.infra_objects)

    def actuals(self) -> tuple[ua_models.TargetResourceKindAwareMixin, ...]:
        return tuple(p.actual for p in self.infra_objects)


class CoreInfraBuilder(builder.UniversalBuilderService):

    def create_infra(
        self, instance: ua_models.InstanceWithDerivativesMixin
    ) -> tp.Collection[ua_models.TargetResourceKindAwareMixin]:
        """Create a list of infrastructure objects.

        The method returns a list of infrastructure objects that are required
        for the instance. For example, nodes, sets, configs, etc.
        """
        raise NotImplementedError

    def actualize_infra(
        self,
        instance: ua_models.InstanceWithDerivativesMixin,
        infra: InfraCollection,
    ) -> tp.Collection[ua_models.TargetResourceKindAwareMixin]:
        """Actualize the infrastructure objects.

        The method is called when the instance is outdated. For example,
        the instance `Config` has derivative `Render`. Single `Config` may
        have multiple `Render` derivatives. If any of the derivatives is
        outdated, this method is called to reactualize this infrastructure.

        Args:
            instance: The instance to actualize.
            infra: The infrastructure objects.
        """
        return infra.targets()

    def create_instance_derivatives(
        self, instance: ua_models.InstanceWithDerivativesMixin
    ) -> tp.Collection[ua_models.TargetResourceKindAwareMixin]:
        """Create the instance.

        The result is an iterable object of derivative objects that are
        required for the instance. For example, the main instance is a
        `Config` so the derivative objects for the the config is a list
        of `Render`. The result is a tuple/list/set/... of render objects.
        The derivative objects should inherit from the `TargetResourceMixin`.
        """
        return self.create_infra(instance)

    def update_instance_derivatives(
        self,
        instance: ua_models.InstanceWithDerivativesMixin,
        resource: ua_models.TargetResourceKindAwareMixin,
        derivative_pairs: tp.Collection[
            tuple[
                ua_models.TargetResourceKindAwareMixin,  # The target resource
                ua_models.TargetResourceKindAwareMixin
                | None,  # The actual resource
            ]
        ],
    ) -> tp.Collection[ua_models.TargetResourceKindAwareMixin]:
        """The hook to update instance derivatives.

        The hook is called when an initiator of updating is an user or
        software from control plane side.
        The default behavior is to send the same list as on instance creation.
        """
        infra_collection = InfraCollection(
            infra_objects=tuple(
                InfraResourcePair(*p) for p in derivative_pairs
            ),
        )

        return self.actualize_infra(instance, infra_collection)

    def actualize_outdated_instance_derivatives(
        self,
        instance: ua_models.InstanceMixin,
        derivative_pairs: tp.Collection[
            tuple[
                ua_models.TargetResourceKindAwareMixin,  # The target resource
                ua_models.TargetResourceKindAwareMixin
                | None,  # The actual resource
            ]
        ],
    ) -> tp.Collection[ua_models.TargetResourceKindAwareMixin]:
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
        infra_collection = InfraCollection(
            infra_objects=tuple(
                InfraResourcePair(*p) for p in derivative_pairs
            ),
        )

        return self.actualize_infra(instance, infra_collection)
