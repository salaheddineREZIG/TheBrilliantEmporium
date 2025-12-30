"""WSGI entrypoint for production servers like Gunicorn."""
from app import create_app

app = create_app()
