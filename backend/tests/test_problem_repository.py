import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import main as backend_main
import scripts.problem_repository as problem_repository_module
from models.problem import ProblemDefinitionV3
from scripts.problem_repository import (
    ProblemRepositoryError,
    build_problem_manifest,
    build_problem_repository,
    collect_problem_records,
    load_problem_repository,
    render_problem_manifest,
)
from scripts.problem_schema import dump_problem_definition, load_problem_definition


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
V3_DIRECTORY = REPOSITORY_ROOT / "problems" / "v3"
IMAGE_DIRECTORY = REPOSITORY_ROOT / "problems" / "image"
MANIFEST_PATH = V3_DIRECTORY / "manifest.json"
MINIMAL_JPEG = b"\xff\xd8test-image\xff\xd9"


def _write_repository_data(
    root: Path,
    definitions: list[ProblemDefinitionV3],
) -> tuple[Path, Path, Path]:
    # 型付き問題定義と最小JPEGを一時directoryへ書き、整合するmanifestも生成してpath群を返す。
    definition_directory = root / "v3"
    image_directory = root / "image"
    definition_directory.mkdir(parents=True)
    image_directory.mkdir(parents=True)
    for definition in definitions:
        (definition_directory / f"{definition.id}.yaml").write_text(
            dump_problem_definition(definition),
            encoding="utf-8",
        )
        (image_directory / f"{definition.id}.jpg").write_bytes(MINIMAL_JPEG)
    records = collect_problem_records(definition_directory, image_directory)
    manifest_path = definition_directory / "manifest.json"
    manifest_path.write_text(
        render_problem_manifest(build_problem_manifest(records)),
        encoding="utf-8",
    )
    return definition_directory, image_directory, manifest_path


def _one_problem_repository(tmp_path: Path) -> tuple[Path, Path, Path]:
    # 一時repository用に実データから1問を読込み、3つのdata pathを返す。
    definition = load_problem_definition(V3_DIRECTORY / "STANDARD-00000001.yaml")
    return _write_repository_data(tmp_path, [definition])


def test_checked_in_repository_is_immutable_and_manifest_matches() -> None:
    # 92問のchecked-in dataがmanifestと一致し、mappingと型付き定義を変更できないことを確認する。
    repository = build_problem_repository(
        V3_DIRECTORY,
        IMAGE_DIRECTORY,
        MANIFEST_PATH,
    )

    assert repository.problem_count == 92
    assert repository.revision == json.loads(MANIFEST_PATH.read_text())["revision"]
    assert repository.require("STANDARD-00000001").definition.id == (
        "STANDARD-00000001"
    )
    with pytest.raises(TypeError):
        repository.records["STANDARD-00000001"] = repository.require(  # type: ignore[index]
            "STANDARD-00000001"
        )
    with pytest.raises(ValidationError):
        repository.require("STANDARD-00000001").definition.id = (  # type: ignore[misc]
            "STANDARD-00000002"
        )


def test_repository_exposes_legacy_compatible_problem_detail(tmp_path: Path) -> None:
    # v3 definitionから既存詳細APIのfieldとinput.txt内容を欠落なく復元できることを確認する。
    definition = load_problem_definition(V3_DIRECTORY / "PRACTICE-awk-02.yaml")
    paths = _write_repository_data(tmp_path, [definition])
    record = build_problem_repository(*paths).require(definition.id)

    assert definition.judge.type == "text"
    assert record.input_text.startswith("aaaaa bbbbb")
    assert record.expected_output == definition.judge.expected_output
    assert record.api_detail() == {
        "title_ja": definition.title.ja,
        "title_en": definition.title.en,
        "statement_ja": definition.statement.ja,
        "statement_en": definition.statement.en,
        "input": record.input_text,
        "expected_output": record.expected_output,
        "answer": definition.reference_solution,
        "image": f"/image/{definition.id}.jpg",
    }


def test_repository_lookup_does_not_reread_problem_files(tmp_path: Path) -> None:
    # 起動時構築後にsource fileを削除しても、memory上の定義・画像をlookupできることを確認する。
    paths = _one_problem_repository(tmp_path)
    repository = build_problem_repository(*paths)
    for directory in paths[:2]:
        for path in directory.iterdir():
            path.unlink()

    record = repository.require("STANDARD-00000001")

    assert record.definition.id == "STANDARD-00000001"
    assert record.answer_image == MINIMAL_JPEG


