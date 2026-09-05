import copy
from pathlib import Path

import pytest
import yaml

from soj_shared.models.problem import MAX_ARTIFACT_BYTES, MAX_FIXTURE_BYTES
from soj_tools.problem_migration import (
    ProblemMigrationError,
    main as migration_main,
    migrate_legacy_file,
    migrate_legacy_mapping,
    write_migrated_problem,
)
from soj_shared.problem_schema import (
    MAX_PROBLEM_SCHEMA_FILE_BYTES,
    ProblemSchemaError,
    dump_problem_definition,
    load_problem_definition,
    parse_problem_definition,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIRECTORY = REPOSITORY_ROOT / "problems" / "yaml_data"
V3_DIRECTORY = REPOSITORY_ROOT / "problems" / "v3"
V3_PROBLEM_IDS = tuple(path.stem for path in sorted(LEGACY_DIRECTORY.glob("*.yaml")))


def _valid_text_data() -> dict[str, object]:
    # 個別のvalidation条件だけを変更できる、最小の有効なtext問題データを返す。
    return {
        "schema_version": 3,
        "id": "STANDARD-00000001",
        "category": "STANDARD",
        "title": {"ja": "タイトル", "en": "Title"},
        "statement": {"ja": "問題文", "en": "Statement"},
        "reference_solution": "printf answer",
        "execution": {
            "stdin": "",
            "fixtures": [],
            "exit_code": "ignore",
            "stderr": "merge",
        },
        "judge": {"type": "text", "expected_output": "answer\n"},
    }


def _yaml(data: object) -> str:
    # Pythonのテストデータをschema parserへ渡すYAML文字列へ変換する。
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def test_valid_text_and_image_problem_definitions_are_typed() -> None:
    # 有効なtext問題とimage問題が、それぞれの型付きjudgeとして読み込まれることを確認する。
    text_definition = parse_problem_definition(_yaml(_valid_text_data()))
    image_definition = load_problem_definition(V3_DIRECTORY / "IMAGE-00000001.yaml")

    assert text_definition.schema_version == 3
    assert text_definition.judge.type == "text"
    assert image_definition.judge.type == "image"
    assert image_definition.judge.artifact.media_type == "image/jpeg"


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing", "title"),
        ("extra", "extra_forbidden"),
        ("version", "schema_version"),
    ],
)
def test_schema_rejects_missing_extra_and_wrong_version_fields(
    case: str,
    message: str,
) -> None:
    # 必須field不足、未知field、version不一致をfail-closedで拒否することを確認する。
    data = _valid_text_data()
    if case == "missing":
        data.pop("title")
    elif case == "extra":
        data["unknown"] = True
    else:
        data["schema_version"] = 2

    with pytest.raises(ProblemSchemaError, match=message):
        parse_problem_definition(_yaml(data))


def test_schema_rejects_wrong_field_types() -> None:
    # 文字列fieldや配列fieldへ異なる型を指定した問題定義を拒否することを確認する。
    wrong_title = _valid_text_data()
    title = wrong_title["title"]
    assert isinstance(title, dict)
    title["ja"] = 123
    wrong_fixtures = _valid_text_data()
    execution = wrong_fixtures["execution"]
    assert isinstance(execution, dict)
    execution["fixtures"] = "input.txt"

    with pytest.raises(ProblemSchemaError):
        parse_problem_definition(_yaml(wrong_title))
    with pytest.raises(ProblemSchemaError):
        parse_problem_definition(_yaml(wrong_fixtures))


def test_schema_rejects_duplicate_yaml_keys() -> None:
    # YAML parserが同名keyの後勝ちを許さず、曖昧な定義を拒否することを確認する。
    duplicate = _yaml(_valid_text_data()) + "schema_version: 3\n"

    with pytest.raises(ProblemSchemaError, match="duplicate key"):
        parse_problem_definition(duplicate)


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "/absolute",
        "nested//file",
        "./file",
        "windows\\file",
        "z.bash",
    ],
)
def test_schema_rejects_unsafe_fixture_paths(path: str) -> None:
    # fixtureがsandbox内の相対pathから逸脱する表現を拒否することを確認する。
    data = _valid_text_data()
    execution = data["execution"]
    assert isinstance(execution, dict)
    execution["fixtures"] = [{"path": path, "content": "fixture"}]

    with pytest.raises(ProblemSchemaError, match="fixture path"):
        parse_problem_definition(_yaml(data))


