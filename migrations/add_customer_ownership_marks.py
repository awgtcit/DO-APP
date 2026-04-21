"""
Migration: Add Ownership Sole Proprietorship and Marks & Numbers
columns to Intra_SalesOrder_BillTo (customer table).

New columns:
  - Ownership_Sole_Proprietorship  (Yes/No flag)
  - Ownership_Sole_Prop_Detail     (Detail text when flag is Yes)
  - Marks_Numbers                  (Marks & Numbers text)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection


TABLE = "Intra_SalesOrder_BillTo"

COLUMNS_TO_ADD = [
    ("Ownership_Sole_Proprietorship", "NVARCHAR(3)",   "NULL"),
    ("Ownership_Sole_Prop_Detail",    "NVARCHAR(MAX)", "NULL"),
    ("Marks_Numbers",                 "NVARCHAR(MAX)", "NULL"),
]


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME = ? AND COLUMN_NAME = ?",
        [table, column],
    )
    return cursor.fetchone()[0] > 0


def main():
    conn = get_connection()
    cursor = conn.cursor()

    for col_name, col_type, col_default in COLUMNS_TO_ADD:
        if column_exists(cursor, TABLE, col_name):
            print(f"  [SKIP] {col_name} already exists")
        else:
            sql = f"ALTER TABLE {TABLE} ADD {col_name} {col_type} {col_default}"
            cursor.execute(sql)
            conn.commit()
            print(f"  [ADD]  {col_name} {col_type}")

    cursor.close()
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    main()
