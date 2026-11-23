"""
Unified Database Adapter & Abstraction Layer
AI Business Operations Copilot - Cross-Engine Database Support (MySQL & SQLite)

Provides a standard DBAPI connection and cursor interface for MySQL that is 100%
compatible with SQLite-style operations in backend/ai_backend.py:
- Parameter placeholder translation (? -> %s)
- Dual-access row dictionaries (row['id'], row[0], dict(row), row.keys())
- Proper lastrowid, rowcount, and transaction handling
- SQLite PRAGMA interception and normalization for MySQL
- Exception translation (wrapping MySQL IntegrityError in DatabaseIntegrityError subclassing sqlite3.IntegrityError)
"""

import re
import sqlite3
import logging
from datetime import datetime, date
from typing import Any, List, Dict, Optional, Tuple, Sequence, Union

logger = logging.getLogger("bizops.database_adapter")


class DatabaseIntegrityError(sqlite3.IntegrityError):
    """IntegrityError subclass that behaves identically to sqlite3.IntegrityError."""
    pass


class DatabaseOperationalError(sqlite3.OperationalError):
    """OperationalError subclass that behaves identically to sqlite3.OperationalError."""
    pass


class RowAdapter:
    """
    A mapping and sequence wrapper matching sqlite3.Row semantics:
    1. Key-based access: row['id'], row['email']
    2. Zero-indexed access: row[0], row[1]
    3. Sequence unpacking: a, b = row (unpacks column values, NOT keys)
    4. Mapping conversion: dict(row), **row, row.keys(), row.values(), row.items()
    5. Normalizes datetime objects to ISO strings matching SQLite response formats
    """
    __slots__ = ("_d", "_order")

    def __init__(self, data_dict: Dict[str, Any], columns_order: Optional[Sequence[str]] = None):
        normalized = {}
        for k, v in data_dict.items():
            if isinstance(v, datetime):
                normalized[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(v, date):
                normalized[k] = v.strftime("%Y-%m-%d")
            else:
                normalized[k] = v
        self._d = normalized
        self._order = list(columns_order) if columns_order is not None else list(normalized.keys())

    def __getitem__(self, item: Union[str, int]) -> Any:
        if isinstance(item, int):
            try:
                key = self._order[item]
                return self._d[key]
            except IndexError:
                raise IndexError(f"Tuple index {item} out of range (columns: {len(self._order)})")
        return self._d[item]

    def __iter__(self):
        """Iterates over column values to support tuple unpacking like sqlite3.Row."""
        for k in self._order:
            yield self._d[k]

    def __contains__(self, key: Any) -> bool:
        return key in self._d

    def __len__(self) -> int:
        return len(self._order)

    def __repr__(self) -> str:
        return f"<RowAdapter {repr(self._d)}>"

    def get(self, key: Any, default: Any = None) -> Any:
        if isinstance(key, int):
            try:
                return self[key]
            except IndexError:
                return default
        return self._d.get(key, default)

    def keys(self):
        return self._order

    def values(self):
        return [self._d[k] for k in self._order]

    def items(self):
        return [(k, self._d[k]) for k in self._order]


class MySQLCursorAdapter:
    """
    Cursor adapter wrapping a DBAPI/PyMySQL cursor to provide
    transparent SQLite compatibility:
    - Translates '?' parameter markers to '%s'
    - Wraps rows in RowAdapter
    - Exposes lastrowid and rowcount
    - Normalizes SQLite PRAGMAs
    """
    def __init__(self, raw_cursor, parent_connection=None):
        self._cursor = raw_cursor
        self._conn = parent_connection
        self.lastrowid: Optional[int] = None
        self.rowcount: int = -1
        self.description: Optional[Tuple] = None
        self._pragma_results: Optional[List[RowAdapter]] = None

    def _translate_query(self, sql: str) -> str:
        """Translates SQLite query syntax to MySQL syntax where appropriate."""
        cleaned = sql.strip()
        
        # In MySQL, ? placeholders must be translated to %s
        translated = re.sub(r'\?', '%s', cleaned)

        # Backtick reserved column names in notifications table if unquoted
        if "notifications" in translated.lower():
            translated = re.sub(r'\bSET\s+read\b', 'SET `read`', translated, flags=re.IGNORECASE)
            translated = re.sub(r'(\bdesc\b|\bread\b)', r'`\1`', translated)
            # Remove double backticks if already backticked
            translated = re.sub(r'``([^`]+)``', r'`\1`', translated)

        return translated

    def execute(self, sql: str, params: Optional[Union[Sequence[Any], Dict[str, Any]]] = None) -> "MySQLCursorAdapter":
        self._pragma_results = None
        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()

        # Intercept SQLite PRAGMA commands
        if sql_upper.startswith("PRAGMA "):
            return self._handle_pragma(sql_stripped)

        translated_sql = self._translate_query(sql_stripped)

        # Normalize parameters (tuples or lists)
        final_params = params
        if params is not None and not isinstance(params, (list, tuple, dict)):
            final_params = (params,)

        try:
            if final_params is not None:
                self._cursor.execute(translated_sql, final_params)
            else:
                self._cursor.execute(translated_sql)

            self.lastrowid = getattr(self._cursor, "lastrowid", None)
            self.rowcount = getattr(self._cursor, "rowcount", -1)
            self.description = getattr(self._cursor, "description", None)
            return self

        except Exception as exc:
            err_type = type(exc).__name__
            err_msg = str(exc)

            # Map MySQL/PyMySQL Integrity errors to DatabaseIntegrityError
            if "IntegrityError" in err_type or any(code in err_msg for code in ["1062", "1451", "1452", "1216", "1217"]):
                raise DatabaseIntegrityError(err_msg) from exc

            # Map Operational errors
            if "OperationalError" in err_type:
                raise DatabaseOperationalError(err_msg) from exc

            raise

    def executemany(self, sql: str, seq_of_params: Sequence[Union[Sequence[Any], Dict[str, Any]]]) -> "MySQLCursorAdapter":
        translated_sql = self._translate_query(sql)
        try:
            self._cursor.executemany(translated_sql, seq_of_params)
            self.rowcount = getattr(self._cursor, "rowcount", -1)
            self.description = getattr(self._cursor, "description", None)
            return self
        except Exception as exc:
            err_type = type(exc).__name__
            err_msg = str(exc)
            if "IntegrityError" in err_type or any(code in err_msg for code in ["1062", "1451", "1452"]):
                raise DatabaseIntegrityError(err_msg) from exc
            if "OperationalError" in err_type:
                raise DatabaseOperationalError(err_msg) from exc
            raise

    def _handle_pragma(self, pragma_sql: str) -> "MySQLCursorAdapter":
        """Simulates SQLite PRAGMA responses for MySQL compatibility."""
        upper = pragma_sql.upper().strip()
        
        # PRAGMA foreign_keys
        if "FOREIGN_KEYS" in upper:
            # If checking status: PRAGMA foreign_keys;
            if "=" not in upper:
                row_data = {"foreign_keys": 1}
                self._pragma_results = [RowAdapter(row_data, ["foreign_keys"])]
                self.description = (("foreign_keys", 0, None, None, None, None, None),)
            else:
                self._pragma_results = []
                self.description = None
            return self

        # PRAGMA busy_timeout, journal_mode, synchronous
        if any(k in upper for k in ["BUSY_TIMEOUT", "JOURNAL_MODE", "SYNCHRONOUS"]):
            if "JOURNAL_MODE" in upper and "=" not in upper:
                self._pragma_results = [RowAdapter({"journal_mode": "wal"}, ["journal_mode"])]
                self.description = (("journal_mode", 0, None, None, None, None, None),)
            else:
                self._pragma_results = []
                self.description = None
            return self

        # PRAGMA table_info(tbl)
        table_info_match = re.search(r"TABLE_INFO\s*\(\s*([a-zA-Z0-9_]+)\s*\)", upper)
        if table_info_match:
            tbl_name = table_info_match.group(1).lower()
            try:
                self._cursor.execute(f"SHOW COLUMNS FROM `{tbl_name}`;")
                cols = self._cursor.fetchall()
                # SQLite table_info returns: (cid, name, type, notnull, dflt_value, pk)
                res = []
                for cid, col in enumerate(cols):
                    # PyMySQL returns tuple: (Field, Type, Null, Key, Default, Extra)
                    field, ctype, null, key, dflt, extra = col
                    res.append(RowAdapter({
                        "cid": cid,
                        "name": field,
                        "type": ctype,
                        "notnull": 1 if null == "NO" else 0,
                        "dflt_value": dflt,
                        "pk": 1 if key == "PRI" else 0
                    }, ["cid", "name", "type", "notnull", "dflt_value", "pk"]))
                self._pragma_results = res
                self.description = (("cid",), ("name",), ("type",), ("notnull",), ("dflt_value",), ("pk",))
                return self
            except Exception as e:
                logger.warning("Could not simulate PRAGMA table_info for %s: %s", tbl_name, e)
                self._pragma_results = []
                self.description = None
                return self

        # Unknown PRAGMA -> no-op
        self._pragma_results = []
        self.description = None
        return self

    def fetchone(self) -> Optional[RowAdapter]:
        if self._pragma_results is not None:
            if self._pragma_results:
                return self._pragma_results.pop(0)
            return None

        row = self._cursor.fetchone()
        if row is None:
            return None

        col_names = [col[0] for col in self._cursor.description]
        row_dict = dict(zip(col_names, row))
        return RowAdapter(row_dict, col_names)

    def fetchall(self) -> List[RowAdapter]:
        if self._pragma_results is not None:
            res = list(self._pragma_results)
            self._pragma_results = []
            return res

        rows = self._cursor.fetchall()
        if not rows:
            return []

        col_names = [col[0] for col in self._cursor.description]
        return [RowAdapter(dict(zip(col_names, r)), col_names) for r in rows]

    def fetchmany(self, size: Optional[int] = None) -> List[RowAdapter]:
        if self._pragma_results is not None:
            count = size or 1
            res = self._pragma_results[:count]
            self._pragma_results = self._pragma_results[count:]
            return res

        rows = self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()
        if not rows:
            return []

        col_names = [col[0] for col in self._cursor.description]
        return [RowAdapter(dict(zip(col_names, r)), col_names) for r in rows]

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class MySQLConnectionAdapter:
    """
    Connection adapter wrapping a raw SQLAlchemy / PyMySQL connection
    to provide standard DBAPI / SQLite-compatible semantics:
    - conn.cursor() -> MySQLCursorAdapter
    - conn.execute(sql, params) -> MySQLCursorAdapter
    - conn.commit(), conn.rollback(), conn.close()
    - Context manager support
    """
    def __init__(self, raw_connection):
        self._raw_conn = raw_connection
        self.is_closed = False

    def cursor(self) -> MySQLCursorAdapter:
        raw_cur = self._raw_conn.cursor()
        return MySQLCursorAdapter(raw_cur, parent_connection=self)

    def execute(self, sql: str, params: Optional[Union[Sequence[Any], Dict[str, Any]]] = None) -> MySQLCursorAdapter:
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        if not self.is_closed:
            self._raw_conn.commit()

    def rollback(self):
        if not self.is_closed:
            try:
                self._raw_conn.rollback()
            except Exception:
                pass

    def close(self):
        if not self.is_closed:
            self.is_closed = True
            try:
                self._raw_conn.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
