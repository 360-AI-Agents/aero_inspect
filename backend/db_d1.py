"""
Minimal DB-API 2.0 driver that talks to a Cloudflare D1 database over HTTP,
via a Worker "outboundByHost" handler (see workers/src/index.js).

D1 has no persistent connection/transaction concept reachable from outside
the Workers runtime, so this driver executes every statement immediately
against D1 as it is issued. `commit()`/`rollback()` are no-ops: there is no
staged, multi-statement atomicity across separate execute() calls. This is
a deliberate simplification for this app (no code path here depends on
cross-statement rollback), not a general-purpose D1 driver.
"""

import json
import os
import urllib.request
import urllib.error

apilevel = "2.0"
threadsafety = 1
paramstyle = "qmark"
sqlite_version_info = (3, 46, 0)

D1_PROXY_URL = os.environ.get("D1_PROXY_URL", "http://d1.internal/query")
D1_PROXY_SECRET = os.environ.get("D1_PROXY_SECRET", "")


class Warning(Exception):
    pass


class Error(Exception):
    pass


class InterfaceError(Error):
    pass


class DatabaseError(Error):
    pass


class DataError(DatabaseError):
    pass


class OperationalError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class InternalError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class NotSupportedError(DatabaseError):
    pass


def _post(payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        D1_PROXY_URL,
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-d1-proxy-secret": D1_PROXY_SECRET,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
    except urllib.error.URLError as e:
        raise OperationalError(f"D1 proxy unreachable: {e}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise OperationalError(f"D1 proxy returned non-JSON response: {raw[:200]!r}") from e

    if not data.get("ok"):
        raise OperationalError(data.get("error", "unknown D1 error"))
    return data


class Cursor:
    def __init__(self, connection: "Connection"):
        self.connection = connection
        self.description = None
        self.rowcount = -1
        self.lastrowid = None
        self._rows = []
        self._rowindex = 0
        self.arraysize = 1

    _ROWS_RETURNING = ("SELECT", "PRAGMA", "WITH", "EXPLAIN")

    def execute(self, sql, params=None):
        params = list(params) if params else []
        data = _post({"sql": sql, "params": params})
        self._load_result(data, sql)
        return self

    def executemany(self, sql, seq_of_params):
        batch = [{"sql": sql, "params": list(p) if p else []} for p in seq_of_params]
        if not batch:
            return self
        data = _post({"batch": batch})
        last = data.get("batch", [{}])[-1]
        self._load_result({"results": last.get("results", []), "meta": last.get("meta", {})}, sql)
        return self

    def _load_result(self, data, sql=""):
        results = data.get("results") or []
        meta = data.get("meta") or {}

        self._rows = [tuple(row.values()) for row in results]
        self._rowindex = 0

        if results:
            # A statement that returned rows: description comes from them.
            self.description = [(k, None, None, None, None, None, None) for k in results[0].keys()]
        elif sql.lstrip().upper().startswith(self._ROWS_RETURNING):
            # A rows-returning statement that just matched nothing -- an
            # empty column list still signals "this is a SELECT" to
            # SQLAlchemy, vs. None which means "this was DML/DDL".
            self.description = []
        else:
            self.description = None

        self.rowcount = meta.get("changes", len(self._rows) or -1)
        self.lastrowid = meta.get("last_row_id")

    def fetchone(self):
        if self._rowindex >= len(self._rows):
            return None
        row = self._rows[self._rowindex]
        self._rowindex += 1
        return row

    def fetchmany(self, size=None):
        size = size or self.arraysize
        rows = self._rows[self._rowindex:self._rowindex + size]
        self._rowindex += len(rows)
        return rows

    def fetchall(self):
        rows = self._rows[self._rowindex:]
        self._rowindex = len(self._rows)
        return rows

    def close(self):
        pass

    def __iter__(self):
        return iter(self._rows[self._rowindex:])


class Connection:
    def cursor(self):
        return Cursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def connect(*args, **kwargs):
    return Connection()
