"""Fix attachment WebPath from /uploads/ to /static/uploads/ so Flask can serve them."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

def run():
    conn = get_connection()
    cur = conn.cursor()

    # Show current state
    cur.execute("SELECT id, FileName, WebPath FROM Intra_SalesOrder_Approved_Attachments")
    for r in cur.fetchall():
        print(f"  id={r[0]}  file={r[1]}  web={r[2]}")

    # Fix paths (WebPath is TEXT type, must cast for REPLACE)
    cur.execute(
        "UPDATE Intra_SalesOrder_Approved_Attachments "
        "SET WebPath = CAST(REPLACE(CAST(WebPath AS NVARCHAR(MAX)), '/uploads/do_attachments/', '/static/uploads/do_attachments/') AS TEXT) "
        "WHERE CAST(WebPath AS NVARCHAR(MAX)) LIKE '/uploads/do_attachments/%'"
    )
    print(f"Updated {cur.rowcount} rows")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    run()
