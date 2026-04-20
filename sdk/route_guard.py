"""
Route Guard — SSO authorization decorators.

Decorator semantics:
    require_permission(code)          – exactly ONE permission required
    require_all_permissions(*codes)   – ALL listed permissions required
    require_any_permissions(*codes)   – at least ONE of the listed
    require_role(role)                – exactly ONE role required
    require_any_roles(*roles)         – at least ONE of the listed roles

Usage:
    from sdk.route_guard import require_permission

    @app.route('/admin')
    @require_permission('ADMIN.PANEL')
    def admin_panel(): ...
"""
from functools import wraps
from flask import session, request, redirect, jsonify


def _check_auth():
    """Return a 401 response if not authenticated, else None."""
    if not session.get('sso_authenticated') and not session.get('email'):
        if request.is_json:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        return redirect('/auth/login')
    return None


def _deny(message='Forbidden'):
    if request.is_json:
        return jsonify({'success': False, 'message': message}), 403
    return message, 403


def require_permission(permission):
    """Require exactly ONE permission code."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            denied = _check_auth()
            if denied:
                return denied
            perms = session.get('sso_permissions', [])
            if permission not in perms:
                return _deny(f'Missing permission: {permission}')
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_all_permissions(*permission_codes):
    """Require ALL of the listed permission codes."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            denied = _check_auth()
            if denied:
                return denied
            user_perms = set(session.get('sso_permissions', []))
            required = set(permission_codes)
            if not required.issubset(user_perms):
                missing = required - user_perms
                return _deny(f'Missing permissions: {", ".join(sorted(missing))}')
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_any_permissions(*permission_codes):
    """Require at least ONE of the listed permission codes."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            denied = _check_auth()
            if denied:
                return denied
            user_perms = set(session.get('sso_permissions', []))
            required = set(permission_codes)
            if not required.intersection(user_perms):
                return _deny('Insufficient permissions')
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_role(role):
    """Require exactly ONE role code."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            denied = _check_auth()
            if denied:
                return denied
            roles = session.get('sso_roles', [])
            if role not in roles:
                return _deny(f'Missing role: {role}')
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_any_roles(*role_codes):
    """Require at least ONE of the listed role codes."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            denied = _check_auth()
            if denied:
                return denied
            user_roles = set(session.get('sso_roles', []))
            required = set(role_codes)
            if not required.intersection(user_roles):
                return _deny('Insufficient roles')
            return f(*args, **kwargs)
        return decorated
    return decorator
