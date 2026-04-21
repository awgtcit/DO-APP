"""
Migration: Add Marks_Numbers column to Intra_SalesOrder table.
Purpose: Store per-order marks and numbers (auto-populated from BillTo customer).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.transaction import read_only, transactional

def migrate_up():
    """Add Marks_Numbers column to Intra_SalesOrder if it doesn't exist."""

    sql_check = """
    SELECT COLUMN_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Intra_SalesOrder'
    AND COLUMN_NAME = 'Marks_Numbers'
    """

    with read_only() as cursor:
        cursor.execute(sql_check)
        exists = cursor.fetchone()

    if exists:
        print("✓ Marks_Numbers column already exists in Intra_SalesOrder")
        return

    sql_add = """
    ALTER TABLE Intra_SalesOrder
    ADD Marks_Numbers NVARCHAR(MAX) NULL
    """

    with transactional() as (_, cursor):
        cursor.execute(sql_add)
        print("✓ Added Marks_Numbers column to Intra_SalesOrder")

def migrate_down():
    """Remove Marks_Numbers column from Intra_SalesOrder if it exists."""

    sql_drop = """
    ALTER TABLE Intra_SalesOrder
    DROP COLUMN Marks_Numbers
    """

    with transactional() as (_, cursor):
        cursor.execute(sql_drop)
        print("✓ Removed Marks_Numbers column from Intra_SalesOrder")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "down":
        migrate_down()
    else:
        migrate_up()
