"""Repository – Facility requests (Intra_TechFacility + Comments)."""

from db.transaction import read_only, transactional

def _r2d(row, columns):
    if row is None:
        return None
    return dict(zip([c[0] for c in columns], row))

def _rows(cursor):
    cols = cursor.description
    return [_r2d(r, cols) for r in cursor.fetchall()]


# ─── Site choices ───────────────────────────────────────────────────
SITES = [
    ("MTC_Office", "MTC Office"),
    ("MTC_Ripping_Area", "MTC Ripping Area"),
    ("MTC_Feeder_Area", "MTC Feeder Area"),
    ("MTC_A1_Prod", "MTC A1 Prod"),
    ("MTC_A2_Prod", "MTC A2 Prod"),
    ("MTC_A3_Prod", "MTC A3 Prod"),
    ("MTC_A4_Prod", "MTC A4 Prod"),
    ("MTC_A5_Prod", "MTC A5 Prod"),
    ("MTC_A6_Prod", "MTC A6 Prod"),
    ("MTC_A7_Prod", "MTC A7 Prod"),
    ("MTC_A8", "MTC A8"),
    ("MTC_A11", "MTC A11"),
    ("MTC_Filter_Area", "MTC Filter Area"),
    ("MTC_Utilities", "MTC Utilities"),
    ("UTC_Office", "UTF Office"),
    ("UTC_Warehouse", "UTF Warehouse"),
    ("UTF_New_Prod", "UTF New Prod"),
    ("UTF_Old_Prod", "UTF Old Prod"),
    ("UTF_Utilities", "UTF Utilities"),
]


# ─── Stats / counts ────────────────────────────────────────────────
def get_counts(emp_id=None):
    """Return {total, open, closed} counts."""
    with read_only() as cur:
        if emp_id:
            cur.execute(
                "SELECT COUNT(*) FROM Intra_TechFacility WHERE EmpID = ?",
                (emp_id,),
            )
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM Intra_TechFacility WHERE EmpID = ? AND status = 'open'",
                (emp_id,),
            )
            opened = cur.fetchone()[0]
        else:
            cur.execute("SELECT COUNT(*) FROM Intra_TechFacility")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM Intra_TechFacility WHERE status = 'open'"
            )
            opened = cur.fetchone()[0]
        return {"total": total, "open": opened, "closed": total - opened}


