FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
	&& apt-get upgrade -y \
	&& (apt-get purge -y python3-wheel python3-jaraco.context python3-jaraco-context || true) \
	&& apt-get autoremove -y \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
	&& python -m pip install --no-cache-dir --upgrade --force-reinstall -r /app/requirements.txt \
	&& python -m pip check

COPY src/app/ /app/

CMD ["python", "main.py"]