def test_schema_rejects_duplicate_and_oversized_fixtures() -> None:
    # fixture pathの重複と1ファイルのbyte上限超過を拒否することを確認する。
    duplicate = _valid_text_data()
    duplicate_execution = duplicate["execution"]
    assert isinstance(duplicate_execution, dict)
    duplicate_execution["fixtures"] = [
        {"path": "input.txt", "content": "one"},
        {"path": "input.txt", "content": "two"},
    ]
    oversized = copy.deepcopy(_valid_text_data())
    oversized_execution = oversized["execution"]
    assert isinstance(oversized_execution, dict)
    oversized_execution["fixtures"] = [
        {"path": "input.txt", "content": "x" * (MAX_FIXTURE_BYTES + 1)}
    ]

    with pytest.raises(ProblemSchemaError, match="unique"):
        parse_problem_definition(_yaml(duplicate))
    with pytest.raises(ProblemSchemaError, match="byte limit"):
        parse_problem_definition(_yaml(oversized))


@pytest.mark.parametrize(
    "artifact",
    [
        {
            "path": "../output.jpg",
            "media_type": "image/jpeg",
            "max_bytes": MAX_ARTIFACT_BYTES,
        },
        {
            "path": "media/output.gif",
            "media_type": "image/jpeg",
            "max_bytes": MAX_ARTIFACT_BYTES,
        },
        {
            "path": "media/output.jpg",
            "media_type": "image/jpeg",
            "max_bytes": MAX_ARTIFACT_BYTES + 1,
        },
    ],
)
def test_schema_rejects_invalid_image_artifact_constraints(
    artifact: dict[str, object],
) -> None:
    # 画像artifactの安全なpath、拡張子とMIMEの対応、byte上限を確認する。
    data = _valid_text_data()
    data["id"] = "IMAGE-00000001"
    data["category"] = "IMAGE"
    data["judge"] = {
        "type": "image",
        "comparison": "exact_pixels",
        "artifact": artifact,
    }

    with pytest.raises(ProblemSchemaError):
        parse_problem_definition(_yaml(data))


def test_schema_rejects_category_judge_mismatch_and_filename_mismatch(
    tmp_path: Path,
) -> None:
    # ID categoryとjudge種別、およびdefinition IDとファイル名の不一致を拒否する。
    category_mismatch = _valid_text_data()
    category_mismatch["category"] = "IMAGE"

    with pytest.raises(ProblemSchemaError, match="category"):
        parse_problem_definition(_yaml(category_mismatch))

    wrong_filename = tmp_path / "STANDARD-00000002.yaml"
    wrong_filename.write_text(_yaml(_valid_text_data()), encoding="utf-8")
    with pytest.raises(ProblemSchemaError, match="filename stem"):
        load_problem_definition(wrong_filename)


def test_schema_rejects_oversized_definition_before_yaml_parsing() -> None:
    # file全体の上限を超えた入力をYAML解析前に拒否することを確認する。
    oversized = "x" * (MAX_PROBLEM_SCHEMA_FILE_BYTES + 1)

    with pytest.raises(ProblemSchemaError, match="file limit"):
        parse_problem_definition(oversized)


def test_v3_and_legacy_problem_id_sets_match() -> None:
    # legacyとv3に同じ92問が1件ずつ存在し、欠落や余分な問題がないことを確認する。
    v3_problem_ids = tuple(path.stem for path in sorted(V3_DIRECTORY.glob("*.yaml")))

    assert len(V3_PROBLEM_IDS) == 92
    assert v3_problem_ids == V3_PROBLEM_IDS


@pytest.mark.parametrize("problem_id", V3_PROBLEM_IDS)
def test_all_v3_files_equal_deterministic_legacy_migration(problem_id: str) -> None:
    # 各v3 YAMLが対応するlegacyデータからの決定的な移行結果と一致することを確認する。
    migrated = migrate_legacy_file(LEGACY_DIRECTORY / f"{problem_id}.yaml")
    v3_path = V3_DIRECTORY / f"{problem_id}.yaml"

    assert load_problem_definition(v3_path) == migrated
    assert v3_path.read_text(encoding="utf-8") == dump_problem_definition(migrated)


