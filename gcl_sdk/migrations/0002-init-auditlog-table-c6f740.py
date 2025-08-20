# Copyright 2016 Eugene Frolov <eugene@frolov.net.ru>
#
# All Rights Reserved.
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
        self._depends = ["0001-universal-agent-391c09.py"]

    @property
    def migration_id(self):
        return "c6f74019-47cb-412a-a11a-d42921f694a4"

    @property
    def is_manual(self):
        return False

    def upgrade(self, session):
        expressions = [
            """
            CREATE TABLE IF NOT EXISTS "gcl_sdk_audit_logs" (
                "uuid" UUID PRIMARY KEY,
                "object_uuid" UUID NOT NULL,
                "object_type" varchar(64) NOT NULL,
                "user_uuid" UUID DEFAULT NULL,
                "action" varchar(64) NOT NULL,
                "created_at" TIMESTAMP(6) NOT NULL DEFAULT NOW(),
                "updated_at" TIMESTAMP(6) NOT NULL DEFAULT NOW()
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS gcl_sdk_audit_logs_object_type_action_idx
                ON gcl_sdk_audit_logs (object_type, action);
            """,
        ]

        for expression in expressions:
            session.execute(expression)

    def downgrade(self, session):
        tables = ["gcl_sdk_audit_logs"]

        for table in tables:
            self._delete_table_if_exists(session, table)


migration_step = MigrationStep()
