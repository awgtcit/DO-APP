"""
Employee Forum repository — DB access for the employee directory,
profile lookup, and birthday queries.
Every query is parameterized.
"""

from db.transaction import read_only


def _r2d(cursor, row) -> dict:
    """Convert a pyodbc Row to a plain dict."""
    return dict(zip([c[0] for c in cursor.description], row))


# ── Directory listing ───────────────────────────────────────────

def get_directory(
    search: str | None = None,
    department: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[dict], int]:
    """
    Return active employees (EmpID > 100) with optional search and
    department filter, plus total count for pagination.
    """
    base = """
        FROM Intra_Users u
        LEFT JOIN Intra_Department d ON u.DeparmentID = d.id
        WHERE u.EmpID > 100
    """
    params: list = []

    if search:
        base += """
            AND (
                u.FirstName LIKE ? OR u.LastName LIKE ?
                OR u.EmailAddress LIKE ?
                OR CAST(u.ContactNo AS VARCHAR(50)) LIKE ?
            )
        """
        like = f"%{search}%"
        params.extend([like, like, like, like])

    if department:
        base += " AND d.name = ? "
        params.append(department)

    count_sql = f"SELECT COUNT(*) {base}"
    list_sql = f"""
        SELECT u.EmpID, u.FirstName, u.LastName, u.EmailAddress,
               CAST(u.ContactNo AS VARCHAR(50)) AS ContactNo,
               u.DeparmentID, u.DesignationID, u.DateOfBirth,
               d.name AS Department
        {base}
        ORDER BY u.FirstName, u.LastName
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    with read_only() as cursor:
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * per_page
        cursor.execute(list_sql, params + [offset, per_page])
        rows = [_r2d(cursor, r) for r in cursor.fetchall()]

    return rows, total


# ── Departments (for filter dropdown) ───────────────────────────

def get_departments() -> list[dict]:
    """Return all departments ordered by name."""
    sql = "SELECT id AS DeptID, name AS DeptName FROM Intra_Department ORDER BY name"
    with read_only() as cursor:
        cursor.execute(sql)
        return [_r2d(cursor, r) for r in cursor.fetchall()]


# ── Single employee profile ────────────────────────────────────

def get_employee(emp_id: int) -> dict | None:
    """Fetch a single employee with department name."""
    sql = """
        SELECT u.EmpID, u.FirstName, u.LastName, u.EmailAddress,
               CAST(u.ContactNo AS VARCHAR(50)) AS ContactNo,
               u.DeparmentID, u.DesignationID, u.DateOfBirth,
               d.name AS Department
        FROM Intra_Users u
        LEFT JOIN Intra_Department d ON u.DeparmentID = d.id
        WHERE u.EmpID = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (emp_id,))
        row = cursor.fetchone()
        return _r2d(cursor, row) if row else None


# ── Birthday list (current month) ──────────────────────────────

def get_birthdays_this_month() -> list[dict]:
    """
    Return employees whose birthday falls in the current month,
    ordered by day-of-month.
    """
    sql = """
        SELECT u.EmpID, u.FirstName, u.LastName, u.EmailAddress,
               u.DateOfBirth,
               d.name AS Department
        FROM Intra_Users u
        LEFT JOIN Intra_Department d ON u.DeparmentID = d.id
        WHERE u.EmpID > 100
          AND MONTH(u.DateOfBirth) = MONTH(GETDATE())
        ORDER BY DAY(u.DateOfBirth)
    """
    with read_only() as cursor:
        cursor.execute(sql)
        return [_r2d(cursor, r) for r in cursor.fetchall()]


# ── Directory stats ─────────────────────────────────────────────

def get_directory_stats() -> dict:
    """Return quick stats for the directory overview."""
    sql = """
        SELECT
            COUNT(*) AS total_employees,
            COUNT(DISTINCT u.DeparmentID) AS total_departments,
            SUM(CASE WHEN MONTH(u.DateOfBirth) = MONTH(GETDATE()) THEN 1 ELSE 0 END) AS birthdays_this_month
        FROM Intra_Users u
        WHERE u.EmpID > 100
    """
    with read_only() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        if not row:
            return {"total_employees": 0, "total_departments": 0, "birthdays_this_month": 0}
        return _r2d(cursor, row)
