"""
Admin Settings repository — DB access for users, restricted words,
module configuration, and workflow management.
"""

import bcrypt
import pyodbc

from db.transaction import transactional, read_only


# ── Helpers ─────────────────────────────────────────────────────
def _row_to_dict(cursor, row) -> dict:
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def _rows_to_list(cursor, rows) -> list[dict]:
    return [_row_to_dict(cursor, r) for r in rows]


# ═══════════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def get_all_users_full() -> list[dict]:
    """All users with credentials and department info."""
    sql = """
        SELECT u.EmpID, u.FirstName, u.LastName, u.EmailAddress,
               u.DeparmentID, u.DesignationID, u.GroupID,
               uc.CredUsername, uc.CredEmail,
               d.name AS DepartmentName
        FROM Intra_Users u
        LEFT JOIN Intra_UserCredentials uc ON u.EmpID = uc.EmpID
        LEFT JOIN Intra_Department d ON u.DeparmentID = d.id
        ORDER BY u.FirstName, u.LastName
    """
    with read_only() as cursor:
        cursor.execute(sql)
        return _rows_to_list(cursor, cursor.fetchall())


def get_user_by_empid(emp_id: int) -> dict | None:
    sql = """
        SELECT u.*, uc.CredUsername, uc.CredEmail
        FROM Intra_Users u
        LEFT JOIN Intra_UserCredentials uc ON u.EmpID = uc.EmpID
        WHERE u.EmpID = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (emp_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def get_user_by_email(email: str) -> dict | None:
    """Look up a local user by primary or credential email."""
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    sql = """
        SELECT TOP 1 u.*, uc.CredUsername, uc.CredEmail
        FROM Intra_Users u
        LEFT JOIN Intra_UserCredentials uc ON u.EmpID = uc.EmpID
        WHERE LOWER(LTRIM(RTRIM(ISNULL(u.EmailAddress, '')))) = ?
           OR LOWER(LTRIM(RTRIM(ISNULL(uc.CredEmail, '')))) = ?
        ORDER BY u.EmpID
    """
    with read_only() as cursor:
        cursor.execute(sql, (normalized_email, normalized_email))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def ensure_auth_shadow_user(first_name: str, last_name: str, email: str,
                            group_id: int = 10) -> int:
    """Ensure an Auth-only user has a local numeric EmpID record."""
    existing = get_user_by_email(email)
    if existing:
        return int(existing["EmpID"])

    normalized_email = (email or "").strip().lower()
    safe_group_id = group_id or 10
    with transactional() as (conn, cursor):
        cursor.execute(
            "SELECT TOP 1 EmpID FROM Intra_Users WHERE LOWER(LTRIM(RTRIM(ISNULL(EmailAddress, '')))) = ?",
            (normalized_email,),
        )
        row = cursor.fetchone()
        if row:
            return int(row[0])

        cursor.execute("SELECT ISNULL(MAX(EmpID), 0) + 1 FROM Intra_Users")
        new_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO Intra_Users (EmpID, FirstName, LastName, EmailAddress, GroupID)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_id, first_name or "", last_name or "", email, safe_group_id),
        )
        return new_id


def create_user(first_name: str, last_name: str, email: str,
                department_id: int, designation_id: int, group_id: int,
                username: str, password: str) -> int:
    """Create a new user + credentials. Returns new EmpID."""
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with transactional() as (conn, cursor):
        # EmpID is NOT auto-increment — generate the next value
        cursor.execute("SELECT ISNULL(MAX(EmpID), 0) + 1 FROM Intra_Users")
        new_id = int(cursor.fetchone()[0])
        cursor.execute("""
            INSERT INTO Intra_Users (EmpID, FirstName, LastName, EmailAddress,
                                     DeparmentID, DesignationID, GroupID)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (new_id, first_name, last_name, email, department_id, designation_id, group_id))
        cursor.execute("""
            INSERT INTO Intra_UserCredentials (EmpID, CredUsername, CredEmail, CredPassword)
            VALUES (?, ?, ?, ?)
        """, (new_id, username, email, hashed))
        return new_id


