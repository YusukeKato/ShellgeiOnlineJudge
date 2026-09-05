FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS build-tools

# Poetryはbuild stageだけに置き、lock済み依存をruntime専用venvへ導入する。
RUN pip install --no-cache-dir poetry==2.4.1 \
    && python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /build
COPY pyproject.toml poetry.lock ./

FROM build-tools AS backend-dependencies
RUN poetry install --only main,backend --no-root --no-interaction --no-ansi

FROM build-tools AS runner-dependencies
RUN poetry install --only main,runner --no-root --no-interaction --no-ansi

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS runtime-common
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
