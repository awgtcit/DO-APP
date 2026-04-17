"""
IT Support ticket repository — all database access for the IT Support module.
Every query is parameterized (no string interpolation).
"""

from db.connection import get_connection
from db.transaction import transactional, read_only


# ── Read ────────────────────────────────────────────────────────────

def get_all_tickets(
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """
    Retrieve tickets with optional filtering, search, and pagination.
    Returns (rows, total_count).
    """
    where_clauses = []
    params: list = []

    if status:
        where_clauses.append("t.status = ?")
        params.append(status)

    if search:
        where_clauses.append(
            "(t.subject LIKE ? OR t.summary LIKE ? OR t.requester LIKE ?)"
        )
        term = f"%{search}%"
        params.extend([term, term, term])

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    offset = (page - 1) * per_page

    # Count query
    count_sql = f"SELECT COUNT(*) FROM Intra_ITSupport t{where_sql}"

    # Data query with pagination
    data_sql = f"""
        SELECT t.*,
               u.FirstName + ' ' + u.LastName AS requester_name,
               COALESCE(u.EmailAddress, uc.CredEmail) AS requester_email
        FROM Intra_ITSupport t
        LEFT JOIN Intra_UserCredentials uc
             ON t.requester = uc.CredEmail OR t.requester = uc.CredUsername
        LEFT JOIN Intra_Users u ON uc.EmpID = u.EmpID
        {where_sql}
        ORDER BY t.id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    with read_only() as cursor:
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        cursor.execute(data_sql, params + [offset, per_page])
        rows = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

    return rows, total


def get_ticket_by_id(ticket_id: int) -> dict | None:
    """Get a single ticket by its ID."""
    sql = """
        SELECT t.*,
               u.FirstName + ' ' + u.LastName AS requester_name,
               COALESCE(u.EmailAddress, uc.CredEmail) AS requester_email
        FROM Intra_ITSupport t
        LEFT JOIN Intra_UserCredentials uc
             ON t.requester = uc.CredEmail OR t.requester = uc.CredUsername
        LEFT JOIN Intra_Users u ON uc.EmpID = u.EmpID
        WHERE t.id = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (ticket_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def count_tickets_by_empid(emp_id: str, status: str | None = None) -> int:
    """Count tickets for a specific employee, optionally filtered by status."""
    if status:
        sql = "SELECT COUNT(*) FROM Intra_ITSupport WHERE requester = ? AND [status] = ?"
        params = (emp_id, status)
    else:
        sql = "SELECT COUNT(*) FROM Intra_ITSupport WHERE requester = ?"
        params = (emp_id,)

    with read_only() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()[0]


# ── Write ───────────────────────────────────────────────────────────

def create_ticket(data: dict) -> int:
    """
    Insert a new IT Support ticket.
    Returns the new ticket ID.
    """
    sql = """
        INSERT INTO Intra_ITSupport
            (requester, subject, onBehalfOf, summary, priority, [status], created_on)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, 'open', GETDATE())
    """
    with transactional() as (conn, cursor):
        cursor.execute(
            sql,
            (
                data["requester_email"],
                data["subject"],
                data.get("on_behalf_of", ""),
                data["summary"],
                data["priority"],
            ),
        )
        new_id = cursor.fetchone()[0]
    return new_id


def update_ticket(ticket_id: int, data: dict) -> bool:
    """Update an existing ticket's mutable fields."""
    sql = """
        UPDATE Intra_ITSupport
        SET subject = ?,
            summary = ?,
            priority = ?,
            onBehalfOf = ?,
            [status] = ?
        WHERE id = ?
    """
    with transactional() as (conn, cursor):
        cursor.execute(
            sql,
            (
                data["subject"],
                data["summary"],
                data["priority"],
                data.get("on_behalf_of", ""),
                data.get("status", "open"),
                ticket_id,
            ),
        )
        return cursor.rowcount > 0


def update_ticket_status(ticket_id: int, status: str) -> bool:
    """Change ticket status only."""
    sql = "UPDATE Intra_ITSupport SET [status] = ? WHERE id = ?"
    with transactional() as (conn, cursor):
        cursor.execute(sql, (status, ticket_id))
        return cursor.rowcount > 0


def delete_ticket(ticket_id: int) -> bool:
    """Hard-delete a ticket (soft-delete preferred in production)."""
    sql = "DELETE FROM Intra_ITSupport WHERE id = ?"
    with transactional() as (conn, cursor):
        cursor.execute(sql, (ticket_id,))
        return cursor.rowcount > 0


# ── Dashboard stats ─────────────────────────────────────────────────

def get_ticket_stats() -> dict:
    """Return aggregate counts for the dashboard."""
    sql = """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN [status] = 'open' THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE WHEN [status] = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
            SUM(CASE WHEN [status] = 'closed' THEN 1 ELSE 0 END) AS closed_count
        FROM Intra_ITSupport
    """
    with read_only() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        return {
            "total": row[0] or 0,
            "open": row[1] or 0,
            "in_progress": row[2] or 0,
            "closed": row[3] or 0,
        }


# ── Helpers ─────────────────────────────────────────────────────────

def _row_to_dict(cursor, row) -> dict:
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))