def update_user(emp_id: int, first_name: str, last_name: str, email: str,
                department_id: int, designation_id: int, group_id: int,
                username: str) -> None:
    """Update user profile (not password)."""
    with transactional() as (conn, cursor):
        cursor.execute("""
            UPDATE Intra_Users
            SET FirstName = ?, LastName = ?, EmailAddress = ?,
                DeparmentID = ?, DesignationID = ?, GroupID = ?
            WHERE EmpID = ?
        """, (first_name, last_name, email, department_id, designation_id, group_id, emp_id))
        cursor.execute("""
            UPDATE Intra_UserCredentials
            SET CredUsername = ?, CredEmail = ?
            WHERE EmpID = ?
        """, (username, email, emp_id))


def reset_password(emp_id: int, new_password: str) -> None:
    """Reset a user's password (bcrypt)."""
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    with transactional() as (conn, cursor):
        cursor.execute(
            "UPDATE Intra_UserCredentials SET CredPassword = ? WHERE EmpID = ?",
            (hashed, emp_id),
        )


def delete_user(emp_id: int) -> None:
    """Delete user credentials and user record."""
    with transactional() as (conn, cursor):
        cursor.execute("DELETE FROM Intra_UserCredentials WHERE EmpID = ?", (emp_id,))
        cursor.execute("DELETE FROM Intra_DMS_Permission WHERE EmpID = ?", (emp_id,))
        try:
            cursor.execute("DELETE FROM Intra_Module_UserAccess WHERE EmpID = ?", (emp_id,))
        except pyodbc.ProgrammingError:
            pass  # Table may not exist
        cursor.execute("DELETE FROM Intra_Admin_UserModuleAccess WHERE EmpID = ?", (emp_id,))
        cursor.execute(
            "DELETE FROM Intra_Admin_UserModuleRole WHERE emp_id = ?", (emp_id,)
        )
        cursor.execute("DELETE FROM Intra_Users WHERE EmpID = ?", (emp_id,))


def get_departments() -> list[dict]:
    sql = "SELECT id AS DepartmentID, name AS DepartmentName FROM Intra_Department ORDER BY name"
    with read_only() as cursor:
        cursor.execute(sql)
        return _rows_to_list(cursor, cursor.fetchall())


def get_designations() -> list[dict]:
    """Return designations if the table exists, otherwise empty list."""
    try:
        sql = "SELECT id AS DesignationID, name AS DesignationName FROM Intra_Designation ORDER BY name"
        with read_only() as cursor:
            cursor.execute(sql)
            return _rows_to_list(cursor, cursor.fetchall())
    except Exception:
        return []


# ── User permissions ───────────────────────────────────────────

def get_user_permissions(emp_id: int) -> dict:
    """Get DMS permission flags for a user."""
    sql = "SELECT * FROM Intra_DMS_Permission WHERE EmpID = ?"
    with read_only() as cursor:
        cursor.execute(sql, (emp_id,))
        row = cursor.fetchone()
        if row:
            return _row_to_dict(cursor, row)
        return {"EmpID": emp_id, "ITAdmin": 0, "Uploader": 0,
                "Approver": 0, "Reviewer1": 0, "Reviewer2": 0}


