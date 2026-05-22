import yaml


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
