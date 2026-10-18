"""文書だけの変更でruntime検査・配備を省略する判定と、その安全側への復帰を検査する。"""

import json
from pathlib import Path
import subprocess
from typing import Any

import pytest

from ci import deploy as ci


SHA = "a" * 40
BASE = "b" * 40
REPO = "example/judge"


@pytest.mark.parametrize(
    "paths",
    [
        ["README.md"],
        ["AGENTS.md", "SECURITY.md", "docs/CI.md"],
        ["backend/README.md", "backend/tests/integration/README.md"],
        ["frontend/README.md"],
    ],
)
def test_markdown_outside_image_inputs_is_documentation_only(paths: list[str]) -> None:
    # imageへcopy・bundleされないMarkdownだけなら、runtime検査と配備を省略できる。
    assert ci.documentation_only(paths)


@pytest.mark.parametrize(
    "paths",
    [
        [],
        ["README.md", "backend/soj_backend/main.py"],
        ["problems/README.md"],
        ["frontend/src/content/notes.md"],
        ["frontend/public/notes.md"],
        ["backend/soj_shared/notes.md"],
        ["deploy/README.md"],
        ["docs/diagram.svg"],
        [".github/workflows/supply_chain.yaml"],
    ],
)
def test_image_inputs_code_or_empty_diff_require_runtime(paths: list[str]) -> None:
    # nginxで配信されるproblems/README.md等や、空・判定不能な差分は省略しない。
    assert not ci.documentation_only(paths)


def git(repository: Path, *args: str) -> str:
    """test専用repositoryでGitを実行し、利用者の設定やhookを読まない。"""
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        env={
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "PATH": "/usr/bin:/bin",
        },
    ).stdout.strip()


