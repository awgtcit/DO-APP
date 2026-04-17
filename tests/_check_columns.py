"""Check current columns in Intra_SalesOrder table."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

conn = get_connection()
cursor = conn.cursor()
cursor.execute(
    "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH "
    "FROM INFORMATION_SCHEMA.COLUMNS "
    "WHERE TABLE_NAME = 'Intra_SalesOrder' "
    "ORDER BY ORDINAL_POSITION"
)
for row in cursor.fetchall():
    print(f"  {row[0]:40s} {row[1]:15s} {row[2] if row[2] else ''}")
cursor.close()
conn.close()
