"""Integration API — receives config pushes from Auth-App Configurator."""
import logging
import os
import re

from flask import Blueprint, request, jsonify

integration_bp = Blueprint('integration_api', __name__, url_prefix='/api/integration')
logger = logging.getLogger(__name__)

_AUTH_URL_KEYS = ('AUTH_BASE_URL',)
_API_KEY_KEYS = ('AUTH_API_KEY',)


def _env_file_path():
    """Return absolute path to project-root .env file."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.env',
    )


def _update_env_file(updates: dict):
    """Update key=value pairs in the .env file in-place."""
    env_path = _env_file_path()
    if not os.path.isfile(env_path):
        raise FileNotFoundError(f'.env file not found at {env_path}')

    with open(env_path, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()

    remaining = dict(updates)
    new_lines = []
    for line in lines:
        stripped = line.strip()
        matched = False
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key = stripped.split('=', 1)[0].strip()
            if key in remaining:
                new_lines.append(f'{key}="{remaining.pop(key)}"\n')
                matched = True
        if not matched:
            new_lines.append(line)

    if remaining:
        new_lines.append('\n')
        for key, val in remaining.items():
            new_lines.append(f'{key}="{val}"\n')

    with open(env_path, 'w', encoding='utf-8') as fh:
        fh.writelines(new_lines)


@integration_bp.route('/receive-config', methods=['POST'])
def receive_config():
    """Accept a config push from Auth-App.

    Auth: X-Application-ID header must match AUTH_APP_APPLICATION_ID.
    """
    incoming_id = (request.headers.get('X-Application-ID') or '').strip()
    expected_id = os.environ.get('AUTH_APP_APPLICATION_ID', '')
    if not incoming_id or not expected_id:
        return jsonify({'success': False, 'message': 'Missing credentials'}), 401
    if incoming_id.lower() != expected_id.lower():
        logger.warning('receive-config: Application-ID mismatch')
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    auth_url = (data.get('auth_url') or '').strip()
    api_key = (data.get('api_key') or '').strip()

    if not auth_url and not api_key:
        return jsonify({'success': False, 'message': 'No config values provided'}), 400

    if auth_url:
        if not re.match(r'^https?://.+', auth_url, re.IGNORECASE):
            return jsonify({'success': False, 'message': 'Invalid auth_url format'}), 400

    env_updates = {}
    if auth_url:
        for k in _AUTH_URL_KEYS:
            env_updates[k] = auth_url
    if api_key:
        for k in _API_KEY_KEYS:
            env_updates[k] = api_key

    try:
        _update_env_file(env_updates)
    except Exception:
        logger.exception('receive-config: Failed to update .env file')
        return jsonify({'success': False, 'message': 'Failed to update .env'}), 500

    for k, v in env_updates.items():
        os.environ[k] = v

    updated = []
    if auth_url:
        updated.append('auth_url')
    if api_key:
        updated.append('api_key')
    logger.info('receive-config: Updated %s via push from Auth-App', ', '.join(updated))
    return jsonify({'success': True, 'message': 'Configuration updated', 'updated': updated})
