FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
	&& apt-get upgrade -y \
	&& (apt-get purge -y python3-wheel python3-jaraco.context python3-jaraco-context || true) \
	&& apt-get autoremove -y \
	&& rm -rf /var/lib/apt/lists/*

ARG SPIFFE_HELPER_VERSION=0.11.0
RUN apt-get update \
	&& apt-get install -y --no-install-recommends ca-certificates wget \
	&& rm -rf /var/lib/apt/lists/* \
	&& wget -q https://github.com/spiffe/spiffe-helper/releases/download/v${SPIFFE_HELPER_VERSION}/spiffe-helper_v${SPIFFE_HELPER_VERSION}_Linux-x86_64.tar.gz \
	&& tar -xzf spiffe-helper_v${SPIFFE_HELPER_VERSION}_Linux-x86_64.tar.gz \
	&& mv spiffe-helper /usr/local/bin/spiffe-helper \
	&& chmod +x /usr/local/bin/spiffe-helper \
	&& rm -f spiffe-helper_v${SPIFFE_HELPER_VERSION}_Linux-x86_64.tar.gz

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
	&& python -m pip install --no-cache-dir --upgrade --force-reinstall -r /app/requirements.txt \
	&& python -m pip check

COPY src/app/ /app/

COPY scripts/container/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV RPS_BIND=0.0.0.0:9002
ENV RPS_MODE=serve
ENV RPS_MTLS=1
ENV RPS_CERT_DIR=/app/certs
ENV SPIFFE_HELPER_CONFIG=/app/spiffe-helper.conf
ENV SPIFFE_AGENT_SOCKET=/tmp/spire-agent/public/api.sock

CMD ["/app/entrypoint.sh"]
