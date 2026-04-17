"""
Migration: Add post-delivery tracking columns to Intra_SalesOrder.

Fujairah Logistics Team fields:
  - Exit_Document_Number   (Exit Document Number from Fujairah Customs)
  - FTA_Declaration_Number (FTA Declaration Number)
  - SAP_Sales_Invoice_Number (SAP Sales Invoice Number)

Sales Team fields:
  - Customs_BOE_Number     (Final Exit – Customs BOE Number)
  - Airway_Bill_Number     (Airway Bill / Bill of Lading Number)
  - IEC_Code               (Final Exit – IEC code used for export)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection


COLUMNS_TO_ADD = [
    ("Exit_Document_Number",    "NVARCHAR(200)", "NULL"),
    ("FTA_Declaration_Number",  "NVARCHAR(200)", "NULL"),
    ("SAP_Sales_Invoice_Number","NVARCHAR(200)", "NULL"),
    ("Customs_BOE_Number",      "NVARCHAR(200)", "NULL"),
    ("Airway_Bill_Number",      "NVARCHAR(500)", "NULL"),
    ("IEC_Code",                "NVARCHAR(200)", "NULL"),
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
        if column_exists(cursor, "Intra_SalesOrder", col_name):
            print(f"  [SKIP] {col_name} already exists")
        else:
            sql = f"ALTER TABLE Intra_SalesOrder ADD {col_name} {col_type} {col_default}"
            cursor.execute(sql)
            conn.commit()
            print(f"  [ADD]  {col_name} {col_type}")

    cursor.close()
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    main()
