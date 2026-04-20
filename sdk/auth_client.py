"""
Auth Client SDK — shared module for all applications integrating with
the Al Wahdania Auth Platform.

Copy this package into the target application and configure AUTH_BASE_URL
and AUTH_API_KEY in the app's environment / config.
"""
import json
import logging
import os
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
