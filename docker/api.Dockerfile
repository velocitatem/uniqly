FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY apps/backend/fastapi/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy API code
COPY apps/backend/fastapi/ ./
COPY src/ ./src/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

EXPOSE 9812

CMD ["python", "server.py"]