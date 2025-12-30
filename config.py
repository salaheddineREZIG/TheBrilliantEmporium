import os
from dotenv import load_dotenv

# Load environment variables from a local .env file when present (development only)
load_dotenv()

class Config:
    """Base configuration with sane defaults."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI') or 'sqlite:///brilliant_emporium.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    DEBUG = os.getenv('DEBUG', 'False').lower() in ('1', 'true', 'yes')
    TESTING = False

    # Session / cookie
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('1', 'true', 'yes')

    # Optional integrations
    SENTRY_DSN = os.getenv('SENTRY_DSN', '')

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///test_brilliant_emporium.db')
