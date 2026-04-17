"""
Transaction context managers.

Provides atomic database operations with automatic commit/rollback
and a read-only helper to eliminate boilerplate.

Usage:
    from db.transaction import transactional, read_only

    # Write operations:
    with transactional() as (conn, cursor):
        cursor.execute("INSERT INTO ... VALUES (?, ?)", (a, b))

    # Read operations:
    with read_only() as cursor:
        cursor.execute("SELECT ...")
        rows = cursor.fetchall()
"""

from contextlib import contextmanager
from typing import Generator, Tuple

import pyodbc

from db.connection import get_connection


@contextmanager
def transactional() -> Generator[Tuple[pyodbc.Connection, pyodbc.Cursor], None, None]:
    """
    Context manager that yields (connection, cursor).
    Commits on clean exit, rolls back on any exception,
    and always closes the connection.
    """
    conn: pyodbc.Connection = get_connection()
    cursor: pyodbc.Cursor = conn.cursor()
    try:
        yield conn, cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@contextmanager
def read_only() -> Generator[pyodbc.Cursor, None, None]:
    """
    Context manager for read-only queries.
    Yields a cursor; automatically closes cursor and connection.
    """
    conn: pyodbc.Connection = get_connection()
    cursor: pyodbc.Cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()
