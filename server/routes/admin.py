from flask import Blueprint, request, jsonify, current_app

from discourse import get_user_info_current_session

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/call/admin/changeLog')
def admin_change_log():
    db = current_app.config['DB']
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
