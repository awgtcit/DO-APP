#!/usr/bin/env python3
"""
Clean all data from SalesOrder tables in mtcintranet1, then load fresh data from SQL script.
"""
import sys
import os
import re
import pyodbc
sys.path.insert(0, '.')

# Connection config for mtcintranet1
SERVER = '172.50.35.75'
DATABASE = 'mtcintranet1'
USER = 'sa'
PASSWORD = 'Admin@123'
DRIVER = '{SQL Server}'

# Tables to clean
TABLES_TO_CLEAN = [
    'Intra_SalesOrder_AWTFZC_Customer',
    'Intra_SalesOrder_UnitPrice',
    'Intra_SalesOrder_Forecast',
    'Intra_SalesOrder_Products',
    'Intra_SalesOrder_PointOfExit',
    'Intra_SalesOrder_Items',
    'Intra_SalesOrder_BillTo',
    'Intra_SalesOrder_ShipTo',
    'Intra_SalesOrder_Receipts',
    'Intra_SalesOrder_ReceiptItems',
    'Intra_SalesOrder_PricingPermission',
    'Intra_SalesOrder'
]

# SQL script file
SQL_SCRIPT_PATH = r'C:\Users\MuhammedNizar\Downloads\sales_data_script.sql'

def build_conn_string():
    """Build ODBC connection string."""
    return (
        f"DRIVER={DRIVER};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={USER};"
        f"PWD={PASSWORD};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=10;"
    )

def clean_all_tables(conn, cursor):
    """Delete all rows from sales order tables."""
    print("=" * 80)
    print("CLEANING EXISTING DATA")
    print("=" * 80)

    for table in TABLES_TO_CLEAN:
        try:
            cursor.execute(f"DELETE FROM [{table}]")
            rows_deleted = cursor.rowcount
            conn.commit()
            print(f"✓ {table}: {rows_deleted} rows deleted")
        except Exception as e:
            print(f"✗ {table}: {str(e)}")
            conn.rollback()

    print()

def extract_sql_statements(sql_file_path):
    """Extract individual SQL statements from SQL file."""
    print("=" * 80)
    print("PARSING SQL SCRIPT")
    print("=" * 80)

    try:
        # Try UTF-16 first (common for SQL Server exports)
        with open(sql_file_path, 'r', encoding='utf-16') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Fall back to UTF-8
        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try latin-1 as last resort
            with open(sql_file_path, 'r', encoding='latin-1') as f:
                content = f.read()

    # Remove BOM if present
    if content.startswith('\ufeff'):
        content = content[1:]

    # Split by GO statements (batch separators in SQL Server)
    statements = []
    current_statement = []

    for line in content.split('\n'):
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith('--'):
            continue

        # Check for GO statement
        if stripped.upper() == 'GO':
            if current_statement:
                stmt = '\n'.join(current_statement).strip()
                if stmt:
                    statements.append(stmt)
                current_statement = []
        else:
            current_statement.append(line)

    # Add any remaining statement
    if current_statement:
        stmt = '\n'.join(current_statement).strip()
        if stmt:
            statements.append(stmt)

    print(f"Extracted {len(statements)} SQL statements")
    print()
    return statements

def execute_sql_statements(conn, cursor, statements):
    """Execute SQL statements one by one."""
    print("=" * 80)
    print("LOADING DATA")
    print("=" * 80)

    successful = 0
    failed = 0
    failed_statements = []

    for idx, statement in enumerate(statements, 1):
        try:
            # Skip print statements and use statements
            if statement.upper().startswith('PRINT') or statement.upper().startswith('USE'):
                continue

            cursor.execute(statement)
            conn.commit()
            successful += 1

            # Print progress every 100 statements
            if idx % 100 == 0:
                print(f"Progress: {idx}/{len(statements)} statements processed...")

        except pyodbc.IntegrityError as e:
            # Ignore duplicate key errors (data already exists)
            if 'PRIMARY KEY' in str(e) or 'Violation' in str(e):
                failed += 1
            else:
                failed += 1
                failed_statements.append((idx, statement[:100], str(e)))
        except Exception as e:
            failed += 1
            if len(failed_statements) < 10:  # Keep first 10 errors
                failed_statements.append((idx, statement[:100], str(e)))

    print()
    print("=" * 80)
    print("LOAD RESULTS")
    print("=" * 80)
    print(f"✓ Successful: {successful}")
    print(f"✗ Failed: {failed}")
    print(f"Total: {len(statements)}")

    if failed_statements:
        print("\nFirst few errors:")
        for stmt_idx, stmt_preview, error in failed_statements[:5]:
            print(f"  Statement {stmt_idx}: {error}")

    print()

def main():
    conn = None
    cursor = None

    try:
        print("\nConnecting to mtcintranet1...")
        conn = pyodbc.connect(build_conn_string(), autocommit=False, timeout=10)
        cursor = conn.cursor()
        print("✓ Connected successfully\n")

        # Step 1: Clean existing data
        clean_all_tables(conn, cursor)

        # Step 2: Read and parse SQL script
        statements = extract_sql_statements(SQL_SCRIPT_PATH)

        # Step 3: Execute statements
        execute_sql_statements(conn, cursor, statements)

        print("=" * 80)
        print("COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        if conn:
            conn.rollback()

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
