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

import sys
import logging
import collections
import typing as tp

from oslo_config import cfg
from oslo_config import types as oslo_types
from restalchemy.common import config_opts as ra_config_opts
from restalchemy.storage.sql import engines
from restalchemy.common import constants as ra_constants

from gcl_sdk.common import utils
from gcl_sdk.common import constants as c
from gcl_sdk.common import log as common_log
from gcl_sdk.common.services import gservice
from gcl_sdk.agents.universal import utils as ua_utils
from gcl_sdk import version


DOMAIN = "gservice"

LOG = logging.getLogger(__name__)


svc_opts = [
    cfg.ListOpt(
        "services",
        default=tuple(),
        help=(
            "List of services to run. The service can be in two formats: "
            "1. <module>:<class> "
            "2. <class>, available loaded from the entry point."
        ),
    ),
    cfg.ListOpt(
        "disable_auto_opts",
        default=tuple(),
        item_type=oslo_types.String,
        help=(
            "List of services to disable auto options loading. "
            "The format is like for the `services` option."
        ),
    ),
    cfg.FloatOpt(
        "iter_min_period",
        default=3,
        help="Minimum period between iterations",
    ),
    cfg.FloatOpt(
        "iter_pause",
        default=0.1,
        help="Pause between iterations",
    ),
]

GCONF = cfg.ConfigOpts()
ra_config_opts.register_posgresql_db_opts(GCONF)
GCONF.register_cli_opts(svc_opts, DOMAIN)


def load_config(
    args: list[str], conf: cfg.ConfigOpts | None = None
) -> cfg.ConfigOpts:
    if conf is None:
        conf = cfg.ConfigOpts()

    conf(
        args=args,
        project=c.GLOBAL_SERVICE_NAME,
        version=f"{c.GLOBAL_SERVICE_NAME.capitalize()} {version.version_info}",
    )
    if not conf.config_file:
        raise FileNotFoundError("Configuration file is not set")

    return conf


def main():
    # Parse config
    gconf = load_config(sys.argv[1:], GCONF)

    # Load DB engine if the corresponding section is present
    if ra_constants.DB_CONFIG_SECTION in gconf:
        engines.engine_factory.configure_postgresql_factory(gconf)

    # Load service classes
    svc_classes = []
    services = []
    for svc in gconf[DOMAIN].services:
        try:
            svc_class = ua_utils.cfg_load_class(svc)
        except ValueError:
            svc_class = utils.load_from_entry_point(c.EP_GC_SERVICES, svc)

        # Allow to load configuration manually for the service
        if svc in gconf[DOMAIN].disable_auto_opts:
            services.append(svc_class.svc_from_config(gconf.config_file))
            continue

        # Register service options
        if opts := svc_class.get_svc_config_opts():
            cfg.CONF.register_cli_opts(opts, svc)
            svc_classes.append((svc, svc_class))
        else:
            services.append(svc_class())

    # Parse config
    load_config(sys.argv[1:], cfg.CONF)

    # Configure logging
    common_log.configure()
    LOG = logging.getLogger(__name__)

    # Load services
    for svc_name, svc_class in svc_classes:
        svc = svc_class(**cfg.CONF[svc_name])
        services.append(svc)

    # Create global service
    service = gservice.GService(
        services=services,
        iter_min_period=gconf[DOMAIN].iter_min_period,
        iter_pause=gconf[DOMAIN].iter_pause,
    )

    service.start()

    LOG.info("Bye!!!")


if __name__ == "__main__":
    main()
