"""
Auth Client SDK — shared module for all applications integrating with
the Al Wahdania Auth Platform.

Copy this package into the target application and configure AUTH_BASE_URL
and AUTH_API_KEY in the app's environment / config.
"""
import json
import logging
import os
import re
import urllib.request
import urllib.error

logger = logging.getLogger('auth_client')

_REQUEST_TIMEOUT = 5  # seconds — keep low to avoid blocking the login flow


def _get_base_url():
    """Read AUTH_BASE_URL at call time so .env changes are picked up after load_dotenv."""
    return os.environ.get('AUTH_BASE_URL', 'http://127.0.0.1:5000')


def _get_api_key():
    """Read AUTH_API_KEY at call time."""
    return os.environ.get('AUTH_API_KEY', '')


def _api_request(method, path, data=None, token=None):
    """Low-level helper — sends a JSON request to Auth-App."""
    base_url = _get_base_url()
    api_key = _get_api_key()
    url = f"{base_url}{path}"
    body = json.dumps(data).encode('utf-8') if data else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Content-Type', 'application/json')

    if token:
        req.add_header('Authorization', f'Bearer {token}')
    elif api_key:
        req.add_header('X-API-Key', api_key)

    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            resp_body = resp.read().decode('utf-8')
            return json.loads(resp_body)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        logger.warning("Auth API error %s %s: %s %s", method, path, e.code, body[:500])
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return {'success': False, 'message': f'HTTP {e.code}: {body[:200]}'}
    except Exception as e:
        logger.error("Auth API connection error: %s", str(e))
        return {'success': False, 'message': str(e)}


def validate_token(token):
    """
    Validate a JWT (access or launch) against Auth-App.
    Returns the full response dict with user, roles, permissions on success.
    """
    result = _api_request('POST', '/api/authorize/validate-token', {'token': token})
    if result.get('success') and result.get('data', {}).get('valid'):
        return result['data']
    return None


def check_permission(user_id, permission_code, application_id=None):
    """Check if a user has a specific permission."""
    payload = {
        'user_id': user_id,
        'permission_code': permission_code,
    }
    if application_id:
        payload['application_id'] = application_id
    result = _api_request('POST', '/api/authorize/check', payload)
    if result.get('success'):
        return result['data']['has_permission']
    return False


def get_user_permissions(user_id, application_id=None):
    """Get all permission codes for a user."""
    params = f"?user_id={user_id}"
    if application_id:
        params += f"&application_id={application_id}"
    result = _api_request('GET', f'/api/authorize/permissions{params}')
    if result.get('success'):
        return result.get('data', [])
    return []


def sync_admin_pages(application_id, pages):
    """
    Sync admin pages to Auth-App on startup.
    ``pages`` is a list of dicts with page_code, page_name, page_url, etc.
    """
    result = _api_request('POST', '/api/sync/admin-pages', {
        'application_id': application_id,
        'pages': pages,
    })
    if result.get('success'):
        logger.info("Admin pages synced: %s", result.get('data', {}).get('summary'))
    else:
        logger.warning("Admin page sync failed: %s", result.get('message'))
    return result


def app_login(login_id, password, app_code):
    """
    Direct app login — validates credentials against Auth-App centrally.
    Returns dict with launch_token on success, or error info on failure.
    """
    result = _api_request('POST', '/api/auth/app-login', {
        'login_id': login_id,
        'password': password,
        'app_code': app_code,
    })
    if result.get('success') and result.get('data'):
        return result['data']
    return {'message': result.get('message', 'Login failed')}


def create_login_challenge(login_id, password, app_code):
    """
    Create a login challenge for mobile confirmation.
    Returns challenge_id + challenge_code on success.
    """
    result = _api_request('POST', '/api/auth/login-challenges', {
        'login_id': login_id,
        'password': password,
        'app_code': app_code,
    })
    if result.get('success') and result.get('data'):
        data = result['data']
        data['status'] = 'challenge_created'
        return data
    return {'message': result.get('message', 'Challenge creation failed')}


