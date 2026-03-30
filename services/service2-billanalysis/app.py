"""
MediCheck Service 2 — Bill Analysis API
Flask application factory.
"""

import os
from flask import Flask
from config import config
from extensions import db


def create_app(config_name: str = None) -> Flask:
    """
    Application factory.
    Usage:
        app = create_app()                    # uses FLASK_ENV or 'default'
        app = create_app('production')        # explicit config
        app = create_app('development')       # for local dev
    """
    app = Flask(__name__)

    # ── Load config ───────────────────────────────────────────────────────────
    config_name = config_name or os.environ.get("FLASK_ENV", "default")
    app.config.from_object(config[config_name])

    # ── Initialise extensions ─────────────────────────────────────────────────
    db.init_app(app)

    # ── Register blueprints ───────────────────────────────────────────────────
    from routes.health  import health_bp
    from routes.upload  import upload_bp
    from routes.confirm import confirm_bp
    from routes.analyse import analyse_bp
    from routes.letter  import letter_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(confirm_bp)
    app.register_blueprint(analyse_bp)
    app.register_blueprint(letter_bp)

    # ── Create DB tables ──────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    return app


# ── Entry point ───────────────────────────────────────────────────────────────
# Used by: flask run (dev), gunicorn app:app (Render)

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
