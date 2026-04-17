"""
Audit logger — records every significant action to the database.

Replaces legacy Intra_DBLog + Intra_UserActivityLog.
All entries are INSERT-only (append-only audit trail).
"""

import logging
import re
from datetime import datetime, timezone

from db.connection import get_connection

logger = logging.getLogger(__name__)


def log_activity(
    emp_id: int,
    user_name: str,
    activity_type: str,
    client_ip: str = "",
    remarks: str = "",
    get_fields: str = "",
    post_fields: str = "",
) -> None:
    """Insert a row into Intra_UserActivityLog."""
    sql = """
        INSERT INTO Intra_UserActivityLog
            (userName, ClientComputer, ClientIP, DateNTime,
             AcitvityType, Get_Fields, Post_Fields, Remarks,
             EmpID, Created_on)
        VALUES (?, '', ?, GETDATE(), ?, ?, ?, ?, ?, GETDATE())
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            sql,
            (user_name, client_ip, activity_type, get_fields, post_fields, remarks, emp_id),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as exc:
        logger.warning("Audit log_activity failed: %s", exc)


def _sanitize_query(query: str) -> str:
    """Redact sensitive parameter values from logged SQL queries."""
    # Redact anything after common sensitive column names
    sanitized = re.sub(
        r"(CredPassword|password|PWD|secret)\s*=\s*'[^']*'",
        r"\1='[REDACTED]'",
        query,
        flags=re.IGNORECASE,
    )
    # Cap length
    return sanitized[:4000]


def log_db_operation(
    emp_id: int,
    query: str,
    status: str = "success",
) -> None:
    """
    Insert a row into Intra_DBLog (mirrors legacy DB mutation logging).
    Sensitive values are redacted before storage.
    """
    sql = """
        INSERT INTO Intra_DBLog (EmpID, Query, Status, Created_on)
        VALUES (?, ?, ?, GETDATE())
    """
    safe_query = _sanitize_query(query)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (emp_id, safe_query, status))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as exc:
        logger.warning("Audit log_db_operation failed: %s", exc)
