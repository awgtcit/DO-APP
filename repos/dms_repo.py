"""
DMS repository — all database access for the Document Management System.
Tables: Intra_DMS_Document, Intra_DMS_Permission, Intra_DMS_Department,
        Intra_DMS_DocumentType, Intra_DMS_DocumentStatus, Intra_DMS_Company,
        Intra_DMS_Party, Intra_DMS_DocumentAttachment.
Every query is parameterized.
"""

from db.transaction import transactional, read_only


# ═══════════════════════════════════════════════════════════════
#  Lookup / reference data
# ═══════════════════════════════════════════════════════════════

def get_departments() -> list[dict]:
    """Return all DMS departments."""
    sql = "SELECT id, CAST(Name AS VARCHAR(200)) AS Name FROM Intra_DMS_Department ORDER BY Name"
    with read_only() as cur:
        cur.execute(sql)
        return [_r2d(cur, r) for r in cur.fetchall()]


def get_document_types() -> list[dict]:
    sql = "SELECT id, CAST(Name AS VARCHAR(200)) AS Name FROM Intra_DMS_DocumentType ORDER BY Name"
    with read_only() as cur:
        cur.execute(sql)
        return [_r2d(cur, r) for r in cur.fetchall()]


def get_document_statuses() -> list[dict]:
    sql = "SELECT id, CAST(Name AS VARCHAR(200)) AS Name FROM Intra_DMS_DocumentStatus ORDER BY id"
    with read_only() as cur:
        cur.execute(sql)
        return [_r2d(cur, r) for r in cur.fetchall()]


def get_companies() -> list[dict]:
    sql = "SELECT id, CAST(Name AS VARCHAR(200)) AS Name FROM Intra_DMS_Company ORDER BY Name"
    with read_only() as cur:
        cur.execute(sql)
        return [_r2d(cur, r) for r in cur.fetchall()]


