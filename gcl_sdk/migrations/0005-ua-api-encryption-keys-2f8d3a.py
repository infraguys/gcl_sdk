#    Copyright 2025-2026 Genesis Corporation.
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


class MigrationStep(migrations.AbstractMigrationStep):

    def __init__(self):
        self._depends = ["0004-ua-resources-relations-e9a811.py"]

    @property
    def migration_id(self):
        return "2f8d3ae1-ff5c-4a69-83ab-54c35b10e4e6"

    @property
    def is_manual(self):
        return False

    def upgrade(self, session):
        sql_expressions = [
            # TABLE
            """
            CREATE TABLE IF NOT EXISTS ua_node_encryption_keys (
                "uuid" UUID NOT NULL PRIMARY KEY,
                "private_key" char(44) NOT NULL,
                "encryption_disabled_until" timestamp NOT NULL
                    DEFAULT current_timestamp,
                "created_at" timestamp NOT NULL DEFAULT current_timestamp,
                "updated_at" timestamp NOT NULL DEFAULT current_timestamp
            );
            """,
        ]

        for expr in sql_expressions:
            session.execute(expr, None)

    def downgrade(self, session):
        self._delete_table_if_exists(session, "ua_node_encryption_keys")


migration_step = MigrationStep()
