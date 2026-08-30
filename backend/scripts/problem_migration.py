import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from models.problem import (
    MAX_ARTIFACT_BYTES,
    PROBLEM_SCHEMA_VERSION,
    ProblemDefinitionV3,
)
from scripts.problem_schema import (
    MAX_PROBLEM_SCHEMA_FILE_BYTES,
    ProblemSchemaError,
    dump_problem_definition,
    load_yaml_mapping,
)


LEGACY_FIELDS = {
    "id",
    "title_ja",
    "title_en",
    "statement_ja",
    "statement_en",
    "input",
    "expected_output",
    "answer",
}


class ProblemMigrationError(ValueError):
    """Raised when a legacy problem cannot be migrated without losing meaning."""


def migrate_legacy_mapping(
    data: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> ProblemDefinitionV3:
    """legacy問題mappingを検証し、同じ内容を表すschema v3 modelへ変換する。

    入力はlegacy YAML由来のmappingと任意のファイル名由来ID。出力は型付きv3定義。
    field不足・余分なfield・型不正・意味を安全に移せない場合は
    ProblemMigrationErrorを送出する。
    """
    if not all(isinstance(key, str) for key in data):
        raise ProblemMigrationError("all legacy problem field names must be strings")
    keys = set(data)
    missing = LEGACY_FIELDS - keys
    extra = keys - LEGACY_FIELDS
    if missing:
        raise ProblemMigrationError(f"missing legacy fields: {sorted(missing)}")
    if extra:
        raise ProblemMigrationError(f"unexpected legacy fields: {sorted(extra)}")
    if not all(isinstance(data[field], str) for field in LEGACY_FIELDS):
        raise ProblemMigrationError("all legacy problem fields must be strings")

    problem_id = data["id"]
    if source_id is not None and problem_id != source_id:
        raise ProblemMigrationError("legacy problem ID must match the filename stem")
    category = problem_id.split("-", maxsplit=1)[0]
    fixtures = (
        [{"path": "input.txt", "content": data["input"]}] if data["input"] else []
    )

    if category == "IMAGE":
        if data["expected_output"]:
            raise ProblemMigrationError(
                "IMAGE problems with expected text output require an explicit migration"
            )
        judge: dict[str, Any] = {
            "type": "image",
            "artifact": {
                "path": "media/output.jpg",
                "media_type": "image/jpeg",
                "max_bytes": MAX_ARTIFACT_BYTES,
            },
        }
    else:
        judge = {
            "type": "text",
            "expected_output": data["expected_output"],
        }

    try:
        return ProblemDefinitionV3.model_validate(
            {
                "schema_version": PROBLEM_SCHEMA_VERSION,
                "id": problem_id,
                "category": category,
                "title": {"ja": data["title_ja"], "en": data["title_en"]},
                "statement": {
                    "ja": data["statement_ja"],
                    "en": data["statement_en"],
                },
                "reference_solution": data["answer"],
                "execution": {
                    "stdin": "",
                    "fixtures": fixtures,
                    "exit_code": "ignore",
                    "stderr": "merge",
                },
                "judge": judge,
            }
        )
    except ValueError as exc:
        raise ProblemMigrationError(
            f"legacy problem is not valid v3 data: {exc}"
        ) from exc


def migrate_legacy_file(path: Path) -> ProblemDefinitionV3:
    """指定されたlegacy YAMLを読み込み、schema v3 modelへ変換して返す。

    入力はlegacy YAMLのpath。読込、容量、YAML、ID、変換に問題があれば
    ProblemMigrationErrorを送出する。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ProblemMigrationError(f"failed to read {path}") from exc
    if len(text.encode("utf-8")) > MAX_PROBLEM_SCHEMA_FILE_BYTES:
        raise ProblemMigrationError(
            f"{path} exceeds the {MAX_PROBLEM_SCHEMA_FILE_BYTES}-byte file limit"
        )
    try:
        data = load_yaml_mapping(text, source=str(path))
    except ProblemSchemaError as exc:
        raise ProblemMigrationError(str(exc)) from exc
    return migrate_legacy_mapping(data, source_id=path.stem)


def write_migrated_problem(
    definition: ProblemDefinitionV3,
    destination: Path,
    *,
    overwrite: bool = False,
) -> None:
    """型付きv3定義をproblem IDと同名のdestination YAMLへ書き込む。

    入力はproblem definition、出力先、上書き許可。戻り値はなく、命名不一致、
    既存fileへの未許可の上書き、書込失敗ではProblemMigrationErrorを送出する。
    """
    if destination.suffix != ".yaml" or destination.stem != definition.id:
        raise ProblemMigrationError(
            "destination must be a .yaml file named with the problem ID"
        )
    mode = "w" if overwrite else "x"
    try:
        with destination.open(mode, encoding="utf-8", newline="\n") as file:
            file.write(dump_problem_definition(definition))
    except FileExistsError as exc:
        raise ProblemMigrationError(
            f"destination already exists: {destination}; use --force to replace it"
        ) from exc
    except OSError as exc:
        raise ProblemMigrationError(f"failed to write {destination}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    """CLI引数のlegacy入力とv3出力先を処理し、成功時に終了code 0を返す。

    入力は省略可能な引数列で、省略時はprocessのcommand lineを使用する。
    変換失敗時はargparseが説明を表示して非0で終了する。
    """
    parser = argparse.ArgumentParser(
        description="Migrate one legacy Shellgei problem YAML file to schema v3.",
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing destination file",
    )
    args = parser.parse_args(argv)

    try:
        definition = migrate_legacy_file(args.source)
        write_migrated_problem(definition, args.destination, overwrite=args.force)
    except ProblemMigrationError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
