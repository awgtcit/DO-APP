"""
Create test users for the Delivery Order application.

Users created:
  1. do.admin      – Full admin (GroupID=1, ITAdmin, all DMS perms)
  2. do.creator    – Regular user who creates delivery orders
  3. do.approver   – Can approve/confirm orders
  4. do.reviewer   – Can review orders
  5. do.uploader   – Can upload documents to orders
  6. do.viewer     – Basic read-only viewer (no special roles)
  7. do.finance    – Finance role (can set price agreed)
  8. do.logistics  – Logistics role (can confirm orders)

All passwords: Test@2025

Usage:
    cd app
    python scripts/create_test_users.py
"""

import hashlib
import sys
import os

# Add parent dir so we can import our db module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import bcrypt
import pyodbc

# ── Config ──────────────────────────────────────────────────────

DB_SERVER   = os.environ.get("DB_SERVER")
DB_NAME     = os.environ.get("DB_NAME")
DB_USER     = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

if not all([DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD]):
    print("ERROR: Set DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD env vars first.")
    sys.exit(1)

PASSWORD    = os.environ.get("TEST_USER_PASSWORD", "Test@2025")
BCRYPT_HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()

DEPT_IT     = 1   # IT & ERP
DEPT_SUPPLY = 3   # Supply Chain

# EmpIDs in the 900100 range (safe — max real EmpID < 820002)
USERS = [
    {
        "emp_id":      900101,
        "username":    "do.admin",
        "email":       "m.nizar@awgtc.com",
        "first_name":  "Admin",
        "last_name":   "DOUser",
        "group_id":    1,          # GroupID=1 → it_admin + admin roles
        "department":  DEPT_IT,
        "dms_perms":   {"ITAdmin": 1, "Uploader": 1, "Approver": 1,
                        "Reviewer1": 1, "Reviewer2": 0},
    },
    {
        "emp_id":      900102,
        "username":    "do.creator",
        "email":       "m.nizar@awgtc.com",
        "first_name":  "Creator",
        "last_name":   "DOUser",
        "group_id":    2,
        "department":  DEPT_SUPPLY,
        "dms_perms":   None,       # No DMS permissions
    },
    {
        "emp_id":      900103,
        "username":    "do.approver",
        "email":       "m.nizar@awgtc.com",
        "first_name":  "Approver",
        "last_name":   "DOUser",
        "group_id":    2,
        "department":  DEPT_SUPPLY,
        "dms_perms":   {"ITAdmin": 0, "Uploader": 0, "Approver": 1,
                        "Reviewer1": 0, "Reviewer2": 0},
    },
    {
        "emp_id":      900104,
        "username":    "do.reviewer",
        "email":       "m.nizar@awgtc.com",
        "first_name":  "Reviewer",
        "last_name":   "DOUser",
        "group_id":    2,
        "department":  DEPT_SUPPLY,
        "dms_perms":   {"ITAdmin": 0, "Uploader": 0, "Approver": 0,
                        "Reviewer1": 1, "Reviewer2": 0},
    },
    {
        "emp_id":      900105,
        "username":    "do.uploader",
        "email":       "m.nizar@awgtc.com",
        "first_name":  "Uploader",
        "last_name":   "DOUser",
        "group_id":    2,
        "department":  DEPT_SUPPLY,
        "dms_perms":   {"ITAdmin": 0, "Uploader": 1, "Approver": 0,
                        "Reviewer1": 0, "Reviewer2": 0},
    },
    {
        "emp_id":      900106,
        "username":    "do.viewer",
        "email":       "m.nizar@awgtc.com",
        "first_name":  "Viewer",
        "last_name":   "DOUser",
        "group_id":    2,
        "department":  DEPT_SUPPLY,
        "dms_perms":   None,       # No DMS permissions
    },
    {
        "emp_id":      900107,
        "username":    "do.finance",
        "email":       "m.nizar@awgtc.com",
        "first_name":  "Finance",
        "last_name":   "DOUser",
        "group_id":    2,
        "department":  DEPT_SUPPLY,
        "dms_perms":   {"ITAdmin": 0, "Uploader": 0, "Approver": 1,
                        "Reviewer1": 0, "Reviewer2": 0},
    },
    {
        "emp_id":      900108,
        "username":    "do.logistics",
        "email":       "m.nizar@awgtc.com",
        "first_name":  "Logistics",
        "last_name":   "DOUser",
        "group_id":    2,
        "department":  DEPT_SUPPLY,
        "dms_perms":   {"ITAdmin": 0, "Uploader": 0, "Approver": 0,
                        "Reviewer1": 1, "Reviewer2": 0},
    },
]


