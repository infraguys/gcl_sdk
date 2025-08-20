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

import uuid as sys_uuid

import pytest

from restalchemy.dm import models as ra_models
from restalchemy.dm import properties
from restalchemy.dm import types as ra_types
from restalchemy.api import applications
from restalchemy.api import middlewares
from restalchemy.api import controllers
from restalchemy.api import routes
from restalchemy.api.middlewares import contexts as context_mw
from restalchemy.api.middlewares import logging as logging_mw
from restalchemy.api.middlewares import errors as errors_mw
from restalchemy.openapi import structures as openapi_structures
from restalchemy.openapi import engines as openapi_engines

from gcl_sdk.agents.universal.dm import models
from gcl_sdk.agents.universal.orch_api import routes as orch_routes
from gcl_sdk.agents.universal.status_api import routes as status_routes
from gcl_sdk.audit.api import routes as audit_routes

FIRST_MIGRATION = "0000-init-events-table-2cfd220e.py"


class FooResource(ra_models.ModelWithUUID, models.ResourceMixin):
    name = properties.property(
        ra_types.String(max_length=64), default="foo-name"
    )
    project_id = properties.property(
        ra_types.UUID(), default=lambda: sys_uuid.uuid4()
    )


class FooTargetResource(ra_models.ModelWithUUID, models.TargetResourceMixin):
    name = properties.property(
        ra_types.String(max_length=64), default="foo-name"
    )
    project_id = properties.property(
        ra_types.UUID(), default=lambda: sys_uuid.uuid4()
    )


def get_openapi_engine():
    openapi_engine = openapi_engines.OpenApiEngine(
        info=openapi_structures.OpenApiInfo(
            title="Test API",
            version="v1",
            description="OpenAPI - Test API",
        ),
        paths=openapi_structures.OpenApiPaths(),
        components=openapi_structures.OpenApiComponents(),
    )
    return openapi_engine


@pytest.fixture(scope="module")
def orch_api_wsgi_app():
    class OrchApiApp(routes.RootRoute):
        pass

    class ApiEndpointController(controllers.RoutesListController):
        __TARGET_PATH__ = "/v1/"

    class ApiEndpointRoute(routes.Route):
        __controller__ = ApiEndpointController
        __allow_methods__ = [routes.FILTER]

        agents = routes.route(orch_routes.UniversalAgentsRoute)

    setattr(
        OrchApiApp,
        "v1",
        routes.route(ApiEndpointRoute),
    )

    return middlewares.attach_middlewares(
        applications.OpenApiApplication(
            route_class=OrchApiApp,
            openapi_engine=get_openapi_engine(),
        ),
        [
            context_mw.ContextMiddleware,
            errors_mw.ErrorsHandlerMiddleware,
            logging_mw.LoggingMiddleware,
        ],
    )


@pytest.fixture(scope="module")
def status_api_wsgi_app():
    class StatusApiApp(routes.RootRoute):
        pass

    class ApiEndpointController(controllers.RoutesListController):
        __TARGET_PATH__ = "/v1/"

    class ApiEndpointRoute(routes.Route):
        __controller__ = ApiEndpointController
        __allow_methods__ = [routes.FILTER]

        agents = routes.route(status_routes.UniversalAgentsRoute)
        kind = routes.route(status_routes.KindRoute)

    setattr(
        StatusApiApp,
        "v1",
        routes.route(ApiEndpointRoute),
    )

    return middlewares.attach_middlewares(
        applications.OpenApiApplication(
            route_class=StatusApiApp,
            openapi_engine=get_openapi_engine(),
        ),
        [
            context_mw.ContextMiddleware,
            errors_mw.ErrorsHandlerMiddleware,
            logging_mw.LoggingMiddleware,
        ],
    )


@pytest.fixture(scope="module")
def audit_api_wsgi_app():
    class AuditApiApp(routes.RootRoute):
        pass

    class ApiEndpointController(controllers.RoutesListController):
        __TARGET_PATH__ = "/v1/"

    class ApiEndpointRoute(routes.Route):
        __controller__ = ApiEndpointController
        __allow_methods__ = [routes.FILTER]

        audit = routes.route(audit_routes.AuditRoute)

    setattr(
        AuditApiApp,
        "v1",
        routes.route(ApiEndpointRoute),
    )

    return middlewares.attach_middlewares(
        applications.OpenApiApplication(
            route_class=AuditApiApp,
            openapi_engine=get_openapi_engine(),
        ),
        [
            context_mw.ContextMiddleware,
            errors_mw.ErrorsHandlerMiddleware,
            logging_mw.LoggingMiddleware,
        ],
    )
