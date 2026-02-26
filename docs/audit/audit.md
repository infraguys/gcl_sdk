# Audit

Audit Log enhance system security by tracking changes to key entities (records in tables).

Main components:

- Audit data model - **AuditRecord** (stored in the **gcl_sdk_audit_logs** table).
- Mixin for models - **AuditLogSQLStorableMixin** automatically creates entries in the Audit model.
- API endpoints - **/audit** endpoint for viewing data from AuditRecord (requires **audit_log.audit_record.read** access rights)


## AuditLogSQLStorableMixin summary

AuditLogSQLStorableMixin extends the insert, update and delete methods of SQLStorableMixin.

Adds new **action** and **object_type** strings parameters to these methods.

- Action refers to the operation performed on an object. If not specified, the base method name is used ("insert" is replaced with "create").

- Object Type refers to the type of object being operated on. If not specified, the table name is used.

Also attempts to retrieve the **user_uuid** from the IAM context for the corresponding field in the AuditRecord table.

Within the transaction, the base method is called followed by inserting an entry in the audit table.


## Quick start

Replace **orm.SQLStorableMixin** with **AuditLogSQLStorableMixin** in any model that requires audit tracking.

API routes:
```
from gcl_sdk.audit.api import routes as audit_routes
...
class ApiEndpointRoute(routes.Route):
    ...
    audit = routes.route(audit_routes.AuditRoute)
```

SDK migrations on startup (cmd/user_api):
```
from gcl_sdk import migrations as sdk_migrations

def main():
    ...
    sdk_migrations.apply_migrations(CONF)
    ...
```

Migration for test and applications - create a new migration as usual, then add this code 
```
from gcl_sdk.common.utils import MigrationEngine
from gcl_sdk import migrations as sdk_migrations

SDK_MIGRATION_FILE_NAME = "0002-init-auditlog-table-c6f740.py"

class MigrationStep(migrations.AbstarctMigrationStep):
    ...
    def upgrade(self, session):
        migration_engine = MigrationEngine._get_migration_engine(sdk_migrations)
        migration_engine.apply_migration(SDK_MIGRATION_FILE_NAME, session)

    def downgrade(self, session):
        migration_engine = MigrationEngine._get_migration_engine(sdk_migrations)
        migration_engine.rollback_migration(SDK_MIGRATION_FILE_NAME, session)
```
