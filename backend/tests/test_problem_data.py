import base64
from pathlib import Path

import yaml

from scripts.judge import ShellgeiJudge


PROBLEMS_DIR = Path(__file__).resolve().parents[2] / "problems"
YAML_DIR = PROBLEMS_DIR / "yaml_data"
IMAGE_DIR = PROBLEMS_DIR / "image"
REQUIRED_FIELDS = {
    "title_ja",
    "title_en",
    "statement_ja",
    "statement_en",
    "input",
    "expected_output",
    "answer",
}


def test_all_problem_records_are_well_formed() -> None:
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
        assert (IMAGE_DIR / f"{yaml_path.stem}.jpg").is_file(), yaml_path.name


def test_judge_accepts_all_expected_problem_outputs() -> None:
    judge = ShellgeiJudge()
    # Production images copy problems below backend/. Tests use the repository source tree.
    judge.base_dir = PROBLEMS_DIR.parent

    for yaml_path in sorted(YAML_DIR.glob("*.yaml")):
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        image_bytes = (IMAGE_DIR / f"{yaml_path.stem}.jpg").read_bytes()
        image = base64.b64encode(image_bytes).decode("ascii")

        assert judge.judge(data["expected_output"], image, yaml_path.stem) == "1", (
            yaml_path.name
        )
