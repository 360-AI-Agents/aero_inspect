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

    # D1 rejects `PRAGMA read_uncommitted` (used by the base sqlite dialect
    # to detect/set isolation level) with "not authorized: SQLITE_AUTH", so
    # skip the PRAGMA round-trip entirely and report a fixed level.
    def get_isolation_level(self, dbapi_connection):
        return "SERIALIZABLE"

    def set_isolation_level(self, dbapi_connection, level):
        pass


registry.register("sqlite.d1http", "backend.db_d1_dialect", "D1Dialect")
