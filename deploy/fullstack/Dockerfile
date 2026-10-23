FROM node:24-alpine AS frontend-build
WORKDIR /workspace
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src ./src
COPY public ./public
COPY docs/design/chart-style.js docs/design/chart-options.js docs/design/chart-palette.json docs/design/chart-surfaces.css ./docs/design/
RUN npm run build

FROM python:3.12-slim AS backend-runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-core.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/scripts/init-empty-database.py backend/scripts/migrate-support-workflow.py backend/scripts/manage-teacher-accounts.py backend/scripts/manage-student-assignments.py ./scripts/
COPY scripts/backup-restore-database.py ./scripts/backup-restore-database.py
RUN mkdir -p /var/lib/health-new/database /app/backend/uploads /app/backend/logs /app/backend/generated-documents /app/backend/temp \
    && useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /var/lib/health-new /app/backend
ENV DATABASE_URL=sqlite:////var/lib/health-new/database/health.db
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=4)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM nginx:1.30.6-alpine AS frontend-runtime
COPY deploy/fullstack/nginx-main.conf /etc/nginx/nginx.conf
COPY deploy/fullstack/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /workspace/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