# ─── Listing ────────────────────────────────────────────────────────
def get_requests(emp_id=None, status=None, page=1, per_page=20, search=None):
    filters = []
    params = []

    if emp_id:
        filters.append("f.EmpID = ?")
        params.append(emp_id)
    if status:
        filters.append("f.status = ?")
        params.append(status)
    if search:
        filters.append(
            "(CAST(f.subject AS VARCHAR(500)) LIKE ? "
            " OR CAST(f.summary AS VARCHAR(MAX)) LIKE ?)"
        )
        params += [f"%{search}%", f"%{search}%"]

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    with read_only() as cur:
        cur.execute(f"SELECT COUNT(*) FROM Intra_TechFacility f {where}", params)
        total = cur.fetchone()[0]
        total_pages = max(1, -(-total // per_page))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page

        cur.execute(
            f"""
            SELECT f.id,
                   f.EmpID,
                   CAST(f.subject AS VARCHAR(500))  AS subject,
                   CAST(f.site AS VARCHAR(200))     AS site,
                   CAST(f.status AS VARCHAR(50))    AS status,
                   f.created_on,
                   f.closed_on,
                   f.deadline,
                   f.lastUpdateDate,
                   u.FirstName,
                   u.LastName
            FROM Intra_TechFacility f
            LEFT JOIN Intra_Users u ON u.EmpID = f.EmpID
            {where}
            ORDER BY f.created_on DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """,
            params + [offset, per_page],
        )
        rows = _rows(cur)

    meta = {"page": page, "per_page": per_page, "total": total, "total_pages": total_pages}
    return rows, meta


# ─── Single request ─────────────────────────────────────────────────
def get_request_by_id(req_id):
    with read_only() as cur:
        cur.execute(
            """
            SELECT f.id, f.EmpID,
                   CAST(f.subject AS VARCHAR(500))    AS subject,
                   CAST(f.site AS VARCHAR(200))       AS site,
                   CAST(f.summary AS VARCHAR(MAX))    AS summary,
                   CAST(f.status AS VARCHAR(50))      AS status,
                   CAST(f.attachments AS VARCHAR(MAX)) AS attachments,
                   CAST(f.random_hex AS VARCHAR(50))  AS random_hex,
                   f.created_on,
                   f.closed_on,
                   f.deadline,
                   f.assigned_to,
                   f.lastUpdateDate,
                   u.FirstName,
                   u.LastName,
                   CAST(u.EmailAddress AS VARCHAR(200)) AS Email
            FROM Intra_TechFacility f
            LEFT JOIN Intra_Users u ON u.EmpID = f.EmpID
            WHERE f.id = ?
            """,
            (req_id,),
        )
        return _r2d(cur.fetchone(), cur.description)


# ─── Create ─────────────────────────────────────────────────────────
def create_request(data):
    with transactional() as (conn, cur):
        import secrets
        hex_val = secrets.token_hex(5)
        cur.execute(
            """
            INSERT INTO Intra_TechFacility
                (EmpID, subject, site, summary, random_hex, attachments,
                 status, created_on, deadline, assigned_to, lastUpdateDate)
            VALUES (?, ?, ?, ?, ?, ?, 'open', GETDATE(), 30, 1356, GETDATE())
            """,
            (
                data["emp_id"],
                data["subject"],
                data["site"],
                data["summary"],
                hex_val,
                data.get("attachments", "N/A"),
            ),
        )
        cur.execute("SELECT SCOPE_IDENTITY()")
        return int(cur.fetchone()[0])


# ─── Status change ──────────────────────────────────────────────────
def close_request(req_id):
    with transactional() as (conn, cur):
        cur.execute(
            "UPDATE Intra_TechFacility "
            "SET status = 'closed', closed_on = GETDATE(), lastUpdateDate = GETDATE() "
            "WHERE id = ?",
            (req_id,),
        )
        return cur.rowcount


def reopen_request(req_id):
    with transactional() as (conn, cur):
        cur.execute(
            "UPDATE Intra_TechFacility "
            "SET status = 'open', closed_on = NULL, lastUpdateDate = GETDATE() "
            "WHERE id = ?",
            (req_id,),
        )
        return cur.rowcount


# ─── Comments ───────────────────────────────────────────────────────
def get_comments(req_id):
    with read_only() as cur:
        cur.execute(
            """
            SELECT c.id, c.requestID, c.created_on,
                   CAST(c.description AS VARCHAR(MAX)) AS description,
                   c.comment_by,
                   CAST(c.request_status AS VARCHAR(50)) AS request_status,
                   u.FirstName, u.LastName
            FROM Intra_TechFacility_Comments c
            LEFT JOIN Intra_Users u ON u.EmpID = c.comment_by
            WHERE c.requestID = ?
            ORDER BY c.id DESC
            """,
            (req_id,),
        )
        return _rows(cur)


def add_comment(req_id, emp_id, description, request_status="open"):
    with transactional() as (conn, cur):
        cur.execute(
            """
            INSERT INTO Intra_TechFacility_Comments
                (requestID, created_on, description, comment_by, request_status)
            VALUES (?, GETDATE(), ?, ?, ?)
            """,
            (req_id, description, emp_id, request_status),
        )
        # Update parent lastUpdateDate
        cur.execute(
            "UPDATE Intra_TechFacility SET lastUpdateDate = GETDATE() WHERE id = ?",
            (req_id,),
        )
        return cur.rowcount
