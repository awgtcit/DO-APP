"""
SSO Session Middleware — enables single-sign-on via the
Al Wahdania Auth Platform.

Bridges SSO session data into DO-APP's existing session format
(email, emp_id, user_name, roles, department_id, group_id) so that
existing controllers and middleware continue to work unchanged.

Usage:
    from sdk.session_middleware import init_sso_middleware
    init_sso_middleware(app)
"""
import logging
import time
from functools import wraps
from flask import request, session, redirect, g, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sdk.auth_client import validate_token

logger = logging.getLogger('auth_sso')

DEFAULT_PUBLIC_PATHS = frozenset([
    '/health', '/api/health', '/favicon.ico',
    '/static', '/auth/login', '/auth/isp',
])

# Admin permissions auto-granted to SSO users flagged as admin in Auth-App
_SSO_ADMIN_PERMISSIONS = [
    'ADMIN.PANEL', 'ADMIN.SETTINGS', 'ADMIN.USERS',
]

# Embed session token max age: 30 minutes
_EMBED_TOKEN_MAX_AGE = 30 * 60


def _create_embed_token(user_info, roles, permissions):
    """Create a signed embed session token for cookie-free iframe auth."""
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='embed-session')
    return s.dumps({
        'uid': user_info.get('id', ''),
        'email': user_info.get('email', ''),
        'roles': roles,
        'perms': permissions,
    })


