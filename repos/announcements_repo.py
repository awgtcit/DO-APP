"""Repository – Announcements (Intra_Announcements + Intra_AnnouncementsSubMenu)."""

from db.transaction import read_only, transactional

# ─── helpers ────────────────────────────────────────────────────────
def _r2d(row, columns):
    if row is None:
        return None
    return dict(zip([c[0] for c in columns], row))


def _rows(cursor):
    cols = cursor.description
    return [_r2d(r, cols) for r in cursor.fetchall()]


# ─── Categories (SubMenu) ──────────────────────────────────────────
def get_categories():
    with read_only() as cur:
        cur.execute(
            "SELECT id, CAST(SubMenuName AS VARCHAR(200)) AS SubMenuName "
            "FROM Intra_AnnouncementsSubMenu ORDER BY SubMenuName ASC"
        )
        return _rows(cur)


def get_category_by_id(cat_id):
    with read_only() as cur:
        cur.execute(
            "SELECT id, CAST(SubMenuName AS VARCHAR(200)) AS SubMenuName "
            "FROM Intra_AnnouncementsSubMenu WHERE id = ?",
            (cat_id,),
        )
        return _r2d(cur.fetchone(), cur.description)


def create_category(name, created_by):
    with transactional() as (conn, cur):
        cur.execute(
            "INSERT INTO Intra_AnnouncementsSubMenu "
            "(SubMenuName, created_on, created_by) "
            "VALUES (?, GETDATE(), ?)",
            (name, created_by),
        )
        cur.execute("SELECT SCOPE_IDENTITY()")
        return cur.fetchone()[0]


# ─── Announcements ─────────────────────────────────────────────────
def get_announcements(category_id=None, page=1, per_page=20, search=None):
    """Return paginated announcements, optionally filtered by category."""
    filters = []
    params = []

    if category_id:
        filters.append("a.SubMenuNameID = ?")
        params.append(category_id)
    if search:
        filters.append(
            "(CAST(a.AnnouncementSubject AS VARCHAR(500)) LIKE ? "
            " OR CAST(a.AnnouncementBody AS VARCHAR(MAX)) LIKE ?)"
        )
        params += [f"%{search}%", f"%{search}%"]

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    with read_only() as cur:
        cur.execute(f"SELECT COUNT(*) FROM Intra_Announcements a {where}", params)
        total = cur.fetchone()[0]
        total_pages = max(1, -(-total // per_page))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page

        cur.execute(
            f"""
            SELECT a.id,
                   a.SubMenuNameID,
                   CAST(a.AnnouncementSubject AS VARCHAR(500)) AS AnnouncementSubject,
                   CAST(a.AnnouncementBody AS VARCHAR(MAX))    AS AnnouncementBody,
                   CAST(a.Attachments AS VARCHAR(MAX))         AS Attachments,
                   a.created_on,
                   CAST(a.created_by AS VARCHAR(200))          AS created_by,
                   CAST(s.SubMenuName AS VARCHAR(200))         AS CategoryName
            FROM Intra_Announcements a
            LEFT JOIN Intra_AnnouncementsSubMenu s ON s.id = a.SubMenuNameID
            {where}
            ORDER BY a.created_on DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """,
            params + [offset, per_page],
        )
        rows = _rows(cur)

    meta = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }
    return rows, meta


def get_announcement_by_id(ann_id):
    with read_only() as cur:
        cur.execute(
            """
            SELECT a.id,
                   a.SubMenuNameID,
                   CAST(a.AnnouncementSubject AS VARCHAR(500)) AS AnnouncementSubject,
                   CAST(a.AnnouncementBody AS VARCHAR(MAX))    AS AnnouncementBody,
                   CAST(a.Attachments AS VARCHAR(MAX))         AS Attachments,
                   a.created_on,
                   CAST(a.created_by AS VARCHAR(200))          AS created_by,
                   CAST(s.SubMenuName AS VARCHAR(200))         AS CategoryName
            FROM Intra_Announcements a
            LEFT JOIN Intra_AnnouncementsSubMenu s ON s.id = a.SubMenuNameID
            WHERE a.id = ?
            """,
            (ann_id,),
        )
        return _r2d(cur.fetchone(), cur.description)


def create_announcement(data, created_by):
    with transactional() as (conn, cur):
        cur.execute(
            """
            INSERT INTO Intra_Announcements
                (SubMenuNameID, AnnouncementSubject, AnnouncementBody,
                 Attachments, created_on, created_by)
            VALUES (?, ?, ?, ?, GETDATE(), ?)
            """,
            (
                data["category_id"],
                data["subject"],
                data["body"],
                data.get("attachments", ""),
                created_by,
            ),
        )
        cur.execute("SELECT SCOPE_IDENTITY()")
        return cur.fetchone()[0]


def update_announcement(ann_id, data):
    with transactional() as (conn, cur):
        cur.execute(
            """
            UPDATE Intra_Announcements
            SET SubMenuNameID       = ?,
                AnnouncementSubject = ?,
                AnnouncementBody    = ?,
                Attachments         = ?
            WHERE id = ?
            """,
            (
                data["category_id"],
                data["subject"],
                data["body"],
                data.get("attachments", ""),
                ann_id,
            ),
        )
        return cur.rowcount


def delete_announcement(ann_id):
    with transactional() as (conn, cur):
        cur.execute("DELETE FROM Intra_Announcements WHERE id = ?", (ann_id,))
        return cur.rowcount
