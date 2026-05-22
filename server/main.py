from flask import Flask
from config_option import load_config
from db import DbManager


def create_app():
    app = Flask(__name__, template_folder='templates')
    cfg = load_config()
    app.config['APP_CONFIG'] = cfg
    app.config['DB'] = DbManager(cfg)
    app.config['API_HEADERS'] = {
        'Api-Key': cfg['discourse_api_key'],
        'Api-Username': 'system'
    }

    from routes.oauth import oauth_bp
    from routes.userinfo import userinfo_bp
    from routes.manage import manage_bp
    from routes.admin import admin_bp
    from routes.static import static_bp

    app.register_blueprint(oauth_bp)
    app.register_blueprint(userinfo_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(static_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    cfg = app.config['APP_CONFIG']
    app.run(debug=False, host='127.0.0.1', port=cfg['listen_port'])
