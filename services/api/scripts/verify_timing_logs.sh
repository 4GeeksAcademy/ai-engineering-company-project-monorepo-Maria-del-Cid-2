#!/usr/bin/env bash
# Script de verificación del TimingMiddleware
# Uso: bash scripts/verify_timing_logs.sh
# Requiere: docker-compose up -d en ejecución y curl

set -euo pipefail

echo "=== Verificación del TimingMiddleware ==="
echo ""

# 1. Petición GET a inventario (debería aparecer en logs)
echo "1. Enviando petición GET a /api/inventory/products..."
curl -sf -o /dev/null -w "HTTP %{http_code}\n" \
  http://localhost:8000/api/inventory/products

# 2. Petición GET a un endpoint de incidents
echo "2. Enviando petición GET a /api/incidents/summary..."
curl -sf -o /dev/null -w "HTTP %{http_code}\n" \
  http://localhost:8000/api/incidents/summary 2>/dev/null || true

# 3. Petición a ruta inexistente (debería dar 404 y loggear igual)
echo "3. Enviando petición a ruta inexistente /api/not-found..."
curl -sf -o /dev/null -w "HTTP %{http_code}\n" \
  http://localhost:8000/api/not-found 2>/dev/null || true

echo ""
echo "=== Buscando líneas de timing en los logs del contenedor backend ==="
docker compose logs backend --tail=50 2>/dev/null | grep "duration_ms" || \
  echo "(No se encontraron líneas con 'duration_ms')"

echo ""
echo "Si ves líneas 'method=... path=... status=... duration_ms=...' "
echo "el middleware está funcionando correctamente."
echo "Si no ves ninguna línea, comprueba que el contenedor backend se ha"
echo "reconstruido:  docker compose build backend && docker compose up -d"