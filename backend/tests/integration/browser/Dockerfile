FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS dependencies
RUN pip install --no-cache-dir poetry==2.4.1 && python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY pyproject.toml poetry.lock ./
RUN poetry install --only e2e --no-root --no-interaction --no-ansi

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ENV PATH="/opt/venv/bin:$PATH" PLAYWRIGHT_BROWSERS_PATH=/ms-playwright HOME=/tmp
COPY --from=dependencies /opt/venv /opt/venv
RUN python -m playwright install --with-deps --only-shell chromium && rm -rf /var/lib/apt/lists/*
COPY backend/tests/integration/browser/check.py /checks/check.py
USER 10001:10001
CMD ["python", "/checks/check.py"]
