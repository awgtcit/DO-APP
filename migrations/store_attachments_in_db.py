"""
Migration: Store attachment files in the database instead of filesystem.

Adds:
  - FileData     VARBINARY(MAX)  — binary file content
  - ContentType  VARCHAR(200)    — MIME type (e.g. application/pdf)

Also back-fills existing attachments from their DirPath on disk.
"""
import sys, os, mimetypes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection


TABLE = "Intra_SalesOrder_Approved_Attachments"

COLUMNS = [
    ("FileData",    "VARBINARY(MAX)"),
    ("ContentType", "VARCHAR(200)"),
]


def column_exists(cursor, table, column):
    cursor.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
        [table, column],
    )
    return cursor.fetchone() is not None


def run():
    conn = get_connection()
    cur = conn.cursor()

    # 1. Add columns if missing
    for col_name, col_type in COLUMNS:
        if column_exists(cur, TABLE, col_name):
            print(f"  Column {col_name} already exists — skipped")
        else:
            cur.execute(f"ALTER TABLE {TABLE} ADD {col_name} {col_type} NULL")
            print(f"  Added column {col_name} ({col_type})")

    conn.commit()

    # 2. Back-fill existing attachments from disk
    cur.execute(
        "SELECT id, FileName, DirPath FROM " + TABLE
        + " WHERE FileData IS NULL"
    )
    rows = cur.fetchall()
    filled = 0
    for att_id, file_name, dir_path in rows:
        # Try multiple possible locations
        paths_to_try = [str(dir_path)]
        # Also try static/uploads path
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        static_path = os.path.join(base, "static", "uploads", "do_attachments")
        if file_name:
            # Files are stored as {order_id}_{filename}
            for f in os.listdir(static_path) if os.path.isdir(static_path) else []:
                if f.endswith(file_name):
                    paths_to_try.append(os.path.join(static_path, f))

        file_bytes = None
        for p in paths_to_try:
            if p and os.path.isfile(p):
                with open(p, "rb") as fh:
                    file_bytes = fh.read()
                print(f"  Read {len(file_bytes)} bytes from {p}")
                break

        if file_bytes:
            content_type = mimetypes.guess_type(file_name or "")[0] or "application/octet-stream"
            cur.execute(
                "UPDATE " + TABLE + " SET FileData=?, ContentType=? WHERE id=?",
                [file_bytes, content_type, att_id],
            )
            filled += 1
            print(f"  Backfilled attachment id={att_id} ({file_name}) — {content_type}")
        else:
            print(f"  WARNING: Could not find file for attachment id={att_id} ({dir_path})")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. Backfilled {filled}/{len(rows)} attachments.")


if __name__ == "__main__":
    run()
