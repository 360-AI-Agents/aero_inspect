"""
Registers a SQLAlchemy dialect "sqlite+d1http" that routes through the
db_d1 DB-API driver (backend/db_d1.py) instead of a real sqlite3 file.
Import this module once, before create_engine() is called, to make the
dialect available.
"""

from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlalchemy.dialects import registry

from backend import db_d1


class D1Dialect(SQLiteDialect):
    driver = "d1http"
    supports_statement_cache = True

    @classmethod
    def import_dbapi(cls):
        return db_d1

    def create_connect_args(self, url):
        return [], {}

    def is_disconnect(self, e, connection, cursor):
        return False

    # The base sqlite dialect's initialize() probes the connection with
    # several PRAGMAs (read_uncommitted for isolation level, database_list
    # for the default schema name, etc.) to auto-detect capabilities. D1
    # rejects most PRAGMAs with "not authorized: SQLITE_AUTH", so skip that
    # probing entirely and report fixed values instead.
    def initialize(self, connection):
        self.server_version_info = (3, 46, 0)
        self.default_schema_name = "main"
        self.default_isolation_level = "SERIALIZABLE"

    def get_isolation_level(self, dbapi_connection):
        return "SERIALIZABLE"

    def set_isolation_level(self, dbapi_connection, level):
        pass

    # has_table() (used by create_all's checkfirst) normally runs
    # `PRAGMA table_info(...)`, which D1 also rejects. sqlite_master is a
    # plain table, not a PRAGMA, so query it directly instead.
    def has_table(self, connection, table_name, schema=None, **kw):
        result = connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return result.first() is not None


registry.register("sqlite.d1http", "backend.db_d1_dialect", "D1Dialect")