@pytest.mark.parametrize("failure", ["missing", "extra", "corrupt"])
def test_repository_rejects_missing_extra_or_corrupt_images(
    tmp_path: Path,
    failure: str,
) -> None:
    # YAMLとJPEGのID集合不一致、およびJPEG形式破損を起動時に拒否することを確認する。
    definition_directory, image_directory, manifest_path = _one_problem_repository(
        tmp_path
    )
    image_path = image_directory / "STANDARD-00000001.jpg"
    if failure == "missing":
        image_path.unlink()
    elif failure == "extra":
        (image_directory / "STANDARD-00000002.jpg").write_bytes(MINIMAL_JPEG)
    else:
        image_path.write_bytes(b"not-a-jpeg")

    with pytest.raises(ProblemRepositoryError):
        build_problem_repository(definition_directory, image_directory, manifest_path)


def test_repository_rejects_corrupt_definition_and_manifest(
    tmp_path: Path,
) -> None:
    # schema不正YAMLと、dataから再計算したrevisionに一致しないmanifestを拒否することを確認する。
    definition_directory, image_directory, manifest_path = _one_problem_repository(
        tmp_path
    )
    definition_path = definition_directory / "STANDARD-00000001.yaml"
    valid_definition = definition_path.read_text(encoding="utf-8")
    definition_path.write_text("schema_version: 3\nid: broken\n", encoding="utf-8")
    with pytest.raises(ProblemRepositoryError, match="definition"):
        build_problem_repository(definition_directory, image_directory, manifest_path)

    definition_path.write_text(valid_definition, encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["revision"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ProblemRepositoryError, match="manifest mismatch"):
        build_problem_repository(definition_directory, image_directory, manifest_path)


def test_repository_rejects_duplicate_manifest_keys(tmp_path: Path) -> None:
    # JSON parserの後勝ちにせず、重複manifest keyを曖昧な入力として拒否することを確認する。
    definition_directory, image_directory, manifest_path = _one_problem_repository(
        tmp_path
    )
    manifest_path.write_text(
        '{"manifest_version":1,"manifest_version":1}',
        encoding="utf-8",
    )

    with pytest.raises(ProblemRepositoryError, match="invalid problem manifest"):
        build_problem_repository(definition_directory, image_directory, manifest_path)


def test_failed_repository_reload_keeps_previous_complete_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # reload構築に失敗しても、process globalへ公開済みの完全なrepositoryを保持することを確認する。
    paths = _one_problem_repository(tmp_path / "valid")
    previous = load_problem_repository(*paths)
    monkeypatch.setattr(problem_repository_module, "_loaded_repository", previous)

    with pytest.raises(ProblemRepositoryError):
        load_problem_repository(
            tmp_path / "missing-v3",
            tmp_path / "missing-image",
            tmp_path / "missing-manifest.json",
        )

    assert problem_repository_module.get_problem_repository() is previous


def test_problem_revision_is_order_independent_and_changes_with_data(
    tmp_path: Path,
) -> None:
    # record入力順ではrevisionが変わらず、問題画像の変更ではrevisionが変わることを確認する。
    definitions = [
        load_problem_definition(V3_DIRECTORY / "STANDARD-00000001.yaml"),
        load_problem_definition(V3_DIRECTORY / "STANDARD-00000002.yaml"),
    ]
    definition_directory, image_directory, _ = _write_repository_data(
        tmp_path,
        definitions,
    )
    records = collect_problem_records(definition_directory, image_directory)
    original = build_problem_manifest(records)
    reversed_order = build_problem_manifest(list(reversed(records)))
    (image_directory / "STANDARD-00000001.jpg").write_bytes(
        b"\xff\xd8changed-image\xff\xd9"
    )
    changed = build_problem_manifest(
        collect_problem_records(definition_directory, image_directory)
    )

    assert original == reversed_order
    assert original.revision != changed.revision


def test_backend_startup_stops_before_database_when_repository_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # repository検証失敗時にDB初期化やrequest受付へ進まず、backend起動を中止することを確認する。
    events: list[str] = []

    class FakeRunnerClient:
        def validate_configuration(self) -> None:
            # runner設定検証が問題data検証より先に実施されたことをeventへ記録する。
            events.append("runner_validate")

    def fail_repository_load() -> None:
        # 起動時repository検証失敗を再現し、後続処理を止める例外を送出する。
        events.append("repository_load")
        raise ProblemRepositoryError("invalid problem data")

    monkeypatch.setattr(backend_main, "runner_client", FakeRunnerClient())
    monkeypatch.setattr(
        backend_main,
        "load_problem_repository",
        fail_repository_load,
    )
    monkeypatch.setattr(
        backend_main.Base.metadata,
        "create_all",
        lambda **_kwargs: events.append("create_all"),
    )

    async def run_lifespan() -> None:
        # backend lifespanへ入り、起動処理が完了するかを非同期contextで確認する。
        async with backend_main.lifespan(backend_main.app):
            events.append("serving")

    with pytest.raises(ProblemRepositoryError, match="invalid problem data"):
        asyncio.run(run_lifespan())

    assert events == ["runner_validate", "repository_load"]
