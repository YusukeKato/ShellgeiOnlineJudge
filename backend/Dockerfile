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

# import境界に必要な共有moduleと現行問題dataだけを収録する。所有者はrootのままにする。
COPY backend/models/__init__.py backend/models/execution.py backend/models/model_shellgei.py \
     backend/models/problem.py backend/models/submission.py ./models/
COPY backend/scripts/__init__.py backend/scripts/async_thread.py backend/scripts/input_validation.py \
     backend/scripts/judge.py backend/scripts/problem_catalog.py backend/scripts/problem_repository.py \
     backend/scripts/problem_schema.py backend/scripts/request_context.py backend/scripts/runner_protocol.py \
     backend/scripts/structured_logging.py ./scripts/
COPY problems/v3/ ./problems/v3/
COPY problems/image/ ./problems/image/
USER 10001:10001

FROM runtime-common AS runner
COPY --from=runner-dependencies /opt/venv /opt/venv
COPY backend/runner_main.py ./
COPY backend/scripts/admission_control.py backend/scripts/container_manager.py backend/scripts/execution_archive.py \
     backend/scripts/run_shellgei.py backend/scripts/runner_http_security.py backend/scripts/sandbox_executor.py \
     backend/scripts/sandbox_limits.py ./scripts/
CMD ["uvicorn", "runner_main:app", "--host", "0.0.0.0", "--port", "8001", "--no-proxy-headers", "--no-access-log"]

# 最終stageを公開backendとし、target未指定の既存buildも公開API用imageを生成する。
FROM runtime-common AS backend
COPY --from=backend-dependencies /opt/venv /opt/venv
COPY backend/main.py ./
COPY backend/api/ ./api/
COPY backend/migrations/ ./migrations/
COPY backend/models/execution_log.py backend/models/model_db.py backend/models/public_api.py ./models/
COPY backend/scripts/database.py backend/scripts/database_migrations.py backend/scripts/execution_log_repository.py \
     backend/scripts/execution_log_retention.py backend/scripts/request_correlation.py backend/scripts/runner_client.py \
     backend/scripts/submit_solution.py ./scripts/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
