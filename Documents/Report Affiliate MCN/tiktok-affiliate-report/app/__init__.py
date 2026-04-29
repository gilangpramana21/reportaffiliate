import os
from flask import Flask
from .models.db import db


def _run_migrations(app):
    """Run idempotent schema migrations."""
    try:
        with app.app_context():
            from sqlalchemy import text
            migrations = [
                "ALTER TABLE report_records ADD COLUMN batch_job_id TEXT",
            ]
            for sql in migrations:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
    except Exception:
        pass


def create_app(config=None):
    app = Flask(__name__, template_folder="templates")

    # Default config
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///tiktok_affiliate.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "uploads"
    )
    app.config["REPORTS_FOLDER"] = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "reports"
    )
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB (naik dari 50MB untuk handle cookie panjang)

    if config:
        app.config.update(config)

    # Init SQLAlchemy
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Run migrations for new columns (idempotent)
        _run_migrations(app)

    # Register blueprints
    from .routes.upload import upload_bp
    from .routes.brands import brands_bp
    from .routes.reports import reports_bp
    from .routes.pages import pages_bp
    from .routes.scraper import scraper_bp
    from .routes.settings import settings_bp
    from .routes.images import images_bp

    app.register_blueprint(upload_bp)
    app.register_blueprint(brands_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(scraper_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(images_bp)

    return app
