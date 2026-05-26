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

RUN useradd --create-home --uid 10001 contentops \
    && chown -R contentops:contentops /app /opt/venv

USER contentops

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import main, config, tools.sheets" || exit 1

CMD ["python", "main.py", "bot"]

LABEL org.opencontainers.image.title="Newtuple ContentOps Agent" \
      org.opencontainers.image.description="Slack Socket Mode agent for Newtuple ContentOps" \
      org.opencontainers.image.source="https://github.com/shailesh-svg/newtuple-contentops"
