"""
Auth service — orchestrates authentication flow.

Flow: Controller → Service → Rules → Repo → Audit
"""

import hashlib
import logging

import bcrypt

from auth.ldap_auth import ldap_authenticate
from repos.user_repo import (
    find_user_credentials,
    find_user_by_email,
    get_isp_status,
    upsert_isp_status,
)
from rules.auth_rules import validate_login, validate_isp_acceptance
from audit.logger import log_activity

logger = logging.getLogger(__name__)


class AuthResult:
    """Standardised auth response."""

    def __init__(self, success: bool, user: dict | None = None, errors: list[str] | None = None):
        self.success = success
        self.user = user or {}
        self.errors = errors or []


def login(username: str, password: str, client_ip: str = "") -> AuthResult:
    """
    Full authentication pipeline:
    1. Validate inputs
    2. Try LDAP
    3. Fallback to DB
    4. Audit log the attempt
    """
    # ── 1. Validate ────────────────────────────────────────────────
    errors = validate_login(username, password)
    if errors:
        return AuthResult(success=False, errors=errors)

    username = username.strip()

    # ── 2. LDAP attempt ────────────────────────────────────────────
    ldap_result = ldap_authenticate(username, password)
    if ldap_result:
        email = ldap_result["email"]
        user_record = find_user_by_email(email)
        if user_record:
            log_activity(
                emp_id=user_record.get("EmpID", 0),
                user_name=username,
                activity_type="LOGIN_LDAP",
                client_ip=client_ip,
                remarks="LDAP authentication successful",
            )
            return AuthResult(
                success=True,
                user={
                    "emp_id": user_record["EmpID"],
                    "email": email,
                    "first_name": user_record.get("FirstName", ""),
                    "last_name": user_record.get("LastName", ""),
                    "department_id": user_record.get("DeparmentID"),
                    "group_id": user_record.get("GroupID"),
                },
            )

    # ── 3. DB fallback ─────────────────────────────────────────────
    db_user = find_user_credentials(username)
    if db_user:
        stored_hash = db_user.get("CredPassword", "")
        # Support both legacy MD5 and modern bcrypt hashes
        password_ok = False
        if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
            # Modern bcrypt hash
            password_ok = bcrypt.checkpw(password.encode(), stored_hash.encode())
        else:
            # Legacy MD5 — compare then upgrade to bcrypt
            input_hash = hashlib.md5(password.encode()).hexdigest()
            password_ok = (stored_hash == input_hash)
            if password_ok:
                # One-time synchronous bcrypt upgrade (~100ms per legacy user).
                # Acceptable latency for a single login; no threading needed.
                _upgrade_password_hash(db_user.get("EmpID", 0), password)

        if password_ok:
            log_activity(
                emp_id=db_user.get("EmpID", 0),
                user_name=username,
                activity_type="LOGIN_DB",
                client_ip=client_ip,
                remarks="DB authentication successful",
            )
            return AuthResult(
                success=True,
                user={
                    "emp_id": db_user["EmpID"],
                    "email": db_user.get("CredEmail") or db_user.get("EmailAddress", ""),
                    "first_name": db_user.get("FirstName", ""),
                    "last_name": db_user.get("LastName", ""),
                    "department_id": db_user.get("DeparmentID"),
                    "group_id": db_user.get("GroupID"),
                },
            )

    # ── 4. Failure ─────────────────────────────────────────────────
    log_activity(
        emp_id=0,
        user_name=username,
        activity_type="LOGIN_FAILED",
        client_ip=client_ip,
        remarks="Invalid credentials",
    )
    return AuthResult(success=False, errors=["Invalid username or password."])


def _upgrade_password_hash(emp_id: int, plaintext_password: str) -> None:
    """Re-hash a legacy MD5 password to bcrypt on successful login."""
    try:
        new_hash = bcrypt.hashpw(plaintext_password.encode(), bcrypt.gensalt()).decode()
        from db.transaction import transactional
        with transactional() as (conn, cursor):
            cursor.execute(
                "UPDATE Intra_UserCredentials SET CredPassword = ? WHERE EmpID = ?",
                (new_hash, emp_id),
            )
        logger.info("Upgraded password hash to bcrypt for EmpID=%s", emp_id)
    except Exception as exc:
        logger.warning("Failed to upgrade password hash for EmpID=%s: %s", emp_id, exc)


def check_isp(email: str) -> bool:
    """Return True if user has accepted the ISP."""
    record = get_isp_status(email)
    return record is not None and record.get("status") == 1


def accept_isp(email: str, emp_id: int, client_ip: str = "") -> list[str]:
    """Mark ISP as accepted. Returns errors list (empty = success)."""
    errors = validate_isp_acceptance(True)
    if errors:
        return errors
    upsert_isp_status(email, 1)
    log_activity(
        emp_id=emp_id,
        user_name=email,
        activity_type="ISP_ACCEPTED",
        client_ip=client_ip,
        remarks="User accepted Information Security Policy",
    )
    return []
