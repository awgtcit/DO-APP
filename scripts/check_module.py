#!/usr/bin/env python3
"""Check module configuration."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import read_only

sql = "SELECT id, module_key FROM Intra_Admin_ModuleConfig WHERE module_key = 'delivery_orders'"
with read_only() as cursor:
    cursor.execute(sql)
    row = cursor.fetchone()
    if row:
        print(f"Module ID: {row[0]}, Module Key: {row[1]}")
    else:
        print("Delivery Orders module not found")
        # Check all modules
        cursor.execute("SELECT id, module_key FROM Intra_Admin_ModuleConfig")
        for r in cursor.fetchall():
            print(f"  ID: {r[0]}, Key: {r[1]}")
