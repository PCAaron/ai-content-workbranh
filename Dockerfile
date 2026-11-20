FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/index.html ./
COPY web/src/ src/
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PRESS_STATE=/app/state
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 desk \
    && install -d -m 0700 -o desk -g desk /app/state
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY manage.py ./
COPY desk/ desk/
COPY press/ press/
COPY docker/start-service.sh docker/
COPY --from=frontend /build/dist web/dist
USER desk
ENTRYPOINT ["sh", "/app/docker/start-service.sh"]
CMD ["web"]
