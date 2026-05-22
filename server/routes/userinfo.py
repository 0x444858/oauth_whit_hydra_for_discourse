from flask import Blueprint, request, jsonify, current_app

from auth import check_access_token_and_scope, specific_scope_check
from discourse import get_user_info_global, get_user_email_by_uid, get_user_email_domain_by_uid

userinfo_bp = Blueprint('userinfo', __name__)


@userinfo_bp.route('/call/userinfo')
def userinfo():
    db = current_app.config['DB']
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
            for g in (u.get('groups') or [])
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


@userinfo_bp.route('/call/userinfo/email')
def userinfo_email():
    db = current_app.config['DB']
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
