from flask import Flask, request, redirect, render_template, make_response, send_file, jsonify
import requests
import json
import secrets
import yaml
import re
from urllib import parse
from db import DbManager

# from functools import wraps

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


def get_user_info_current_session(req) -> dict | None:
    """
    获取当前登录用户信息
    :param req: flask 的 request 对象
    :return: 用户信息(成功) 或 None(失败)
    """
    # 从 cookies 获取 Discourse session
    request_cookies = req.cookies
    if '_t' not in request_cookies:
        return None
    # 验证 Discourse session
    try:
        r = requests.get(
            config['discourse_session_url'],
            cookies=request_cookies,
            timeout=config['timeout']
        )
        r.raise_for_status()
        user_info = r.json()['current_user']
        return user_info
    except (requests.exceptions.RequestException, KeyError, json.JSONDecodeError):
        # 任何异常都视为未登录
        return None


def get_user_info_global(uid: int | str) -> dict | None:
    """
    获取指定 uid 用户信息
    :param uid: uid
    :return: 用户信息(成功) 或 None(失败)
    """
    url = config['discourse_user_info_template_url'].format(uid=uid)

    try:
        r = requests.get(
            url,
            headers=discourse_api_headers,
            timeout=config['timeout']
        )
        r.raise_for_status()
        user_info = r.json()
        return user_info
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return None


def get_user_email_by_uid(uid: int | str) -> dict | None:
    """
    获取指定 uid 用户邮箱
    :param uid: uid
    :return: 邮箱信息(成功) 或 None(失败)
    """
    u = get_user_info_global(uid)
    if u is None:
        return None
    try:
        url = config['discourse_user_email_template_url'].format(username=parse.quote(u['username']))
        r = requests.get(
            url,
            headers=discourse_api_headers,
            timeout=config['timeout']
        )
        r.raise_for_status()
        j = r.json()
        email: str = j['email']
        secondary_emails: list[str] = j['secondary_emails']
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return None
    return {
        'email': email,
        'secondary_emails': secondary_emails
    }


def get_user_email_domain_by_uid(uid: int | str) -> dict | None:
    """
    获取指定 uid 用户邮箱域名
    :param uid: uid
    :return: 邮箱域名(成功) 或 None(失败)
    """
    email_info = get_user_email_by_uid(uid)
    if email_info is None:
        return None
    email = email_info['email'].split('@')[1]
    secondary_emails = [e.split('@')[1] for e in email_info['secondary_emails']]
    return {
        'email_domain': email,
        'secondary_email_domains': secondary_emails
    }


def get_access_token_info(req) -> tuple[dict, bool] | tuple[str, int]:
    """
    从 Authorization header 获取 access_token 并进行基本判断
    :param req: flask 的 request 对象
    :return: (用户字典, True) 或 (报错信息, 错误码)
    """
    access_token = req.headers.get('Authorization')
    if not access_token:
        return 'Missing access_token', 400
    access_token = access_token.split(' ')
    if access_token[0] != 'Bearer' or len(access_token) != 2:
        return 'Invalid access_token type', 400
    access_token_str: str = access_token[1]
    try:
        r = requests.post(
            config['hydra_token_verify_url'],
            data={'token': access_token_str},
            timeout=config['timeout']
        )
        r.raise_for_status()
        j: dict = r.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error point 1 in get_access_token_info', 500
    if not j.get('active'):
        return 'Access_token expired', 400
    return j, True


def check_access_token_and_scope(req, needed_scopes: list[str]) -> tuple[dict, bool] | tuple[str, int]:
    """
    检查请求是否包含合法的 access_token 以及是否包含需要的 scope
    :param req: flask 的 request 对象
    :param needed_scopes: 需要包含的 scope 列表
    :return: (token信息字典, True) 或 (报错信息, 错误码)
    """
    token_info, status = get_access_token_info(req)
    if status is not True:
        return token_info, status
    if set(needed_scopes) > set(token_info['scope'].split()):
        return 'Insufficient scope', 403
    return token_info, True


def specific_scope_check(t, scope_to_check: list[str]) -> list[bool]:
    """
    检查 token 是否包含所需 scope ,依次返回
    :param t: get_access_token_info 返回的 token信息字典
    :param scope_to_check: 需要检查的 scope 列表
    :return: bool列表，依次对应传入的 scope 是否在 token 中
    """
    token_scopes = t['scope'].split()
    return [scope in token_scopes for scope in scope_to_check]


