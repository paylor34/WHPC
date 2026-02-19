from flask import Flask
from config import Config
from data.models import db


def create_app(config=None, start_scheduler: bool = False) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config or Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from app.routes import bp
    app.register_blueprint(bp)

    if start_scheduler:
        from scheduler import start_scheduler as _start
        _scheduler = _start(app, interval_hours=Config.REFRESH_INTERVAL_HOURS)
        # Attach so routes.py can expose job status
        app.scheduler = _scheduler

    return app