def get_parties() -> list[dict]:
    sql = "SELECT id, CAST(Name AS VARCHAR(200)) AS Name FROM Intra_DMS_Party ORDER BY Name"
    with read_only() as cur:
        cur.execute(sql)
        return [_r2d(cur, r) for r in cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  Permissions
# ═══════════════════════════════════════════════════════════════

def get_user_dms_permissions(emp_id: int) -> list[dict]:
    """Get all DMS permission rows for a user (one per department)."""
    sql = """
        SELECT dp.*, CAST(dd.Name AS VARCHAR(200)) AS DepartmentName
        FROM Intra_DMS_Permission dp
        LEFT JOIN Intra_DMS_Department dd ON dp.DepartmentID = dd.id
        WHERE dp.EmpID = ?
        ORDER BY dd.Name
    """
    with read_only() as cur:
        cur.execute(sql, [emp_id])
        return [_r2d(cur, r) for r in cur.fetchall()]


def is_dms_itadmin(emp_id: int) -> bool:
    """Check if user has ITAdmin flag in any department."""
    sql = "SELECT TOP 1 1 FROM Intra_DMS_Permission WHERE EmpID = ? AND ITAdmin = 1"
    with read_only() as cur:
        cur.execute(sql, [emp_id])
        return cur.fetchone() is not None


def get_user_role_for_department(emp_id: int, dept_id: int) -> dict | None:
    """Get user's DMS role flags for a specific department."""
    sql = """
        SELECT Uploader, Approver, Reviewer1, Reviewer2, ITAdmin
        FROM Intra_DMS_Permission
        WHERE EmpID = ? AND DepartmentID = ?
    """
    with read_only() as cur:
        cur.execute(sql, [emp_id, dept_id])
        row = cur.fetchone()
        return _r2d(cur, row) if row else None


def get_users_by_role_in_department(dept_id: int, role: str) -> list[dict]:
    """Get all users with a specific DMS role in a department.
    role: 'Uploader', 'Approver', 'Reviewer1', 'Reviewer2', 'ITAdmin'
    """
    valid_roles = {"Uploader", "Approver", "Reviewer1", "Reviewer2", "ITAdmin"}
    if role not in valid_roles:
        return []
    sql = f"""
        SELECT dp.EmpID, u.FirstName, u.LastName, u.EmailAddress
        FROM Intra_DMS_Permission dp
        LEFT JOIN Intra_Users u ON dp.EmpID = u.EmpID
        WHERE dp.DepartmentID = ? AND dp.{role} = 1
    """
    with read_only() as cur:
        cur.execute(sql, [dept_id])
        return [_r2d(cur, r) for r in cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  Documents — listing
# ═══════════════════════════════════════════════════════════════

def get_documents_for_department(
    dept_id: int,
    emp_id: int,
    is_itadmin: bool = False,
    is_reviewer2: bool = False,
    status_id: int | None = None,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """
    Get paginated documents for a department.
    Reviewer2 for non-own departments: only see status 3 or 7.
    """
    where = ["d.DeptID = ?"]
    params: list = [dept_id]

    # Reviewer2 visibility: non-own department sees only status 3, 7
    if is_reviewer2 and not is_itadmin:
        where.append("d.DocStatusID IN (3, 7)")

    if status_id:
        where.append("d.DocStatusID = ?")
        params.append(status_id)

    if search:
        where.append("(CAST(d.Name AS VARCHAR(500)) LIKE ? OR CAST(d.Description AS VARCHAR(500)) LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term])

    where_sql = " WHERE " + " AND ".join(where)
    offset = (page - 1) * per_page

    count_sql = f"SELECT COUNT(*) FROM Intra_DMS_Document d{where_sql}"
    data_sql = f"""
        SELECT d.id,
               CAST(d.Name AS VARCHAR(500)) AS Name,
               CAST(d.Description AS VARCHAR(2000)) AS Description,
               d.DeptID, d.DocTypeID, d.DocStatusID, d.CompanyID, d.PartyID,
               d.Confidential,
               CONVERT(VARCHAR(10), d.ValidFrom, 120) AS ValidFrom,
               CONVERT(VARCHAR(10), d.ValidTo, 120) AS ValidTo,
               CONVERT(VARCHAR(19), d.Created_on, 120) AS Created_on,
               d.Created_by,
               CAST(ds.Name AS VARCHAR(100)) AS StatusName,
               CAST(dt.Name AS VARCHAR(200)) AS DocTypeName,
               ISNULL(u.FirstName + ' ' + u.LastName, '') AS CreatedByName
        FROM Intra_DMS_Document d
        LEFT JOIN Intra_DMS_DocumentStatus ds ON d.DocStatusID = ds.id
        LEFT JOIN Intra_DMS_DocumentType dt ON d.DocTypeID = dt.id
        LEFT JOIN Intra_Users u ON d.Created_by = u.EmpID
        {where_sql}
        ORDER BY d.id DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    with read_only() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()[0]
        cur.execute(data_sql, params + [offset, per_page])
        rows = [_r2d(cur, r) for r in cur.fetchall()]

    return rows, total


# ═══════════════════════════════════════════════════════════════
#  Documents — single
# ═══════════════════════════════════════════════════════════════

def get_document_by_id(doc_id: int) -> dict | None:
    """Load a single document with all lookups (7-table JOIN)."""
    sql = """
        SELECT d.id,
               CAST(d.Name AS VARCHAR(500)) AS Name,
               CAST(d.Description AS VARCHAR(4000)) AS Description,
               d.DeptID, d.DocTypeID, d.DocStatusID, d.CompanyID, d.PartyID,
               d.Confidential,
               CAST(d.Remarks AS VARCHAR(4000)) AS Remarks,
               CONVERT(VARCHAR(10), d.ValidFrom, 120) AS ValidFrom,
               CONVERT(VARCHAR(10), d.ValidTo, 120) AS ValidTo,
               CONVERT(VARCHAR(19), d.Created_on, 120) AS Created_on,
               CONVERT(VARCHAR(19), d.Modified_on, 120) AS Modified_on,
               d.Created_by, d.Modified_by,
               CAST(dt.Name AS VARCHAR(200)) AS DocTypeName,
               CAST(dd.Name AS VARCHAR(200)) AS DepartmentName,
               CAST(dc.Name AS VARCHAR(200)) AS CompanyName,
               CAST(dp.Name AS VARCHAR(200)) AS PartyName,
               CAST(ds.Name AS VARCHAR(100)) AS StatusName,
               ISNULL(u.FirstName + ' ' + u.LastName, '') AS CreatedByName,
               CASE WHEN d.Confidential = 1 THEN 'Yes' ELSE 'No' END AS ConfidentialLabel
        FROM Intra_DMS_Document d
        LEFT JOIN Intra_DMS_DocumentType dt ON d.DocTypeID = dt.id
        LEFT JOIN Intra_DMS_Department dd ON d.DeptID = dd.id
        LEFT JOIN Intra_DMS_Company dc ON d.CompanyID = dc.id
        LEFT JOIN Intra_DMS_Party dp ON d.PartyID = dp.id
        LEFT JOIN Intra_DMS_DocumentStatus ds ON d.DocStatusID = ds.id
        LEFT JOIN Intra_Users u ON d.Created_by = u.EmpID
        WHERE d.id = ?
    """
    with read_only() as cur:
        cur.execute(sql, [doc_id])
        row = cur.fetchone()
        return _r2d(cur, row) if row else None


def get_document_attachments(doc_id: int) -> list[dict]:
    """Get all active attachments for a document."""
    sql = """
        SELECT id, DocumentID,
               CAST(Name AS VARCHAR(500)) AS Name,
               CAST(Description AS VARCHAR(2000)) AS Description,
               CONVERT(VARCHAR(10), ValidFrom, 120) AS ValidFrom,
               CONVERT(VARCHAR(10), ValidTo, 120) AS ValidTo,
               Status,
               CONVERT(VARCHAR(19), Created_on, 120) AS Created_on
        FROM Intra_DMS_DocumentAttachment
        WHERE DocumentID = ? AND ISNULL(Status, '1') = '1'
        ORDER BY id
    """
    with read_only() as cur:
        cur.execute(sql, [doc_id])
        return [_r2d(cur, r) for r in cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  Documents — CRUD
# ═══════════════════════════════════════════════════════════════

def create_document(data: dict) -> int:
    """Insert a new DMS document (status = 1 DRAFT). Returns new ID."""
    sql = """
        INSERT INTO Intra_DMS_Document
            (Name, Description, ValidFrom, ValidTo, DeptID, DocTypeID,
             CompanyID, PartyID, Confidential, DocStatusID,
             Created_on, Created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE(), ?)
    """
    with transactional() as (conn, cur):
        cur.execute(sql, [
            data["name"], data.get("description", ""),
            data.get("valid_from"), data.get("valid_to"),
            data["dept_id"], data["doc_type_id"],
            data.get("company_id"), data.get("party_id"),
            1 if data.get("confidential") else 0,
            data["created_by"],
        ])
        cur.execute("SELECT SCOPE_IDENTITY()")
        return int(cur.fetchone()[0])


def update_document(doc_id: int, data: dict) -> bool:
    """Update a DRAFT document's editable fields."""
    sql = """
        UPDATE Intra_DMS_Document
        SET Name = ?, Description = ?, ValidFrom = ?, ValidTo = ?,
            DocTypeID = ?, CompanyID = ?, PartyID = ?, Confidential = ?,
            Modified_on = GETDATE(), Modified_by = ?
        WHERE id = ? AND DocStatusID = 1
    """
    with transactional() as (conn, cur):
        cur.execute(sql, [
            data["name"], data.get("description", ""),
            data.get("valid_from"), data.get("valid_to"),
            data["doc_type_id"],
            data.get("company_id"), data.get("party_id"),
            1 if data.get("confidential") else 0,
            data["modified_by"], doc_id,
        ])
        return cur.rowcount > 0


def update_document_status(doc_id: int, status_id: int, emp_id: int, remarks: str = "") -> bool:
    """Change document status. Core workflow transition."""
    sql = """
        UPDATE Intra_DMS_Document
        SET DocStatusID = ?, Remarks = ?, Modified_on = GETDATE(), Modified_by = ?
        WHERE id = ?
    """
    with transactional() as (conn, cur):
        cur.execute(sql, [status_id, remarks, emp_id, doc_id])
        return cur.rowcount > 0


# ═══════════════════════════════════════════════════════════════
#  Attachments — CRUD
# ═══════════════════════════════════════════════════════════════

def add_attachment(data: dict) -> int:
    """Add an attachment to a document. Returns new attachment ID."""
    sql = """
        INSERT INTO Intra_DMS_DocumentAttachment
            (DocumentID, Name, Description, ValidFrom, ValidTo, Status, Created_on, Created_by)
        VALUES (?, ?, ?, ?, ?, '1', GETDATE(), ?)
    """
    with transactional() as (conn, cur):
        cur.execute(sql, [
            data["document_id"], data["name"],
            data.get("description", ""),
            data.get("valid_from"), data.get("valid_to"),
            data["created_by"],
        ])
        cur.execute("SELECT SCOPE_IDENTITY()")
        return int(cur.fetchone()[0])


def delete_attachment(attachment_id: int) -> bool:
    """Soft-delete an attachment (set Status = '0')."""
    sql = "UPDATE Intra_DMS_DocumentAttachment SET Status = '0' WHERE id = ?"
    with transactional() as (conn, cur):
        cur.execute(sql, [attachment_id])
        return cur.rowcount > 0


# ═══════════════════════════════════════════════════════════════
#  Admin — CRUD for lookup tables
# ═══════════════════════════════════════════════════════════════

def create_department(name: str, created_by: int) -> int:
    sql = "INSERT INTO Intra_DMS_Department (Name, Created_by, Modified_on) VALUES (?, ?, GETDATE())"
    with transactional() as (conn, cur):
        cur.execute(sql, [name, created_by])
        cur.execute("SELECT SCOPE_IDENTITY()")
        return int(cur.fetchone()[0])


def create_document_type(name: str, created_by: int) -> int:
    sql = "INSERT INTO Intra_DMS_DocumentType (Name, Created_by, Modified_on) VALUES (?, ?, GETDATE())"
    with transactional() as (conn, cur):
        cur.execute(sql, [name, created_by])
        cur.execute("SELECT SCOPE_IDENTITY()")
        return int(cur.fetchone()[0])


def create_company(name: str, created_by: int) -> int:
    sql = "INSERT INTO Intra_DMS_Company (Name, Created_by, Modified_on) VALUES (?, ?, GETDATE())"
    with transactional() as (conn, cur):
        cur.execute(sql, [name, created_by])
        cur.execute("SELECT SCOPE_IDENTITY()")
        return int(cur.fetchone()[0])


def create_party(name: str, created_by: int) -> int:
    sql = "INSERT INTO Intra_DMS_Party (Name, Created_by, Modified_on) VALUES (?, ?, GETDATE())"
    with transactional() as (conn, cur):
        cur.execute(sql, [name, created_by])
        cur.execute("SELECT SCOPE_IDENTITY()")
        return int(cur.fetchone()[0])


# ═══════════════════════════════════════════════════════════════
#  Dashboard stats
# ═══════════════════════════════════════════════════════════════

def get_dms_stats(dept_id: int | None = None) -> dict:
    """Return counts by status for dashboard KPIs."""
    where = f" WHERE DeptID = {dept_id}" if dept_id else ""
    # Using parameterized approach
    if dept_id:
        sql = """
            SELECT COUNT(*) AS total,
                SUM(CASE WHEN DocStatusID = 1 THEN 1 ELSE 0 END) AS draft,
                SUM(CASE WHEN DocStatusID = 2 THEN 1 ELSE 0 END) AS submitted,
                SUM(CASE WHEN DocStatusID = 3 THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN DocStatusID = 7 THEN 1 ELSE 0 END) AS finalized,
                SUM(CASE WHEN DocStatusID IN (4, 8) THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN DocStatusID = 9 THEN 1 ELSE 0 END) AS cancelled
            FROM Intra_DMS_Document WHERE DeptID = ?
        """
        params = [dept_id]
    else:
        sql = """
            SELECT COUNT(*) AS total,
                SUM(CASE WHEN DocStatusID = 1 THEN 1 ELSE 0 END) AS draft,
                SUM(CASE WHEN DocStatusID = 2 THEN 1 ELSE 0 END) AS submitted,
                SUM(CASE WHEN DocStatusID = 3 THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN DocStatusID = 7 THEN 1 ELSE 0 END) AS finalized,
                SUM(CASE WHEN DocStatusID IN (4, 8) THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN DocStatusID = 9 THEN 1 ELSE 0 END) AS cancelled
            FROM Intra_DMS_Document
        """
        params = []

    with read_only() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        if not row:
            return {k: 0 for k in ("total", "draft", "submitted", "approved", "finalized", "rejected", "cancelled")}
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _r2d(cursor, row) -> dict:
    """Convert a pyodbc Row to a dict."""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))
