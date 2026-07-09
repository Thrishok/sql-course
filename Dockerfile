# Render's native Python environment can't apt-get install a JVM (read-only,
# non-root build sandbox), so this branch deploys via Docker instead — a
# Docker-based Render Web Service builds this image, giving full control over
# the base OS to install Java for PySpark.
FROM python:3.11-slim

# Java 17 (LTS) — PySpark 3.5.x officially supports up to Java 17.
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT; config.py/run.py already read it and bind 0.0.0.0.
CMD ["python", "run.py"]
