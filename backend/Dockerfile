FROM python:3.13-slim

# .pyc files are dead weight in a container - the image is rebuilt, never
# re-run in place. Unbuffered output makes logs reach `docker logs` as they
# happen instead of sitting in a pipe buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# requirements.txt on its own first. Docker caches one layer per instruction,
# keyed on what was copied - so editing a .py file leaves the pip layer intact
# and a rebuild takes seconds instead of a minute.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Root inside a container is root on the host if anything escapes. This user
# owns only what it needs.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/staticfiles \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# The default role. Compose overrides this for the Celery worker.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--access-logfile", "-"]