def check_client_id(client_id: str) -> str | bool:
    """
    检查 client_id 是否符合规范
    :param client_id: client_id
    :return: True 或 拒绝原因
    """
    if len(client_id) < 3 or len(client_id) > 64:
        return 'Invalid client_id length'
    if not re.match(r'^[a-zA-Z0-9_-]+$', client_id):
        return 'Invalid client_id characters'
    return True


def check_redirect_uris(redirect_uris: list[str]) -> str | bool:
    """
    检查 redirect_uris 是否符合规范
    :param redirect_uris: redirect_uris
    :return: True 或 拒绝原因
    """
    errors = []
    for redirect_uri in redirect_uris:
        redirect_uri = redirect_uri.strip()
        if not redirect_uri:
            errors.append('Empty redirect_uri')
            continue
        if redirect_uri.startswith('http://'):
            errors.append('Redirect_uri cannot start with http://')
            continue
        if '*' in redirect_uri or '#' in redirect_uri or '?' in redirect_uri:
            errors.append('Redirect_uri cannot contain * or # or ?')
            continue
        pass
    return True if not errors else '; '.join(errors)


# def require_login(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         c_u = get_user_info_current_session(request)
#         if c_u is None:
#             return redirect(config['discourse_login_url'])
#         return f(*args, **kwargs)
#     return decorated_function


@app.route('/call/login')
def login():
    login_challenge = request.args.get('login_challenge')
    if not login_challenge:
        return 'Missing login_challenge', 400
    user_info = get_user_info_current_session(request)
    if user_info is None:
        return redirect(config['discourse_login_url'])
    user_id: int = user_info['id']
    # 通知 Hydra 用户已登录
    try:
        r = requests.put(
            config['hydra_login_accept_url'],
            params={'login_challenge': login_challenge},
            json={
                "subject": str(user_id),
                "remember": True,
                "remember_for": 3600
            },
            timeout=config['timeout']
        )
        r.raise_for_status()
        redirect_to = r.json()['redirect_to']
    except requests.exceptions.RequestException:
        return 'Internal server error point 1 in call login', 500
    return redirect(redirect_to)


