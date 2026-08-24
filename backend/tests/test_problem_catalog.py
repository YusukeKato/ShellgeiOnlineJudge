import asyncio
import json
from pathlib import Path

import pytest

import api.api_shellgei as api_shellgei
import main as backend_main
import scripts.problem_catalog as problem_catalog
from scripts.problem_catalog import ProblemCatalogError, build_problem_catalog


def _write_problem(
    yaml_directory: Path,
    problem_id: str,
    *,
    title_ja: object = "日本語タイトル",
    title_en: object = "English title",
) -> Path:
    yaml_directory.mkdir(parents=True, exist_ok=True)
    yaml_path = yaml_directory / f"{problem_id}.yaml"
    yaml_path.write_text(
        f"title_ja: {json.dumps(title_ja, ensure_ascii=False)}\n"
        f"title_en: {json.dumps(title_en, ensure_ascii=False)}\n",
        encoding="utf-8",
    )
    return yaml_path


def test_problem_catalog_is_sorted_and_pre_serialized(tmp_path: Path) -> None:
    yaml_directory = tmp_path / "yaml_data"
    _write_problem(yaml_directory, "STANDARD-00000002", title_en="Second")
    _write_problem(yaml_directory, "PRACTICE-00000001", title_en="First")

    catalog = build_problem_catalog(yaml_directory)
    response_data = json.loads(catalog.response_body)

    assert [problem["id"] for problem in response_data] == [
        "PRACTICE-00000001",
        "STANDARD-00000002",
    ]
    assert response_data[0]["category"] == "PRACTICE"
    assert catalog.problem_count == 2
    assert catalog.etag.startswith('"') and catalog.etag.endswith('"')


def test_problem_list_request_uses_loaded_catalog_without_reading_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    yaml_directory = tmp_path / "yaml_data"
    yaml_path = _write_problem(yaml_directory, "STANDARD-00000001")
    catalog = build_problem_catalog(yaml_directory)
    monkeypatch.setattr(problem_catalog, "_loaded_catalog", catalog)
    yaml_path.unlink()

    response = asyncio.run(api_shellgei.get_problems_list(None))

    assert response.status_code == 200
    assert response.body == catalog.response_body
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.headers["etag"] == catalog.etag


def test_problem_list_returns_not_modified_for_matching_etag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    yaml_directory = tmp_path / "yaml_data"
    _write_problem(yaml_directory, "STANDARD-00000001")
    catalog = build_problem_catalog(yaml_directory)
    monkeypatch.setattr(problem_catalog, "_loaded_catalog", catalog)

    response = asyncio.run(api_shellgei.get_problems_list(catalog.etag))

    assert response.status_code == 304
    assert response.body == b""
    assert response.headers["etag"] == catalog.etag


@pytest.mark.parametrize(
    "problem_id,title_ja,title_en",
    [
        ("INVALID_ID", "title", "title"),
        ("STANDARD-00000001", 1, "title"),
        ("STANDARD-00000001", "title", None),
    ],
)
def test_problem_catalog_rejects_invalid_metadata(
    tmp_path: Path,
    problem_id: str,
    title_ja: object,
    title_en: object,
) -> None:
    yaml_directory = tmp_path / "yaml_data"
    _write_problem(
        yaml_directory,
        problem_id,
        title_ja=title_ja,
        title_en=title_en,
    )

    with pytest.raises(ProblemCatalogError):
        build_problem_catalog(yaml_directory)


def test_problem_catalog_rejects_empty_directory(tmp_path: Path) -> None:
    yaml_directory = tmp_path / "yaml_data"
    yaml_directory.mkdir()

    with pytest.raises(ProblemCatalogError, match="no problem data found"):
        build_problem_catalog(yaml_directory)


def test_failed_reload_keeps_the_previous_complete_catalog(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    valid_directory = tmp_path / "valid"
    _write_problem(valid_directory, "STANDARD-00000001")
    previous = problem_catalog.load_problem_catalog(valid_directory)
    monkeypatch.setattr(problem_catalog, "_loaded_catalog", previous)

    with pytest.raises(ProblemCatalogError):
        problem_catalog.load_problem_catalog(tmp_path / "missing")

    assert problem_catalog.get_problem_catalog() is previous


def test_backend_startup_fails_before_database_work_when_catalog_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeRunnerClient:
        def validate_configuration(self) -> None:
            events.append("runner_validate")

    def fail_catalog_load() -> None:
        events.append("catalog_load")
        raise ProblemCatalogError("invalid problem data")

    monkeypatch.setattr(backend_main, "runner_client", FakeRunnerClient())
    monkeypatch.setattr(backend_main, "load_problem_catalog", fail_catalog_load)
    monkeypatch.setattr(
        backend_main.Base.metadata,
        "create_all",
        lambda **_kwargs: events.append("create_all"),
    )

    async def run_lifespan() -> None:
        async with backend_main.lifespan(backend_main.app):
            events.append("serving")

    with pytest.raises(ProblemCatalogError, match="invalid problem data"):
        asyncio.run(run_lifespan())

    assert events == ["runner_validate", "catalog_load"]
