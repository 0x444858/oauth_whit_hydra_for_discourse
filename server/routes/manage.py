import json
import requests
import secrets
from flask import Blueprint, request, jsonify, make_response, current_app

from discourse import get_user_info_current_session, get_user_info_global
from validation import check_client_id, check_redirect_uris

manage_bp = Blueprint('manage', __name__)


@manage_bp.route('/call/manage/appLog')
def manage_app_log():
    db = current_app.config['DB']
    uid = request.args.get('uid')
    uid_all_raw = request.args.get('uid_all')
    time_limit = request.args.get('time_limit')
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 403
    if c_u.get('admin') is not True or uid is None:
        uid = c_u.get('id')
    if time_limit is not None:
        time_limit = int(time_limit)
    uid_all = uid_all_raw is not None and c_u.get('admin') is True
    r = db.get_recent_logs(int(uid), time_limit, uid_all)
    client_ids = [row['client_id'] for row in r]
    client_dict = db.get_client_names(client_ids)
    return jsonify({
        'logs': r,
        'client_dict': client_dict
    })


@manage_bp.route('/call/manage/authData')
def manage_auth_data():
    db = current_app.config['DB']
    uid = request.args.get('uid')
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 403
    if c_u.get('admin') is not True or uid is None:
        uid = str(c_u['id'])
    r = db.get_authorized_clients(uid)
    client_ids = [row['client_id'] for row in r]
    client_dict = db.get_client_names(client_ids)
    return jsonify({
        'auth_data': r,
        'client_dict': client_dict
    })


@manage_bp.route('/call/manage/revoke', methods=['POST'])
def manage_revoke():
    cfg = current_app.config['APP_CONFIG']
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
            cfg['hydra_token_revoke_url'],
            params=args,
            timeout=cfg['timeout']
        )
        if r.status_code == 204:
            return '', 204
        else:
            j = r.json()
            return 'Revoke failed', (j.get('status_code') or 500)
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error', 500


@manage_bp.route('/call/manage/myApps')
def manage_my_app():
    db = current_app.config['DB']
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return 'Need login', 404
    uid = request.args.get('uid')
    uid_all_raw = request.args.get('uid_all')
    if c_u.get('admin') is not True or uid is None:
        uid = str(c_u['id'])
    uid_all = uid_all_raw is not None and c_u.get('admin') is True
    page = request.args.get('page', 1, type=int)
    return jsonify(db.get_client_by_uid(uid, page, uid_all))


@manage_bp.route('/call/manage/applyNewApp', methods=['POST'])
def apply_new_app():
    cfg = current_app.config['APP_CONFIG']
    db = current_app.config['DB']
    j = request.get_json(silent=True)
    if j is None:
        return 'Invalid body', 400
    client_id = j.get('client_id')
    client_name = j.get('client_name')
    redirect_uris = j.get('redirect_uris')
    scope = j.get('scope')
    if not all([client_id, client_name, redirect_uris, scope]):
        return 'Missing parameter', 400
    if not all([isinstance(client_id, str), isinstance(client_name, str),
                isinstance(scope, str)]):
        return 'Invalid body', 400
    if not isinstance(redirect_uris, list) or not all(isinstance(u, str) for u in redirect_uris):
        return 'Invalid redirect_uris format', 400
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
    if c_u.get('admin') is not True:
        sys_configs = db.get_sys_config()
        if sys_configs.get('allow_new_client_apply') == 'f':
            return 'New client apply is not allowed', 403
        allowed_ids_str = sys_configs.get('new_apply_allowed_group_ids', '')
        if allowed_ids_str:
            try:
                allowed_ids = json.loads(allowed_ids_str)
            except json.JSONDecodeError:
                allowed_ids = []
            if allowed_ids:
                user_groups = c_u.get('groups', [])
                if not {g['id'] for g in user_groups}.intersection(allowed_ids):
                    return 'You are not in an allowed group', 403
    uid = c_u.get('id')
    username = c_u.get('username')
    try:
        r = requests.get(cfg['hydra_client_template_url'].format(client_id=client_id), timeout=cfg['timeout'])
        if r.status_code == 200:
            return 'Client_id exists, please use another one', 400
    except requests.exceptions.RequestException:
        return 'Internal server error', 500
    try:
        r = requests.post(
            cfg['hydra_clients_url'],
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
            timeout=cfg['timeout']
        )
        if r.status_code == 201:
            db.log_change(uid, username, 'client', client_id, 'create_client', None, None, None)
            j = r.json()
            response = make_response(jsonify({
                'client_id': j.get('client_id'),
                'client_name': j.get('client_name'),
                'client_secret': j.get('client_secret'),
                'redirect_uris': j.get('redirect_uris'),
                'scope': j.get('scope'),
                'owner': j.get('owner')
            }))
            response.status_code = 201
            return response
        else:
            return 'Apply failed', r.status_code
    except requests.exceptions.RequestException:
        return 'Internal server error', 500


@manage_bp.route('/call/manage/deleteApp', methods=['POST'])
def delete_app():
    cfg = current_app.config['APP_CONFIG']
    db = current_app.config['DB']
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
        r = requests.get(cfg['hydra_client_template_url'].format(client_id=client_id), timeout=cfg['timeout'])
        if r.status_code != 200:
            return 'Client_id not exists', 400
        client_info = r.json()
    except requests.exceptions.RequestException:
        return 'Internal server error', 500
    if str(c_u.get('id')) != client_info.get('owner') and c_u.get('admin') is not True:
        return 'Permission denied', 403
    try:
        r = requests.delete(
            cfg['hydra_client_template_url'].format(client_id=client_id),
            timeout=cfg['timeout']
        )
        if r.status_code == 204:
            db.log_change(c_u['id'], c_u['username'], 'client', client_id, 'delete_client', None, None, None)
            return '', 204
        else:
            return 'Delete failed', r.status_code
    except requests.exceptions.RequestException:
        return 'Internal server error', 500


@manage_bp.route('/call/manage/updateApp', methods=['POST'])
def update_app():
    cfg = current_app.config['APP_CONFIG']
    db = current_app.config['DB']
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
        r = requests.get(cfg['hydra_client_template_url'].format(client_id=client_id), timeout=cfg['timeout'])
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
        if not isinstance(redirect_uris, list) or not all(isinstance(u, str) for u in redirect_uris):
            return 'Invalid redirect_uris format', 400
        tr = check_redirect_uris(redirect_uris)
        if tr is not True:
            return tr, 400
        old_r = '\n'.join(client_info.get('redirect_uris'))
        new_r = '\n'.join(redirect_uris)
        if old_r != new_r:
            op_list.append({'op': 'replace', 'path': '/redirect_uris', 'value': redirect_uris})
            log_list.append(('change_redirect_uris', old_r, new_r))
    if new_owner and str(new_owner) != client_info.get('owner') and c_u.get('admin') is True:
        try:
            new_owner = int(new_owner)
        except (ValueError, TypeError):
            return 'Invalid new_owner', 400
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
            r = requests.patch(cfg['hydra_client_template_url'].format(client_id=client_id), json=op_list,
                               timeout=cfg['timeout'])
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
    return 'Invalid request', 400
