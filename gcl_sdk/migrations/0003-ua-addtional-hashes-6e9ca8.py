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
from restalchemy.storage.sql import migrations


class MigrationStep(migrations.AbstarctMigrationStep):

    def __init__(self):
        self._depends = ["0002-init-auditlog-table-c6f740.py"]

    @property
    def migration_id(self):
        return "6e9ca843-3268-4449-a507-76258f43c53f"

    @property
    def is_manual(self):
        return False

    def upgrade(self, session):
        sql_expressions = [
            """
            ALTER TABLE ua_target_resources
                ADD COLUMN master_hash varchar(256) NOT NULL DEFAULT '';
            """,
            """
            ALTER TABLE ua_target_resources
                ADD COLUMN master_full_hash varchar(256) NOT NULL DEFAULT '';
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_target_resources_hash_idx
                ON ua_target_resources (hash);
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_target_resources_full_hash_idx
                ON ua_target_resources (full_hash);
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_target_resources_master_hash_idx
                ON ua_target_resources (master_hash);
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_target_resources_master_full_hash_idx
                ON ua_target_resources (master_full_hash);
            """,
            """
            CREATE OR REPLACE VIEW ua_outdated_master_hash_resources_view AS
                SELECT
                    ua_target_resources.uuid as uuid,
                    ua_target_resources.kind as kind,
                    ua_target_resources.res_uuid as target_resource,
                    masters.res_uuid as master
                FROM ua_target_resources JOIN ua_target_resources as masters ON 
                    ua_target_resources.master = masters.uuid
                WHERE ua_target_resources.master_hash != masters.hash AND
                    ua_target_resources.kind != masters.kind;
            """,
            """
            CREATE OR REPLACE VIEW ua_outdated_master_full_hash_resources_view AS
                SELECT
                    ua_target_resources.uuid as uuid,
                    ua_target_resources.kind as kind,
                    ua_target_resources.res_uuid as target_resource,
                    masters.res_uuid as master
                FROM ua_target_resources JOIN ua_target_resources as masters ON 
                    ua_target_resources.master = masters.uuid
                WHERE ua_target_resources.master_full_hash != masters.full_hash AND
                    ua_target_resources.kind != masters.kind;
            """,
        ]

        for expr in sql_expressions:
            session.execute(expr, None)

    def downgrade(self, session):
        sql_types = [
            "ALTER TABLE ua_target_resources DROP COLUMN IF EXISTS master_hash;",
            "ALTER TABLE ua_target_resources DROP COLUMN IF EXISTS master_full_hash;",
            "DROP INDEX IF EXISTS ua_target_resources_hash_idx;",
            "DROP INDEX IF EXISTS ua_target_resources_full_hash_idx;",
            "DROP INDEX IF EXISTS ua_target_resources_master_hash_idx;",
            "DROP INDEX IF EXISTS ua_target_resources_master_full_hash_idx;",
        ]

        views = [
            "ua_outdated_master_hash_resources_view",
            "ua_outdated_master_full_hash_resources_view",
        ]

        for view_name in views:
            self._delete_view_if_exists(session, view_name)

        for expr in sql_types:
            session.execute(expr, None)


migration_step = MigrationStep()
