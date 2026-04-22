"""
Application entry-point.
Validates environment, then starts the Flask dev server.
"""

import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from config import Config

# Configure root logger so ALL loggers (email_service, etc.) output to console
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)


def _check_env() -> None:
    missing = Config.validate()
    if missing:
        print("\n[ERROR] Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print(
            "\nRun  .\\setup_credentials.ps1  first to configure credentials.\n"
        )
        sys.exit(1)


def create_app():
    """Application factory."""
    from flask import Flask

    _check_env()

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(Config)

    # ── Register blueprints ────────────────────────────────────────
    from controllers.auth_controller import auth_bp
    from controllers.dashboard_controller import dashboard_bp
    from controllers.it_support_controller import it_support_bp
    from controllers.placeholder_controller import placeholder_bp
    from controllers.webapp_controller import webapp_bp
    from controllers.delivery_order_controller import do_bp
    from controllers.dms_controller import dms_bp
    from controllers.announcements_controller import announcements_bp
    from controllers.facility_controller import facility_bp
    from controllers.forum_controller import forum_bp
    from controllers.isp_admin_controller import isp_admin_bp
    from controllers.do_management_controller import do_mgmt_bp
    from controllers.admin_settings_controller import admin_settings_bp
    from controllers.integration_controller import integration_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(it_support_bp)
    app.register_blueprint(placeholder_bp)
    app.register_blueprint(webapp_bp)
    app.register_blueprint(do_bp)
    app.register_blueprint(do_mgmt_bp)
    app.register_blueprint(dms_bp)
    app.register_blueprint(announcements_bp)
    app.register_blueprint(facility_bp)
    app.register_blueprint(forum_bp)
    app.register_blueprint(isp_admin_bp)
    app.register_blueprint(admin_settings_bp)
    app.register_blueprint(integration_bp)

    # ── SSO Middleware (must run BEFORE legacy session check) ─────
    from sdk.session_middleware import init_sso_middleware

    init_sso_middleware(app, public_paths=[
        '/health', '/api/health', '/favicon.ico',
        '/static', '/auth/login', '/auth/isp', '/auth/logout',
        '/api/integration',
    ], login_url='/auth/login')

    # ── Sync admin pages to Auth Platform (runs once on first request) ──
    ADMIN_PAGES = [
        {'code': 'DASHBOARD',       'name': 'Dashboard',          'url': '/dashboard',       'icon': 'bi-speedometer2',   'display_order': 1,  'category': 'DASHBOARD'},
        {'code': 'DELIVERY_ORDER',  'name': 'Delivery Orders',    'url': '/delivery-orders', 'icon': 'bi-truck',          'display_order': 2,  'category': 'DELIVERY_ORDER'},
        {'code': 'DO_MANAGEMENT',   'name': 'DO Management',      'url': '/do-management',   'icon': 'bi-clipboard-data', 'display_order': 3,  'category': 'DO_MANAGEMENT'},
        {'code': 'DMS',             'name': 'Document Management','url': '/dms',              'icon': 'bi-folder2-open',   'display_order': 4,  'category': 'DMS'},
        {'code': 'ANNOUNCEMENTS',   'name': 'Announcements',      'url': '/announcements',   'icon': 'bi-megaphone',      'display_order': 5,  'category': 'ANNOUNCEMENTS'},
        {'code': 'FACILITY',        'name': 'Facility',           'url': '/facility',        'icon': 'bi-building',       'display_order': 6,  'category': 'FACILITY'},
        {'code': 'FORUM',           'name': 'Forum',              'url': '/forum',           'icon': 'bi-chat-dots',      'display_order': 7,  'category': 'FORUM'},
        {'code': 'IT_SUPPORT',      'name': 'IT Support',         'url': '/it-support',      'icon': 'bi-headset',        'display_order': 8,  'category': 'IT_SUPPORT'},
        {'code': 'ISP',             'name': 'ISP Admin',          'url': '/isp-admin',       'icon': 'bi-shield-check',   'display_order': 9,  'category': 'ISP'},
        {'code': 'ADMIN',           'name': 'Admin Panel',        'url': '/admin',           'icon': 'bi-gear',           'display_order': 10, 'category': 'ADMIN'},
        {'code': 'EMAIL_CONFIG',    'name': 'Email Config',       'url': '/admin/email-config', 'icon': 'bi-envelope-gear', 'display_order': 11, 'category': 'ADMIN'},
        {'code': 'AUDIT_LOG',       'name': 'Audit Log',          'url': '/admin/audit',     'icon': 'bi-clock-history',  'display_order': 12, 'category': 'AUDIT_LOG'},
    ]

    app_id = app.config.get('AUTH_APP_APPLICATION_ID', '')
    if app_id:
        from sdk.app_registry_sync import sync_pages_on_startup
        sync_pages_on_startup(app, app_id, ADMIN_PAGES)

    # ── Jinja2 globals ─────────────────────────────────────────────
    from datetime import datetime as _dt
    app.jinja_env.globals["now"] = _dt.now

    def _has_perm(code):
        """Jinja2 global: check if current user has a permission code."""
        from flask import session as _s
        return code in _s.get('sso_permissions', [])

    app.jinja_env.globals['has_perm'] = _has_perm

    # ── Custom Jinja2 filters ────────────────────────────────────
    from ui_utils import register_filters
    register_filters(app)

    @app.context_processor
    def inject_globals():
        try:
            from flask import session as s
            emp_id = s.get("emp_id")
            user_roles = s.get("roles", [])

            # Build visible modules for dynamic sidebar (cached in session)
            visible_modules = []
            is_admin = ("admin" in user_roles or "it_admin" in user_roles)
            # Always populate sidebar for authenticated users.
            # emp_id may be 0 for SSO-only users — still show globally-enabled modules.
            if s.get("sso_authenticated") or s.get("email"):
                cached = s.get("_sidebar_cache")
                if cached and cached.get("emp_id") == emp_id:
                    visible_modules = cached["modules"]
                else:
                    try:
                        from services.admin_settings_service import get_visible_modules
                        user_group_ids = []
                        if emp_id:
                            try:
                                from repos.admin_settings_repo import get_user_access_groups as _get_uag
                                user_group_ids = _get_uag(emp_id)
                            except Exception:
                                pass
                        visible_modules = get_visible_modules(emp_id or 0, user_group_ids)
                        s["_sidebar_cache"] = {"emp_id": emp_id, "modules": visible_modules}
                    except Exception:
                        visible_modules = []

            return dict(
                current_user_email=s.get("email"),
                current_user_name=s.get("user_name"),
                current_user_empid=emp_id,
                sidebar_modules=visible_modules,
                is_admin_user=is_admin,
            )
        except RuntimeError:
            # No request context (e.g. PDF generation in background)
            return dict(
                current_user_email=None,
                current_user_name=None,
                current_user_empid=None,
                sidebar_modules=[],
                is_admin_user=False,
            )

    return app


if __name__ == "__main__":
    application = create_app()
    is_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    application.run(host="0.0.0.0", port=5080, debug=is_debug)
