"""API・UI・配布metadataで共有する製品versionを同梱の正本から読み取る。"""

import json
from importlib.resources import files

APP_VERSION: str = json.loads(
    files("soj_shared").joinpath("version.json").read_text(encoding="utf-8")
)["version"]
