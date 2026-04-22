"""Runtime SMTP settings resolver."""

import logging

from config import Config
from repos import email_admin_repo
from utils.secret_crypto import decrypt_secret

logger = logging.getLogger(__name__)


def get_runtime_smtp_settings() -> dict:
    cfg = None
    try:
        cfg = email_admin_repo.get_active_smtp_config()
    except Exception:
        logger.exception("Failed to fetch active SMTP config from DB; using env fallback")

    if cfg:
        try:
            return {
                "host": cfg.get("smtp_host") or "",
                "port": int(cfg.get("smtp_port") or 587),
                "user": cfg.get("smtp_username") or "",
                "password": decrypt_secret(cfg.get("smtp_password_encrypted") or ""),
                "from_email": cfg.get("sender_email") or cfg.get("smtp_username") or "",
                "from_name": cfg.get("sender_name") or "",
                "use_tls": bool(cfg.get("use_tls")),
                "use_ssl": bool(cfg.get("use_ssl")),
            }
        except Exception:
            logger.exception("Invalid DB SMTP config; using env fallback")

    return {
        "host": Config.SMTP_HOST,
        "port": int(Config.SMTP_PORT),
        "user": Config.SMTP_USER,
        "password": Config.SMTP_PASSWORD,
        "from_email": Config.SMTP_USER,
        "from_name": "",
        "use_tls": True,
        "use_ssl": False,
    }
