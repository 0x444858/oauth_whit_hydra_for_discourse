from flask import Flask, request, redirect, jsonify, render_template
import config
import base64
import requests

app = Flask(__name__, template_folder='.')

domain = config.DOMAIN


@app.route('/')
def index():
    return render_template('index.html', domain=domain)


@app.route('/oauth_callback')
def oauth_callback():
    code = request.args.get('code')
    if not code:
        error = request.args.get('error')
        error_description = request.args.get('error_description')
        if not error or not error_description:
            return 'Missing code or error', 400
        return redirect(f'{config.ERROR_REDIRECT_URL}?error={error}&error_description={error_description}')
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{config.CLIENT_ID}:{config.CLIENT_SECRET}".encode()).decode()}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'http://127.0.0.1:48484/oauth_callback'
    }
    try:
        r = requests.post(
            config.TOKEN_URL,
            headers=headers,
            data=data,
            timeout=config.TIMEOUT
        )
        r.raise_for_status()
        j = r.json()
    except requests.exceptions.RequestException:
        return 'Internal server error point 1 in oauth callback', 500
    access_token = j.get('access_token')
    scope = j.get('scope')
    scopes = scope.split()
    scope_test_request_urls = []
    if 'profile' in scopes:
        url = f'https://{domain}/call/userinfo'
        scope_test_request_urls.append(url)
        if 'active' in scopes:
            url += '?additional=active'
            scope_test_request_urls.append(url)
    if 'email_domain' in scopes:
        url = f'https://{domain}/call/email'
        scope_test_request_urls.append(url)
        if 'email' in scopes:
            url += '?additional=email'
            scope_test_request_urls.append(url)
    scope_test_results = []
    for url in scope_test_request_urls:
        try:
            r = requests.get(
                url,
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=config.TIMEOUT
            )
            r.raise_for_status()
            scope_test_results.append({'url': url, 'result': r.json()})
        except requests.exceptions.RequestException:
            scope_test_results.append({'url': url, 'result': 'error'})
    return jsonify({'token': j, 'scope_test': scope_test_results})


if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=config.LISTEN_PORT)
