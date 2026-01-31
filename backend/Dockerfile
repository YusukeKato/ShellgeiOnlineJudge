FROM python:3.12-slim

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
COPY problems/ ./backend/public/

# 作業ディレクトリをbackendに変更
WORKDIR /app/backend

RUN echo "0.0" > unixtime.txt && chmod 666 unixtime.txt \
    && echo "0" > shellgei_id.txt && chmod 666 shellgei_id.txt

# uvicornサーバーの起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]