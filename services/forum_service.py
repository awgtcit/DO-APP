"""
Employee Forum service — business logic for the employee directory,
profile viewing, and birthday list.
"""

from repos.forum_repo import (
    get_directory,
    get_departments,
    get_employee,
    get_birthdays_this_month,
    get_directory_stats,
)


# ── Directory ──────────────────────────────────────────────────

def list_employees(
    search: str | None = None,
    department: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[dict], int]:
    """Return paginated employee directory."""
    return get_directory(
        search=search,
        department=department,
        page=page,
        per_page=per_page,
    )


def get_department_options() -> list[dict]:
    """Return departments for the filter dropdown."""
    return get_departments()


def get_stats() -> dict:
    """Quick KPI stats for the directory overview."""
    return get_directory_stats()


# ── Profile ────────────────────────────────────────────────────

def get_employee_profile(emp_id: int) -> dict | None:
    """
    Return a single employee profile enriched with computed fields.
    """
    emp = get_employee(emp_id)
    if not emp:
        return None

    # Build full name
    first = emp.get("FirstName") or ""
    last = emp.get("LastName") or ""
    emp["full_name"] = f"{first} {last}".strip() or "Unknown"

    # Initials for avatar
    emp["initials"] = (first[:1] + last[:1]).upper() or "?"

    return emp


# ── Birthdays ──────────────────────────────────────────────────

def get_birthday_list() -> list[dict]:
    """
    Return employees with birthdays in the current month,
    enriched with display data.
    """
    people = get_birthdays_this_month()
    for p in people:
        first = p.get("FirstName") or ""
        last = p.get("LastName") or ""
        p["full_name"] = f"{first} {last}".strip() or "Unknown"
        p["initials"] = (first[:1] + last[:1]).upper() or "?"
        dob = p.get("DateOfBirth")
        p["birthday_display"] = dob.strftime("%d %B") if dob else ""
    return people