def poll_login_challenge(challenge_id, poll_token=''):
    """Poll login challenge status."""
    path = f'/api/auth/login-challenges/{challenge_id}'
    if poll_token:
        path += f'?poll_token={poll_token}'
    result = _api_request('GET', path)
    if result.get('success') and result.get('data'):
        return result['data']
    return None


def sso_login(employee_id, app_code):
    """
    Passwordless SSO — initiate login by employee ID.
    Creates a challenge and sends FCM push to user's mobile device.
    """
    result = _api_request('POST', '/api/auth/sso-login', {
        'employee_id': employee_id,
        'app_code': app_code,
    })
    if result.get('success') and result.get('data'):
        return result['data']
    return {'message': result.get('message', 'SSO login failed')}


def poll_sso_challenge(challenge_id, poll_token=''):
    """Poll SSO challenge status."""
    path = f'/api/auth/sso-poll/{challenge_id}'
    if poll_token:
        path += f'?poll_token={poll_token}'
    result = _api_request('GET', path)
    if result.get('success') and result.get('data'):
        return result['data']
    return None


# ── Access-Control SDK (Roles / Permissions / Users) ──────────────────────

def get_app_roles(application_id):
    """Get all roles for this application (API-key auth via sync endpoint)."""
    params = f'?application_id={application_id}'
    result = _api_request('GET', f'/api/sync/roles{params}')
    if result.get('success'):
        return result.get('data', [])
    logger.warning("get_app_roles failed: %s", result.get('message'))
    return []


def get_all_permissions(application_id=None):
    """List every permission registered in Auth-App (API-key auth)."""
    params = f'?application_id={application_id}' if application_id else ''
    result = _api_request('GET', f'/api/permissions{params}')
    if result.get('success'):
        return result.get('data', [])
    logger.warning("get_all_permissions failed: %s", result.get('message'))
    return []


def get_role_permissions(role_id):
    """Get permissions mapped to a specific role (API-key auth)."""
    result = _api_request('GET', f'/api/roles/{role_id}/permissions')
    if result.get('success'):
        return result.get('data', [])
    logger.warning("get_role_permissions failed: %s", result.get('message'))
    return []


def map_role_permissions(role_id, permission_ids, application_id=None):
    """Full-replace permissions for a role (API-key auth via sync endpoint)."""
    result = _api_request('PUT', f'/api/sync/roles/{role_id}/permissions',
                          data={'application_id': application_id,
                                'permission_ids': permission_ids})
    return result


def get_app_users(application_id, page=1, per_page=50):
    """List users assigned to this application (API-key auth).
    Returns (list, meta_dict) on success, (None, None) on failure."""
    params = f'?page={int(page)}&per_page={int(per_page)}'
    result = _api_request('GET', f'/api/applications/{application_id}/users{params}')
    if result.get('success'):
        return result.get('data', []), result.get('meta', {})
    logger.warning("get_app_users failed: %s", result.get('message'))
    return None, None


def get_user_roles(user_id, application_id=None):
    """Get roles assigned to a user (API-key auth via sync endpoint)."""
    params = f'?application_id={application_id}' if application_id else ''
    result = _api_request('GET', f'/api/sync/users/{user_id}/roles{params}')
    if result.get('success'):
        return result.get('data', [])
    logger.warning("get_user_roles failed: %s", result.get('message'))
    return []


def sync_user_roles(user_id, application_id, role_codes):
    """Replace user's roles for this application (API-key auth via sync endpoint)."""
    result = _api_request('PUT', f'/api/sync/users/{user_id}/roles', data={
        'application_id': application_id,
        'role_codes': role_codes,
    })
    return result


