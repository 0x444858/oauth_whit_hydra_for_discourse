import requests
import json
import secrets
from flask import Blueprint, request, redirect, render_template, make_response, jsonify, current_app

from discourse import get_user_info_current_session

oauth_bp = Blueprint('oauth', __name__)


@oauth_bp.route('/call/login')
def login():
    cfg = current_app.config['APP_CONFIG']
    login_challenge = request.args.get('login_challenge')
    if not login_challenge:
        return 'Missing login_challenge', 400
    user_info = get_user_info_current_session(request)
    if user_info is None:
        return redirect(cfg['discourse_login_url'])
    user_id: int = user_info['id']
    try:
        r = requests.put(
            cfg['hydra_login_accept_url'],
            params={'login_challenge': login_challenge},
            json={
                "subject": str(user_id),
                "remember": True,
                "remember_for": 3600
            },
            timeout=cfg['timeout']
        )
        r.raise_for_status()
        redirect_to = r.json()['redirect_to']
    except requests.exceptions.RequestException:
        return 'Internal server error point 1 in call login', 500
    return redirect(redirect_to)


@oauth_bp.route('/call/consent')
def consent():
    cfg = current_app.config['APP_CONFIG']
    consent_challenge = request.args.get('consent_challenge')
    if not consent_challenge:
        return 'Missing consent_challenge', 400
    try:
        r = requests.get(cfg['hydra_consent_info_url'],
                         params={'consent_challenge': consent_challenge},
                         timeout=cfg['timeout'])
        r.raise_for_status()
        j: dict = r.json()
        client: dict = j['client']
        metadata: dict = client.get('metadata')
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error point 1 in call consent', 500
    consent_info = {
        'challenge': j.get('challenge'),
        'requested_scopes': j.get('requested_scope'),
        'client_id': client.get('client_id'),
        'client_name': client.get('client_name'),
        'client_provider': metadata.get('provider')
    }
    nonce = secrets.token_urlsafe(16)
    html = render_template(
        'consent.html',
        consent_info=json.dumps(consent_info, ensure_ascii=False),
        nonce=nonce,
        user_page_url_prefix=cfg['discourse_user_page_url_prefix'],
        sensitive_scopes_list=json.dumps(cfg['sensitive_scopes_list'], ensure_ascii=False)
    )
    response = make_response(html)
    csp = (
        f"default-src 'self'; "
        f"script-src 'nonce-{nonce}'; "
        f"style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data:; "
        f"frame-ancestors 'none';"
    )
    response.headers['Content-Security-Policy'] = csp
    return response


@oauth_bp.route('/call/consent/accept', methods=['POST'])
def consent_accept():
    cfg = current_app.config['APP_CONFIG']
    try:
        j = request.get_json(silent=True)
        if j is None:
            return 'Invalid body', 400
        consent_challenge = j['challenge']
        now_grant_scopes = j['grant_scopes']
    except KeyError:
        return 'Invalid body', 400
    if not consent_challenge or not now_grant_scopes:
        return 'Missing consent_challenge or grant_scopes', 400
    try:
        r = requests.get(cfg['hydra_consent_info_url'],
                         params={'consent_challenge': consent_challenge},
                         timeout=cfg['timeout'])
        r.raise_for_status()
        j: dict = r.json()
        consent_requested_scope: list = j['requested_scope']
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error point 1 in call consent accept', 500
    if set(now_grant_scopes) > set(consent_requested_scope):
        return 'Invalid grant_scopes', 400
    if 'offline_access' in now_grant_scopes and any(s in cfg['sensitive_scopes_set'] for s in now_grant_scopes):
        now_grant_scopes.remove('offline_access')
    ab = {
        "grant_scope": now_grant_scopes,
        "remember": False
    }
    try:
        r = requests.put(
            cfg['hydra_consent_accept_url'],
            params={'consent_challenge': consent_challenge},
            json=ab,
            timeout=cfg['timeout']
        )
        r.raise_for_status()
        j = r.json()
        if 'redirect_to' not in j:
            return 'Internal server error point 3 in call consent accept', 500
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return 'Internal server error point 2 in call consent accept', 500
    return jsonify(j)


@oauth_bp.route('/call/consent/reject', methods=['POST'])
def consent_reject():
    cfg = current_app.config['APP_CONFIG']
    try:
        j = request.get_json(silent=True)
        if j is None:
            return 'Invalid body', 400
        consent_challenge = j['consent_challenge']
    except KeyError:
        return 'Invalid body', 400
    try:
        r = requests.put(
            cfg['hydra_consent_reject_url'],
            params={'consent_challenge': consent_challenge},
            json={'error_description': 'User canceled'},
            timeout=cfg['timeout']
        )
        r.raise_for_status()
        j = r.json()
        if 'redirect_to' not in j:
            return 'Internal server error point 2 in call consent reject', 500
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error point 1 in call consent reject', 500
    return jsonify(j)
