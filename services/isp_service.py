"""
ISP Status service — business logic for the ISP acceptance admin view.
"""

from repos.isp_repo import get_all_isp_records, get_isp_stats


def is_isp_admin(roles: list[str]) -> bool:
    """Only IT admins can view ISP status records."""
    return "it_admin" in roles or "admin" in roles


def list_isp_records(
    search: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    """Return paginated ISP acceptance records."""
    records, total = get_all_isp_records(
        search=search,
        page=page,
        per_page=per_page,
    )
    # Enrich with display-friendly date strings
    for r in records:
        created = r.get("created")
        r["accepted_display"] = created.strftime("%d-%b-%Y %I:%M %p") if created else "—"
    return records, total


def isp_overview_stats() -> dict:
    """Return ISP acceptance stats for the admin dashboard."""
    return get_isp_stats()
