from flask import Flask, request, redirect, jsonify, render_template, session
import config
import base64
import json
import secrets
import requests

app = Flask(__name__, template_folder='.')
app.secret_key = secrets.token_hex(32)

domain = config.DOMAIN
redirect_uri = f'http://127.0.0.1:{config.LISTEN_PORT}/oauth_callback'


@app.route('/')
def index():
    return render_template('index.html', domain=domain)


@app.route('/start')
def start():
    scope = request.args.get('scope', 'openid profile')
    state = secrets.token_urlsafe(20)
    session['oauth_state'] = state
    session['oauth_scope'] = scope
    params = {
        'response_type': 'code',
        'client_id': config.CLIENT_ID,
        'redirect_uri': redirect_uri,
        'scope': scope,
        'state': state,
    }
    auth_url = f'https://{domain}/oauth2/auth?{"&".join(f"{k}={v}" for k, v in params.items())}'
    return redirect(auth_url)


@app.route('/oauth_callback')
def oauth_callback():
    expected_state = session.pop('oauth_state', None)
    requested_scope = session.pop('oauth_scope', 'unknown')

    code = request.args.get('code')
    error = request.args.get('error')
    error_description = request.args.get('error_description')

    if error:
        return jsonify({
            'success': False,
            'error': error,
            'error_description': error_description,
            'stage': 'authorization',
        })

    if not code:
        return jsonify({
            'success': False,
            'error': 'missing code parameter',
            'stage': 'authorization_callback',
        }), 400

    state = request.args.get('state')
    if expected_state is None:
        return jsonify({
            'success': False,
            'error': 'no state in session (session expired or direct access)',
            'stage': 'state_validation',
        }), 400
    if state != expected_state:
        return jsonify({
            'success': False,
            'error': 'state mismatch — possible CSRF attack',
            'expected_state': expected_state,
            'received_state': state,
            'stage': 'state_validation',
        }), 400

    # Exchange authorization code for tokens
    token_result = exchange_code_for_token(code)
    if not token_result['success']:
        return jsonify(token_result), 500

    tokens = token_result['tokens']
    access_token = tokens.get('access_token')
    scopes = tokens.get('scope', '').split()

    # Decode id_token payload (without signature verification — Hydra already verified)
    id_token_claims = decode_jwt_payload(tokens.get('id_token'))

    # Test userinfo endpoints
    userinfo_results = test_userinfo_endpoints(access_token, scopes)

    # Test token refresh if offline_access was granted
    refresh_result = None
    if 'offline_access' in scopes and tokens.get('refresh_token'):
        refresh_result = test_refresh_token(tokens['refresh_token'])

    return jsonify({
        'success': True,
        'requested_scope': requested_scope,
        'granted_scope': tokens.get('scope'),
        'id_token_claims': id_token_claims,
        'expires_in': tokens.get('expires_in'),
        'userinfo': userinfo_results,
        'refresh_test': refresh_result,
    })


def exchange_code_for_token(code):
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{config.CLIENT_ID}:{config.CLIENT_SECRET}".encode()).decode()}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }
    try:
        r = requests.post(config.TOKEN_URL, headers=headers, data=data, timeout=config.TIMEOUT)
        r.raise_for_status()
        return {'success': True, 'tokens': r.json()}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': str(e), 'stage': 'token_exchange'}


def decode_jwt_payload(jwt_str):
    if not jwt_str:
        return None
    try:
        parts = jwt_str.split('.')
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += '=' * (4 - len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode())
    except Exception:
        return None


def test_userinfo_endpoints(access_token, scopes):
    results = {}
    headers = {'Authorization': f'Bearer {access_token}'}

    if 'profile' in scopes:
        url = f'https://{domain}/call/userinfo'
        results['profile'] = fetch_url(url, headers)
        if 'active' in scopes:
            results['profile_active'] = fetch_url(f'{url}?additional=active', headers)

    if 'email_domain' in scopes:
        url = f'https://{domain}/call/userinfo/email'
        results['email_domain'] = fetch_url(url, headers)
        if 'email' in scopes:
            results['email'] = fetch_url(f'{url}?additional=email', headers)

    return results


def test_refresh_token(refresh_token):
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{config.CLIENT_ID}:{config.CLIENT_SECRET}".encode()).decode()}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    }
    try:
        r = requests.post(config.TOKEN_URL, headers=headers, data=data, timeout=config.TIMEOUT)
        r.raise_for_status()
        j = r.json()
        return {
            'success': True,
            'new_access_token_preview': j.get('access_token', '')[:50] + '...',
            'new_refresh_token_preview': (j.get('refresh_token', '') or '')[:50] + '...',
            'scope': j.get('scope'),
        }
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': str(e)}


def fetch_url(url, headers):
    try:
        r = requests.get(url, headers=headers, timeout=config.TIMEOUT)
        r.raise_for_status()
        return {'status': r.status_code, 'data': r.json()}
    except requests.exceptions.RequestException as e:
        return {'status': getattr(e.response, 'status_code', None), 'error': str(e)}


if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=config.LISTEN_PORT)
