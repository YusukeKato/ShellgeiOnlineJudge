import json
import os
import time
import urllib.error
import uuid
from collections.abc import Iterator
from typing import Any

import docker
import pytest

from tests.compose_support import ComposeStack, ROOT
from scripts.problem_repository import build_problem_repository


pytestmark = [
    pytest.mark.docker,
    pytest.mark.compose_e2e,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1"
        or os.getenv("SOJ_RUN_COMPOSE_E2E") != "1",
        reason="explicit isolated-host opt-in and prebuilt Compose/browser images required",
    ),
]
REPOSITORY = build_problem_repository(
    ROOT / "problems/v3", ROOT / "problems/image", ROOT / "problems/v3/manifest.json"
)


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ComposeStack]:
    """本番Composeから専用環境を起動し、部分失敗時にも当該projectの資源だけを回収する。"""
    assert os.environ.get("DOCKER_HOST", "").startswith("unix://")
    client = docker.from_env(timeout=30)
    try:
        assert "name=rootless" in client.info()["SecurityOptions"]
        project = f"soj-e2e-{uuid.uuid4().hex}"
        environment = ComposeStack(client, tmp_path_factory.mktemp(project), project)
        try:
            environment.compose("config", "--quiet")
            environment.compose(
                "up",
                "--detach",
                "--no-build",
                "--pull",
                "never",
                "--wait",
                "--wait-timeout",
                "90",
            )
            frontend = environment.service("frontend")
            port = frontend.attrs["NetworkSettings"]["Ports"]["443/tcp"][0]
            assert port["HostIp"] == "127.0.0.1"
            environment.url = f"https://127.0.0.1:{port['HostPort']}"
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    if environment.request("/api/problems")[0] == 200:
                        break
                except (urllib.error.URLError, ConnectionError):
                    pass
                time.sleep(0.5)
            else:
                pytest.fail("Compose API did not become ready through TLS nginx")
            yield environment
        finally:
            environment.close()
            owned = {"label": f"com.docker.compose.project={project}"}
            assert not client.containers.list(all=True, filters=owned)
            assert not client.networks.list(filters=owned)
            assert not client.volumes.list(filters=owned)
            assert not environment.sandboxes()
            for filename in ("test.env", "key.pem", "cert.pem"):
                (environment.directory / filename).unlink()
    finally:
        client.close()


def db_rows(stack: ComposeStack, ids: list[int]) -> list[dict[str, Any]]:
    """一時DBの保存行をIDで読み、APIの保存済み表示だけで成功とみなさない。"""
    script = """
import json, sys
from sqlalchemy import select
from scripts.database import SessionLocal
from models.model_db import ExecutionLog
with SessionLocal() as session:
    rows = session.execute(select(ExecutionLog).where(ExecutionLog.id.in_(json.loads(sys.argv[1])))).scalars()
    print(json.dumps([{'id': row.id, 'verdict': row.verdict, 'status': row.execution_status} for row in rows]))
"""
    result = stack.service("backend").exec_run(
        ["python", "-c", script, json.dumps(ids)]
    )
    assert result.exit_code == 0, "test DB query failed"
    return json.loads(result.output)


def test_frontend_proxy_and_real_submission_contract(stack: ComposeStack) -> None:
    # TLS nginxを通して静的配信・問題API・typed判定・PostgreSQLの実保存を確認する。
    status, headers, body = stack.request("/")
    assert status == 200 and b'<div id="root">' in body
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    status, _, body = stack.request("/api/problems")
    assert status == 200
    assert len(json.loads(body)) == REPOSITORY.problem_count
    for command, verdict, execution, reason in (
        ("echo test", "accepted", "completed", None),
        ("printf wrong", "wrong_answer", "completed", None),
        ("sleep 20", "execution_failure", "timed_out", "timed_out"),
        ("seq 1 2000", "execution_failure", "output_limit", "output_truncated"),
    ):
        response = stack.submit(command)
        assert response["verdict"] == verdict
        assert response["execution"]["status"] == execution
        if reason:
            assert response["reason"] == reason
        assert response["persistence"] == "saved"
        assert db_rows(stack, [response["submission_id"]]) == [
            {"id": response["submission_id"], "verdict": verdict, "status": execution}
        ]
    response = stack.submit(
        REPOSITORY.require("IMAGE-00000001").definition.reference_solution,
        "IMAGE-00000001",
    )
    assert response["verdict"] == "accepted"
    assert response["artifact"]["media_type"] == "image/jpeg"


