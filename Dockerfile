FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN python -m venv "$VIRTUAL_ENV"

COPY agent/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY agent/ /app/

# Default telemetry location; override with a mounted volume in prod
# (e.g. CONTENTOPS_DB=/data/ops.db on Fly.io).
ENV CONTENTOPS_DB=/app/data/ops.db

RUN useradd --create-home --uid 10001 contentops \
    && mkdir -p /app/data \
    && chown -R contentops:contentops /app /opt/venv

USER contentops

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import main, config, tools.sheets, observability, quality_gate" || exit 1

# Default process is the Slack bot. Override to run the dashboard:
#   docker run ... python main.py dashboard
CMD ["python", "main.py", "bot"]

LABEL org.opencontainers.image.title="Newtuple ContentOps Agent" \
      org.opencontainers.image.description="Slack Socket Mode agent for Newtuple ContentOps" \
      org.opencontainers.image.source="https://github.com/shailesh-svg/newtuple-contentops"
