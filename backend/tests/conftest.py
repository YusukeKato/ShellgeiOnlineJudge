"""test収集時のbackend importには専用のmemory DBを使い、hostの接続設定を引き継がない。"""

import os


# 実PostgreSQLを必要とするtestは、それぞれのfixtureで専用DBと接続URLを用意する。
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
