FROM node:22.22.0-bookworm-slim

ARG PI_VERSION
ARG FRAMEWORK_VERSION

LABEL org.opencontainers.image.title="Pi Agent Bench sandbox" \
      org.opencontainers.image.version="${FRAMEWORK_VERSION}" \
      dev.pi.version="${PI_VERSION}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g --ignore-scripts "@earendil-works/pi-coding-agent@${PI_VERSION}" \
    && python3 -m pip install --break-system-packages --no-cache-dir \
        pytest==9.1.1 \
        pytest-randomly==3.15.0 \
        fastapi==0.110.3 \
        httpx==0.27.0 \
        pydantic==2.7.1 \
        sqlalchemy==2.0.29 \
        sqlalchemy-utils==0.41.2 \
        starlette==0.37.2 \
        uvicorn==0.29.0 \
    && useradd --create-home --shell /bin/bash eval \
    && mkdir -p /workspace /opt/verifiers \
    && chown eval:eval /workspace

COPY --chown=root:root verifiers/ /opt/verifiers/

RUN find /opt/verifiers -type d -exec chmod 700 {} + \
    && find /opt/verifiers -type f -exec chmod 700 {} +

ARG BENCHMARK_SOURCE_FINGERPRINT=unknown
LABEL dev.pi.benchmark-source="${BENCHMARK_SOURCE_FINGERPRINT}"

USER eval
WORKDIR /workspace
ENV HOME=/home/eval

CMD ["sleep", "infinity"]
