FROM python:3.12.16-slim-trixie@sha256:962f801b08c870ac2a51b72bf02dae38c9a4162319e5e882ec244e198188d54e AS python-base

# 初回APTからTLS検証とretry/redirect抑止を適用し、APT・zlib修正版を全派生stageへ継承する。
COPY ci/prepare_apt.sh /tmp/soj-prepare-apt.sh
RUN sh /tmp/soj-prepare-apt.sh debian /etc/ssl/certs/ca-certificates.crt \
    && apt-get install -y --no-install-recommends --only-upgrade zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -f /tmp/soj-prepare-apt.sh /etc/apt/apt.conf.d/99soj-apt-bootstrap \
    && rm -rf /var/lib/apt/lists/*

# OS CA修正版を含むbaseから、pipと新規venvのseedもhash検証付きで更新する。
COPY ci/bootstrap_pip.py /tmp/soj-bootstrap-pip.py
RUN python /tmp/soj-bootstrap-pip.py --update-ensurepip \
    && rm /tmp/soj-bootstrap-pip.py

# Playwright同梱Nodeと同じmajorの公式修正版を、digest固定で取得する。
FROM node:24.22.3@sha256:1f442b36c20ffab5e7bb8eb833faef0eb61c2716bcb7b9a68b1edf19551dab2e AS node-runtime

FROM python-base AS dependencies
RUN pip install --no-cache-dir poetry==2.5.1 certifi==2026.10.23 && python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY pyproject.toml poetry.lock ./
RUN poetry install --only e2e --no-root --no-interaction --no-ansi
# final stageへvenvをコピーする前に旧private binaryを置換し、旧copyをruntime layerへ残さない。
COPY --from=node-runtime /usr/local/bin/node /opt/venv/lib/python3.12/site-packages/playwright/driver/node
RUN test "$(/opt/venv/lib/python3.12/site-packages/playwright/driver/node --version)" = v24.22.3

FROM python-base
ENV PATH="/opt/venv/bin:$PATH" PLAYWRIGHT_BROWSERS_PATH=/ms-playwright HOME=/tmp NODE_OPTIONS=--use-openssl-ca
COPY --from=dependencies /opt/venv /opt/venv
RUN python -m playwright install --with-deps --only-shell chromium && rm -rf /var/lib/apt/lists/*
COPY backend/tests/integration/browser/check.py /checks/check.py
COPY backend/soj_tools/__init__.py backend/soj_tools/problem_review.py /checks/soj_tools/
USER 10001:10001
CMD ["python", "/checks/check.py"]
