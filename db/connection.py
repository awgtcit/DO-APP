"""
Database connection helper — pyodbc + ODBC Driver 17 for SQL Server.
All credentials come from environment variables via config.py.
Uses pyodbc's built-in connection pooling for performance.

Usage:
    from db.connection import get_connection
    conn = get_connection()
"""

import pyodbc
from config import Config

# Enable pyodbc's built-in connection pooling
pyodbc.pooling = True


def _build_connection_string() -> str:
    return (
        f"DRIVER={Config.DB_DRIVER};"
        f"SERVER={Config.DB_SERVER};"
        f"DATABASE={Config.DB_NAME};"
        f"UID={Config.DB_USER};"
        f"PWD={Config.DB_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )


def get_connection() -> pyodbc.Connection:
    """
    Return a pyodbc Connection from the pool.
    Caller is responsible for closing it (returns it to pool).
    """
    return pyodbc.connect(_build_connection_string(), autocommit=False)


def test_connection() -> bool:
    """Quick connectivity test. Returns True on success."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True
    except pyodbc.Error:
        return False
