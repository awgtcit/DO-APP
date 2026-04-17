"""
User repository — all DB access related to users & credentials.
Every query is parameterized.
"""

from db.transaction import transactional, read_only


def find_user_by_email(email: str) -> dict | None:
    """Look up a user by email address."""
    sql = """
        SELECT u.*, uc.CredUsername, uc.CredEmail
        FROM Intra_Users u
        INNER JOIN Intra_UserCredentials uc ON u.EmpID = uc.EmpID
        WHERE uc.CredEmail = ? OR u.EmailAddress = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (email, email))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def find_user_by_username(username: str) -> dict | None:
    """Look up a user by username or EmpID."""
    sql = """
        SELECT u.*, uc.CredUsername, uc.CredEmail, uc.CredPassword
        FROM Intra_Users u
        INNER JOIN Intra_UserCredentials uc ON u.EmpID = uc.EmpID
        WHERE uc.CredUsername = ? OR uc.CredEmail = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (username, username))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def find_user_by_empid(emp_id: int) -> dict | None:
    """Look up a user by EmpID."""
    sql = "SELECT * FROM Intra_Users WHERE EmpID = ?"
    with read_only() as cursor:
        cursor.execute(sql, (emp_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def get_all_users() -> list[dict]:
    """Return all users ordered by EmpID."""
    sql = "SELECT * FROM Intra_Users ORDER BY EmpID ASC"
    with read_only() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]


def get_isp_status(email: str) -> dict | None:
    """Check ISP acceptance status for a user."""
    sql = "SELECT * FROM Isp_Status WHERE email = ?"
    with read_only() as cursor:
        cursor.execute(sql, (email,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def upsert_isp_status(email: str, status: int) -> None:
    """Create or update ISP acceptance record."""
    existing = get_isp_status(email)
    with transactional() as (conn, cursor):
        if existing:
            cursor.execute(
                "UPDATE Isp_Status SET status = ?, modified = GETDATE() WHERE email = ?",
                (status, email),
            )
        else:
            cursor.execute(
                "INSERT INTO Isp_Status (email, status, created) VALUES (?, ?, GETDATE())",
                (email, status),
            )


def authenticate_db(username: str, password_hash: str) -> dict | None:
    """
    Look up credentials for a user in Intra_UserCredentials.
    Returns the user record for the caller to verify the password.
    NOTE: Legacy passwords are stored as MD5 hashes. The auth service
    handles comparison and will re-hash to bcrypt on successful login.
    """
    sql = """
        SELECT uc.*, u.FirstName, u.LastName, u.EmpID, u.EmailAddress,
               u.DeparmentID, u.DesignationID, u.GroupID
        FROM Intra_UserCredentials uc
        INNER JOIN Intra_Users u ON uc.EmpID = u.EmpID
        WHERE (uc.CredEmail = ? OR uc.CredUsername = ?)
    """
    with read_only() as cursor:
        cursor.execute(sql, (username, username))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def get_user_roles(emp_id: int, group_id: int | None = None) -> list[str]:
    """Build a roles list from DMS permissions, module access, and GroupID.

    Queries DMS permissions and module access separately so that a missing
    table does not prevent other role sources from loading.
    GroupID == 1 typically means IT / admin in the legacy system.
    """
    roles: set[str] = set()

    # GroupID-based roles (no DB query needed)
    if group_id == 1:
        roles.update(("it_admin", "admin"))

    # DMS permissions query
    dms_sql = """
        SELECT CAST(ISNULL(ITAdmin, 0) AS VARCHAR) AS val1,
               CAST(ISNULL(Uploader, 0) AS VARCHAR) AS val2,
               CAST(ISNULL(Approver, 0) AS VARCHAR) AS val3,
               CAST(CASE WHEN ISNULL(Reviewer1, 0) = 1 OR ISNULL(Reviewer2, 0) = 1
                    THEN 1 ELSE 0 END AS VARCHAR) AS val4
        FROM Intra_DMS_Permission WHERE EmpID = ?
    """
    try:
        with read_only() as cursor:
            cursor.execute(dms_sql, (emp_id,))
            row = cursor.fetchone()
            if row:
                d = _row_to_dict(cursor, row)
                if d["val1"] == "1":
                    roles.update(("it_admin", "admin"))
                if d["val2"] == "1":
                    roles.add("uploader")
                if d["val3"] == "1":
                    roles.add("approver")
                if d["val4"] == "1":
                    roles.add("reviewer")
    except Exception:
        pass  # Table may not exist in all environments

    # Module access query (separate so a missing table doesn't break DMS roles)
    mag_sql = """
        SELECT mag.Name AS GroupName
        FROM Intra_Module_UserAccess mua
        INNER JOIN Intra_Module_AccessGroup mag ON mua.AccessGroupID = mag.id
        WHERE mua.EmpID = ?
    """
    try:
        with read_only() as cursor:
            cursor.execute(mag_sql, (emp_id,))
            for row in cursor.fetchall():
                d = _row_to_dict(cursor, row)
                if d.get("GroupName"):
                    role_name = d["GroupName"].lower().replace(" ", "_")
                    if role_name:
                        roles.add(role_name)
    except Exception:
        pass  # Tables may not exist in all environments

    return list(roles)


# ── Helpers ─────────────────────────────────────────────────────────
def _row_to_dict(cursor, row) -> dict:
    """Convert a pyodbc Row to a dictionary."""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))
