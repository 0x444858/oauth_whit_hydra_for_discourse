from flask import Flask, request, redirect, render_template, make_response, send_file, jsonify
import yaml

app = Flask(__name__, template_folder='templates')


def load_config() -> dict:
    with open('config.yaml', 'r', encoding='utf-8') as f:
        c: dict = yaml.safe_load(f)
    discourse_url_outer: str = c['discourse_url_outer']
    discourse_url_inner: str = c['discourse_url_inner']
    hydra_admin_url: str = c['hydra_admin_url']
    return c | {
        'discourse_login_url': discourse_url_outer + '/login',
        'discourse_session_url': discourse_url_inner + '/session/current.json',
        'discourse_user_page_url_prefix': discourse_url_outer + '/u/',
        'discourse_user_info_template_url': discourse_url_inner + '/admin/users/{uid}.json',
        'discourse_user_email_template_url': discourse_url_inner + '/u/{username}/emails.json',

        'hydra_login_accept_url': hydra_admin_url + '/admin/oauth2/auth/requests/login/accept',
        'hydra_consent_info_url': hydra_admin_url + '/admin/oauth2/auth/requests/consent',
        'hydra_consent_accept_url': hydra_admin_url + '/admin/oauth2/auth/requests/consent/accept',
        'hydra_consent_reject_url': hydra_admin_url + '/admin/oauth2/auth/requests/consent/reject',
        'hydra_token_verify_url': hydra_admin_url + '/admin/oauth2/introspect',
        'hydra_token_revoke_url': hydra_admin_url + '/admin/oauth2/auth/sessions/consent',
        'hydra_client_template_url': hydra_admin_url + '/admin/clients/{client_id}',
        'hydra_clients_url': hydra_admin_url + '/admin/clients',

        'sensitive_scopes_set': set(c['sensitive_scopes_list'])
    }


@app.route('/call/<path:path>')
def file_sender(path):
    PUBLIC_ROUTES = {
        'error': 'web/error.html'
    }
    USER_ROUTES = {
        'manage': 'web/manage.html',
        'doc': 'web/doc.html',
        'js/manage.js': 'web/js/manage.js',
        'css/manage.css': 'web/css/manage.css'
    }
    ADMIN_ROUTES = {
        'admin': 'web/manage.html',
        'js/admin.js': 'web/js/admin.js',
        'admin.html': 'web/admin.html',
        'css/admin.css': 'web/css/admin.css'
    }
    ROUTES = PUBLIC_ROUTES | USER_ROUTES | ADMIN_ROUTES
    if path in ROUTES:
        return send_file(ROUTES[path])
    return '', 404


if __name__ == '__main__':
    config = load_config()
    app.run(debug=False, host='127.0.0.1', port=config['listen_port'])
