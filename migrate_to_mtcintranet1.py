#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '.')

# Set source database to mtcintranet
os.environ['DB_SERVER'] = '172.50.35.75'
os.environ['DB_NAME'] = 'mtcintranet'
os.environ['DB_USER'] = 'sa'
os.environ['DB_PASSWORD'] = 'Admin@123'
os.environ['DB_DRIVER'] = '{SQL Server}'

from services.db_config_service import migrate_tables

# Target configuration - explicitly point to mtcintranet1
target_cfg = {
    'server': '172.50.35.75',
    'database': 'mtcintranet1',
    'user': 'sa',
    'password': 'Admin@123',
    'driver': '{SQL Server}'
}

# All 12 SalesOrder tables to migrate
tables_to_migrate = [
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

print("Starting migration to mtcintranet1...")
print(f"Tables to migrate: {len(tables_to_migrate)}")
print()

# Run migration with data
results = migrate_tables(
    target_cfg=target_cfg,
    tables=tables_to_migrate,
    include_data=True,
    copy_mode='all'  # Copy all data
)

# Display results
print("\n" + "="*80)
print("MIGRATION RESULTS")
print("="*80)

successful = 0
failed = 0
total_rows = 0

for result in results:
    status_icon = "✓" if result['status'] == 'ok' else "✗"
    rows = result.get('rows_copied', 0)
    total_rows += rows

    if result['status'] == 'ok':
        successful += 1
    else:
        failed += 1

    print(f"{status_icon} {result['table']}: {result['status']} ({rows} rows)")
    if result.get('message'):
        print(f"   Message: {result['message']}")

print()
print("="*80)
print(f"Summary: {successful} successful, {failed} failed")
print(f"Total rows migrated: {total_rows:,}")
print("="*80)