def get_effective_permissions(user_id, application_id):
    """Resolve effective permission codes for a user (API-key auth)."""
    params = f'?application_id={application_id}'
    result = _api_request('GET', f'/api/users/{user_id}/permissions{params}')
    if result.get('success'):
        return result.get('data', [])
    logger.warning("get_effective_permissions failed: %s", result.get('message'))
    return []


def refresh_session_permissions(user_id, application_id):
    """Fetch fresh permissions from Auth-App and return them as a list of codes."""
    perms = get_effective_permissions(user_id, application_id)
    return [p['code'] if isinstance(p, dict) else p for p in perms]


def persist_env_config(updates):
    """Persist key-value pairs to the project .env file.
    `updates` is a dict of ENV_KEY -> value.
    Synchronous I/O is acceptable here — config saves are rare admin actions."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    env_path = os.path.normpath(env_path)

    if not updates:
        return

    # Sanitize: strip newlines and control characters to prevent env injection
    sanitized = {}
    for k, v in updates.items():
        clean = re.sub(r'[\r\n\x00-\x1f]', '', str(v))
        sanitized[k] = clean
    updates = sanitized

    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            env_key = stripped.split('=', 1)[0].strip()
            if env_key in updates:
                new_lines.append(f'{env_key}="{updates[env_key]}"\n')
                updated_keys.add(env_key)
                continue
        new_lines.append(line)

    for env_key, env_val in updates.items():
        if env_key not in updated_keys:
            new_lines.append(f'{env_key}="{env_val}"\n')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)


def verify_connectivity(auth_url, api_key=''):
    """Test connectivity and API reachability of an Auth-App instance.
    Returns dict with 'connectivity', 'api_reachable', 'success', 'message'."""
    result = {'connectivity': False, 'api_reachable': False, 'success': False, 'message': ''}

    # Step 1: Connectivity check
    try:
        req = urllib.request.Request(auth_url, method='GET')
        req.add_header('User-Agent', 'DO-Admin/1.0')
        with urllib.request.urlopen(req, timeout=8) as resp:
            connectivity_ok = resp.status < 500
    except urllib.error.HTTPError as e:
        connectivity_ok = e.code < 500
    except Exception as exc:
        result['message'] = f'Cannot reach Auth server: {exc}'
        return result

    result['connectivity'] = connectivity_ok
    if not connectivity_ok:
        result['message'] = 'Auth server returned a server error.'
        return result

    # Step 2: API authentication check
    try:
        test_url = f"{auth_url.rstrip('/')}/api/authorize/validate-token"
        body = json.dumps({'token': '__connection_test__'}).encode('utf-8')
        req = urllib.request.Request(test_url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('User-Agent', 'DO-Admin/1.0')
        if api_key:
            req.add_header('X-API-Key', api_key)
        with urllib.request.urlopen(req, timeout=8) as resp:
            result['api_reachable'] = True
            result['success'] = True
            result['message'] = 'API endpoint responded successfully.'
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403, 422):
            result['api_reachable'] = True
            result['success'] = True
            result['message'] = f'API endpoint reachable (HTTP {e.code}).'
        else:
            result['message'] = f'API returned HTTP {e.code}.'
    except Exception as exc:
        result['message'] = f'API check failed: {exc}'

    if not result['success']:
        result['message'] = f"Server reachable but API check failed. {result['message']}"
    return result


def create_role(application_id, code, name, description='', scope_type='APPLICATION'):
    """Create a new role via the sync endpoint (single-role push)."""
    role_data = {
        'code': code,
        'name': name,
        'description': description,
        'scope_type': scope_type,
    }
    result = _api_request('POST', '/api/sync/roles', data={
        'application_id': application_id,
        'roles': [role_data],
    })
    if result.get('success'):
        created = result.get('data', {}).get('created', [])
        if created:
            return {'success': True, 'role_id': created[0].get('id'), 'code': code}
        return {'success': True, 'message': 'Role already exists or was updated'}
    return {'success': False, 'message': result.get('message', 'Failed to create role')}
