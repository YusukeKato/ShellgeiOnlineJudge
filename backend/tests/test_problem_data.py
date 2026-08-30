import base64
import hashlib
import json
from pathlib import Path

import yaml

from scripts.judge import JudgeVerdict, ShellgeiJudge
from scripts.problem_repository import build_problem_repository
from scripts.runner_protocol import ExecutionArtifact


PROBLEMS_DIR = Path(__file__).resolve().parents[2] / "problems"
YAML_DIR = PROBLEMS_DIR / "yaml_data"
IMAGE_DIR = PROBLEMS_DIR / "image"
SEMANTIC_MANIFEST_PATH = PROBLEMS_DIR / "semantic_manifest.json"
REQUIRED_FIELDS = {
    "id",
    "title_ja",
    "title_en",
    "statement_ja",
    "statement_en",
    "input",
    "expected_output",
    "answer",
}


def _definition_sha256(data: dict[str, str]) -> str:
    # YAMLの書式やkey順に影響されないよう、問題定義をcanonical JSON化してSHA-256を求める。
    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _problem_semantics(yaml_path: Path) -> dict[str, object]:
    # 1問分のYAMLと正解画像から、移行前に固定するsemantic情報とhashを組み立てる。
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    image_path = IMAGE_DIR / f"{yaml_path.stem}.jpg"
    return {
        "id": yaml_path.stem,
        "category": yaml_path.stem.split("-", maxsplit=1)[0],
        "has_input": bool(data["input"]),
        "expected_output_kind": "empty" if data["expected_output"] == "" else "text",
        "definition_sha256": _definition_sha256(data),
        "answer_image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
    }


def test_all_problem_records_are_well_formed() -> None:
    # 全問題で必須fieldの型、IDとファイル名の一致、対応する正解画像の存在を確認する。
    yaml_paths = sorted(YAML_DIR.glob("*.yaml"))

    assert yaml_paths
    assert len(yaml_paths) == len(list(IMAGE_DIR.glob("*.jpg")))

    for yaml_path in yaml_paths:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        assert isinstance(data, dict), yaml_path.name
        assert REQUIRED_FIELDS <= data.keys(), yaml_path.name
        assert all(isinstance(data[field], str) for field in REQUIRED_FIELDS), (
            yaml_path.name
        )
        assert data["id"] == yaml_path.stem, yaml_path.name
        assert (IMAGE_DIR / f"{yaml_path.stem}.jpg").is_file(), yaml_path.name


def test_problem_semantic_manifest_matches_all_legacy_records() -> None:
    # 全92問から再計算したsemantic情報が、保存済みmanifestと完全に一致することを確認する。
    manifest = json.loads(SEMANTIC_MANIFEST_PATH.read_text(encoding="utf-8"))
    actual = [
        _problem_semantics(yaml_path) for yaml_path in sorted(YAML_DIR.glob("*.yaml"))
    ]

    assert manifest == {
        "manifest_version": 1,
        "problem_count": 92,
        "problems": actual,
    }
    assert sum(problem["has_input"] is True for problem in actual) == 68
    assert sum(problem["expected_output_kind"] == "empty" for problem in actual) == 5
    assert {
        category: sum(problem["category"] == category for problem in actual)
        for category in ("IMAGE", "PRACTICE", "STANDARD")
    } == {"IMAGE": 5, "PRACTICE": 36, "STANDARD": 51}


def test_judge_accepts_all_expected_problem_outputs() -> None:
    # 全問題の期待出力と正解画像を現在のjudgeへ渡し、すべて正解判定になることを確認する。
    repository = build_problem_repository(
        PROBLEMS_DIR / "v3",
        IMAGE_DIR,
        PROBLEMS_DIR / "v3/manifest.json",
    )
    judge = ShellgeiJudge(repository)

    for yaml_path in sorted(YAML_DIR.glob("*.yaml")):
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        image_bytes = (IMAGE_DIR / f"{yaml_path.stem}.jpg").read_bytes()
        image = base64.b64encode(image_bytes).decode("ascii")

        definition = repository.require(yaml_path.stem).definition
        artifact = None
        if definition.judge.type == "image":
            artifact = ExecutionArtifact(
                path=definition.judge.artifact.path,
                media_type=definition.judge.artifact.media_type,
                data=image,
            )
        assert (
            judge.judge(data["expected_output"], artifact, yaml_path.stem).verdict
            is JudgeVerdict.ACCEPTED
        ), yaml_path.name
