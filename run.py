"""
Application entry-point.
Validates environment, then starts the Flask dev server.
"""

import logging
import os
import sys

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

    # ── Global before-request: session check ───────────────────────
    from auth.middleware import check_session

    app.before_request(check_session)

    # ── Jinja2 globals ─────────────────────────────────────────────
    from datetime import datetime as _dt
    app.jinja_env.globals["now"] = _dt.now

    # ── Custom Jinja2 filters ────────────────────────────────────
    from ui_utils import register_filters
    register_filters(app)

    @app.context_processor
    def inject_globals():
        try:
            from flask import session as s
            emp_id = s.get("emp_id")
            user_roles = s.get("roles", [])

            # Build visible modules for dynamic sidebar
            visible_modules = []
            is_admin = ("admin" in user_roles or "it_admin" in user_roles)
            if emp_id:
                try:
                    from services.admin_settings_service import get_visible_modules
                    user_group_ids = []
                    try:
                        from repos.admin_settings_repo import get_user_access_groups as _get_uag
                        user_group_ids = _get_uag(emp_id)
                    except Exception:
                        pass
                    visible_modules = get_visible_modules(emp_id, user_group_ids)
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
