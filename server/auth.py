import requests
import json
from flask import current_app


def get_access_token_info(req) -> tuple[dict, bool] | tuple[str, int]:
    """从 Authorization header 获取 access_token 并进行基本判断"""
    cfg = current_app.config['APP_CONFIG']
    access_token = req.headers.get('Authorization')
    if not access_token:
        return 'Missing access_token', 400
    access_token = access_token.split(' ')
    if access_token[0] != 'Bearer' or len(access_token) != 2:
        return 'Invalid access_token type', 400
    access_token_str: str = access_token[1]
    try:
        r = requests.post(
            cfg['hydra_token_verify_url'],
            data={'token': access_token_str},
            timeout=cfg['timeout']
        )
        r.raise_for_status()
        j: dict = r.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return 'Internal server error point 1 in get_access_token_info', 500
    if not j.get('active'):
        return 'Access_token expired', 400
    return j, True


def check_access_token_and_scope(req, needed_scopes: list[str]) -> tuple[dict, bool] | tuple[str, int]:
    """检查请求是否包含合法的 access_token 以及是否包含需要的 scope"""
    token_info, status = get_access_token_info(req)
    if status is not True:
        return token_info, status
    if set(needed_scopes) > set(token_info['scope'].split()):
        return 'Insufficient scope', 403
    return token_info, True


def specific_scope_check(t, scope_to_check: list[str]) -> list[bool]:
    """检查 token 是否包含所需 scope，依次返回"""
    token_scopes = t['scope'].split()
    return [scope in token_scopes for scope in scope_to_check]
