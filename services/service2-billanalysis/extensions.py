from flask_sqlalchemy import SQLAlchemy

# Initialised here, bound to app in create_app() via db.init_app(app)
db = SQLAlchemy()
