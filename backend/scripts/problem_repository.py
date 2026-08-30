import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from models.problem import (
    MAX_ARTIFACT_BYTES,
    PROBLEM_MANIFEST_VERSION,
    PROBLEM_SCHEMA_VERSION,
    ProblemDefinitionV3,
    ProblemManifestV1,
)
from scripts.problem_catalog import ProblemCatalog, build_problem_catalog
from scripts.problem_schema import ProblemSchemaError, load_problem_definition


DEFAULT_PROBLEM_DATA_DIRECTORY = Path(__file__).resolve().parent.parent / "problems"
DEFAULT_PROBLEM_DEFINITION_DIRECTORY = DEFAULT_PROBLEM_DATA_DIRECTORY / "v3"
DEFAULT_PROBLEM_IMAGE_DIRECTORY = DEFAULT_PROBLEM_DATA_DIRECTORY / "image"
DEFAULT_PROBLEM_MANIFEST_PATH = DEFAULT_PROBLEM_DEFINITION_DIRECTORY / "manifest.json"
MAX_PROBLEM_MANIFEST_BYTES = 16_384


class ProblemRepositoryError(RuntimeError):
    """問題data一式を安全に読込・検証できない場合に送出する例外。"""


@dataclass(frozen=True)
class ProblemRecord:
    """1問分の型付き定義と判定用画像を不変な値として保持する。"""

    definition: ProblemDefinitionV3
    answer_image: bytes
    answer_image_base64: str

    @property
    def fixtures(self) -> tuple[tuple[str, str], ...]:
        """問題定義のfixtureを、archive作成用のpath・内容tupleとして返す。"""
        return tuple(
            (fixture.path, fixture.content)
            for fixture in self.definition.execution.fixtures
        )

    @property
    def input_text(self) -> str:
        """互換API用にinput.txt fixtureの内容を返し、なければ空文字列を返す。"""
        return next(
            (content for path, content in self.fixtures if path == "input.txt"),
            "",
        )

    @property
    def expected_output(self) -> str:
        """文字列問題の期待出力を返し、画像問題では空文字列を返す。"""
        judge = self.definition.judge
        return judge.expected_output if judge.type == "text" else ""

    def api_detail(self) -> dict[str, str]:
        """型付き定義を既存の問題詳細APIと同じfield構成へ変換して返す。"""
        definition = self.definition
        return {
            "title_ja": definition.title.ja,
            "title_en": definition.title.en,
            "statement_ja": definition.statement.ja,
            "statement_en": definition.statement.en,
            "input": self.input_text,
            "expected_output": self.expected_output,
            "answer": definition.reference_solution,
            "image": f"/image/{definition.id}.jpg",
        }


@dataclass(frozen=True)
class ProblemRepository:
    """起動時に検証した全問題をrevision付きで保持する不変repository。"""

    records: Mapping[str, ProblemRecord]
    revision: str
    catalog: ProblemCatalog

    def get(self, problem_id: str) -> ProblemRecord | None:
        """入力IDに対応する問題recordを返し、未登録ならNoneを返す。"""
        return self.records.get(problem_id)

    def require(self, problem_id: str) -> ProblemRecord:
        """入力IDに対応する問題recordを返し、未登録ならKeyErrorを送出する。"""
        return self.records[problem_id]

    @property
    def problem_count(self) -> int:
        """起動時に検証済みの問題数を返す。"""
        return len(self.records)


