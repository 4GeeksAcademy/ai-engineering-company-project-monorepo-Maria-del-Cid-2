FROM node:24-alpine

WORKDIR /app

COPY uis/backoffice/talent-pipeline-tracker/package.json \
  uis/backoffice/talent-pipeline-tracker/package-lock.json \
  /app/backoffice/
RUN npm ci --prefix /app/backoffice

COPY uis/website /app/website
COPY uis/backoffice/talent-pipeline-tracker /app/backoffice
COPY uis/proxy-server.js uis/start.sh /app/

ENV BACKEND_URL=http://backend:8000 \
    NEXT_INTERNAL_PORT=3002 \
    NEXT_PUBLIC_NEXOVA_API_BASE=/api \
    NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE=/api

RUN chmod +x /app/start.sh

EXPOSE 3000 3001

CMD ["sh", "/app/start.sh"]
