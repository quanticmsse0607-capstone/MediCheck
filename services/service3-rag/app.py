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
    import logging
    from rag.chain import init_chain, is_ready

    try:
        init_chain(app)
    except Exception as exc:
        logging.getLogger(__name__).exception(
            "RAG chain failed to initialize — aborting startup"
        )
        raise

    # ── Guard against debug-reloader resetting module globals (L5) ───────────
    # Flask's Werkzeug reloader can reload modules, resetting _vectorstore and
    # _chain to None. The before_request hook re-initializes on the next request
    # if the singletons were reset, rather than serving silent 503s.
    @app.before_request
    def _ensure_chain_initialized():
        if not is_ready():
            logging.getLogger(__name__).warning(
                "RAG chain not ready on request — re-initializing"
            )
            init_chain(app)

    return app


# ── Entry point ───────────────────────────────────────────────────────────────
# Used by: flask run (dev), gunicorn app:app (Render)

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5002)
