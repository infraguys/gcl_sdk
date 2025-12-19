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
                "hash" varchar(256) NOT NULL DEFAULT '',
                "full_hash" varchar(256) NOT NULL DEFAULT '',
                "created_at" timestamp NOT NULL DEFAULT current_timestamp,
                "updated_at" timestamp NOT NULL DEFAULT current_timestamp
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
            # VIEWS
            # """
            # CREATE OR REPLACE VIEW ua_outdated_tracked_hash_instances_view AS
            #     SELECT
            #         tracked.uuid as uuid,
            #         tracked.watcher as watcher,
            #         tracked.target as target,
            #         tracked.target_kind as target_kind,
            #         tracked.watcher_kind as watcher_kind,
            #         tracked.hash as hash
            #     FROM ua_tracked_resources tracked
            #     JOIN ua_target_resources utr ON
            #         tracked.target = utr.res_uuid AND tracked.target_kind = utr.kind
            #     WHERE tracked.hash != utr.hash;
            # """,
            """
            CREATE OR REPLACE VIEW ua_outdated_tracked_full_hash_instances_view AS
                SELECT
                    tracked.uuid as uuid,
                    tracked.uuid as tracked_resource,
                    tracked.watcher_kind as watcher_kind,
                    tracked.full_hash as full_hash,
                    utr.full_hash as actual_full_hash,
                    uar.uuid as actual_resource
                FROM ua_tracked_resources tracked
                JOIN ua_target_resources utr ON
                    tracked.target = utr.res_uuid
                LEFT JOIN ua_actual_resources uar ON
                    tracked.target = uar.res_uuid
                WHERE tracked.full_hash != utr.full_hash;
            """,
        ]

        for expr in sql_expressions:
            session.execute(expr, None)

    def downgrade(self, session):
        views = [
            # "ua_outdated_tracked_hash_instances_view",
            "ua_outdated_tracked_full_hash_instances_view",
        ]
        for view_name in views:
            self._delete_view_if_exists(session, view_name)

        self._delete_table_if_exists(session, "ua_tracked_resources")


migration_step = MigrationStep()
