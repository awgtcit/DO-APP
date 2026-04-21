"""
Upload sales data from SQL script to mtcintranet1 database.
Extracts individual SQL statements and executes them one by one.
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection


def extract_statements(filepath):
    """Extract individual SQL statements from the file."""
    encodings = ['utf-8-sig', 'utf-16', 'utf-8', 'latin-1']
    content = None

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            print(f"  Decoded with {enc}")
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if content is None:
        raise RuntimeError(f"Could not decode: {filepath}")

    statements = []
    current = []

    for line in content.splitlines():
        stripped = line.strip()

        # Skip blank lines and GO
        if not stripped or re.match(r'^GO\s*$', stripped, re.IGNORECASE):
            if current:
                stmt = ' '.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            continue

        # Skip comments and print/USE statements
        if (stripped.startswith('--') or stripped.startswith('/***') or
                stripped.startswith('*/') or
                re.match(r'^print\b', stripped, re.IGNORECASE) or
                re.match(r'^USE\b', stripped, re.IGNORECASE)):
            # Flush any pending statement first
            if current:
                stmt = ' '.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            continue

        # If line starts a new statement keyword, flush previous
        if (re.match(r'^(SET|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b', stripped, re.IGNORECASE)
                and current):
            stmt = ' '.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = [stripped]
        else:
            current.append(stripped)

    # Flush last
    if current:
        stmt = ' '.join(current).strip()
        if stmt:
            statements.append(stmt)

    return statements


def upload_sales_data():
    """Execute all extracted SQL statements."""
    sql_file = 'c:/Users/MuhammedNizar/Downloads/sales_data_script.sql'

    if not os.path.exists(sql_file):
        print(f"File not found: {sql_file}")
        return False

    print(f"Reading: {sql_file}")
    statements = extract_statements(sql_file)
    print(f"Extracted {len(statements)} statements\n")

    successful = 0
    failed = 0
    errors = {}

    conn = get_connection()
    conn.autocommit = True  # Avoid transaction interference with SET IDENTITY_INSERT

    try:
        cursor = conn.cursor()
        for i, stmt in enumerate(statements, 1):
            try:
                cursor.execute(stmt)
                successful += 1
                if i % 200 == 0:
                    pct = int(i / len(statements) * 100)
                    print(f"  {i}/{len(statements)} ({pct}%)...")
            except Exception as e:
                failed += 1
                err_key = str(e)[:80]
                errors[err_key] = errors.get(err_key, 0) + 1
                if failed <= 5:
                    preview = stmt[:100]
                    print(f"  Stmt {i} FAILED: {str(e)[:100]}")
                    print(f"    -> {preview}")
        cursor.close()
    finally:
        conn.close()

    print(f"\n{'='*60}")
    print(f"Upload Complete!")
    print(f"  Successful: {successful}")
    print(f"  Failed:     {failed}")
    print(f"  Total:      {len(statements)}")
    if errors:
        print("\nError summary:")
        for msg, count in sorted(errors.items(), key=lambda x: -x[1]):
            print(f"  [{count}x] {msg}")
    print(f"{'='*60}")

    return failed == 0


if __name__ == '__main__':
    print("Starting sales data upload...\n")
    try:
        success = upload_sales_data()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