@app.route('/call/consent')
def consent():
    consent_challenge = request.args.get('consent_challenge')
    if not consent_challenge:
        return 'Missing consent_challenge', 400
    try:
        r = requests.get(config['hydra_consent_info_url'],
                         params={'consent_challenge': consent_challenge},
                         timeout=config['timeout'])
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
    # test only
    # consent_info = {
    #     'challenge': 'consent_challenge_Id',
    #     'requested_scopes': [
    #         "openid",
    #         "profile",
    #         "active",
    #         "email_domain",
    #         "email",
    #         "offline_access"
    #     ],
    #     'client_id': 'local_test',
    #     'client_name': '本地测试客户端',
    #     'client_provider': {
    #         "uid": -1,
    #         "name": "system"
    #     }
    # }
    nonce = secrets.token_urlsafe(16)
    html = render_template(
        'consent.html',
        consent_info=json.dumps(consent_info, ensure_ascii=False),
        nonce=nonce,
        user_page_url_prefix=config['discourse_user_page_url_prefix'],
        sensitive_scopes_list=json.dumps(config['sensitive_scopes_list'], ensure_ascii=False)
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


@app.route('/call/consent/accept', methods=['POST'])
def consent_accept():
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
        r = requests.get(config['hydra_consent_info_url'],
                         params={'consent_challenge': consent_challenge},
                         timeout=config['timeout'])
        r.raise_for_status()
        j: dict = r.json()
        consent_requested_scope: list = j['requested_scope']
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error point 1 in call consent accept', 500
    if set(now_grant_scopes) > set(consent_requested_scope):
        return 'Invalid grant_scopes', 400
    if 'offline_access' in now_grant_scopes and any(s in config['sensitive_scopes_set'] for s in now_grant_scopes):
        now_grant_scopes.remove('offline_access')
    ab = {
        "grant_scope": now_grant_scopes,
        "remember": False
    }
    try:
        r = requests.put(
            config['hydra_consent_accept_url'],
            params={'consent_challenge': consent_challenge},
            json=ab,
            timeout=config['timeout']
        )
        r.raise_for_status()
        j = r.json()
        if 'redirect_to' not in j:
            return 'Internal server error point 3 in call consent accept', 500
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return 'Internal server error point 2 in call consent accept', 500
    return jsonify(j)


@app.route('/call/consent/reject', methods=['POST'])
def consent_reject():
    try:
        j = request.get_json(silent=True)
        if j is None:
            return 'Invalid body', 400
        consent_challenge = j['consent_challenge']
    except KeyError:
        return 'Invalid body', 400
    try:
        r = requests.put(
            config['hydra_consent_reject_url'],
            params={'consent_challenge': consent_challenge},
            json={'error_description': 'User canceled'},
            timeout=config['timeout']
        )
        r.raise_for_status()
        j = r.json()
        if 'redirect_to' not in j:
            return 'Internal server error point 2 in call consent reject', 500
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error point 1 in call consent reject', 500
    return jsonify(j)


@app.route('/call/userinfo')
def userinfo():
    token_info, status = check_access_token_and_scope(request, ['profile'])
    if status is not True:
        return token_info, status
    try:
        uid = int(token_info.get('sub'))
        client_id = token_info.get('client_id')
    except ValueError:
        return 'Internal server error point 1 in userinfo', 400
    u = get_user_info_global(uid)
    if u is None:
        return 'Internal server error point 2 in userinfo', 500
    rt_dict = {
        'id': u.get('id'),
        'username': u.get('username'),
        'name': u.get('name'),
        'avatar_template': u.get('avatar_template'),
        'title': u.get('title'),
        'trust_level': u.get('trust_level'),
        'admin': u.get('admin'),
        'moderator': u.get('moderator'),
        'groups': [
            {
                'id': g.get('id'),
                'name': g.get('name')
            }
            for g in u.get('groups')
        ]
    }
    used_scopes = {'profile'}
    additional = request.args.get('additional')
    if additional == 'active':
        sc = specific_scope_check(token_info, ['active'])
        if sc[0] is True:
            rt_dict |= {
                'created_at': u.get('created_at'),
                'days_visited': u.get('days_visited'),
                'flags_received_count': u.get('flags_received_count'),
                'last_seen_at': u.get('last_seen_at'),
                'like_count': u.get('like_count'),
                'like_given_count': u.get('like_given_count'),
                'post_count': u.get('post_count'),
                'posts_read_count': u.get('posts_read_count'),
                'time_read': u.get('time_read'),
                'topic_count': u.get('topic_count'),
                'topics_entered': u.get('topics_entered'),
            }
            used_scopes |= {'active'}
    db.log_access(client_id, uid, used_scopes)
    return jsonify(rt_dict)


@app.route('/call/userinfo/email')
def userinfo_email():
    token_info, status = check_access_token_and_scope(request, ['email_domain'])
    if status is not True:
        return token_info, status
    try:
        uid = int(token_info.get('sub'))
        client_id = token_info.get('client_id')
    except ValueError:
        return 'Internal server error point 1 in userinfo_email', 400
    additional = request.args.get('additional')
    if additional == 'email':
        sc = specific_scope_check(token_info, ['email'])
        if sc[0] is True:
            r = get_user_email_by_uid(uid)
            used_scopes = {'email', 'email_domain'}
            db.log_access(client_id, uid, used_scopes)
            return jsonify(r)
    r = get_user_email_domain_by_uid(uid)
    used_scopes = {'email_domain'}
    db.log_access(client_id, uid, used_scopes)
    return jsonify(r)


@app.route('/call/manage/appLog')
def manage_app_log():
    uid = request.args.get('uid')
    uid_all = request.args.get('uid_all')
    time_limit = request.args.get('time_limit')
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 403
    if c_u.get('admin') is not True or uid is None:
        uid = c_u.get('id')
    if time_limit is not None:
        time_limit = int(time_limit)
    uid_all = uid_all and c_u.get('admin')
    r = db.get_recent_logs(int(uid), time_limit, uid_all)
    client_ids = [row['client_id'] for row in r]
    client_dict = db.get_client_names(client_ids)
    return jsonify({
        'logs': r,
        'client_dict': client_dict
    })


@app.route('/call/manage/authData')
def manage_auth_data():
    uid = request.args.get('uid')
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 403
    if c_u.get('admin') is not True or uid is None:
        uid = str(c_u['id'])
    r = db.get_authorized_clients(uid)
    client_ids = [row['client_id'] for row in r]
    client_dict = db.get_client_names(client_ids)
    return jsonify(
        {
            'auth_data': r,
            'client_dict': client_dict
        }
    )


@app.route('/call/manage/revoke', methods=['POST'])
def manage_revoke():
    j = request.get_json(silent=True)
    if j is None:
        return 'Invalid body', 400
    client_id = j.get('client_id')
    uid = j.get('uid')
    revoke_all = j.get('all')
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 403
    if c_u.get('admin') is not True or uid is None:
        uid = str(c_u['id'])
    if client_id is None and revoke_all is not True:
        return 'No client id', 400
    args = {'subject': uid}
    args |= {'all': True} if revoke_all else {'client': client_id}
    try:
        r = requests.delete(
            config['hydra_token_revoke_url'],
            params=args,
            timeout=config['timeout']
        )
        if r.status_code == 204:
            return '', 204
        else:
            j = r.json()
            return 'Revoke failed', j['status_code']
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error', 500


@app.route('/call/manage/myApps')
def manage_my_app():
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 404
    uid = request.args.get('uid')
    uid_all = request.args.get('uid_all')
    if c_u.get('admin') is not True or uid is None:
        uid = str(c_u['id'])
    uid_all = uid_all and c_u.get('admin') is True
    page = request.args.get('page', 1)
    return jsonify(db.get_client_by_uid(uid, page, uid_all))


@app.route('/call/manage/applyNewApp', methods=['POST'])
def apply_new_app():
    j = request.get_json(silent=True)
    if j is None:
        return 'Invalid body', 400
    client_id = j.get('client_id')
    client_name = j.get('client_name')
    redirect_uris = j.get('redirect_uris')
    scope = j.get('scope')
    if not all([client_id, client_name, redirect_uris, scope]):
        return 'Missing parameter', 400
    if not all([isinstance(client_id, str), isinstance(client_name, str), isinstance(redirect_uris, list),
                isinstance(scope, str)]):
        return 'Invalid body', 400
    tc = check_client_id(client_id)
    if tc is not True:
        return tc, 400
    if len(client_name) > 64:
        return 'Client name too long', 400
    tr = check_redirect_uris(redirect_uris)
    if tr is not True:
        return tr, 400
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 403
    sys_configs = db.get_sys_config()
    if sys_configs.get('allow_new_client_apply') == 'f' and c_u.get('admin') is not True:
        return 'New client apply is not allowed', 403
    uid = c_u.get('id')
    username = c_u.get('username')
    try:
        r = requests.get(config['hydra_client_template_url'].format(client_id=client_id), timeout=config['timeout'])
        if r.status_code == 200:
            return 'Client_id exists, please use another one', 400
    except requests.exceptions.RequestException:
        return 'Internal server error', 500
    try:
        r = requests.post(
            config['hydra_clients_url'],
            json={
                'client_id': client_id,
                'client_name': client_name,
                'redirect_uris': redirect_uris,
                'scope': scope,
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "client_secret_basic",
                "owner": str(uid),
                "metadata": {
                    "provider": {
                        "uid": uid,
                        "name": username
                    }
                }
            },
            timeout=config['timeout']
        )
        if r.status_code == 201:
            db.log_change(uid, username, 'client', client_id, 'create_client', None, None, None)
            j = r.json()
            response = make_response(jsonify(
                {
                    'client_id': j.get('client_id'),
                    'client_name': j.get('client_name'),
                    'client_secret': j.get('client_secret'),
                    'redirect_uris': j.get('redirect_uris'),
                    'scope': j.get('scope'),
                    'owner': j.get('owner')
                })
            )
            response.status_code = 201
            return response
        else:
            return 'Apply failed', r.status_code
    except requests.exceptions.RequestException:
        return 'Internal server error', 500


@app.route('/call/manage/deleteApp', methods=['POST'])
def delete_app():
    client_id = request.form.get('client_id')
    if not client_id:
        return 'Missing parameter', 400
    tc = check_client_id(client_id)
    if tc is not True:
        return tc, 400
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 403
    try:
        r = requests.get(config['hydra_client_template_url'].format(client_id=client_id), timeout=config['timeout'])
        if r.status_code != 200:
            return 'Client_id not exists', 400
        client_info = r.json()
    except requests.exceptions.RequestException:
        return 'Internal server error', 500
    if str(c_u.get('id')) != client_info.get('owner') and c_u.get('admin') is not True:
        return 'Permission denied', 403
    try:
        r = requests.delete(
            config['hydra_client_template_url'].format(client_id=client_id),
            timeout=config['timeout']
        )
        if r.status_code == 204:
            db.log_change(c_u['id'], c_u['username'], 'client', client_id, 'delete_client', None, None, None)
            return '', 204
        else:
            return 'Delete failed', r.status_code
    except requests.exceptions.RequestException:
        return 'Internal server error', 500


@app.route('/call/manage/updateApp', methods=['POST'])
def update_app():
    j = request.get_json(silent=True)
    if not j or not isinstance(j, dict):
        return 'Invalid body', 400
    client_id = j.get('client_id')
    client_name = j.get('client_name')
    redirect_uris = j.get('redirect_uris')
    scope = j.get('scope')
    reset_client_secret = j.get('reset_client_secret')
    new_owner = j.get('new_owner')
    reason = j.get('reason')
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 403
    tc = check_client_id(client_id)
    if tc is not True:
        return tc, 400
    if len(client_name) > 64:
        return 'Client name too long', 400
    try:
        r = requests.get(config['hydra_client_template_url'].format(client_id=client_id), timeout=config['timeout'])
        if r.status_code != 200:
            return 'Client_id not exists', 400
        client_info = r.json()
    except requests.exceptions.RequestException:
        return 'Internal server error', 500
    if str(c_u.get('id')) != client_info.get('owner') and c_u.get('admin') is not True:
        return 'Permission denied', 403
    op_list = []
    log_list = []
    if redirect_uris:
        tr = check_redirect_uris(redirect_uris)
        if tr is not True:
            return tr, 400
        old_r = '\n'.join(client_info.get('redirect_uris'))
        new_r = '\n'.join(redirect_uris)
        if old_r != new_r:
            op_list.append({'op': 'replace', 'path': '/redirect_uris', 'value': redirect_uris})
            log_list.append(('change_redirect_uris', old_r, new_r))
    if new_owner and str(new_owner) != client_info.get('owner') and c_u.get('admin') is True:
        new_owner_info = get_user_info_global(new_owner)
        if new_owner_info is None:
            return 'New owner not exists', 400
        op_list.append({'op': 'replace', 'path': '/owner', 'value': str(new_owner)})
        op_list.append({'op': 'replace', 'path': '/metadata/provider',
                        'value': {'uid': new_owner, 'name': new_owner_info.get('username')}})
        log_list.append(('change_owner', client_info.get('owner'), new_owner))
    if client_name and client_name != client_info.get('client_name'):
        op_list.append({'op': 'replace', 'path': '/client_name', 'value': client_name})
        log_list.append(('change_client_name', client_info.get('client_name'), client_name))
    if scope and scope != client_info.get('scope'):
        op_list.append({'op': 'replace', 'path': '/scope', 'value': scope})
        log_list.append(('change_scope', client_info.get('scope'), scope))
    if reset_client_secret:
        new_secret = secrets.token_urlsafe(32)
        op_list.append({'op': 'replace', 'path': '/client_secret', 'value': new_secret})
        log_list.append(('reset_client_secret', None, None))
    if op_list:
        try:
            r = requests.patch(config['hydra_client_template_url'].format(client_id=client_id), json=op_list,
                               timeout=config['timeout'])
            if r.status_code == 200:
                for log in log_list:
                    db.log_change(c_u['id'], c_u['username'], 'client', client_id, *log, action_reason=reason)
                j = r.json()
                return jsonify({
                    'client_id': j.get('client_id'),
                    'client_name': j.get('client_name'),
                    'client_secret': j.get('client_secret'),
                    'redirect_uris': j.get('redirect_uris'),
                    'scope': j.get('scope'),
                    'owner': j.get('owner')
                })
            else:
                return 'Update failed', r.status_code
        except requests.exceptions.RequestException:
            return 'Internal server error', 500


@app.route('/call/manage/changeLog')
def manage_change_log():
    c_u = get_user_info_current_session(request)
    if c_u is None or c_u.get('admin') is not True:
        return '', 404
    filters = {}
    for param in ['target_type', 'action_code', 'target_id', 'old_value', 'new_value',
                   'time_start', 'time_end', 'operator_uid', 'operator_username', 'reason']:
        val = request.args.get(param)
        if val is not None and val != '':
            filters[param] = val
    page = request.args.get('page', 1, type=int)
    return jsonify(db.get_change_logs(filters, page))


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
    }
    if path in PUBLIC_ROUTES:
        return send_file(PUBLIC_ROUTES[path])
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return redirect(config['discourse_login_url'])
    if path in ADMIN_ROUTES:
        if c_u.get('admin') is not True:
            return '', 404
        return send_file(ADMIN_ROUTES[path])
    elif path in USER_ROUTES:
        return send_file(USER_ROUTES[path])
    return '', 404


if __name__ == '__main__':
    config = load_config()
    db = DbManager(config)
    discourse_api_headers = {
        'Api-Key': config['discourse_api_key'],
        'Api-Username': 'system'
    }
    app.run(debug=False, host='127.0.0.1', port=config['listen_port'])
