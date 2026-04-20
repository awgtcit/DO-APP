"""
Configuration — loads credentials and secrets from environment variables.
Operational defaults (timeouts, domain lists) may be hardcoded.
"""

import os
import secrets


def _safe_int(value: str, default: int) -> int:
    """Convert string to int, returning default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class Config:
    """Base configuration loaded from environment variables."""

    # Flask core
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    PERMANENT_SESSION_LIFETIME = _safe_int(os.environ.get("SESSION_LIFETIME", "1800"), 1800)  # seconds
    TEMPLATES_AUTO_RELOAD = True  # Enable template auto-reload for development
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB upload limit

    # ── Database (SQL Server via ODBC 17) ──────────────────────────
    DB_SERVER = os.environ.get("DB_SERVER", "")
    DB_NAME = os.environ.get("DB_NAME", "")
    DB_USER = os.environ.get("DB_USER", "")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_DRIVER = os.environ.get("DB_DRIVER", "{SQL Server}")

    # ── LDAP ───────────────────────────────────────────────────────
    LDAP_SERVER = os.environ.get("LDAP_SERVER", "")
    LDAP_PORT = int(os.environ.get("LDAP_PORT", "389"))
    LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "dc=ad,dc=com")
    LDAP_DOMAINS = [
        d.strip()
        for d in os.environ.get(
            "LDAP_DOMAINS",
            "@moderntobacco.ae,@universal.moderntobacco.ae,@alwahdania.com",
        ).split(",")
        if d.strip()
    ]

    # ── Auth Platform (SSO) ───────────────────────────────────────
    AUTH_BASE_URL = os.environ.get("AUTH_BASE_URL", "http://127.0.0.1:5001")
    AUTH_API_KEY = os.environ.get("AUTH_API_KEY", "")
    AUTH_APP_APPLICATION_ID = os.environ.get("AUTH_APP_APPLICATION_ID", "")
    AUTH_APP_CODE = os.environ.get("AUTH_APP_CODE", "DOAPP")

    # ── SMTP ───────────────────────────────────────────────────────
    SMTP_HOST = os.environ.get("SMTP_HOST") or os.environ.get("SMTP_SERVER", "")
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required env vars."""
        required = ["DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD"]
        missing = [v for v in required if not getattr(cls, v)]
        return missing
