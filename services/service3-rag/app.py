"""
MediCheck Service 3 — RAG & Letter Service
Flask application factory.
"""

import os
from flask import Flask
from flask_cors import CORS
from config import config


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

    # ── CORS — allow Service 2 and local dev to call this service ─────────────
    CORS(app, origins=app.config["CORS_ORIGINS"])

    # ── Register blueprints ───────────────────────────────────────────────────
    from routes.health import health_bp
    from routes.explain import explain_bp
    from routes.draft_letter import draft_letter_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(explain_bp)
    app.register_blueprint(draft_letter_bp)

    # ── Initialize RAG chain ──────────────────────────────────────────────────
    from rag.chain import init_chain

    init_chain(app)

    return app


# ── Entry point ───────────────────────────────────────────────────────────────
# Used by: flask run (dev), gunicorn app:app (Render)

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5002)