def test_private_runner_rejects_authentication_and_revision_mismatch(
    stack: ComposeStack,
) -> None:
    # private network上の実runnerが実行前に認証・revision不一致を拒否し、sandboxを消費しない。
    before = {container.id for container in stack.sandboxes()}
    script = """
import json, os, urllib.request, urllib.error
from scripts.problem_repository import load_problem_repository
from scripts.runner_protocol import RUNNER_PROTOCOL_VERSION, RUNNER_EXECUTE_PATH
repository = load_problem_repository()
payload = dict(protocol_version=RUNNER_PROTOCOL_VERSION, request_id='a'*32,
               problem_revision=repository.revision, shellgei='echo test', problem_id='STANDARD-00000001')
statuses = []
for token, revision in [('x'*64, repository.revision), (os.environ['RUNNER_SHARED_SECRET'], '0'*64)]:
    payload['problem_revision'] = revision
    request = urllib.request.Request('http://runner:8001'+RUNNER_EXECUTE_PATH,
        data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=10)
    except urllib.error.HTTPError as error:
        statuses.append(error.code)
print(json.dumps(statuses))
"""
    result = stack.service("backend").exec_run(["python", "-c", script])
    assert result.exit_code == 0, "private runner probe failed"
    assert json.loads(result.output) == [401, 409]
    assert {container.id for container in stack.sandboxes()} == before


def test_db_outage_preserves_judgment_and_recovers_persistence(
    stack: ComposeStack,
) -> None:
    # test DBだけを停止し、判定を失わず保存不能を返すことと、永続volumeからの復帰を確認する。
    saved = stack.submit("echo test")
    try:
        stack.compose("stop", "--timeout", "20", "db")
        response = stack.submit("echo test")
        assert response["verdict"] == "accepted"
        assert response["persistence"] == "unavailable"
        assert response["submission_id"] is None
    finally:
        stack.compose("start", "db")
        stack.wait_command("db", ["pg_isready", "-U", "e2e", "-d", "e2e"])
    recovered = stack.submit("echo test")
    assert recovered["persistence"] == "saved"
    assert (
        len(db_rows(stack, [saved["submission_id"], recovered["submission_id"]])) == 2
    )


def test_runner_outage_and_crash_recovery(stack: ComposeStack) -> None:
    # 停止時の503、強制終了後の旧pool回収、process終了時の自動再起動を個別に確認する。
    try:
        stack.compose("stop", "--timeout", "20", "runner")
        response = stack.submit("echo test", expected=503)
        assert response["code"] == "runner_unavailable"
    finally:
        stack.compose("start", "runner")
        stack.wait_runner()
    assert stack.submit("echo test")["verdict"] == "accepted"
    # pool補充の完了を待ってからkillするため、自然な補充を回収成功と取り違えない。
    stack.wait_runner()
    old = {container.id for container in stack.sandboxes()}
    assert old
    runner = stack.service("runner")
    # Docker killは手動停止なので明示的にstartする。shutdown hookが動かない経路の回収検査。
    try:
        runner.kill(signal="SIGKILL")
        assert stack.submit("echo test", expected=503)["code"] == "runner_unavailable"
        assert old <= {container.id for container in stack.sandboxes()}
    finally:
        stack.compose("start", "runner")
        stack.wait_runner()
    assert old.isdisjoint(container.id for container in stack.sandboxes())
    assert stack.submit("echo test")["verdict"] == "accepted"
    # PID 1が扱うsignalでprocessを終了する。Dockerのstop/killを使わずrestart policyを検査。
    runner.reload()
    restarts = runner.attrs["RestartCount"]
    runner.exec_run(["python", "-c", "import os, signal; os.kill(1, signal.SIGTERM)"])
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        runner.reload()
        if runner.attrs["RestartCount"] > restarts and runner.status == "running":
            break
        time.sleep(0.5)
    else:
        pytest.fail("runner restart policy did not recover")
    stack.wait_runner()
    assert stack.submit("echo test")["verdict"] == "accepted"


def test_browser_submissions_and_display(stack: ComposeStack) -> None:
    # socket・DB secretを持たないChromiumから実UIを操作し、表示とDBの保存を照合する。
    browser = stack.client.containers.create(
        stack.browser_image,
        name=f"{stack.project}-browser",
        init=True,
        network=f"{stack.project}_frontend_backend",
        shm_size="256m",
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        labels={"com.docker.compose.project": stack.project},
    )
    try:
        browser.start()
        status = browser.wait(timeout=180)
        output = browser.logs(tail=100).decode()
        assert status["StatusCode"] == 0, output
        ids = json.loads(output)["submission_ids"]
        assert len(ids) == 5
        assert len(db_rows(stack, ids)) == 5
    finally:
        browser.remove(force=True, v=True)


@pytest.mark.full_regression
@pytest.mark.skipif(
    os.getenv("SOJ_RUN_FULL_REGRESSION") != "1",
    reason="full problem regression requires additional opt-in",
)
def test_all_reference_solutions_through_compose(stack: ComposeStack) -> None:
    # 全manifest問題をnginxから提出し、backend判定とDB保存までの本番経路を通す。
    ids = []
    for problem_id, record in REPOSITORY.records.items():
        response = stack.submit(record.definition.reference_solution, problem_id)
        assert response["verdict"] == "accepted", problem_id
        assert response["persistence"] == "saved", problem_id
        ids.append(response["submission_id"])
    assert len(set(ids)) == REPOSITORY.problem_count
    rows = db_rows(stack, ids)
    assert all(row["verdict"] == "accepted" for row in rows)
    assert len(rows) == REPOSITORY.problem_count
