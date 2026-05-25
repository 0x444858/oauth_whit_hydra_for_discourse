from flask import Blueprint, request, redirect, send_file, current_app

from discourse import get_user_info_current_session

static_bp = Blueprint('static', __name__)

PUBLIC_ROUTES = {
    'error': 'web/error.html'
}
USER_ROUTES = {
    'manage': 'web/manage.html',
    'js/manage.js': 'web/js/manage.js',
    'css/manage.css': 'web/css/manage.css'
}
ADMIN_ROUTES = {
    'admin': 'web/manage.html',
    'js/admin.js': 'web/js/admin.js',
    'admin.html': 'web/admin.html',
}


@static_bp.route('/call/<path:path>')
def file_sender(path):
    cfg = current_app.config['APP_CONFIG']
    if path in PUBLIC_ROUTES:
        return send_file(PUBLIC_ROUTES[path])
    c_u = get_user_info_current_session(request)
    if c_u is None:
        return redirect(cfg['discourse_login_url'])
    if path in ADMIN_ROUTES:
        if c_u.get('admin') is not True:
            return '', 404
        return send_file(ADMIN_ROUTES[path])
    elif path in USER_ROUTES:
        return send_file(USER_ROUTES[path])
    return '', 404


@static_bp.route('/call/doc')
def doc_redirect():
    db = current_app.config['DB']
    url = db.get_sys_config().get('doc_url', '')
    if url:
        return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><script>location.replace({url!r}+location.hash)</script></head></html>'''
    return '', 404
