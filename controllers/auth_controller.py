"""
Auth controller — login, logout, ISP acceptance.
Same pattern as cGR8s: own login form calling Auth-App API,
MFA challenge flow, SSO-via-mobile, pending confirmation page.
"""

import logging
import os

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify, current_app,
)

from sdk.auth_client import (
    validate_token as sdk_validate_token,
    app_login,
    poll_login_challenge,
    sso_login,
    poll_sso_challenge,
)
from sdk.session_middleware import _bridge_sso_to_legacy
from services.auth_service import check_isp, accept_isp

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _init_sso_session(user_info, method='sso'):
    """Populate Flask session from validated Auth user info (same as cGR8s)."""
    session['sso_user'] = user_info['user']
    sso_roles = [r['code'] for r in user_info.get('roles', [])]
    session['sso_roles'] = sso_roles
    session['sso_permissions'] = user_info.get('permissions', [])
    session['sso_authenticated'] = True
    session['embed_mode'] = False          # standalone login — never embed
    session.permanent = True

    # Bridge to DO-APP legacy session format
    _bridge_sso_to_legacy(user_info, sso_roles)

    logger.info("%s login: %s", method.capitalize(), user_info['user'].get('email'))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Show login form or process direct login via Auth-App API."""
    if session.get("sso_authenticated") or session.get("email"):
        return redirect(url_for("delivery_orders.dashboard"))

    app_code = current_app.config.get(
        'AUTH_APP_CODE',
        os.getenv('AUTH_APP_CODE', 'DO'),
    )

    if request.method == "POST":
        login_id = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")

        if not login_id or not password:
            flash("Please enter both username and password.", "error")
            return render_template("auth/login.html")

        # Call Auth-App app-login API
        result = app_login(login_id, password, app_code)

        if result and result.get('status') == 'challenge_created':
            # MFA / mobile confirmation required — redirect to pending page
            return redirect(url_for('auth.pending_confirmation',
                                    challenge_id=result['challenge_id'],
                                    challenge_code=result['challenge_code'],
                                    poll_token=result.get('poll_token', '')))

        if result and result.get('launch_token'):
            # Direct login succeeded — validate token & create session
            user_info = sdk_validate_token(result['launch_token'])
            if user_info:
                _init_sso_session(user_info, method='direct')

                # ISP gate — use email from user_info directly (session bridging already done)
                email = user_info.get('user', {}).get('email', '')
                if email and not check_isp(email):
                    return redirect(url_for("auth.isp_accept"))

                return redirect(url_for("delivery_orders.dashboard"))

        # Login failed
        error_msg = 'Invalid credentials or access denied.'
        if result and result.get('message'):
            error_msg = result['message']
        flash(error_msg, 'error')
        return render_template("auth/login.html")

    return render_template("auth/login.html")


@auth_bp.route("/login/pending")
def pending_confirmation():
    """Show pending-confirmation page while waiting for mobile approval."""
    challenge_id = request.args.get('challenge_id', '')
    challenge_code = request.args.get('challenge_code', '')
    poll_token = request.args.get('poll_token', '')
    sso = request.args.get('sso', '')
    if not challenge_id:
        return redirect(url_for('auth.login'))
    return render_template('auth/pending_confirmation.html',
                           challenge_id=challenge_id,
                           challenge_code=challenge_code,
                           poll_token=poll_token,
                           sso=sso)


@auth_bp.route("/login/poll/<challenge_id>")
def poll_challenge(challenge_id):
    """AJAX endpoint — polls login challenge status from Auth API."""
    poll_token = request.args.get('poll_token', '')
    sso = request.args.get('sso', '')
    if not poll_token:
        return jsonify({'status': 'ERROR', 'message': 'Missing poll token'}), 400

    # Use SSO poll endpoint for SSO challenges, regular for MFA
    if sso:
        result = poll_sso_challenge(challenge_id, poll_token=poll_token)
    else:
        result = poll_login_challenge(challenge_id, poll_token=poll_token)
    if not result:
        return jsonify({'status': 'ERROR', 'message': 'Unable to check status'}), 500

    status = result.get('status', 'PENDING')
    response = {'status': status}

    if status == 'APPROVED' and result.get('launch_token'):
        # Validate the launch token and create session
        user_info = sdk_validate_token(result['launch_token'])
        if user_info:
            _init_sso_session(user_info, method='sso_confirmed' if sso else 'confirmed')
            response['redirect'] = url_for('delivery_orders.dashboard')

    return jsonify(response)


@auth_bp.route("/login/sso", methods=["POST"])
def sso_login_route():
    """Handle SSO login via employee ID — creates challenge, sends push to mobile."""
    employee_id = request.form.get('employee_id', '').strip()
    if not employee_id:
        return jsonify({'success': False, 'message': 'Please enter your Employee ID.'}), 400

    app_code = current_app.config.get(
        'AUTH_APP_CODE',
        os.getenv('AUTH_APP_CODE', 'DO'),
    )

    result = sso_login(employee_id, app_code)

    if result and result.get('challenge_id'):
        return jsonify({
            'success': True,
            'redirect': url_for('auth.pending_confirmation',
                                challenge_id=result['challenge_id'],
                                challenge_code=result.get('challenge_code', ''),
                                poll_token=result.get('poll_token', ''),
                                sso='1'),
        })

    error_msg = result.get('message', 'SSO login failed') if result else 'SSO login failed'
    return jsonify({'success': False, 'message': error_msg}), 400


@auth_bp.route("/isp", methods=["GET"])
def isp_accept():
    if not session.get("email"):
        return redirect(url_for("auth.login"))
    return render_template("auth/isp_accept.html")


@auth_bp.route("/isp", methods=["POST"], endpoint="isp_accept_post")
def isp_accept_post():
    email = session.get("email")
    emp_id = session.get("emp_id", 0)
    if not email:
        return redirect(url_for("auth.login"))

    errors = accept_isp(email, emp_id, request.remote_addr or "")
    if errors:
        for err in errors:
            flash(err, "danger")
        return render_template("auth/isp_accept.html")

    flash("Policy accepted. Welcome!", "success")
    return redirect(url_for("delivery_orders.dashboard"))


@auth_bp.route("/logout")
def logout():
    user_email = session.get('email') or (session.get('sso_user') or {}).get('email', 'unknown')
    session.clear()
    logger.info('User %s logged out', user_email)
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