def _validate_embed_token(token_str):
    """Validate and decode an embed session token."""
    try:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='embed-session')
        return s.loads(token_str, max_age=_EMBED_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def _populate_g(user_dict, roles, permissions):
    """Populate Flask g with user context."""
    g.current_user = user_dict
    g.current_user_id = user_dict.get('id')
    g.current_roles = roles
    g.current_permissions = permissions
    g.user_id = user_dict.get('id')
    g.user_email = user_dict.get('email', '')
    g.user_roles = roles
    g.user_permissions = permissions


def _bridge_sso_to_legacy(user_info, roles):
    """
    Bridge SSO session data into DO-APP's existing session format.
    DO-APP controllers rely on session['email'], session['emp_id'],
    session['user_name'], session['roles'], etc.
    """
    _logger = logging.getLogger(__name__)
    user = user_info.get('user', user_info)

    emp_id = 0
    try:
        from services.admin_settings_service import (
            resolve_or_create_local_emp_id_from_auth_user,
        )

        emp_id = (
            resolve_or_create_local_emp_id_from_auth_user(
                {
                    'employee_code': user.get('employee_code'),
                    'employee_id': user.get('employee_id'),
                    'emp_id': user.get('emp_id'),
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'email': user.get('email', ''),
                    'group_id': user.get('group_id'),
                },
                create_if_missing=True,
            )
            or 0
        )
    except Exception:
        _logger.debug("SSO bridge: local emp_id resolution failed", exc_info=True)

    _logger.debug("SSO bridge: email=%s, emp_id=%s (employee_code=%r)",
                 user.get('email'), emp_id, user.get('employee_code'))

    session['email'] = user.get('email', '')
    session['emp_id'] = emp_id
    session['user_name'] = (
        f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        or user.get('display_name', '')
    )
    session['department_id'] = user.get('department_id')
    session['group_id'] = user.get('group_id')
    session.permanent = True

    # Map SSO roles to DO-APP's legacy role strings
    legacy_roles = set()
    sso_role_codes = set(roles)

    # Admin detection: Auth-App is_admin flag or admin roles
    if user.get('is_admin') or 'SYS_ADMIN' in sso_role_codes or 'DO_ADMIN' in sso_role_codes:
        legacy_roles.update(('admin', 'it_admin'))

    # Map specific Auth-App roles → DO-APP legacy roles
    role_mapping = {
        'DO_ADMIN': ('admin', 'it_admin'),
        'DO_SALES': ('sales',),
        'DO_LOGISTICS': ('logistics',),
        'DO_APPROVER': ('approver',),
        'DO_REVIEWER': ('reviewer',),
        'DO_DMS_ADMIN': ('it_admin', 'dms_admin'),
        'DO_UPLOADER': ('dms_uploader',),
        'DO_FACILITY': ('facility',),
    }
    for sso_role, legacy in role_mapping.items():
        if sso_role in sso_role_codes:
            legacy_roles.update(legacy)

    # Fallback: if user has any roles but none mapped, give basic access
    if sso_role_codes and not legacy_roles:
        legacy_roles.add('user')

    session['roles'] = list(legacy_roles)


def init_sso_middleware(app, public_paths=None, login_url='/auth/login'):
    """
    Register a before_request handler that validates SSO sessions.
    On first hit with a ?token= query param, validates the launch token
    and populates the Flask session (both SSO and legacy DO-APP format).
    """
    public = frozenset(public_paths) if public_paths else DEFAULT_PUBLIC_PATHS

    @app.before_request
    def _sso_before_request():
        path = request.path
        if any(path.startswith(p) for p in public):
            return None

        # Handle incoming launch token from Auth-App SSO
        launch_token = request.args.get('token')
        if launch_token:
            user_info = validate_token(launch_token)
            if user_info:
                # SSO session keys
                session['sso_user'] = user_info['user']
                sso_roles = [r['code'] for r in user_info.get('roles', [])]
                session['sso_roles'] = sso_roles
                session['sso_permissions'] = user_info.get('permissions', [])
                session['sso_token'] = launch_token
                session['sso_authenticated'] = True
                session['sso_perm_ts'] = time.time()
                session['embed_mode'] = request.args.get('embed') == '1'
                session.permanent = True

                # Auto-grant admin permissions for Auth-App admins
                if user_info['user'].get('is_admin'):
                    for p in _SSO_ADMIN_PERMISSIONS:
                        if p not in session['sso_permissions']:
                            session['sso_permissions'].append(p)

                # Bridge to DO-APP's legacy session format
                _bridge_sso_to_legacy(user_info, sso_roles)

                logger.info("SSO login: %s", user_info['user'].get('email'))
                _populate_g(user_info['user'], session['sso_roles'],
                            session['sso_permissions'])

                # Generate embed session token
                g.embed_session_token = _create_embed_token(
                    user_info['user'], session['sso_roles'],
                    session['sso_permissions'])
                return None
            else:
                logger.warning("Invalid launch token from %s", request.remote_addr)

        # Handle embed session token (cookie-free fallback for iframes)
        embed_token = (
            request.args.get('embed_token')
            or request.form.get('embed_token')
            or request.headers.get('X-Embed-Token')
        )
        if embed_token:
            payload = _validate_embed_token(embed_token)
            if payload:
                user_dict = {'id': payload['uid'], 'email': payload['email']}
                session['sso_user'] = user_dict
                session['sso_roles'] = payload['roles']
                session['sso_permissions'] = payload['perms']
                session['sso_authenticated'] = True
                _populate_g(user_dict, payload['roles'], payload['perms'])
                g.embed_session_token = _create_embed_token(
                    user_dict, payload['roles'], payload['perms'])

                # Bridge to legacy format for embed mode too
                _bridge_sso_to_legacy({'user': user_dict}, payload['roles'])

                logger.debug("Embed token auth: %s", payload['email'])
                return None
            else:
                logger.warning("Invalid embed token from %s", request.remote_addr)

        # Existing SSO session → populate g
        if session.get('sso_authenticated'):
            g.current_user = session.get('sso_user', {})
            g.current_user_id = g.current_user.get('id')
            g.current_roles = session.get('sso_roles', [])
            g.current_permissions = session.get('sso_permissions', [])
            g.user_id = g.current_user_id
            g.user_email = g.current_user.get('email', '')
            g.user_roles = g.current_roles
            g.user_permissions = g.current_permissions
            return None

        # Legacy local session still valid (LDAP/DB login) → pass through
        if session.get('email'):
            return None

        # Not authenticated at all
        if request.is_json:
            from flask import jsonify
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        return redirect(login_url)


def require_sso_auth(f):
    """Decorator for routes that require an active SSO session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('sso_authenticated') and not session.get('email'):
            if request.is_json:
                from flask import jsonify
                return jsonify({'success': False, 'message': 'Authentication required'}), 401
            return redirect('/auth/login')
        if session.get('sso_authenticated'):
            g.current_user = session.get('sso_user', {})
            g.current_user_id = g.current_user.get('id')
            g.current_roles = session.get('sso_roles', [])
            g.current_permissions = session.get('sso_permissions', [])
            g.user_id = g.current_user_id
            g.user_email = g.current_user.get('email', '')
            g.user_roles = g.current_roles
            g.user_permissions = g.current_permissions
        return f(*args, **kwargs)
    return decorated
