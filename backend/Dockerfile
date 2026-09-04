FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /app

# Poetryのインストール
RUN pip install poetry

# 依存関係ファイルのコピー (キャッシュ効率化のため先にコピー)
COPY pyproject.toml poetry.lock* ./

# 仮想環境を作成せずにシステムにインストール
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# ソースコードのコピー
COPY backend/ ./backend/

# 問題データのコピー
COPY problems/ ./backend/problems/

# 作業ディレクトリをbackendに変更
WORKDIR /app/backend

# uvicornサーバーの起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
