import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from soj_shared.models.problem import ProblemDefinitionV3


PROBLEM_LIST_CACHE_CONTROL = "public, max-age=300"


@dataclass(frozen=True)
class ProblemCatalog:
    """一覧APIの応答本文とcache情報を保持する不変なcatalog。"""

    response_body: bytes
    etag: str
    problem_count: int


def build_problem_catalog(
    definitions: Iterable[ProblemDefinitionV3],
) -> ProblemCatalog:
    """型検証済み問題定義から、ID順の一覧API応答とETagを生成する。

    入力は問題定義の反復可能object、出力は不変なProblemCatalog。
    問題が0件の場合はValueErrorを送出する。
    """
    summaries = [
        {
            "id": definition.id,
            "category": definition.category,
            "title_ja": definition.title.ja,
            "title_en": definition.title.en,
        }
        for definition in sorted(definitions, key=lambda item: item.id)
    ]
    if not summaries:
        raise ValueError("problem catalog must not be empty")

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
