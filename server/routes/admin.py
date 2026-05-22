import json
from functools import wraps

from flask import Blueprint, request, jsonify, current_app

from discourse import get_user_info_current_session

admin_bp = Blueprint('admin', __name__)


def _validate_bool(value):
    if value not in ('t', 'f'):
        return "Value must be 't' or 'f'"
    return


def _validate_group_ids(value):
    if value == '':
        return None
    try:
        arr = json.loads(value)
    except json.JSONDecodeError:
        return "Value must be empty or a JSON array of integers (e.g. '[12,50,51]')"
    if not isinstance(arr, list) or not all(isinstance(x, int) for x in arr):
        return "Value must be empty or a JSON array of integers (e.g. '[12,50,51]')"
    return


SETTINGS_VALIDATORS = {
    'allow_new_client_apply': _validate_bool,
    'new_apply_allowed_group_ids': _validate_group_ids,
}


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        c_u = get_user_info_current_session(request)
        if c_u is None or c_u.get('admin') is not True:
            return '', 404
        return f(*args, **kwargs)

    return decorated


@admin_bp.route('/call/admin/changeLog')
@admin_required
def admin_change_log():
    db = current_app.config['DB']
    filters = {}
    for param in ['target_type', 'action_code', 'target_id', 'old_value', 'new_value',
                  'time_start', 'time_end', 'operator_uid', 'operator_username', 'reason']:
        val = request.args.get(param)
        if val is not None and val != '':
            filters[param] = val
    page = request.args.get('page', 1, type=int)
    return jsonify(db.get_change_logs(filters, page))


@admin_bp.route('/call/admin/settings', methods=['GET'])
@admin_required
def admin_get_settings():
    db = current_app.config['DB']
    return jsonify(db.get_sys_config())


@admin_bp.route('/call/admin/settings', methods=['POST'])
@admin_required
def admin_set_settings():
    db = current_app.config['DB']
    j = request.get_json(silent=True)
    if not isinstance(j, dict):
        return 'Invalid body', 400
    key = j.get('key')
    value = j.get('value')
    if not key or value is None:
        return 'Missing parameter', 400
    validator = SETTINGS_VALIDATORS.get(key)
    if validator:
        err = validator(value)
        if err:
            return err, 400
    else:
        return 'Invalid key', 400
    c_u = get_user_info_current_session(request)
    old = db.get_sys_config().get(key)
    db.set_sys_config(key, value)
    db.log_change(c_u['id'], c_u['username'], 'system_settings', key,
                  'change_settings', old, value, None)
    return '', 204
