from flask import Flask, send_file
from config import load_config

app = Flask(__name__, template_folder='templates')


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
        'css/admin.css': 'web/css/admin.css'
    }
    ROUTES = PUBLIC_ROUTES | USER_ROUTES | ADMIN_ROUTES
    if path in ROUTES:
        return send_file(ROUTES[path])
    return '', 404


if __name__ == '__main__':
    config = load_config()
    app.run(debug=False, host='127.0.0.1', port=config['listen_port'])
