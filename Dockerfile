# Build stage: install Python deps into a virtualenv.
FROM python:3.12-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Runtime stage: slim image with the venv + app code.
FROM python:3.12-slim
# Node is needed so Node/JS tool scripts can execute alongside Python tools.
RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    rm -rf /var/lib/apt/lists/*
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app
COPY --from=build /opt/venv /opt/venv
USER 1000:1000
WORKDIR /app
RUN mkdir -p /opt/omniforge/data && chown -R 1000:1000 /opt/omniforge
COPY --chown=1000:1000 app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
