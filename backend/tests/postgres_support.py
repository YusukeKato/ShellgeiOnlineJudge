"""全DB統合testで同じbuild済みimageと移行元の固定imageを参照する。"""

import os
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def database_image() -> str:
    """SOJ_DB_IMAGEを優先し、省略時は本番Composeのlocal build名を返す。pullは行わない。"""
    return (
        os.environ.get("SOJ_DB_IMAGE")
        or yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["db"][
            "image"
        ]
    )


def upstream_postgres_image() -> str:
    """既存volumeの互換性test用に、DB Dockerfileから固定PostgreSQL baseを読み取る。"""
    references = [
        line.split()[1]
        for line in (ROOT / "deploy/postgres/Dockerfile").read_text().splitlines()
        if line.startswith("FROM postgres:")
    ]
    if len(references) != 1 or "@sha256:" not in references[0]:
        raise ValueError("one pinned PostgreSQL base is required")
    return references[0]
