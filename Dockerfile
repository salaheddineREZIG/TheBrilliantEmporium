FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Use shell form to expand $PORT variable
CMD gunicorn wsgi:app --bind 0.0.0.0:$8000 --workers 3 --worker-tmp-dir /dev/shm