def test_changed_paths_reads_tree_diff_and_rejects_unknown_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 実Gitで追加・削除を含む差分を読み、存在しないcommitや不正SHAは判定不能にする。
    git(tmp_path, "init", "-q")
    (tmp_path / "app.py").write_text("old\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "app.py").unlink()
    (tmp_path / "README.md").write_text("docs\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "head")
    head = git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.chdir(tmp_path)
    assert sorted(ci.changed_paths(base, head) or []) == ["README.md", "app.py"]
    assert ci.changed_paths("c" * 40, head) is None
    assert ci.changed_paths("HEAD", head) is None


def deploy_run(run_id: int, sha: str, **changes: Any) -> dict:
    """完了したmain pushのdeploy runを作る。"""
    return {
        "id": run_id,
        "head_sha": sha,
        "head_branch": "main",
        "event": "push",
        "path": ".github/workflows/deploy.yaml",
        "head_repository": {"full_name": REPO},
        **changes,
    }


def deploy_jobs(recorded: str | None) -> dict:
    """記録stepの結果を指定したdeploy jobを返す。Noneはjob skip相当でstepなし。"""
    steps = [{"name": "Transfer verified images and update production"}]
    if recorded is not None:
        steps.append({"name": ci.DEPLOY_RECORD_STEP, "conclusion": recorded})
    return {"jobs": [{"name": "gate", "steps": []}, {"name": "deploy", "steps": steps}]}


def test_deployed_commit_uses_latest_confirmed_update_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Supersededで記録stepがskipされたrunやfork・PR由来のrunを、配備済みとみなさない。
    runs = [
        deploy_run(10, "1" * 40),
        deploy_run(11, "2" * 40),
        deploy_run(12, "3" * 40, head_repository={"full_name": "fork/judge"}),
        deploy_run(13, "4" * 40, event="pull_request"),
        deploy_run(14, "5" * 40),
    ]
    jobs = {
        10: deploy_jobs("success"),
        11: deploy_jobs("success"),
        12: deploy_jobs("success"),
        13: deploy_jobs("success"),
        14: deploy_jobs("skipped"),
    }

    def api(path: str) -> dict:
        """deploy workflowのrun一覧と、全attemptのjob一覧を返す。"""
        if "/workflows/deploy.yaml/runs?" in path:
            assert "status=completed" in path and "branch=main" in path
            return {"workflow_runs": runs}
        run_id = int(path.split("/runs/")[1].split("/")[0])
        assert path.endswith("/jobs?filter=all")
        return jobs[run_id]

    monkeypatch.setattr(ci, "api", api)
    assert ci.deployed_commit(REPO) == "2" * 40
    jobs[11] = deploy_jobs(None)
    jobs[10] = deploy_jobs("failure")
    assert ci.deployed_commit(REPO) is None


@pytest.mark.parametrize(
    "base,paths,expected",
    [
        (BASE, ["README.md"], True),
        (BASE, ["README.md", "ci/deploy.py"], False),
        (BASE, None, False),
        (None, ["README.md"], False),
    ],
)
def test_deployment_unchanged_requires_known_base_and_documentation_diff(
    monkeypatch: pytest.MonkeyPatch,
    base: str | None,
    paths: list[str] | None,
    expected: bool,
) -> None:
    # 配備済みcommitが不明、差分取得不能、コード変更ありのいずれも配備側へ倒す。
    monkeypatch.setattr(ci, "deployed_commit", lambda _: base)
    monkeypatch.setattr(ci, "changed_paths", lambda *_: paths)
    assert ci.deployment_unchanged(REPO, SHA) is expected


def test_deployment_unchanged_treats_api_failure_as_deployable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # GitHub APIの障害を「変更なし」と扱って配備やruntime検査を省略しない。
    def unavailable(_: str) -> str:
        """gh apiの失敗を再現する。"""
        raise subprocess.CalledProcessError(1, "gh")

    monkeypatch.setattr(ci, "deployed_commit", unavailable)
    assert not ci.deployment_unchanged(REPO, SHA)


def run_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, event_name: str, ref: str
) -> str:
    """指定eventでscopeを実行し、GITHUB_OUTPUTへ書かれた値を返す。"""
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"base": {"sha": BASE}}}))
    output = tmp_path / "output"
    output.unlink(missing_ok=True)
    for key, value in {
        "GITHUB_EVENT_NAME": event_name,
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_SHA": SHA,
        "GITHUB_REF": ref,
        "GITHUB_OUTPUT": str(output),
    }.items():
        monkeypatch.setenv(key, value)
    ci.scope()
    return output.read_text()


def test_scope_compares_pr_with_base_and_main_with_deployed_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # PRはbase SHAとの差分、main pushは配備済みcommitとの比較で省略可否を決める。
    compared = []

    def changed(base: str, head: str) -> list[str]:
        """比較したcommitを記録し、文書だけの差分を返す。"""
        compared.append((base, head))
        return ["README.md"]

    monkeypatch.setattr(ci, "changed_paths", changed)
    assert run_scope(monkeypatch, tmp_path, "pull_request", "refs/pull/1/merge") == (
        "runtime=false\n"
    )
    assert compared == [(BASE, SHA)]
    monkeypatch.setattr(ci, "deployment_unchanged", lambda repo, sha: True)
    assert run_scope(monkeypatch, tmp_path, "push", "refs/heads/main") == (
        "runtime=false\n"
    )
    monkeypatch.setattr(ci, "deployment_unchanged", lambda repo, sha: False)
    assert run_scope(monkeypatch, tmp_path, "push", "refs/heads/main") == (
        "runtime=true\n"
    )


@pytest.mark.parametrize(
    "event_name,ref",
    [
        ("schedule", "refs/heads/main"),
        ("workflow_dispatch", "refs/heads/main"),
        ("push", "refs/heads/feature"),
    ],
)
def test_scope_runs_runtime_for_periodic_manual_and_other_refs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, event_name: str, ref: str
) -> None:
    # 週次・手動・main以外のpushでは差分を見ずに全検査する。
    monkeypatch.setattr(ci, "changed_paths", lambda *_: ["README.md"])
    monkeypatch.setattr(ci, "deployment_unchanged", lambda repo, sha: True)
    assert run_scope(monkeypatch, tmp_path, event_name, ref) == "runtime=true\n"


