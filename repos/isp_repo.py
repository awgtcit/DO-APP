"""
ISP Status repository — DB access for the Information Security Policy
acceptance tracking (admin view).
Every query is parameterized.
"""

from db.transaction import read_only


def _r2d(cursor, row) -> dict:
    """Convert a pyodbc Row to a plain dict."""
    return dict(zip([c[0] for c in cursor.description], row))


def get_all_isp_records(
    search: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    """
    Return all ISP acceptance records with optional email search,
    ordered by created date descending, plus total count.
    """
    base = " FROM Isp_Status WHERE 1=1 "
    params: list = []

    if search:
        base += " AND email LIKE ? "
        params.append(f"%{search}%")

    count_sql = f"SELECT COUNT(*) {base}"
    list_sql = f"""
        SELECT id, email, status, created, modified
        {base}
        ORDER BY created DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    with read_only() as cursor:
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * per_page
        cursor.execute(list_sql, params + [offset, per_page])
        rows = [_r2d(cursor, r) for r in cursor.fetchall()]

    return rows, total


def get_isp_stats() -> dict:
    """Return quick ISP acceptance stats."""
    sql = """
        SELECT
            COUNT(*) AS total_accepted,
            MIN(created) AS first_accepted,
            MAX(created) AS last_accepted
        FROM Isp_Status
    """
    with read_only() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        if not row:
            return {"total_accepted": 0, "first_accepted": None, "last_accepted": None}
        return _r2d(cursor, row)
