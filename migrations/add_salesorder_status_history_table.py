"""
Migration: Ensure Intra_SalesOrder_StatusHistory exists for DO workflow transaction records.

Creates table if missing and adds required columns if table already exists.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection


TABLE_NAME = "Intra_SalesOrder_StatusHistory"

COLUMNS = [
    ("order_id", "INT", "NOT NULL"),
    ("po_number", "NVARCHAR(100)", "NULL"),
    ("from_status", "NVARCHAR(100)", "NULL"),
    ("to_status", "NVARCHAR(100)", "NOT NULL"),
    ("action_type", "NVARCHAR(50)", "NOT NULL DEFAULT 'STATUS_CHANGE'"),
    ("actor_emp_id", "INT", "NULL"),
    ("actor_name", "NVARCHAR(200)", "NULL"),
    ("actor_role", "NVARCHAR(100)", "NULL"),
    ("remarks", "NVARCHAR(1000)", "NULL"),
    ("price_signature", "NVARCHAR(128)", "NULL"),
    ("total_amount", "DECIMAL(18,2)", "NULL"),
    ("reject_reason", "NVARCHAR(500)", "NULL"),
    ("reject_remarks", "NVARCHAR(1000)", "NULL"),
    ("created_on", "DATETIME", "NOT NULL DEFAULT GETDATE()"),
]


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
        [table_name],
    )
    return cursor.fetchone()[0] > 0


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME = ? AND COLUMN_NAME = ?",
        [table_name, column_name],
    )
    return cursor.fetchone()[0] > 0


def index_exists(cursor, index_name: str) -> bool:
    cursor.execute("SELECT COUNT(*) FROM sys.indexes WHERE name = ?", [index_name])
    return cursor.fetchone()[0] > 0


def create_table(cursor):
    cursor.execute(
        f"""
        CREATE TABLE {TABLE_NAME} (
            id INT IDENTITY(1,1) PRIMARY KEY,
            order_id INT NOT NULL,
            po_number NVARCHAR(100) NULL,
            from_status NVARCHAR(100) NULL,
            to_status NVARCHAR(100) NOT NULL,
            action_type NVARCHAR(50) NOT NULL DEFAULT 'STATUS_CHANGE',
            actor_emp_id INT NULL,
            actor_name NVARCHAR(200) NULL,
            actor_role NVARCHAR(100) NULL,
            remarks NVARCHAR(1000) NULL,
            price_signature NVARCHAR(128) NULL,
            total_amount DECIMAL(18,2) NULL,
            reject_reason NVARCHAR(500) NULL,
            reject_remarks NVARCHAR(1000) NULL,
            created_on DATETIME NOT NULL DEFAULT GETDATE()
        )
        """
    )


def main():
    conn = get_connection()
    cursor = conn.cursor()

    if not table_exists(cursor, TABLE_NAME):
        create_table(cursor)
        conn.commit()
        print(f"  [ADD] {TABLE_NAME} table")
    else:
        print(f"  [SKIP] {TABLE_NAME} already exists")

    for col_name, col_type, col_nullable in COLUMNS:
        if column_exists(cursor, TABLE_NAME, col_name):
            print(f"  [SKIP] {col_name} already exists")
            continue
        sql = f"ALTER TABLE {TABLE_NAME} ADD {col_name} {col_type} {col_nullable}"
        cursor.execute(sql)
        conn.commit()
        print(f"  [ADD]  {col_name} {col_type}")

    ix_name = "IX_SalesOrder_StatusHistory_Order_Created"
    if not index_exists(cursor, ix_name):
        cursor.execute(
            f"CREATE INDEX {ix_name} ON {TABLE_NAME} (order_id, created_on DESC, id DESC)"
        )
        conn.commit()
        print(f"  [ADD]  {ix_name}")
    else:
        print(f"  [SKIP] {ix_name} already exists")

    cursor.close()
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    main()
