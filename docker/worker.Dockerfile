FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir redis celery

# Copy code with correct structure
COPY apps/worker/ ./
COPY src/ ./src/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import redis; r=redis.from_url('redis://redis:6379'); r.ping()" || exit 1

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Clean start for celerybeat
RUN rm -f /app/celerybeat-schedule*

CMD ["celery", "-A", "worker", "worker", "--beat", "--loglevel=info", "--schedule=/tmp/celerybeat-schedule"]