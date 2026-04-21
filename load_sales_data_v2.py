#!/usr/bin/env python3
"""
Clean and load sales data directly from SQL script with proper batch handling.
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

def load_sql_file(file_path):
    """Load SQL file with proper encoding detection."""
    try:
        # Try UTF-16 first
        with open(file_path, 'r', encoding='utf-16') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            # Fall back to UTF-8
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try latin-1 as last resort
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()

def clean_and_execute_sql(conn, cursor, sql_content):
    """Clean SQL content and execute statements."""
    print("=" * 80)
    print("PARSING AND EXECUTING SQL")
    print("=" * 80)

    # Remove BOM if present
    if sql_content.startswith('\ufeff'):
        sql_content = sql_content[1:]

    # Remove initial USE statement to ensure we use mtcintranet1
    sql_content = re.sub(r'^USE\s+\[.*?\].*?$', '', sql_content, flags=re.MULTILINE | re.IGNORECASE)

    # Split by GO statements
    statements = []
    current_statement = []

    for line in sql_content.split('\n'):
        stripped = line.strip()

        # Skip empty lines and SQL comments
        if not stripped or stripped.startswith('--'):
            continue

        # Handle GO statement (batch separator)
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

    print(f"Extracted {len(statements)} statements")

    successful = 0
    failed = 0
    failed_details = []

    for idx, statement in enumerate(statements, 1):
        try:
            # Skip PRINT statements
            if statement.upper().startswith('PRINT'):
                continue

            cursor.execute(statement)
            conn.commit()
            successful += 1

            # Progress indicator
            if idx % 50 == 0:
                print(f"  Processed {idx}/{len(statements)}...")

        except pyodbc.ProgrammingError as e:
            # Handle SQL syntax errors
            failed += 1
            if len(failed_details) < 5:
                failed_details.append(f"Statement {idx}: {str(e)[:100]}")
        except pyodbc.IntegrityError as e:
            # Skip duplicate key errors (data already exists)
            if 'PRIMARY KEY' in str(e):
                pass  # Silently skip
            else:
                failed += 1
                if len(failed_details) < 5:
                    failed_details.append(f"Statement {idx}: {str(e)[:100]}")
        except Exception as e:
            failed += 1
            if len(failed_details) < 5:
                failed_details.append(f"Statement {idx}: {str(e)[:100]}")

    print()
    print("=" * 80)
    print("EXECUTION RESULTS")
    print("=" * 80)
    print(f"✓ Successful: {successful}")
    print(f"✗ Failed/Skipped: {failed}")

    if failed_details:
        print("\nErrors encountered:")
        for detail in failed_details:
            print(f"  {detail}")

    print()

def verify_data(conn, cursor):
    """Verify data in all tables."""
    print("=" * 80)
    print("DATA VERIFICATION")
    print("=" * 80)

    tables = [
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

    total = 0
    for table in tables:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM [{table}]')
            count = cursor.fetchone()[0]
            total += count
            status = "✓" if count > 0 else "✗"
            print(f"{status} {table}: {count:,} rows")
        except Exception as e:
            print(f"✗ {table}: Error - {str(e)[:50]}")

    print(f"\nTotal rows: {total:,}")
    print()

def main():
    conn = None
    cursor = None

    try:
        print("\nConnecting to mtcintranet1...")
        conn = pyodbc.connect(build_conn_string(), autocommit=False, timeout=10)
        cursor = conn.cursor()
        print("✓ Connected successfully\n")

        # Load SQL file
        print("Loading SQL script...")
        sql_content = load_sql_file(SQL_SCRIPT_PATH)
        print(f"✓ Loaded {len(sql_content):,} characters\n")

        # Clean and execute
        clean_and_execute_sql(conn, cursor, sql_content)

        # Verify results
        verify_data(conn, cursor)

        print("=" * 80)
        print("COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Critical Error: {str(e)}")
        if conn:
            conn.rollback()

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
