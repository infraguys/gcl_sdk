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
        self._depends = ["0000-init-events-table-2cfd220e.py"]

    @property
    def migration_id(self):
        return "391c09b0-9093-4a82-a310-34e2b65bf6c7"

    @property
    def is_manual(self):
        return False

    def upgrade(self, session):
        sql_expressions = [
            # TABLES
            """
            DROP TYPE IF EXISTS enum_agent_status;
            CREATE TYPE "enum_agent_status" AS ENUM (
                'NEW',
                'ACTIVE',
                'ERROR',
                'DISABLED'
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS ua_agents (
                "uuid" UUID NOT NULL PRIMARY KEY,
                "name" varchar(255) NOT NULL,
                "description" varchar(255) NOT NULL,
                "capabilities" JSONB NOT NULL,
                "facts" JSONB NOT NULL,
                "node" UUID NOT NULL,
                "status" enum_agent_status NOT NULL DEFAULT 'NEW',
                "created_at" timestamp NOT NULL DEFAULT current_timestamp,
                "updated_at" timestamp NOT NULL DEFAULT current_timestamp
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_agents_node_idx
                ON ua_agents (node);
            """,
            """
            CREATE TABLE IF NOT EXISTS ua_actual_resources (
                "uuid" UUID NOT NULL,
                "kind" varchar(64) NOT NULL,
                "res_uuid" UUID NOT NULL PRIMARY KEY,
                "value" JSONB NOT NULL,
                "status" varchar(32) NOT NULL,
                "node" UUID DEFAULT NULL,
                "hash" varchar(256) NOT NULL,
                "full_hash" varchar(256) NOT NULL,
                "created_at" timestamp NOT NULL DEFAULT current_timestamp,
                "updated_at" timestamp NOT NULL DEFAULT current_timestamp,
                UNIQUE (uuid, kind)
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_actual_resources_node_id_idx
                ON ua_actual_resources (node);
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_actual_resources_kind_id_idx
                ON ua_actual_resources (kind);
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_actual_resources_full_hash_id_idx
                ON ua_actual_resources (full_hash);
            """,
            """
            CREATE TABLE IF NOT EXISTS ua_target_resources (
                "uuid" UUID NOT NULL,
                "kind" varchar(64) NOT NULL,
                "res_uuid" UUID NOT NULL PRIMARY KEY,
                "value" JSONB NOT NULL,
                "status" varchar(32) NOT NULL DEFAULT 'ACTIVE',
                "hash" varchar(256) NOT NULL,
                "full_hash" varchar(256) NOT NULL,
                "node" UUID DEFAULT NULL,
                "agent" UUID references ua_agents(uuid) ON DELETE CASCADE,
                "master" UUID DEFAULT NULL,
                "tracked_at" timestamp NOT NULL DEFAULT current_timestamp,
                "created_at" timestamp NOT NULL DEFAULT current_timestamp,
                "updated_at" timestamp NOT NULL DEFAULT current_timestamp,
                UNIQUE (uuid, kind)
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_target_resources_agent_id_idx
                ON ua_target_resources (agent);
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_target_resources_master_id_idx
                ON ua_target_resources (master);
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_target_resources_kind_id_idx
                ON ua_target_resources (kind);
            """,
            """
            CREATE OR REPLACE VIEW ua_outdated_resources_view AS
                SELECT
                    ua_target_resources.uuid as uuid,
                    ua_target_resources.kind as kind,
                    ua_target_resources.res_uuid as target_resource,
                    ua_actual_resources.res_uuid as actual_resource
                FROM ua_target_resources INNER JOIN ua_actual_resources ON 
                    ua_target_resources.uuid = ua_actual_resources.uuid
                WHERE ua_target_resources.full_hash != ua_actual_resources.full_hash;
            """,
        ]

        for expr in sql_expressions:
            session.execute(expr, None)

    def downgrade(self, session):
        sql_types = [
            """
            DROP TYPE IF EXISTS enum_agent_status;
            """,
        ]

        tables = [
            "ua_actual_resources",
            "ua_target_resources",
            "ua_agents",
        ]

        views = [
            "ua_outdated_resources_view",
        ]

        for view_name in views:
            self._delete_view_if_exists(session, view_name)

        for table_name in tables:
            self._delete_table_if_exists(session, table_name)

        for expr in sql_types:
            session.execute(expr, None)


migration_step = MigrationStep()