def get_connection():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_SERVER};DATABASE={DB_NAME};"
        f"UID={DB_USER};PWD={DB_PASSWORD}"
    )
    return pyodbc.connect(conn_str)


def create_users():
    conn = get_connection()
    cur = conn.cursor()

    created = 0
    skipped = 0

    for u in USERS:
        emp_id = u["emp_id"]

        # ── Check if user already exists ──
        cur.execute("SELECT EmpID FROM Intra_Users WHERE EmpID = ?", (emp_id,))
        if cur.fetchone():
            print(f"  SKIP  {u['username']:16s}  (EmpID {emp_id} already exists)")
            skipped += 1
            continue

        # ── 1. Insert into Intra_Users ──
        cur.execute(
            """INSERT INTO Intra_Users
               (GroupID, EmpID, FirstName, LastName, UserName,
                EmailAddress, Gender, DeparmentID, UserStatus)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                u["group_id"],
                emp_id,
                u["first_name"],
                u["last_name"],
                u["username"],
                u["email"],
                "M",
                u["department"],
                "WORKING",
            ),
        )

        # ── 2. Insert into Intra_UserCredentials ──
        cur.execute(
            """INSERT INTO Intra_UserCredentials
               (CredUsername, CredPassword, EmpID, CredEmail,
                Created_by, Created_on)
               VALUES (?, ?, ?, ?, ?, GETDATE())""",
            (
                u["username"],
                BCRYPT_HASH,
                emp_id,
                u["email"],
                0,
            ),
        )

        # ── 3. Insert DMS permissions (if any) ──
        if u["dms_perms"]:
            p = u["dms_perms"]
            cur.execute(
                """INSERT INTO Intra_DMS_Permission
                   (EmpID, DepartmentID, Uploader, Approver,
                    Reviewer1, Reviewer2, ITAdmin,
                    Created_by, Created_on)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE())""",
                (
                    emp_id,
                    u["department"],
                    p["Uploader"],
                    p["Approver"],
                    p["Reviewer1"],
                    p["Reviewer2"],
                    p["ITAdmin"],
                    0,
                ),
            )

        # ── 4. Insert ISP acceptance (so they skip the ISP page) ──
        cur.execute(
            """INSERT INTO Isp_Status (email, status, created)
               VALUES (?, 1, GETDATE())""",
            (u["email"],),
        )

        conn.commit()
        created += 1

        # Build role summary
        roles = []
        if u["group_id"] == 1:
            roles.extend(["it_admin", "admin"])
        if u["dms_perms"]:
            if u["dms_perms"]["ITAdmin"]:
                roles.extend(["it_admin", "admin"])
            if u["dms_perms"]["Uploader"]:
                roles.append("uploader")
            if u["dms_perms"]["Approver"]:
                roles.append("approver")
            if u["dms_perms"]["Reviewer1"] or u["dms_perms"].get("Reviewer2"):
                roles.append("reviewer")
        roles = sorted(set(roles)) or ["(none)"]

        print(f"  OK    {u['username']:16s}  EmpID={emp_id}  roles={', '.join(roles)}")

    conn.close()

    print(f"\nDone: {created} created, {skipped} skipped.")
    print(f"\nAll passwords: {PASSWORD}")
    print("\nUser summary:")
    print("-" * 72)
    print(f"  {'Username':<18s} {'Password':<14s} {'Roles'}")
    print("-" * 72)

    role_map = {
        "do.admin":     "it_admin, admin, uploader, approver, reviewer",
        "do.creator":   "(none) — regular user",
        "do.approver":  "approver",
        "do.reviewer":  "reviewer",
        "do.uploader":  "uploader",
        "do.viewer":    "(none) — read-only viewer",
        "do.finance":   "approver → DO Finance",
        "do.logistics": "reviewer → DO Logistics",
    }
    for u in USERS:
        print(f"  {u['username']:<18s} {PASSWORD:<14s} {role_map[u['username']]}")
    print("-" * 72)


if __name__ == "__main__":
    print("Creating test users for Delivery Order app...\n")
    create_users()
