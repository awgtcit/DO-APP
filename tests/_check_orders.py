from db.connection import get_connection
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT TOP 1 id, PO_Number, Status FROM Intra_SalesOrder WHERE Status = 'CONFIRMED' ORDER BY id DESC")
row = cursor.fetchone()
if row:
    print(f"Found CONFIRMED order: id={row[0]}, PO={row[1]}, Status={row[2]}")
else:
    print("No CONFIRMED orders found")
    cursor.execute("SELECT Status, COUNT(*) as cnt FROM Intra_SalesOrder GROUP BY Status ORDER BY cnt DESC")
    print("Status counts:")
    for r in cursor.fetchall():
        print(f"  {r[0]}: {r[1]}")
conn.close()
