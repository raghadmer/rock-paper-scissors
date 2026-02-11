FROM python:3.10-alpine

WORKDIR /app

RUN apk update \
    && apk upgrade \
    && apk cache clean

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --upgrade --force-reinstall -r /app/requirements.txt \
    && python -m pip check

COPY src/app/ /app/

COPY scripts/container/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV RPS_BIND=0.0.0.0:9002
ENV RPS_MTLS=1
ENV RPS_CERT_DIR=/app/certs

CMD ["/app/entrypoint.sh"]
