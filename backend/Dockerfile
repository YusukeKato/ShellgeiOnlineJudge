FROM python:3.12.15-slim-trixie@sha256:e2e1e343308c173790faed72f2b2592fb201619fcde30af505883ded3f474ea5 AS build-tools

# Poetryはbuild stageだけに置き、lock済み依存をruntime専用venvへ導入する。
RUN pip install --no-cache-dir poetry==2.5.1 \
    && python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /build
COPY pyproject.toml poetry.lock ./

FROM build-tools AS backend-dependencies
RUN poetry install --only main,backend --no-root --no-interaction --no-ansi

FROM build-tools AS runner-dependencies
RUN poetry install --only main,runner --no-root --no-interaction --no-ansi

FROM python:3.12.15-slim-trixie@sha256:e2e1e343308c173790faed72f2b2592fb201619fcde30af505883ded3f474ea5 AS runtime-common
LABEL org.opencontainers.image.version="3.0.2"

# Python baseを維持し、CVE-2026-103111の修正済みPCRE2だけを限定更新する。
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade libpcre2-8-0=10.46-1~deb13u3 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp
RUN groupadd --gid 10001 soj \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin soj
WORKDIR /app/backend

# 専用API・DB・Docker実装へ依存しない共有packageと問題dataを収録する。所有者はrootのままにする。
COPY backend/soj_shared/ ./soj_shared/
COPY problems/v3/ ./problems/v3/
COPY problems/image/ ./problems/image/
USER 10001:10001

FROM runtime-common AS runner
COPY --from=runner-dependencies /opt/venv /opt/venv
COPY backend/soj_runner/ ./soj_runner/
CMD ["uvicorn", "soj_runner.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-proxy-headers", "--no-access-log"]

# 最終stageを公開backendとし、target未指定の既存buildも公開API用imageを生成する。
FROM runtime-common AS backend
COPY --from=backend-dependencies /opt/venv /opt/venv
COPY backend/soj_backend/ ./soj_backend/
CMD ["uvicorn", "soj_backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
