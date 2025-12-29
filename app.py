# app.py
from flask import Flask, render_template, redirect, url_for
from extensions import db, login_manager, csrf
from flask_migrate import Migrate
import os

def create_app():
    """Application factory function"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///brilliant_emporium.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_ENABLED'] = True
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate = Migrate(app, db)
    
    # Import blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    
    # Root route
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return render_template('landing.html')
    
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