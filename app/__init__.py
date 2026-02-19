from flask import Flask
from config import Config
from data.models import db


def create_app(config=None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config or Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from app.routes import bp
    app.register_blueprint(bp)

    return app
