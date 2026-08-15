# Use a secure, slim base image
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies needed for compiling psycopg2 or building libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt requirements.txt
COPY requirements-dev.txt requirements-dev.txt

# Install dependencies into a wheels directory
RUN pip install --no-cache-dir --user -r requirements.txt

# Final production stage
FROM python:3.11-slim as runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from the builder stage
COPY --from=builder /root/.local /root/.local
COPY . /app

# Ensure local packages are on PATH
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Run as a non-privileged system user for container security hardening
RUN useradd -u 10001 -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
