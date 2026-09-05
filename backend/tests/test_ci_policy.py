import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def workflows() -> list[dict]:
    """GitHub Actions定義を文字列として読み、YAML 1.1のon→bool変換を避ける。"""
    return [
        yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        for path in (ROOT / ".github/workflows").glob("*.yaml")
    ]


def test_workflows_pin_actions_and_limit_permissions_and_runtime() -> None:
    # mutable Action、永続credential、無制限job、不要なwrite権限を検出する。
    for workflow in workflows():
        assert workflow["permissions"] == {"contents": "read"}
        assert workflow["concurrency"]["cancel-in-progress"] == "true"
        assert not {"pull_request_target", "workflow_run"} & workflow["on"].keys()
        for name, job in workflow["jobs"].items():
            assert job["runs-on"] == "ubuntu-24.04"
            assert 1 <= int(job["timeout-minutes"]) <= 45
            if name != "provenance":
                assert job.get("permissions", {"contents": "read"}) == {
                    "contents": "read"
                }
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"])
                    if step["uses"].startswith("actions/checkout@"):
                        assert step["with"]["persist-credentials"] == "false"
                assert "continue-on-error" not in step


def test_attestation_is_separated_from_untrusted_code_and_pr_jobs() -> None:
    # OIDC/write権限を持つjobはmain pushだけで動き、PRコードやscriptを実行しない。
    workflow = yaml.load(
        (ROOT / ".github/workflows/supply_chain.yaml").read_text(),
        Loader=yaml.BaseLoader,
    )
    job = workflow["jobs"]["provenance"]
    assert "github.event_name == 'push'" in job["if"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert job["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }
    assert {"source", "runtime"} <= set(job["needs"])
    assert all(
        "run" not in step and not step.get("uses", "").startswith("actions/checkout@")
        for step in job["steps"]
    )
