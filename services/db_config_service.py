"""
Database Connection Manager service.
Handles testing, migrating, and switching the application's DB connection.
"""
import logging
import os
import re
import pyodbc
from config import Config
from db.schema_metadata import ALL_TABLES, MASTER_TABLES

logger = logging.getLogger(__name__)

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_FILE = os.path.join(_APP_ROOT, ".env")

def get_current_config() -> dict:
    return {
        "server": Config.DB_SERVER,
        "database": Config.DB_NAME,
        "user": Config.DB_USER,
        "driver": Config.DB_DRIVER,
    }


def _build_conn_string(cfg: dict) -> str:
    driver = cfg.get("driver") or "{ODBC Driver 17 for SQL Server}"
    return (
        f"DRIVER={driver};"
        f"SERVER={cfg['server']};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['user']};"
        f"PWD={cfg['password']};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=10;"
    )


def _build_master_conn_string(cfg: dict) -> str:
    """Build a connection string that targets SQL Server's master database."""
    driver = cfg.get("driver") or "{ODBC Driver 17 for SQL Server}"
    return (
        f"DRIVER={driver};"
        f"SERVER={cfg['server']};"
        "DATABASE=master;"
        f"UID={cfg['user']};"
        f"PWD={cfg['password']};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=10;"
    )


def _validate_database_name(db_name: str) -> None:
    """Reject unsafe DB names before constructing CREATE DATABASE statements."""
    if not db_name or not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise ValueError("Database name must contain only letters, numbers, and underscore.")


