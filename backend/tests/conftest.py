"""test収集時のbackend importには専用のmemory DBを使い、hostの接続設定を引き継がない。"""

import os


# 実PostgreSQLを必要とするtestは、それぞれのfixtureで専用DBと接続URLを用意する。
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# 非Docker testの既定値。実imageの検証時は呼出元のimmutable IDを維持する。
if os.getenv("SOJ_RUN_DOCKER_TESTS") != "1":
    os.environ.setdefault("SANDBOX_IMAGE_ID", "test/sandbox@sha256:" + "a" * 64)
