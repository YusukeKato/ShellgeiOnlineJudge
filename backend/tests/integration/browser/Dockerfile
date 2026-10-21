FROM python:3.12.15-slim-trixie@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2 AS python-base

# OS CA修正版を含むbaseから、pipと新規venvのseedもhash検証付きで更新する。
COPY ci/bootstrap_pip.py /tmp/soj-bootstrap-pip.py
RUN python /tmp/soj-bootstrap-pip.py --update-ensurepip \
    && rm /tmp/soj-bootstrap-pip.py

FROM python-base AS dependencies
RUN pip install --no-cache-dir poetry==2.5.1 certifi==2026.10.19 && python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY pyproject.toml poetry.lock ./
RUN poetry install --only e2e --no-root --no-interaction --no-ansi

FROM python-base
ENV PATH="/opt/venv/bin:$PATH" PLAYWRIGHT_BROWSERS_PATH=/ms-playwright HOME=/tmp NODE_OPTIONS=--use-openssl-ca
COPY --from=dependencies /opt/venv /opt/venv
RUN python -m playwright install --with-deps --only-shell chromium && rm -rf /var/lib/apt/lists/*
COPY backend/tests/integration/browser/check.py /checks/check.py
COPY backend/soj_tools/__init__.py backend/soj_tools/problem_review.py /checks/soj_tools/
USER 10001:10001
CMD ["python", "/checks/check.py"]