def ensure_database_exists(cfg: dict) -> dict:
    """
    Ensure the target database exists on the target server.
    Returns: {ok: bool, created: bool, error?: str}
    """
    db_name = (cfg.get("database") or "").strip()
    conn = None
    cur = None
    try:
        _validate_database_name(db_name)
        conn = pyodbc.connect(_build_master_conn_string(cfg), autocommit=True, timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT DB_ID(?)", [db_name])
        exists = cur.fetchone()[0] is not None
        created = False
        if not exists:
            # DB name is validated above; use quoted identifier for safety.
            cur.execute(f"CREATE DATABASE [{db_name}]")
            created = True
        return {"ok": True, "created": created}
    except Exception as exc:
        return {"ok": False, "created": False, "error": str(exc)}
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def test_connection(cfg: dict) -> dict:
    """Test connection to given config. Returns {ok, server_name, db_name, error}."""
    conn = None
    cursor = None
    try:
        ensure_result = ensure_database_exists(cfg)
        if not ensure_result.get("ok"):
            return {"ok": False, "error": ensure_result.get("error", "Unable to verify database.")}

        conn_str = _build_conn_string(cfg)
        conn = pyodbc.connect(conn_str, autocommit=True, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT @@SERVERNAME, DB_NAME()")
        row = cursor.fetchone()
        return {
            "ok": True,
            "server_name": str(row[0]),
            "db_name": str(row[1]),
            "db_created": bool(ensure_result.get("created")),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _get_table_schema(cursor, table: str) -> list:
    cursor.execute(
        """
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
               NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """,
        [table],
    )
    return [
        {
            "name": row[0], "type": row[1],
            "max_len": row[2], "num_precision": row[3],
            "num_scale": row[4], "nullable": row[5], "default": row[6],
        }
        for row in cursor.fetchall()
    ]


def _get_primary_keys(cursor, table: str) -> list:
    cursor.execute(
        """
        SELECT kcu.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
               AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
        WHERE tc.TABLE_NAME = ? AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        ORDER BY kcu.ORDINAL_POSITION
        """,
        [table],
    )
    return [row[0] for row in cursor.fetchall()]


def _get_identity_columns(cursor, table: str) -> set:
    try:
        cursor.execute(
            """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
              AND COLUMNPROPERTY(
                    OBJECT_ID(TABLE_SCHEMA + '.' + TABLE_NAME),
                    COLUMN_NAME, 'IsIdentity') = 1
            """,
            [table],
        )
        return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()


def _build_col_ddl(col: dict, identity_cols: set) -> str:
    name = f"[{col['name']}]"
    dtype = col["type"].upper()
    is_identity = col["name"] in identity_cols

    if dtype in ("NVARCHAR", "VARCHAR", "CHAR", "NCHAR"):
        max_len = col["max_len"]
        len_str = "MAX" if (max_len is None or max_len == -1) else str(max_len)
        type_str = f"{dtype}({len_str})"
    elif dtype in ("DECIMAL", "NUMERIC"):
        p = col["num_precision"] or 18
        s = col["num_scale"] or 0
        type_str = f"{dtype}({p},{s})"
    elif dtype == "VARBINARY":
        max_len = col["max_len"]
        len_str = "MAX" if (max_len is None or max_len == -1) else str(max_len)
        type_str = f"VARBINARY({len_str})"
    else:
        type_str = dtype

    identity_str = " IDENTITY(1,1)" if is_identity else ""
    null_str = " NULL" if col["nullable"] == "YES" else " NOT NULL"
    default_str = ""
    if col["default"] and not is_identity:
        default_str = f" DEFAULT {col['default'].strip()}"

    return f"    {name} {type_str}{identity_str}{null_str}{default_str}"


def _generate_create_table(table: str, cols: list, pks: list, identity_cols: set) -> str:
    col_ddls = [_build_col_ddl(c, identity_cols) for c in cols]
    if pks:
        pk_cols = ", ".join(f"[{pk}]" for pk in pks)
        col_ddls.append(f"    CONSTRAINT [PK_{table}] PRIMARY KEY ({pk_cols})")
    body = ",\n".join(col_ddls)
    return f"CREATE TABLE [{table}] (\n{body}\n)"


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
        [table],
    )
    return cursor.fetchone()[0] > 0


def _existing_tables(cursor, tables: list[str]) -> set[str]:
    """Fetch existing tables in one round-trip for the provided table list."""
    if not tables:
        return set()
    placeholders = ", ".join("?" for _ in tables)
    cursor.execute(
        f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME IN ({placeholders})",
        tables,
    )
    return {row[0] for row in cursor.fetchall()}


def _prefetch_table_metadata(cursor, tables: list[str]) -> dict[str, dict]:
    """Prefetch columns, PKs, and identity columns for all tables in batched queries."""
    metadata = {
        t: {"cols": [], "pks": [], "identity_cols": set()}
        for t in tables
    }
    if not tables:
        return metadata

    placeholders = ", ".join("?" for _ in tables)

    cursor.execute(
        f"""
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
               NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME IN ({placeholders})
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """,
        tables,
    )
    for row in cursor.fetchall():
        metadata[row[0]]["cols"].append(
            {
                "name": row[1], "type": row[2],
                "max_len": row[3], "num_precision": row[4],
                "num_scale": row[5], "nullable": row[6], "default": row[7],
            }
        )

    cursor.execute(
        f"""
        SELECT tc.TABLE_NAME, kcu.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
           AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
        WHERE tc.TABLE_NAME IN ({placeholders})
          AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        ORDER BY tc.TABLE_NAME, kcu.ORDINAL_POSITION
        """,
        tables,
    )
    for row in cursor.fetchall():
        metadata[row[0]]["pks"].append(row[1])

    cursor.execute(
        f"""
        SELECT t.name AS table_name, c.name AS column_name
        FROM sys.tables t
        JOIN sys.columns c ON t.object_id = c.object_id
        WHERE t.name IN ({placeholders})
          AND c.is_identity = 1
        """,
        tables,
    )
    for row in cursor.fetchall():
        metadata[row[0]]["identity_cols"].add(row[1])

    return metadata


def _migrate_single_table(
    src_cur,
    tgt_cur,
    tgt_conn,
    table: str,
    src_existing: set[str],
    tgt_existing: set[str],
    metadata: dict[str, dict],
    include_data: bool,
    copy_mode: str,
) -> dict:
    """Migrate schema/data for one table and keep operation atomic per table."""
    result = {"table": table, "status": "ok", "rows_copied": 0, "message": ""}
    try:
        if table not in src_existing:
            result.update(status="skipped", message="Not found in source")
            return result

        cols = metadata.get(table, {}).get("cols", [])
        pks = metadata.get(table, {}).get("pks", [])
        identity_cols = metadata.get(table, {}).get("identity_cols", set())

        if table in tgt_existing:
            result["message"] = "Table exists (schema skipped). "
        else:
            ddl = _generate_create_table(table, cols, pks, identity_cols)
            tgt_cur.execute(ddl)
            tgt_existing.add(table)
            result["message"] = "Schema created. "

        should_copy_data = False
        if include_data:
            if copy_mode == "all":
                should_copy_data = True
            elif copy_mode == "masters_only":
                # Master table list is authoritative for this mode.
                should_copy_data = table in MASTER_TABLES

        if should_copy_data:
            src_cur.execute(f"SELECT * FROM [{table}]")
            col_names = ", ".join(f"[{c['name']}]" for c in cols)
            placeholders = ", ".join("?" for _ in cols)
            insert_sql = f"INSERT INTO [{table}] ({col_names}) VALUES ({placeholders})"
            copied = 0
            batch_size = 1000

            if identity_cols:
                tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
            try:
                while True:
                    rows = src_cur.fetchmany(batch_size)
                    if not rows:
                        break
                    tgt_cur.executemany(insert_sql, rows)
                    copied += len(rows)
            finally:
                if identity_cols:
                    tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] OFF")

            result["rows_copied"] = copied
            result["message"] += f"{copied} rows copied." if copied else "No data."
        elif include_data:
            result["message"] += "Data copy skipped for transaction table (schema only)."

        tgt_conn.commit()
    except Exception as exc:
        tgt_conn.rollback()
        result.update(status="error", message=str(exc))
        logger.exception("Migration error for table %s", table)

    return result


def migrate_tables(
    target_cfg: dict,
    tables: list | None = None,
    include_data: bool = True,
    copy_mode: str = "masters_only",
) -> list:
    """
    Migrate listed tables from current DB to target DB.
    Returns a list of per-table result dicts: {table, status, rows_copied, message}.
    """
    if tables is None:
        tables = ALL_TABLES

    if copy_mode not in ("all", "masters_only", "none"):
        copy_mode = "masters_only"
    include_data = bool(include_data) and copy_mode != "none"

    ensure_result = ensure_database_exists(target_cfg)
    if not ensure_result.get("ok"):
        return [
            {
                "table": t,
                "status": "error",
                "rows_copied": 0,
                "message": f"Database preparation failed: {ensure_result.get('error', 'unknown error')}",
            }
            for t in tables
        ]

    src_conn = tgt_conn = None
    src_cur = tgt_cur = None
    try:
        src_conn = pyodbc.connect(
            _build_conn_string({
                "server": Config.DB_SERVER,
                "database": Config.DB_NAME,
                "user": Config.DB_USER,
                "password": Config.DB_PASSWORD,
                "driver": Config.DB_DRIVER,
            }),
            autocommit=True,
        )
        tgt_conn = pyodbc.connect(_build_conn_string(target_cfg), autocommit=True)
        tgt_conn.autocommit = False
        src_cur = src_conn.cursor()
        tgt_cur = tgt_conn.cursor()
    except Exception as exc:
        if src_conn:
            src_conn.close()
        if tgt_conn:
            tgt_conn.close()
        return [{"table": t, "status": "error", "rows_copied": 0,
                 "message": f"Connection failed: {exc}"} for t in tables]

    results = []
    try:
        src_existing = _existing_tables(src_cur, tables)
        tgt_existing = _existing_tables(tgt_cur, tables)
        metadata = _prefetch_table_metadata(src_cur, list(src_existing))

        for table in tables:
            results.append(
                _migrate_single_table(
                    src_cur=src_cur,
                    tgt_cur=tgt_cur,
                    tgt_conn=tgt_conn,
                    table=table,
                    src_existing=src_existing,
                    tgt_existing=tgt_existing,
                    metadata=metadata,
                    include_data=include_data,
                    copy_mode=copy_mode,
                )
            )
    finally:
        if src_cur:
            src_cur.close()
        if src_conn:
            src_conn.close()
        if tgt_cur:
            tgt_cur.close()
        if tgt_conn:
            tgt_conn.close()

    return results


def save_and_switch(cfg: dict) -> None:
    """Persist new DB config to .env and update in-memory Config + reset pool."""
    _update_env_file(cfg)
    Config.DB_SERVER = cfg["server"]
    Config.DB_NAME = cfg["database"]
    Config.DB_USER = cfg["user"]
    Config.DB_PASSWORD = cfg["password"]
    if cfg.get("driver"):
        Config.DB_DRIVER = cfg["driver"]
    # Flush pyodbc connection pool so next calls use the new server
    pyodbc.pooling = False
    pyodbc.pooling = True


def _update_env_file(cfg: dict) -> None:
    """Update or create .env with new DB connection values."""
    key_map = {
        "DB_SERVER": cfg["server"],
        "DB_NAME": cfg["database"],
        "DB_USER": cfg["user"],
        "DB_PASSWORD": cfg["password"],
    }
    if cfg.get("driver"):
        key_map["DB_DRIVER"] = cfg["driver"]

    lines: list = []
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

    updated: set = set()
    new_lines = []
    for line in lines:
        replaced = False
        for key, val in key_map.items():
            if re.match(rf"^{re.escape(key)}\s*=", line):
                new_lines.append(f"{key}={val}\n")
                updated.add(key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    for key, val in key_map.items():
        if key not in updated:
            new_lines.append(f"{key}={val}\n")

    with open(_ENV_FILE, "w", encoding="utf-8") as fh:
        fh.writelines(new_lines)
