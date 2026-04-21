#!/usr/bin/env python3
"""Debug script to check customer manager role assignment."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyodbc

server = "172.50.35.75"
database = "mtcintranet1"
username = "sa"
password = "Admin@123"

conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;Connection Timeout=10;"

try:
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    print("=" * 80)
    print("CHECKING CUSTOMER MANAGER ROLE ASSIGNMENT")
    print("=" * 80)
    print()

    # Get module ID for delivery_orders
    cursor.execute("SELECT id FROM Intra_Admin_ModuleConfig WHERE module_key = 'delivery_orders'")
    module_row = cursor.fetchone()
    if module_row:
        module_id = module_row[0]
        print(f"✓ Delivery Orders Module ID: {module_id}")
        print()

        # Check all users with customer manager role
        cursor.execute("""
            SELECT umr.emp_id, umr.role_key, umr.assigned_at
            FROM Intra_Admin_UserModuleRole umr
            WHERE umr.module_id = ? AND umr.role_key = 'do_customer_manager'
            ORDER BY umr.assigned_at DESC
        """, (module_id,))

        rows = cursor.fetchall()
        if rows:
            print("✓ Users with do_customer_manager role:")
            for row in rows:
                emp_id, role_key, assigned_at = row
                print(f"  - emp_id: {emp_id}, role: {role_key}, assigned: {assigned_at}")
            print()
        else:
            print("✗ No users with do_customer_manager role found")
            print()

        # Check what roles do we have in the system
        cursor.execute("""
            SELECT DISTINCT role_key
            FROM Intra_Admin_UserModuleRole
            WHERE module_id = ?
            ORDER BY role_key
        """, (module_id,))

        role_rows = cursor.fetchall()
        print("✓ All roles assigned for delivery_orders module:")
        for row in role_rows:
            print(f"  - {row[0]}")
        print()

        # Check all emp_id assignments
        cursor.execute("""
            SELECT emp_id, role_key, assigned_at
            FROM Intra_Admin_UserModuleRole
            WHERE module_id = ?
            ORDER BY emp_id, role_key
        """, (module_id,))

        user_rows = cursor.fetchall()
        print("✓ All user role assignments for delivery_orders:")
        for row in user_rows:
            emp_id, role_key, assigned_at = row
            print(f"  emp_id: {emp_id:5} | role: {role_key:25} | assigned: {assigned_at}")

    else:
        print("✗ Delivery Orders module not found")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
