# Field Radar: API + built web app on one port (Render, or any Docker host). Build with scripts/build_image.sh,
# which passes the gitignored inputs as named contexts: `pack` (the data pack) and `v2` (out/v2).
# No secrets in the image: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / APP_PASSWORD come from the host's env vars.

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# The pack minus Apetit's own workbook (not CC BY), staged so the excluded folder never reaches a final layer.
FROM busybox:1.36 AS pack_clean
COPY --from=pack . /pack
RUN rm -rf /pack/data/00_apetit_original

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026 SERVE_DB=/app/out/serve.duckdb PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=web /web/dist web/dist
COPY --from=pack_clean /pack data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026
COPY --from=v2 . out/v2
RUN test -f out/serve.duckdb && test -f out/v2/scenarios/index.json && test -f web/dist/index.html \
    && test ! -e data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026/data/00_apetit_original
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
