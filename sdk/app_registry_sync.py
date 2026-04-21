"""
App Registry Sync — syncs admin pages to the Auth Platform.

NOTE: Flask 3.0 removed before_first_request.  We use a before_request
hook with a closure flag so the sync runs exactly once on the first
incoming HTTP request, which is the standard Flask 3.x pattern.
"""
import logging
from sdk.auth_client import sync_admin_pages

logger = logging.getLogger('auth_sync')


def sync_pages_on_startup(app, application_id, admin_pages):
    """
    Register a before_request handler that runs ONCE on the first
    request to sync admin pages to the Auth Platform.

    This intentionally defers to the first request rather than running
    at import time so the app can start even if the Auth Platform is
    temporarily unreachable.
    """
    synced = {'done': False}

    @app.before_request
    def _sync_once():
        if synced['done']:
            return None
        synced['done'] = True
        try:
            result = sync_admin_pages(application_id, admin_pages)
            if result:
                logger.info("Admin pages synced to Auth Platform (%d pages)", len(admin_pages))
            else:
                logger.warning("Admin page sync returned no result — Auth Platform may be unreachable")
        except Exception as e:
            logger.error("Failed to sync admin pages: %s", e)
        return None
