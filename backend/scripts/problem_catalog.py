import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.input_validation import validate_problem_id


DEFAULT_PROBLEM_YAML_DIRECTORY = (
    Path(__file__).resolve().parent.parent / "problems" / "yaml_data"
)
PROBLEM_LIST_CACHE_CONTROL = "public, max-age=300"


class ProblemCatalogError(RuntimeError):
    """Raised when the problem list cannot be loaded safely at startup."""


@dataclass(frozen=True)
class ProblemCatalog:
    response_body: bytes
    etag: str
    problem_count: int


_loaded_catalog: ProblemCatalog | None = None


def _problem_summary(yaml_path: Path, data: Any) -> dict[str, str]:
    if not isinstance(data, Mapping):
        raise ProblemCatalogError(f"{yaml_path.name} must contain a YAML mapping")

    try:
        validate_problem_id(yaml_path.stem)
    except ValueError as exc:
        raise ProblemCatalogError(
            f"{yaml_path.name} has an invalid problem ID"
        ) from exc

    title_ja = data.get("title_ja")
    title_en = data.get("title_en")
    if not isinstance(title_ja, str) or not isinstance(title_en, str):
        raise ProblemCatalogError(
            f"{yaml_path.name} must contain string title_ja and title_en fields"
        )

    return {
        "id": yaml_path.stem,
        "category": yaml_path.stem.split("-")[0],
        "title_ja": title_ja,
        "title_en": title_en,
    }


def build_problem_catalog(yaml_directory: Path) -> ProblemCatalog:
    try:
        yaml_paths = sorted(yaml_directory.glob("*.yaml"))
    except OSError as exc:
        raise ProblemCatalogError(
            f"failed to list problem data in {yaml_directory}"
        ) from exc

    if not yaml_paths:
        raise ProblemCatalogError(f"no problem data found in {yaml_directory}")

    summaries: list[dict[str, str]] = []
    for yaml_path in yaml_paths:
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ProblemCatalogError(f"failed to load {yaml_path.name}") from exc
        summaries.append(_problem_summary(yaml_path, data))

    response_body = json.dumps(
        summaries,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(response_body).hexdigest()
    return ProblemCatalog(
        response_body=response_body,
        etag=f'"{digest}"',
        problem_count=len(summaries),
    )


def load_problem_catalog(
    yaml_directory: Path = DEFAULT_PROBLEM_YAML_DIRECTORY,
) -> ProblemCatalog:
    global _loaded_catalog

    catalog = build_problem_catalog(yaml_directory)
    _loaded_catalog = catalog
    return catalog


def get_problem_catalog() -> ProblemCatalog:
    if _loaded_catalog is None:
        raise RuntimeError("problem catalog has not been loaded")
    return _loaded_catalog
