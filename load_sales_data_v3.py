#!/usr/bin/env python3
"""
Clean and load sales data from SQL script with proper statement handling.
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

def extract_statements(sql_content):
    """Extract individual SQL statements from script."""
    # Remove BOM if present
    if sql_content.startswith('\ufeff'):
        sql_content = sql_content[1:]

    # Remove initial USE statement to ensure we use mtcintranet1
    sql_content = re.sub(r'^USE\s+\[.*?\].*?$', '', sql_content, flags=re.MULTILINE | re.IGNORECASE)

    statements = []
    current_statement = []
    in_statement = False

    for line in sql_content.split('\n'):
        stripped = line.strip()

        # Skip empty lines and SQL comments
        if not stripped or stripped.startswith('--'):
            continue

        # Skip PRINT statements
        if stripped.upper().startswith('PRINT'):
            continue

        # Handle GO statement (batch separator)
        if stripped.upper() == 'GO':
            if current_statement:
                stmt = '\n'.join(current_statement).strip()
                if stmt and not stmt.upper().startswith('USE'):
                    statements.append(stmt)
                current_statement = []
                in_statement = False
        else:
            current_statement.append(line)
            in_statement = True

    # Add any remaining statement
    if current_statement:
        stmt = '\n'.join(current_statement).strip()
        if stmt and not stmt.upper().startswith('USE'):
            statements.append(stmt)

    return statements

def execute_sql_statements(conn, cursor, statements):
    """Execute SQL statements with autocommit."""
    print("=" * 80)
    print("EXECUTING SQL STATEMENTS")
    print("=" * 80)

    successful = 0
    failed = 0
    skipped = 0
    failed_details = []

    for idx, statement in enumerate(statements, 1):
        try:
            cursor.execute(statement)
            successful += 1

            # Progress indicator
            if idx % 100 == 0:
                print(f"  Processed {idx}/{len(statements)}...")

        except pyodbc.IntegrityError as e:
            # Skip duplicate key errors
            if 'PRIMARY KEY' in str(e) or 'Violation' in str(e):
                skipped += 1
            else:
                failed += 1
                if len(failed_details) < 5:
                    failed_details.append(f"Stmt {idx}: {str(e)[:80]}")
        except pyodbc.ProgrammingError as e:
            # Skip syntax or other programming errors
            failed += 1
            if len(failed_details) < 5:
                failed_details.append(f"Stmt {idx}: {str(e)[:80]}")
        except Exception as e:
            failed += 1
            if len(failed_details) < 5:
                failed_details.append(f"Stmt {idx}: {str(e)[:80]}")

    print(f"  Processed {len(statements)}/{len(statements)}")

    print()
    print("=" * 80)
    print("EXECUTION RESULTS")
    print("=" * 80)
    print(f"✓ Successful: {successful:,}")
    print(f"⊘ Skipped (duplicates): {skipped:,}")
    print(f"✗ Failed: {failed:,}")
    print(f"Total: {len(statements):,}")

    if failed_details:
        print("\nFirst errors:")
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
            status = "✓" if count > 0 else "•"
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
        # Use autocommit=True for individual statement execution
        conn = pyodbc.connect(build_conn_string(), autocommit=True, timeout=10)
        cursor = conn.cursor()
        print("✓ Connected successfully\n")

        # Load SQL file
        print("Loading SQL script...")
        sql_content = load_sql_file(SQL_SCRIPT_PATH)
        print(f"✓ Loaded {len(sql_content):,} characters\n")

        # Extract statements
        print("Parsing statements...")
        statements = extract_statements(sql_content)
        print(f"✓ Extracted {len(statements):,} statements\n")

        # Execute
        execute_sql_statements(conn, cursor, statements)

        # Verify
        verify_data(conn, cursor)

        print("=" * 80)
        print("✓ COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Critical Error: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
