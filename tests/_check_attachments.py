"""Check attachment table schema."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute(
    "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH "
    "FROM INFORMATION_SCHEMA.COLUMNS "
    "WHERE TABLE_NAME='Intra_SalesOrder_Approved_Attachments' "
    "ORDER BY ORDINAL_POSITION"
)
for r in cur.fetchall():
    print(f"{r[0]:30s} {r[1]:15s} {r[2]}")

print("\n--- Sample rows ---")
cur.execute("SELECT id, SalesOrder_ID, FileName, WebPath, DirPath FROM Intra_SalesOrder_Approved_Attachments")
for r in cur.fetchall():
    print(f"  id={r[0]} order={r[1]} file={r[2]} web={r[3]} dir={r[4]}")

cur.close()
conn.close()
