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

import logging
import typing as tp

from gcl_looper.services import basic


LOG = logging.getLogger(__name__)


class GService(basic.BasicService):

    def __init__(
        self,
        services: tp.Collection[basic.BasicService],
        iter_min_period: float = 1,
        iter_pause: float = 0.1,
    ):
        super().__init__(iter_min_period, iter_pause)
        self._services = services

    def _setup(self):
        LOG.info("Setup all services")
        for service in self._services:
            service._setup()

    def _iteration(self):
        # Iterate all services
        for service in self._services:
            service._loop_iteration()
