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
#    Unless reqtrackeded by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from restalchemy.storage.sql import migrations


class MigrationStep(migrations.AbstractMigrationStep):

    def __init__(self):
        self._depends = ["0003-ua-addtional-hashes-6e9ca8.py"]

    @property
    def migration_id(self):
        return "e9a81187-e61d-4dc6-80fc-becc22c0e897"

    @property
    def is_manual(self):
        return False

    def upgrade(self, session):
        sql_expressions = [
            # TABLE
            """
            CREATE TABLE IF NOT EXISTS ua_tracked_resources (
                "uuid" UUID NOT NULL PRIMARY KEY,
                "watcher" UUID references ua_target_resources(res_uuid) ON DELETE CASCADE,
                "target" UUID references ua_target_resources(res_uuid) ON DELETE CASCADE,
                "watcher_kind" varchar(64) NOT NULL,
                "target_kind" varchar(64) NOT NULL,
                "tracked_at" timestamp NOT NULL DEFAULT current_timestamp,
                "created_at" timestamp NOT NULL DEFAULT current_timestamp,
                "updated_at" timestamp NOT NULL DEFAULT current_timestamp,
                UNIQUE (watcher, target)
            );
            """,
            # INDEXES
            """
            CREATE INDEX IF NOT EXISTS ua_tracked_resources_watcher_idx
                ON ua_tracked_resources (watcher, watcher_kind);
            """,
            """
            CREATE INDEX IF NOT EXISTS ua_tracked_resources_target_idx
                ON ua_tracked_resources (target, target_kind);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_ua_tracked_target_tracked_at
                ON ua_tracked_resources(target, tracked_at);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_ua_target_res_uuid_updated_at
                ON ua_target_resources(res_uuid, updated_at);
            """,
            # VIEWS
            """
            CREATE OR REPLACE VIEW ua_outdated_tracked_resources_view AS
                SELECT
                    tracked.uuid as uuid,
                    tracked.uuid as tracked_resource,
                    tracked.watcher_kind as watcher_kind,
                    tracked.tracked_at as tracked_at,
                    utr.updated_at as target_updated_at
                FROM ua_tracked_resources tracked
                JOIN ua_target_resources utr ON
                    tracked.target = utr.res_uuid
                WHERE tracked.tracked_at != utr.updated_at;
            """,
            """
            CREATE OR REPLACE VIEW ua_resource_pair_view AS
                SELECT
                    utr.uuid as uuid,
                    utr.kind as kind,
                    utr.res_uuid as res_uuid,
                    utr.res_uuid as target_resource,
                    uar.res_uuid as actual_resource
                FROM ua_target_resources utr
                LEFT JOIN ua_actual_resources uar ON
                    utr.res_uuid = uar.res_uuid;
            """,
            """
            CREATE OR REPLACE VIEW ua_outdated_resources_view AS
                SELECT
                    ua_target_resources.uuid as uuid,
                    ua_target_resources.kind as kind,
                    ua_target_resources.res_uuid as target_resource,
                    ua_actual_resources.res_uuid as actual_resource
                FROM ua_target_resources INNER JOIN ua_actual_resources ON 
                    ua_target_resources.res_uuid = ua_actual_resources.res_uuid
                WHERE ua_target_resources.full_hash != ua_actual_resources.full_hash;
            """,
        ]

        for expr in sql_expressions:
            session.execute(expr, None)

    def downgrade(self, session):
        sql_expressions = [
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

        views = [
            "ua_outdated_tracked_resources_view",
            "ua_resource_pair_view",
        ]

        for expr in sql_expressions:
            session.execute(expr, None)

        for view_name in views:
            self._delete_view_if_exists(session, view_name)

        self._delete_table_if_exists(session, "ua_tracked_resources")


migration_step = MigrationStep()
