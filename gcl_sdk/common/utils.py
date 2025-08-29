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

import os
import logging
import typing as tp
import importlib_metadata

from restalchemy.storage.sql import migrations

LOG = logging.getLogger(__name__)

EVENT_PAYLOADS_GROUP = "gcl_sdk_event_payloads"


def load_event_payload_map() -> dict:
    event_payload_map = {
        ep.name: ep.load()
        for ep in importlib_metadata.entry_points(
            group=EVENT_PAYLOADS_GROUP,
        )
    }
    return event_payload_map


def load_from_entry_point(group: str, name: str) -> tp.Any:
    """Load class from entry points."""
    for ep in importlib_metadata.entry_points(group=group):
        if ep.name == name:
            return ep.load()

    raise RuntimeError(f"No class '{name}' found in entry points {group}")


class MigrationEngine(migrations.MigrationEngine):
    """
    Helper for apply library migration from another project.
    Used from the migration file. Example:

    from gcl_sdk.common.utils import MigrationEngine
    from gcl_sdk import migrations as sdk_migrations

    SDK_MIGRATION_FILE_NAME = "0002-init-auditlog-table-c6f740.py"

    class MigrationStep(migrations.AbstarctMigrationStep):
    ...
    def upgrade(self, session):
        migration_engine = MigrationEngine._get_migration_engine(sdk_migrations)
        migration_engine.apply_migration(SDK_MIGRATION_FILE_NAME, session)

    def downgrade(self, session)
        migration_engine = MigrationEngine._get_migration_engine(sdk_migrations)
        migration_engine.rollback_migration(SDK_MIGRATION_FILE_NAME, session)
    """

    @classmethod
    def _get_migration_engine(cls, migrations_module):
        migration_path = os.path.dirname(migrations_module.__file__)
        return cls(migrations_path=migration_path)

    def apply_migration(self, migration_name, session):
        filename = self.get_file_name(migration_name)
        self._init_migration_table(session)
        migrations = self._load_migration_controllers(session)

        migration = migrations[filename]
        if migration.is_applied():
            LOG.warning("Migration '%s' is already applied", migration.name)
        else:
            LOG.info("Applying migration '%s'", migration.name)
            migrations[filename].apply(session, migrations)

    def rollback_migration(self, migration_name, session):
        filename = self.get_file_name(migration_name)
        self._init_migration_table(session)
        migrations = self._load_migration_controllers(session)
        migration = migrations[filename]
        if not migration.is_applied():
            LOG.warning("Migration '%s' is not applied", migration.name)
        else:
            LOG.info("Rolling back migration '%s'", migration.name)
            migrations[filename].rollback(session, migrations)
