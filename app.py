# app.py
from flask import Flask, render_template, redirect, url_for, jsonify
from extensions import db, login_manager, csrf
from flask_migrate import Migrate
import os

# Load configuration via config.py (supports development/production/testing)
from config import DevelopmentConfig, ProductionConfig, TestingConfig

def create_app(test_config=None):
    """Application factory function"""
    app = Flask(__name__)
    
    # Choose config based on FLASK_ENV
    env = os.environ.get('FLASK_ENV', 'development').lower()
    if env == 'production':
        app.config.from_object(ProductionConfig)
    elif env == 'testing':
        app.config.from_object(TestingConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Override with explicit test config if provided (used by tests)
    if test_config:
        app.config.update(test_config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate = Migrate(app, db)

    # Optional Sentry initialization
    try:
        from sentry_sdk import init as sentry_init
        from sentry_sdk.integrations.flask import FlaskIntegration
        if app.config.get('SENTRY_DSN'):
            sentry_init(dsn=app.config.get('SENTRY_DSN'), integrations=[FlaskIntegration()])
    except Exception:
        # If sentry isn't installed or misconfigured, continue silently
        pass
    
    # Import blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.accounts import accounts_bp
    from routes.transactions import transactions_bp
    from routes.categories import categories_bp
    from routes.budgets import budgets_bp
    from routes.transfers import transfers_bp
    from routes.reports import reports_bp
    from routes.settings import settings_bp
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp, url_prefix='/accounts')
    app.register_blueprint(transactions_bp, url_prefix='/transactions')
    app.register_blueprint(categories_bp, url_prefix='/categories')
    app.register_blueprint(budgets_bp, url_prefix='/budgets')
    app.register_blueprint(transfers_bp, url_prefix='/transfers')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(settings_bp, url_prefix='/settings')

    # Jinja test: check if a date's month matches a YYYYMM month key
    def month_equal(value, month_key):
        """Return True if date `value` falls in the month represented by `month_key`.
        month_key may be an int (YYYYMM) or a string 'YYYYMM' or 'YYYY-MM'.
        """
        try:
            if value is None:
                return False
            # normalize month_key to YYYYMM string
            if isinstance(month_key, int):
                key = str(month_key)
            else:
                key = str(month_key).replace('-', '')
            if len(key) != 6:
                return False
            y = int(key[:4]); m = int(key[4:6])
            return (hasattr(value, 'year') and hasattr(value, 'month') and value.year == y and value.month == m)
        except Exception:
            return False

    app.jinja_env.tests['month_equal'] = month_equal

    
    # Root route
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return render_template('landing.html')

    # Health endpoint (useful for load balancers / platform checks)
    @app.route('/healthz')
    def healthz():
        return jsonify({'status': 'ok'}), 200
    
    # Simple 404 handler
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app

# For development
if __name__ == '__main__':
    from datetime import datetime
    app = create_app()
    app.run(debug=True)