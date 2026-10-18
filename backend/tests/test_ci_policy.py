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
        deployment = workflow["name"] == "Production deploy"
        assert workflow["concurrency"]["cancel-in-progress"] == (
            "false" if deployment else "true"
        )
        assert not {"pull_request_target", "workflow_run"} & workflow["on"].keys()
        for name, job in workflow["jobs"].items():
            assert job["runs-on"] == "ubuntu-24.04"
            assert 1 <= int(job["timeout-minutes"]) <= (60 if deployment else 45)
            if deployment:
                expected = {"contents": "read", "actions": "read"}
                if name == "deploy":
                    expected["attestations"] = "read"
                    expected["id-token"] = "write"
                assert job["permissions"] == expected
            elif name != "provenance":
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


def test_deployment_requires_main_ci_and_verification_before_ssh() -> None:
    # PRには本番資格情報を渡さず、同じcommitのCIと署名検証を経てSSHを開始する。
    workflow = yaml.load(
        (ROOT / ".github/workflows/deploy.yaml").read_text(), Loader=yaml.BaseLoader
    )
    assert workflow["on"] == {"push": {"branches": ["main"]}}
    assert workflow["concurrency"]["group"] == "production-deploy"
    gate = workflow["jobs"]["gate"]
    assert "vars.PRODUCTION_DEPLOY_ENABLED == 'true'" in gate["if"]
    assert "secrets." not in str(gate)
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] == "gate"
    assert deploy["environment"] == "production"
    steps = deploy["steps"]
    assert steps[1]["with"]["run-id"] == "${{ needs.gate.outputs.run-id }}"
    assert "ci/deploy.py verify" in steps[2]["run"]
    assert "secrets." not in str(steps[:3])
    assert "ci/install_session_manager.sh" in steps[3]["run"]
    assert steps[4]["uses"].startswith("aws-actions/configure-aws-credentials@")
    assert steps[4]["with"]["role-to-assume"] == "${{ vars.DEPLOY_AWS_ROLE_ARN }}"
    assert "secrets." not in str(steps[:5])
    assert "ci/deploy.py transfer" in steps[5]["run"]


def test_ci_runs_on_pr_and_main_without_duplicate_branch_push() -> None:
    # 作業branchはPRで検査し、配備を守るmain pushと定期検査は残す。
    for workflow in workflows():
        if workflow["name"] == "Production deploy":
            continue
        assert workflow["on"]["push"] == {"branches": ["main"]}
        assert "pull_request" in workflow["on"]
        assert "schedule" in workflow["on"]
    workflow = next(w for w in workflows() if w["name"] == "Supply Chain CI")
    steps = workflow["jobs"]["runtime"]["steps"]
    assert steps[0]["with"]["fetch-depth"] == "0"
    selection = next(
        i for i, step in enumerate(steps) if "problem_review.py" in step.get("run", "")
    )
    regression = next(
        i for i, step in enumerate(steps) if step.get("id") == "regression"
    )
    assert selection < regression
    assert steps[regression]["env"]["SOJ_RUN_FULL_REGRESSION"] == "1"

    assert "shopt -s nullglob" in steps[regression]["run"]
    assert "test_problem_*_solutions.py" in steps[regression]["run"]


def test_runtime_vulnerability_db_update_finishes_before_scan() -> None:
    # buildと並行するDB更新を同じstep内でwaitし、失敗時にscanへ進まないことを確認する。
    workflow = next(w for w in workflows() if w["name"] == "Supply Chain CI")
    steps = workflow["jobs"]["runtime"]["steps"]
    update = next(
        i for i, step in enumerate(steps) if "db update" in step.get("run", "")
    )
    scan = next(i for i, step in enumerate(steps) if step.get("id") == "scan")
    install = next(
        i for i, step in enumerate(steps) if "install_tools.py" in step.get("run", "")
    )
    script = steps[update]["run"]
    # DB保存先はinstall stepがGITHUB_ENVへ設定するため、更新より前に置く。
    assert install < update < scan
    assert sum("db update" in step.get("run", "") for step in steps) == 1
    assert "grype_update=$!" in script
    assert 'wait "$grype_update" || grype_status=$?' in script
    assert script.rstrip().endswith('test "$grype_status" -eq 0')
    assert "continue-on-error" not in steps[update]