def upsert_user_permissions(emp_id: int, it_admin: int, uploader: int,
                            approver: int, reviewer1: int, reviewer2: int) -> None:
    """Create or update DMS permission flags."""
    with transactional() as (conn, cursor):
        cursor.execute("SELECT 1 FROM Intra_DMS_Permission WHERE EmpID = ?", (emp_id,))
        exists = cursor.fetchone()
        if exists:
            cursor.execute("""
                UPDATE Intra_DMS_Permission
                SET ITAdmin = ?, Uploader = ?, Approver = ?,
                    Reviewer1 = ?, Reviewer2 = ?
                WHERE EmpID = ?
            """, (it_admin, uploader, approver, reviewer1, reviewer2, emp_id))
        else:
            cursor.execute("""
                INSERT INTO Intra_DMS_Permission
                    (EmpID, ITAdmin, Uploader, Approver, Reviewer1, Reviewer2)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (emp_id, it_admin, uploader, approver, reviewer1, reviewer2))


def get_user_access_groups(emp_id: int) -> list[int]:
    """Get list of access group IDs for a user."""
    sql = "SELECT AccessGroupID FROM Intra_Module_UserAccess WHERE EmpID = ?"
    try:
        with read_only() as cursor:
            cursor.execute(sql, (emp_id,))
            return [row[0] for row in cursor.fetchall()]
    except pyodbc.ProgrammingError:
        return []  # Table may not exist


def set_user_access_groups(emp_id: int, group_ids: list[int]) -> None:
    """Replace a user's access groups."""
    try:
        with transactional() as (conn, cursor):
            cursor.execute("DELETE FROM Intra_Module_UserAccess WHERE EmpID = ?", (emp_id,))
            for gid in group_ids:
                cursor.execute(
                    "INSERT INTO Intra_Module_UserAccess (EmpID, AccessGroupID) VALUES (?, ?)",
                    (emp_id, gid),
                )
    except pyodbc.ProgrammingError:
        pass  # Table may not exist


def get_all_access_groups() -> list[dict]:
    sql = "SELECT id, Name AS GroupName FROM Intra_Module_AccessGroup ORDER BY Name"
    with read_only() as cursor:
        cursor.execute(sql)
        return _rows_to_list(cursor, cursor.fetchall())


# ═══════════════════════════════════════════════════════════════
#  RESTRICTED WORDS
# ═══════════════════════════════════════════════════════════════

def get_restricted_words() -> list[dict]:
    sql = """
        SELECT rw.id, rw.word, rw.added_by, rw.created_at,
               u.FirstName + ' ' + u.LastName AS added_by_name
        FROM Intra_Admin_RestrictedWords rw
        LEFT JOIN Intra_Users u ON rw.added_by = u.EmpID
        ORDER BY rw.word
    """
    with read_only() as cursor:
        cursor.execute(sql)
        return _rows_to_list(cursor, cursor.fetchall())


def add_restricted_word(word: str, added_by: int) -> int:
    """Add a restricted word. Returns new ID."""
    with transactional() as (conn, cursor):
        cursor.execute(
            "INSERT INTO Intra_Admin_RestrictedWords (word, added_by) OUTPUT INSERTED.id VALUES (?, ?)",
            (word.strip().lower(), added_by),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def delete_restricted_word(word_id: int) -> None:
    with transactional() as (conn, cursor):
        cursor.execute("DELETE FROM Intra_Admin_RestrictedWords WHERE id = ?", (word_id,))


def get_all_restricted_words_set() -> set[str]:
    """Return a set of all restricted words (lowercase) for fast lookup."""
    sql = "SELECT word FROM Intra_Admin_RestrictedWords"
    with read_only() as cursor:
        cursor.execute(sql)
        return {row[0].lower() for row in cursor.fetchall()}


# ═══════════════════════════════════════════════════════════════
#  MODULE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

def get_all_modules() -> list[dict]:
    sql = "SELECT * FROM Intra_Admin_ModuleConfig ORDER BY sort_order"
    with read_only() as cursor:
        cursor.execute(sql)
        return _rows_to_list(cursor, cursor.fetchall())


def get_module_by_id(module_id: int) -> dict | None:
    sql = "SELECT * FROM Intra_Admin_ModuleConfig WHERE id = ?"
    with read_only() as cursor:
        cursor.execute(sql, (module_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def toggle_module(module_id: int, is_enabled: bool) -> None:
    with transactional() as (conn, cursor):
        cursor.execute(
            "UPDATE Intra_Admin_ModuleConfig SET is_enabled = ? WHERE id = ?",
            (1 if is_enabled else 0, module_id),
        )


def get_module_group_access(module_id: int) -> list[dict]:
    sql = """
        SELECT mga.*, mag.Name AS GroupName
        FROM Intra_Admin_ModuleGroupAccess mga
        INNER JOIN Intra_Module_AccessGroup mag ON mga.group_id = mag.id
        WHERE mga.module_id = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (module_id,))
        return _rows_to_list(cursor, cursor.fetchall())


def set_module_group_access(module_id: int,
                            group_settings: list[dict]) -> None:
    """Replace group access for a module. group_settings: [{group_id, is_enabled}]."""
    with transactional() as (conn, cursor):
        cursor.execute(
            "DELETE FROM Intra_Admin_ModuleGroupAccess WHERE module_id = ?",
            (module_id,),
        )
        for gs in group_settings:
            cursor.execute("""
                INSERT INTO Intra_Admin_ModuleGroupAccess (module_id, group_id, is_enabled)
                VALUES (?, ?, ?)
            """, (module_id, gs["group_id"], 1 if gs.get("is_enabled") else 0))


def get_module_user_access(module_id: int) -> list[dict]:
    sql = """
        SELECT uma.*, u.FirstName + ' ' + u.LastName AS user_name
        FROM Intra_Admin_UserModuleAccess uma
        INNER JOIN Intra_Users u ON uma.emp_id = u.EmpID
        WHERE uma.module_id = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (module_id,))
        return _rows_to_list(cursor, cursor.fetchall())


def set_module_user_access(module_id: int, emp_id: int, is_enabled: bool) -> None:
    with transactional() as (conn, cursor):
        cursor.execute("""
            MERGE Intra_Admin_UserModuleAccess AS t
            USING (SELECT ? AS module_id, ? AS emp_id) AS s
            ON t.module_id = s.module_id AND t.emp_id = s.emp_id
            WHEN MATCHED THEN UPDATE SET is_enabled = ?
            WHEN NOT MATCHED THEN INSERT (module_id, emp_id, is_enabled) VALUES (?, ?, ?);
        """, (module_id, emp_id, 1 if is_enabled else 0,
              module_id, emp_id, 1 if is_enabled else 0))


def get_visible_modules_for_user(emp_id: int, user_group_ids: list[int]) -> list[dict]:
    """
    3-tier visibility: Global → Group → User.
    Returns modules the user can see.

    Uses bulk queries to avoid N+1 DB round-trips.
    """
    all_modules = get_all_modules()

    # ── Bulk-fetch user overrides ──────────────────────────────
    user_overrides: dict[int, bool] = {}
    with read_only() as cursor:
        cursor.execute(
            "SELECT module_id, is_enabled FROM Intra_Admin_UserModuleAccess WHERE emp_id = ?",
            (emp_id,),
        )
        for row in cursor.fetchall():
            user_overrides[row[0]] = bool(row[1])

    # ── Bulk-fetch group overrides ─────────────────────────────
    # Maps module_id → list of is_enabled flags across groups
    group_overrides: dict[int, list[bool]] = {}
    if user_group_ids:
        placeholders = ",".join("?" for _ in user_group_ids)
        with read_only() as cursor:
            cursor.execute(
                f"SELECT module_id, is_enabled FROM Intra_Admin_ModuleGroupAccess "
                f"WHERE group_id IN ({placeholders})",
                user_group_ids,
            )
            for row in cursor.fetchall():
                group_overrides.setdefault(row[0], []).append(bool(row[1]))

    # ── Apply 3-tier logic in-memory ───────────────────────────
    visible = []
    for mod in all_modules:
        # Tier 1: Global disabled → nobody sees it
        if not mod.get("is_enabled"):
            continue

        mid = mod["id"]

        # Tier 3: Per-user override (most specific)
        if mid in user_overrides:
            if user_overrides[mid]:
                visible.append(mod)
            continue

        # Tier 2: Per-group override
        if mid in group_overrides:
            # If ANY group says disabled, user is blocked
            if any(not flag for flag in group_overrides[mid]):
                continue
            visible.append(mod)
            continue

        # No overrides → globally enabled means visible
        visible.append(mod)

    return visible


# ═══════════════════════════════════════════════════════════════
#  WORKFLOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def get_workflow_statuses(module_key: str) -> list[dict]:
    sql = """
        SELECT * FROM Intra_Admin_WorkflowStatus
        WHERE module_key = ? ORDER BY sort_order
    """
    with read_only() as cursor:
        cursor.execute(sql, (module_key,))
        return _rows_to_list(cursor, cursor.fetchall())


def get_workflow_transitions(module_key: str) -> list[dict]:
    sql = """
        SELECT * FROM Intra_Admin_WorkflowTransition
        WHERE module_key = ? ORDER BY from_status, to_status
    """
    with read_only() as cursor:
        cursor.execute(sql, (module_key,))
        return _rows_to_list(cursor, cursor.fetchall())


def add_workflow_status(module_key: str, status_key: str,
                        display_name: str, sort_order: int,
                        is_terminal: bool) -> int:
    with transactional() as (conn, cursor):
        cursor.execute("""
            INSERT INTO Intra_Admin_WorkflowStatus
                (module_key, status_key, display_name, sort_order, is_terminal)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?)
        """, (module_key, status_key, display_name, sort_order,
              1 if is_terminal else 0))
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def update_workflow_status(status_id: int, display_name: str,
                           sort_order: int, is_terminal: bool) -> None:
    with transactional() as (conn, cursor):
        cursor.execute("""
            UPDATE Intra_Admin_WorkflowStatus
            SET display_name = ?, sort_order = ?, is_terminal = ?
            WHERE id = ?
        """, (display_name, sort_order, 1 if is_terminal else 0, status_id))


def delete_workflow_status(status_id: int) -> None:
    with transactional() as (conn, cursor):
        # Get module_key and status_key to cascade-delete transitions
        cursor.execute(
            "SELECT module_key, status_key FROM Intra_Admin_WorkflowStatus WHERE id = ?",
            (status_id,),
        )
        row = cursor.fetchone()
        if row:
            mk, sk = row[0], row[1]
            cursor.execute(
                "DELETE FROM Intra_Admin_WorkflowTransition WHERE module_key = ? AND (from_status = ? OR to_status = ?)",
                (mk, sk, sk),
            )
        cursor.execute("DELETE FROM Intra_Admin_WorkflowStatus WHERE id = ?", (status_id,))


def add_workflow_transition(module_key: str, from_status: str,
                            to_status: str, required_role: str | None) -> int:
    with transactional() as (conn, cursor):
        cursor.execute("""
            INSERT INTO Intra_Admin_WorkflowTransition
                (module_key, from_status, to_status, required_role)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?)
        """, (module_key, from_status, to_status, required_role))
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def update_workflow_transition_role(transition_id: int, required_role: str) -> None:
    """Update the required_role on an existing transition."""
    with transactional() as (conn, cursor):
        cursor.execute(
            "UPDATE Intra_Admin_WorkflowTransition SET required_role = ? WHERE id = ?",
            (required_role, transition_id),
        )


def delete_workflow_transition(transition_id: int) -> None:
    with transactional() as (conn, cursor):
        cursor.execute(
            "DELETE FROM Intra_Admin_WorkflowTransition WHERE id = ?",
            (transition_id,),
        )


# ═══════════════════════════════════════════════════════════════
#  PER-MODULE USER ROLES
# ═══════════════════════════════════════════════════════════════

def get_user_module_roles(module_id: int) -> list[dict]:
    """Get all user-role assignments for a specific module.
    Uses LEFT JOIN so Auth-only users (not in Intra_Users) still appear."""
    sql = """
        SELECT umr.id, umr.module_id, umr.emp_id, umr.role_key,
               umr.assigned_by, umr.assigned_at,
               u.FirstName + ' ' + u.LastName AS user_name,
               u.EmailAddress AS user_email,
               a.FirstName + ' ' + a.LastName AS assigned_by_name
        FROM Intra_Admin_UserModuleRole umr
        LEFT JOIN Intra_Users u ON umr.emp_id = u.EmpID
        LEFT JOIN Intra_Users a ON umr.assigned_by = a.EmpID
        WHERE umr.module_id = ?
        ORDER BY umr.role_key, umr.emp_id
    """
    with read_only() as cursor:
        cursor.execute(sql, (module_id,))
        return _rows_to_list(cursor, cursor.fetchall())


def get_user_roles_for_module(emp_id: int | str, module_id: int) -> list[str]:
    """Get role keys for a specific user in a specific module."""
    sql = """
        SELECT role_key FROM Intra_Admin_UserModuleRole
        WHERE emp_id = ? AND module_id = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (emp_id, module_id))
        return [row[0] for row in cursor.fetchall()]


def get_all_module_roles_for_user(emp_id: int | str) -> dict[str, list[str]]:
    """Get all module roles for a user.  Returns {module_key: [role_key, …]}."""
    sql = """
        SELECT mc.module_key, umr.role_key
        FROM Intra_Admin_UserModuleRole umr
        INNER JOIN Intra_Admin_ModuleConfig mc ON umr.module_id = mc.id
        WHERE umr.emp_id = ?
    """
    with read_only() as cursor:
        cursor.execute(sql, (emp_id,))
        result: dict[str, list[str]] = {}
        for row in cursor.fetchall():
            result.setdefault(row[0], []).append(row[1])
        return result


def assign_user_module_role(module_id: int, emp_id: int | str,
                            role_key: str, assigned_by: int) -> None:
    """Assign a role to a user for a module (idempotent)."""
    with transactional() as (conn, cursor):
        cursor.execute("""
            MERGE Intra_Admin_UserModuleRole AS t
            USING (SELECT ? AS module_id, ? AS emp_id, ? AS role_key) AS s
            ON t.module_id = s.module_id AND t.emp_id = s.emp_id
               AND t.role_key = s.role_key
            WHEN NOT MATCHED THEN
                INSERT (module_id, emp_id, role_key, assigned_by, assigned_at)
                VALUES (?, ?, ?, ?, GETDATE());
        """, (module_id, emp_id, role_key,
              module_id, emp_id, role_key, assigned_by))


def revoke_user_module_role(module_id: int, emp_id: int | str,
                            role_key: str) -> None:
    """Remove a specific role from a user for a module."""
    with transactional() as (conn, cursor):
        cursor.execute(
            "DELETE FROM Intra_Admin_UserModuleRole "
            "WHERE module_id = ? AND emp_id = ? AND role_key = ?",
            (module_id, emp_id, role_key),
        )


def set_user_module_roles(module_id: int, emp_id: int | str,
                          role_keys: list[str], assigned_by: int) -> None:
    """Replace all roles for a user in a module."""
    with transactional() as (conn, cursor):
        cursor.execute(
            "DELETE FROM Intra_Admin_UserModuleRole "
            "WHERE module_id = ? AND emp_id = ?",
            (module_id, emp_id),
        )
        for rk in role_keys:
            cursor.execute(
                "INSERT INTO Intra_Admin_UserModuleRole "
                "(module_id, emp_id, role_key, assigned_by, assigned_at) "
                "VALUES (?, ?, ?, ?, GETDATE())",
                (module_id, emp_id, rk, assigned_by),
            )


def delete_all_user_module_roles(emp_id: int | str) -> None:
    """Remove all module role assignments for a user (used on user deletion)."""
    with transactional() as (conn, cursor):
        cursor.execute(
            "DELETE FROM Intra_Admin_UserModuleRole WHERE emp_id = ?",
            (emp_id,),
        )


# ═══════════════════════════════════════════════════════════════
#  WORKFLOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def get_workflow_flow_dict(module_key: str) -> dict[str, list[str]]:
    """Build a STATUS_FLOW-style dict from the DB for a given module."""
    statuses = get_workflow_statuses(module_key)
    transitions = get_workflow_transitions(module_key)

    flow: dict[str, list[str]] = {}
    for s in statuses:
        flow[s["status_key"]] = []
    for t in transitions:
        fk = t["from_status"]
        if fk not in flow:
            flow[fk] = []
        flow[fk].append(t["to_status"])

    return flow


# ═══════════════════════════════════════════════════════════════
#  CUSTOM MODULE ROLE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

def get_custom_module_roles(module_key: str) -> list[dict]:
    """Get custom (DB-defined) roles for a module."""
    sql = """
        SELECT id, module_key, role_key, display_label, created_by, created_at
        FROM Intra_Admin_ModuleRoleConfig
        WHERE module_key = ?
        ORDER BY display_label
    """
    with read_only() as cursor:
        cursor.execute(sql, (module_key,))
        return _rows_to_list(cursor, cursor.fetchall())


def add_custom_module_role(module_key: str, role_key: str,
                           display_label: str, created_by: int) -> int:
    """Add a custom role for a module. Returns new ID."""
    with transactional() as (conn, cursor):
        cursor.execute("""
            INSERT INTO Intra_Admin_ModuleRoleConfig
                (module_key, role_key, display_label, created_by)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?)
        """, (module_key, role_key, display_label, created_by))
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def delete_custom_module_role(role_id: int) -> None:
    """Delete a custom role config entry and cascade-remove user assignments."""
    with transactional() as (conn, cursor):
        # Get the role_key and module_key before deleting
        cursor.execute(
            "SELECT role_key, module_key FROM Intra_Admin_ModuleRoleConfig WHERE id = ?",
            (role_id,),
        )
        row = cursor.fetchone()
        if row:
            role_key, module_key = row[0], row[1]
            # Remove user assignments for this role in the matching module
            cursor.execute("""
                DELETE umr FROM Intra_Admin_UserModuleRole umr
                INNER JOIN Intra_Admin_ModuleConfig mc
                    ON umr.module_id = mc.id AND mc.module_key = ?
                WHERE umr.role_key = ?
            """, (module_key, role_key))
        cursor.execute(
            "DELETE FROM Intra_Admin_ModuleRoleConfig WHERE id = ?",
            (role_id,),
        )
