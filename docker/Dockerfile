FROM python:3.13-slim

WORKDIR /src
COPY . /src

RUN apt-get update \
  && apt-get install -y --no-install-recommends bash ca-certificates git \
  && rm -rf /var/lib/apt/lists/* \
  && python -m pip install --upgrade pip \
  && python -m pip install .[test]

CMD ["bash", "docker/run-smoke.sh"]
