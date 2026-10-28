"""通常問題の連番と、改番前に記録した問題内容・画像の保持を確認する。"""

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from soj_shared.problem_repository import build_problem_repository


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
BASELINE = json.loads(
    (Path(__file__).parent / "fixtures/standard_problem_renumbering.json").read_text()
)


def test_standard_problem_ids_are_consecutive() -> None:
    # 現行の通常問題を1から件数までの集合と照合し、欠番・0始まり・余分なIDを検出する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    ids = {
        record.definition.id
        for record in repository.records.values()
        if record.definition.category == "STANDARD"
    }
    assert ids == {f"STANDARD-{n:08d}" for n in range(1, len(ids) + 1)}


@pytest.mark.parametrize("baseline", BASELINE["problems"], ids=lambda b: b["new_id"])
def test_renumbering_preserves_definition_and_image(baseline: dict[str, str]) -> None:
    # 改番前commitから採取したhashと照合し、ID以外の全fieldと画像bytesが変わっていないことを確認する。
    new_id = baseline["new_id"]
    data = yaml.safe_load((PROBLEMS / "v3" / f"{new_id}.yaml").read_text())
    assert data.pop("id") == new_id
    canonical = json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    assert (
        hashlib.sha256(canonical).hexdigest()
        == baseline["definition_without_id_sha256"]
    )
    assert (
        hashlib.sha256((PROBLEMS / "image" / f"{new_id}.jpg").read_bytes()).hexdigest()
        == baseline["image_sha256"]
    )