def test_scope_runs_runtime_when_pr_event_is_malformed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # event fileの欠落・不正形式を、文書だけの変更として扱わない。
    monkeypatch.setattr(ci, "changed_paths", lambda *_: ["README.md"])
    output = tmp_path / "output"
    for key, value in {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(tmp_path / "missing.json"),
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_SHA": SHA,
        "GITHUB_OUTPUT": str(output),
    }.items():
        monkeypatch.setenv(key, value)
    ci.scope()
    assert output.read_text() == "runtime=true\n"


def gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    unchanged: bool,
    runtime_succeeded: bool,
) -> Path:
    """全CI成功済みの状態でgateを1回実行し、GITHUB_OUTPUTのpathを返す。"""
    monkeypatch.setattr(ci, "context", lambda: (REPO, SHA))
    monkeypatch.setattr(ci, "latest_main", lambda *_: True)
    monkeypatch.setattr(ci, "successful_run", lambda *_: 30)
    monkeypatch.setattr(ci, "api", lambda path: {"workflow_runs": []})
    monkeypatch.setattr(ci, "deployment_unchanged", lambda *_: unchanged)
    monkeypatch.setattr(ci, "runtime_job_succeeded", lambda *_: runtime_succeeded)
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    ci.wait_for_ci()
    return output


def test_gate_skips_deployment_for_documentation_only_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 配備済みcommitとの差分が文書だけなら、archiveの有無に関わらず配備jobを起動しない。
    output = gate(monkeypatch, tmp_path, unchanged=True, runtime_succeeded=False)
    assert not output.exists()


def test_gate_fails_when_deployment_needs_skipped_runtime_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 判定後に配備済みcommitが変わり、配備が必要なのにarchiveがない場合は成功扱いしない。
    with pytest.raises(RuntimeError, match="re-run Supply Chain"):
        gate(monkeypatch, tmp_path, unchanged=False, runtime_succeeded=False)
    assert not (tmp_path / "output").exists()


def test_runtime_job_success_is_read_from_supply_chain_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # skipされたruntime jobや別名jobの成功を、配備archiveの存在とみなさない。
    jobs = {"jobs": [{"name": ci.RUNTIME_JOB, "conclusion": "skipped"}]}
    monkeypatch.setattr(ci, "api", lambda path: jobs)
    assert not ci.runtime_job_succeeded(REPO, 30)
    jobs["jobs"].append({"name": "Other job", "conclusion": "success"})
    assert not ci.runtime_job_succeeded(REPO, 30)
    jobs["jobs"][0]["conclusion"] = "success"
    assert ci.runtime_job_succeeded(REPO, 30)


def test_transfer_records_only_confirmed_production_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # host側でSupersededになり別commitのままなら、配備済みの記録stepを起動しない。
    monkeypatch.setattr(ci, "context", lambda: (REPO, SHA))
    monkeypatch.setattr(ci, "latest_main", lambda *_: True)
    for key, value in {
        "DEPLOY_INSTANCE_ID": "i-0123456789abcdef0",
        "DEPLOY_AWS_REGION": "ap-northeast-1",
        "DEPLOY_USER": "soj",
        "DEPLOY_PORT": "22",
        "DEPLOY_REPOSITORY": "/srv/judge",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "DEPLOY_SSH_KEY": "test-private-key",
        "DEPLOY_KNOWN_HOSTS": "test-known-host",
        "GITHUB_OUTPUT": str(tmp_path / "output"),
    }.items():
        monkeypatch.setenv(key, value)

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        """本番の成功記録には、更新前の別commitを返す。"""
        return subprocess.CompletedProcess(
            args, 0, json.dumps({"source_commit": BASE}), ""
        )

    monkeypatch.setattr(ci.subprocess, "run", run)
    ci.transfer(tmp_path)
    assert not (tmp_path / "output").exists()