_loaded_repository: ProblemRepository | None = None


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """JSON objectのkey-value列をdict化し、重複keyがあればValueErrorを送出する。"""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_manifest(path: Path) -> ProblemManifestV1:
    """manifest JSONを上限・重複key・schema込みで検証し、型付き値を返す。"""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ProblemRepositoryError(
            f"failed to read problem manifest: {path}"
        ) from exc
    if len(payload) > MAX_PROBLEM_MANIFEST_BYTES:
        raise ProblemRepositoryError(
            f"problem manifest exceeds {MAX_PROBLEM_MANIFEST_BYTES} bytes: {path}"
        )
    try:
        data = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
        return ProblemManifestV1.model_validate(data)
    except (UnicodeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
        raise ProblemRepositoryError(f"invalid problem manifest: {path}") from exc


def _validate_answer_image(path: Path) -> bytes:
    """判定用JPEGを読んで形式とbyte上限を検証し、画像bytesを返す。"""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ProblemRepositoryError(f"failed to read answer image: {path}") from exc
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise ProblemRepositoryError(
            f"answer image exceeds {MAX_ARTIFACT_BYTES} bytes: {path}"
        )
    if (
        len(payload) < 4
        or not payload.startswith(b"\xff\xd8")
        or not payload.endswith(b"\xff\xd9")
    ):
        raise ProblemRepositoryError(f"answer image is not a complete JPEG: {path}")
    return payload


def calculate_problem_revision(records: Sequence[ProblemRecord]) -> str:
    """問題定義と画像digestをID順に正規化し、全体のSHA-256 revisionを返す。"""
    canonical_data = {
        "problem_schema_version": PROBLEM_SCHEMA_VERSION,
        "problems": [
            {
                "definition": record.definition.model_dump(mode="json"),
                "answer_image_sha256": hashlib.sha256(record.answer_image).hexdigest(),
            }
            for record in sorted(records, key=lambda item: item.definition.id)
        ],
    }
    payload = json.dumps(
        canonical_data,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_problem_manifest(records: Sequence[ProblemRecord]) -> ProblemManifestV1:
    """検証済みrecord群から、件数とrevisionを持つmanifest modelを生成して返す。"""
    return ProblemManifestV1(
        manifest_version=PROBLEM_MANIFEST_VERSION,
        problem_schema_version=PROBLEM_SCHEMA_VERSION,
        problem_count=len(records),
        revision=calculate_problem_revision(records),
    )


def render_problem_manifest(manifest: ProblemManifestV1) -> str:
    """manifest modelをkey順が安定した改行付きJSON文字列として返す。"""
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def collect_problem_records(
    definition_directory: Path,
    image_directory: Path,
) -> list[ProblemRecord]:
    """v3 YAMLと同名JPEGを全件読込・検証し、ID順のrecord listを返す。"""
    try:
        definition_paths = sorted(definition_directory.glob("*.yaml"))
        image_paths = sorted(image_directory.glob("*.jpg"))
    except OSError as exc:
        raise ProblemRepositoryError("failed to list problem data") from exc
    if not definition_paths:
        raise ProblemRepositoryError(
            f"no problem definitions found in {definition_directory}"
        )

    definition_ids = {path.stem for path in definition_paths}
    image_ids = {path.stem for path in image_paths}
    if definition_ids != image_ids:
        missing_images = sorted(definition_ids - image_ids)
        extra_images = sorted(image_ids - definition_ids)
        raise ProblemRepositoryError(
            "problem definition/image ID mismatch: "
            f"missing_images={missing_images}, extra_images={extra_images}"
        )

    records: list[ProblemRecord] = []
    for definition_path in definition_paths:
        try:
            definition = load_problem_definition(definition_path)
        except ProblemSchemaError as exc:
            raise ProblemRepositoryError(
                f"failed to load problem definition: {definition_path}"
            ) from exc
        image = _validate_answer_image(image_directory / f"{definition.id}.jpg")
        records.append(
            ProblemRecord(
                definition=definition,
                answer_image=image,
                answer_image_base64=base64.b64encode(image).decode("ascii"),
            )
        )
    return records


def build_problem_repository(
    definition_directory: Path = DEFAULT_PROBLEM_DEFINITION_DIRECTORY,
    image_directory: Path = DEFAULT_PROBLEM_IMAGE_DIRECTORY,
    manifest_path: Path = DEFAULT_PROBLEM_MANIFEST_PATH,
) -> ProblemRepository:
    """問題dataを一度だけ読込・検証し、manifestと一致する不変repositoryを返す。

    入力はv3 YAML directory、JPEG directory、manifest path。欠損、破損、
    ID集合またはrevisionの不一致があればProblemRepositoryErrorを送出する。
    """
    records = collect_problem_records(definition_directory, image_directory)
    manifest = _load_manifest(manifest_path)
    calculated_manifest = build_problem_manifest(records)
    if manifest != calculated_manifest:
        raise ProblemRepositoryError(
            "problem manifest mismatch: "
            f"expected={manifest.model_dump(mode='json')}, "
            f"actual={calculated_manifest.model_dump(mode='json')}"
        )

    record_mapping = MappingProxyType(
        {record.definition.id: record for record in records}
    )
    return ProblemRepository(
        records=record_mapping,
        revision=manifest.revision,
        catalog=build_problem_catalog(record.definition for record in records),
    )


def load_problem_repository(
    definition_directory: Path = DEFAULT_PROBLEM_DEFINITION_DIRECTORY,
    image_directory: Path = DEFAULT_PROBLEM_IMAGE_DIRECTORY,
    manifest_path: Path = DEFAULT_PROBLEM_MANIFEST_PATH,
) -> ProblemRepository:
    """検証済みrepositoryを構築してprocess globalへ公開し、その値を返す。

    構築に失敗した場合は例外を送出し、以前に公開済みの値は変更しない。
    """
    global _loaded_repository

    repository = build_problem_repository(
        definition_directory,
        image_directory,
        manifest_path,
    )
    _loaded_repository = repository
    return repository


def get_problem_repository() -> ProblemRepository:
    """起動時に公開済みのrepositoryを返し、未loadならRuntimeErrorを送出する。"""
    if _loaded_repository is None:
        raise RuntimeError("problem repository has not been loaded")
    return _loaded_repository
