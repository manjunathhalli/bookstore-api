# Feature: Docker — package the app the same way for every machine (yours,
# a teammate's, and eventually AWS) instead of "works on my machine".
#
# One image, two different *processes* run from it (see docker-compose.yml):
#   - the FastAPI web server   (CMD below)
#   - the Celery worker        (docker-compose overrides the command)
# Same code, same dependencies, same image — only the entrypoint differs.

FROM python:3.12-slim

# Prevents .pyc files and forces stdout/stderr to be unbuffered so `docker
# logs` shows prints/log lines immediately instead of batching them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System libraries the Python deps below need to *compile/link* against:
#   - default-libmysqlclient-dev + pkg-config: not required by PyMySQL itself
#     (it's a pure-Python driver) but harmless to include if you ever swap in
#     mysqlclient; kept minimal here since PyMySQL needs none of this.
#   - build-essential: some wheels (e.g. cryptography) fall back to compiling.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so `docker build` reuses this cached layer as long
# as requirements.txt hasn't changed, even if application code has.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
