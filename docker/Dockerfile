FROM python:3.13-slim

WORKDIR /src
COPY . /src

RUN apt-get update \
  && apt-get install -y --no-install-recommends bash ca-certificates git \
  && rm -rf /var/lib/apt/lists/* \
  && python -m pip install --upgrade pip \
  && python -m pip install .[test]

# Defense-in-depth: drop root (connector/node ports are >1024, non-root is fine).
RUN useradd -m -u 10001 app && chown -R app:app .
USER app

CMD ["bash", "docker/run-smoke.sh"]
