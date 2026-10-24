ARG PYTHON_IMAGE=python:3.13-slim@sha256:e5c5e1775e212d259fa017226b2719de00a8c134335a0d4bc538dc6727984353
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BOT_PROCESS_RESTART_ENABLED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && useradd --uid 1000 --create-home bot \
    && mkdir -p /app/data && chown bot:bot /app/data
COPY --chown=bot:bot qqbot ./qqbot
USER bot
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
CMD ["python", "-m", "qqbot.app"]