@pytest.mark.parametrize("problem_id", V3_PROBLEM_IDS)
def test_all_v3_definitions_preserve_legacy_problem_semantics(problem_id: str) -> None:
    # 全fieldをlegacy値と照合し、構造変更で問題文・入出力・解答の意味が変わらないことを確認する。
    legacy = yaml.safe_load(
        (LEGACY_DIRECTORY / f"{problem_id}.yaml").read_text(encoding="utf-8")
    )
    definition = load_problem_definition(V3_DIRECTORY / f"{problem_id}.yaml")
    fixture_input = (
        definition.execution.fixtures[0].content
        if definition.execution.fixtures
        else ""
    )
    expected_output = (
        definition.judge.expected_output if definition.judge.type == "text" else ""
    )

    assert definition.id == legacy["id"]
    assert definition.category == problem_id.split("-", maxsplit=1)[0]
    assert definition.title.ja == legacy["title_ja"]
    assert definition.title.en == legacy["title_en"]
    assert definition.statement.ja == legacy["statement_ja"]
    assert definition.statement.en == legacy["statement_en"]
    assert definition.reference_solution == legacy["answer"]
    assert definition.execution.stdin == ""
    assert fixture_input == legacy["input"]
    assert expected_output == legacy["expected_output"]


def test_migration_preserves_legacy_input_as_an_isolated_fixture() -> None:
    # legacyのinputをstdinへ誤変換せず、input.txt fixtureとして保持することを確認する。
    migrated = migrate_legacy_file(LEGACY_DIRECTORY / "PRACTICE-awk-02.yaml")

    assert migrated.execution.stdin == ""
    assert len(migrated.execution.fixtures) == 1
    assert migrated.execution.fixtures[0].path == "input.txt"
    assert migrated.execution.fixtures[0].content.startswith("aaaaa bbbbb")
    assert migrated.execution.exit_code == "ignore"
    assert migrated.execution.stderr == "merge"


def test_migration_rejects_lossy_or_ambiguous_legacy_data() -> None:
    # 欠落fieldやimage問題のtext期待値を、意味を失う自動変換にせず拒否する。
    missing = {
        key: value
        for key, value in yaml.safe_load(
            (LEGACY_DIRECTORY / "STANDARD-00000001.yaml").read_text(encoding="utf-8")
        ).items()
        if key != "answer"
    }
    image_with_text = yaml.safe_load(
        (LEGACY_DIRECTORY / "IMAGE-00000001.yaml").read_text(encoding="utf-8")
    )
    image_with_text["expected_output"] = "unexpected"

    with pytest.raises(ProblemMigrationError, match="missing legacy fields"):
        migrate_legacy_mapping(missing)
    with pytest.raises(ProblemMigrationError, match="explicit migration"):
        migrate_legacy_mapping(image_with_text)


def test_migration_writer_refuses_to_overwrite_by_default(tmp_path: Path) -> None:
    # migration出力のファイル名を検証し、既定では既存データを上書きしないことを確認する。
    definition = migrate_legacy_file(LEGACY_DIRECTORY / "STANDARD-00000001.yaml")
    destination = tmp_path / "STANDARD-00000001.yaml"
    destination.write_text("existing", encoding="utf-8")

    with pytest.raises(ProblemMigrationError, match="problem ID"):
        write_migrated_problem(definition, tmp_path / "wrong-name.yaml")
    with pytest.raises(ProblemMigrationError, match="already exists"):
        write_migrated_problem(definition, destination)
    assert destination.read_text(encoding="utf-8") == "existing"


def test_migration_cli_writes_a_valid_v3_definition(tmp_path: Path) -> None:
    # CLIがlegacyファイルを読み、schemaで再検証できるv3 YAMLを出力することを確認する。
    source = LEGACY_DIRECTORY / "STANDARD-00000001.yaml"
    destination = tmp_path / source.name

    assert migration_main([str(source), str(destination)]) == 0
    assert load_problem_definition(destination) == migrate_legacy_file(source)
