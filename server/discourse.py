import requests
import json
from urllib import parse
from flask import current_app


def get_user_info_current_session(req) -> dict | None:
    """获取当前登录用户信息"""
    cfg = current_app.config['APP_CONFIG']
    request_cookies = req.cookies
    if '_t' not in request_cookies:
        return None
    try:
        r = requests.get(
            cfg['discourse_session_url'],
            cookies=request_cookies,
            timeout=cfg['timeout']
        )
        r.raise_for_status()
        user_info = r.json()['current_user']
        return user_info
    except (requests.exceptions.RequestException, KeyError, json.JSONDecodeError):
        return None


def get_user_info_global(uid: int | str) -> dict | None:
    """获取指定 uid 用户信息"""
    cfg = current_app.config['APP_CONFIG']
    api_headers = current_app.config['API_HEADERS']
    url = cfg['discourse_user_info_template_url'].format(uid=uid)
    try:
        r = requests.get(url, headers=api_headers, timeout=cfg['timeout'])
        r.raise_for_status()
        return r.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return None


def get_user_email_by_uid(uid: int | str) -> dict | None:
    """获取指定 uid 用户邮箱"""
    cfg = current_app.config['APP_CONFIG']
    api_headers = current_app.config['API_HEADERS']
    u = get_user_info_global(uid)
    if u is None:
        return None
    try:
        url = cfg['discourse_user_email_template_url'].format(username=parse.quote(u['username']))
        r = requests.get(url, headers=api_headers, timeout=cfg['timeout'])
        r.raise_for_status()
        j = r.json()
        email: str = j['email']
        secondary_emails: list[str] = j['secondary_emails']
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        return None
    return {'email': email, 'secondary_emails': secondary_emails}


def get_user_email_domain_by_uid(uid: int | str) -> dict | None:
    """获取指定 uid 用户邮箱域名"""
    email_info = get_user_email_by_uid(uid)
    if email_info is None:
        return None
    email = email_info['email'].split('@')[1]
    secondary_emails = [e.split('@')[1] for e in email_info['secondary_emails']]
    return {'email_domain': email, 'secondary_email_domains': secondary_emails}
