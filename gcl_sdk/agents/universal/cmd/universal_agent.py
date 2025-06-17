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
import sys
import typing as tp
import configparser

import bazooka
from oslo_config import cfg

from gcl_sdk.common import config
from gcl_sdk.common import log as infra_log
from gcl_sdk.common import utils
from gcl_sdk.agents.universal.clients.http import orch
from gcl_sdk.agents.universal.clients.http import status
from gcl_sdk.agents.universal.services import agent
from gcl_sdk.agents.universal.drivers import base as driver_base
from gcl_sdk.agents.universal import constants as c


DOMAIN = "universal_agent"


core_agent_opts = [
    cfg.StrOpt(
        "orch_endpoint",
        default="http://localhost:11011",
        help="Endpoint of Genesis Core Orch API",
    ),
    cfg.StrOpt(
        "status_endpoint",
        default="http://localhost:11011",
        help="Endpoint of Genesis Core Status API",
    ),
    cfg.ListOpt(
        "caps_drivers",
        default=None,
        help="List of agent capability drivers",
    ),
    cfg.ListOpt(
        "facts_drivers",
        default=None,
        help="List of agent facts drivers",
    ),
]

CONF = cfg.CONF
CONF.register_cli_opts(core_agent_opts, DOMAIN)


def load_driver(
    class_: tp.Type[
        driver_base.AbstractCapabilityDriver | driver_base.AbstractFactDriver
    ],
) -> driver_base.AbstractCapabilityDriver | driver_base.AbstractFactDriver:
    parser = configparser.ConfigParser()
    parser.read(cfg.CONF.config_file)

    if not parser.has_section(class_.__name__):
        return class_()

    params = {}
    for option in parser.options(class_.__name__):
        if option in parser.defaults():
            continue

        params[option] = parser.get(class_.__name__, option)

    return class_(**params)


def main():
    # Parse config
    config.parse(sys.argv[1:])

    # Configure logging
    infra_log.configure()
    log = logging.getLogger(__name__)

    # Prepare clients
    http_client = bazooka.Client(default_timeout=20)
    orch_api = orch.OrchAPI(
        CONF[DOMAIN].orch_endpoint,
        http_client=http_client,
    )
    status_api = status.StatusAPI(
        CONF[DOMAIN].status_endpoint,
        http_client=http_client,
    )

    # Load drivers from entry points
    caps_drivers = []
    facts_drivers = []

    capabilities = set()
    facts = set()

    # Load capability drivers
    for driver_name in CONF[DOMAIN].caps_drivers or tuple():
        driver_class = utils.load_from_entry_point(
            c.EP_UNIVERSAL_AGENT, driver_name
        )
        driver = load_driver(driver_class)

        # Check for duplicate capabilities
        driver_capabilities = driver.get_capabilities()
        if set(driver_capabilities) & capabilities:
            raise ValueError(
                f"Driver {driver_name} has duplicate capabilities"
            )
        capabilities |= set(driver_capabilities)

        caps_drivers.append(driver)
        log.info("Loaded driver: %s", driver_name)

    # Load fact drivers
    for driver_name in CONF[DOMAIN].facts_drivers or tuple():
        driver_class = utils.load_from_entry_point(
            c.EP_UNIVERSAL_AGENT, driver_name
        )
        driver = load_driver(driver_class)

        # Check for duplicate capabilities
        driver_facts = driver.get_facts()
        if set(driver_facts) & facts:
            raise ValueError(f"Driver {driver_name} has duplicate facts")
        facts |= set(driver_facts)

        facts_drivers.append(driver)
        log.info("Loaded driver: %s", driver_name)

    service = agent.UniversalAgentService(
        orch_api=orch_api,
        status_api=status_api,
        caps_drivers=caps_drivers,
        facts_drivers=facts_drivers,
        iter_min_period=3,
    )

    service.start()

    log.info("Bye!!!")


if __name__ == "__main__":
    main()
