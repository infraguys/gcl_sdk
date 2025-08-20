from restalchemy.api import routes

from gcl_sdk.audit.api import controllers


class AuditRoute(routes.Route):
    __controller__ = controllers.AuditController
    __allow_methods__ = [routes.GET, routes.FILTER]
