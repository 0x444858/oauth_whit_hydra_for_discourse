import re
from urllib.parse import urlparse


def check_client_id(client_id: str) -> str | bool:
    """检查 client_id 是否符合规范"""
    if len(client_id) < 3 or len(client_id) > 64:
        return 'Invalid client_id length'
    if not re.match(r'^[a-zA-Z0-9_-]+$', client_id):
        return 'Invalid client_id characters'
    return True


def check_redirect_uris(redirect_uris: list[str]) -> str | bool:
    errors = []
    for redirect_uri in redirect_uris:
        redirect_uri = redirect_uri.strip()
        if not redirect_uri:
            errors.append('Empty redirect_uri')
            continue
        try:
            parsed = urlparse(redirect_uri)
        except Exception:
            errors.append(f'Invalid URI: {redirect_uri}')
            continue
        if parsed.scheme != 'https':
            errors.append(f'Only https scheme is allowed, got "{parsed.scheme}"')
            continue
        if not parsed.hostname:
            errors.append('Redirect_uri must include a host')
            continue
        if '*' in redirect_uri or '#' in redirect_uri or '?' in redirect_uri:
            errors.append('Redirect_uri cannot contain * or # or ?')
            continue
    return True if not errors else '; '.join(errors)
