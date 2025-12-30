# Deployment notes

Quick checklist to prepare the app for production:

- Set environment variables in platform or `.env` (do not commit `.env`):
  - `SECRET_KEY` — secure random value
  - `DATABASE_URL` — e.g. PostgreSQL connection string for production
  - `FLASK_ENV=production` and `DEBUG=False`
  - `SENTRY_DSN` (optional)
- Use Postgres (recommended) instead of SQLite for production when:
  - Multiple concurrent users or multiple workers are expected
  - You need reliable backups, connection pooling, or managed DB features
- SQLite is acceptable for single-user, low-traffic deployments, demos, or prototypes but not recommended for multi-worker production.

Recommended files added:
- `config.py` — centralizes configuration for dev/prod/test
- `.env.example` — template for environment variables
- `Procfile` — for platforms like Heroku
- `Dockerfile` + `.dockerignore` — for container deploys
- `wsgi.py` — WSGI entrypoint used by Gunicorn
- `requirements.txt` — pinned python dependencies

Deploy example with Docker:
- docker build -t brilliant-emporium:latest .
- docker run -p 8000:8000 -e DATABASE_URL="sqlite:///brilliant_emporium.db" -e SECRET_KEY="..." brilliant-emporium:latest

Heroku / Render:
- Add Procfile and the necessary env vars in the platform settings

Health checks:
- A `/healthz` route returns 200 for load balancer health checks

Migrations:
- Use `flask db init` / `flask db migrate` / `flask db upgrade` (Flask-Migrate & Alembic)

Security:
- Ensure `.env` is ignored by git
- Rotate `SECRET_KEY` if it was accidentally committed
