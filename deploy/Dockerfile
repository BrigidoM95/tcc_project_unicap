FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/tcc-web
COPY tcc-web/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && useradd --create-home --uid 10001 unicap
COPY --chown=unicap:unicap tcc-web/ /app/tcc-web/
COPY deploy/entrada.sh /app/entrada.sh
RUN mkdir -p /app/tcc-web/media /app/tcc-web/staticfiles && chown -R unicap:unicap /app/tcc-web && chmod +x /app/entrada.sh
USER unicap
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/',timeout=3)" || exit 1
ENTRYPOINT ["/app/entrada.sh"]
