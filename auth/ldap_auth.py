"""
LDAP authentication helper.

Attempts to bind against the configured LDAP/AD server
using the provided username and password.
Falls back to database-based authentication if LDAP is unavailable.
"""

import logging

from ldap3 import Server, Connection, ALL, NTLM
from config import Config

logger = logging.getLogger(__name__)

# Domain suffixes to try when binding
_DOMAINS = Config.LDAP_DOMAINS


def ldap_authenticate(username: str, password: str) -> dict | None:
    """
    Try LDAP bind for each configured domain.

    Returns a dict with user attributes on success, or None on failure.
    """
    if not Config.LDAP_SERVER:
        logger.debug("LDAP not configured — skipping")
        return None

    server = Server(Config.LDAP_SERVER, port=Config.LDAP_PORT, get_info=ALL)

    for domain in _DOMAINS:
        user_principal = f"{username}{domain}"
        try:
            conn = Connection(
                server,
                user=user_principal,
                password=password,
                auto_bind=True,
                raise_exceptions=True,
            )
            # Search for user attributes
            conn.search(
                Config.LDAP_BASE_DN,
                f"(userPrincipalName={user_principal})",
                attributes=["mail", "displayName", "sAMAccountName", "memberOf"],
            )
            if conn.entries:
                entry = conn.entries[0]
                result = {
                    "email": str(entry.mail) if hasattr(entry, "mail") else user_principal,
                    "display_name": str(entry.displayName) if hasattr(entry, "displayName") else username,
                    "sam_account": str(entry.sAMAccountName) if hasattr(entry, "sAMAccountName") else username,
                    "groups": [str(g) for g in entry.memberOf] if hasattr(entry, "memberOf") else [],
                }
                conn.unbind()
                return result
            conn.unbind()
        except Exception as exc:
            logger.debug("LDAP bind failed for %s: %s", domain, exc)
            continue

    return None
