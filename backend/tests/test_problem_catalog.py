import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import api.api_shellgei as api_shellgei
from scripts.problem_catalog import build_problem_catalog
from scripts.problem_schema import load_problem_definition


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
V3_DIRECTORY = REPOSITORY_ROOT / "problems" / "v3"


def _definitions():
    # catalog単体テスト用に、順序を逆にした2件の型検証済み問題定義を返す。
    return [
        load_problem_definition(V3_DIRECTORY / "STANDARD-00000002.yaml"),
        load_problem_definition(V3_DIRECTORY / "PRACTICE-awk-01.yaml"),
    ]


def test_problem_catalog_is_sorted_and_pre_serialized() -> None:
    # 入力順に依存せずID順の一覧本文・件数・ETagが事前生成されることを確認する。
    catalog = build_problem_catalog(_definitions())
    response_data = json.loads(catalog.response_body)

    assert [problem["id"] for problem in response_data] == [
        "PRACTICE-awk-01",
        "STANDARD-00000002",
    ]
    assert response_data[0]["category"] == "PRACTICE"
    assert catalog.problem_count == 2
    assert catalog.etag.startswith('"') and catalog.etag.endswith('"')


def test_problem_catalog_rejects_empty_definitions() -> None:
    # 問題0件のcatalogを生成せず、起動時の異常として拒否することを確認する。
    with pytest.raises(ValueError, match="must not be empty"):
        build_problem_catalog([])


def test_problem_list_request_uses_repository_catalog_without_reading_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 一覧requestが検証済みrepository内の事前生成本文だけを返すことを確認する。
    catalog = build_problem_catalog(_definitions())
    repository = SimpleNamespace(catalog=catalog)
    monkeypatch.setattr(
        api_shellgei,
        "get_problem_repository",
        lambda: repository,
    )

    response = asyncio.run(api_shellgei.get_problems_list(None))

    assert response.status_code == 200
    assert response.body == catalog.response_body
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.headers["etag"] == catalog.etag


def test_problem_list_returns_not_modified_for_matching_etag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If-None-MatchがcatalogのETagと一致した場合に本文なしの304を返すことを確認する。
    catalog = build_problem_catalog(_definitions())
    repository = SimpleNamespace(catalog=catalog)
    monkeypatch.setattr(
        api_shellgei,
        "get_problem_repository",
        lambda: repository,
    )

    response = asyncio.run(api_shellgei.get_problems_list(catalog.etag))

    assert response.status_code == 304
    assert response.body == b""
    assert response.headers["etag"] == catalog.etag
