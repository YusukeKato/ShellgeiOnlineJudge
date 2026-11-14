"""全DB統合testで同じbuild済みimageと移行元の固定imageを参照する。"""

import os
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
# 更新先Dockerfileから導出せず、実際の旧15.19とのvolume互換性を継続して検査する。
POSTGRES_UPGRADE_BASELINE = (
    "postgres:15-alpine@sha256:"
    "a46e076249ce434e41203b8c1dadfaa025b9726331d72390df038385d6dc29cd"
)


def database_image() -> str:
    """SOJ_DB_IMAGEを優先し、省略時は本番Composeのlocal build名を返す。pullは行わない。"""
    return (
        os.environ.get("SOJ_DB_IMAGE")
        or yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["db"][
            "image"
        ]
    )


def upstream_postgres_image() -> str:
    """既存volumeの互換性test用に、更新前の固定PostgreSQL 15.19を返す。pullは行わない。"""
    return POSTGRES_UPGRADE_BASELINE
