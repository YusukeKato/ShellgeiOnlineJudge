"""独自Ubuntu sandboxの必要コマンドと不要機能の制限を通常の実行経路で検証する。"""

import asyncio
import os
import uuid

import pytest

from soj_runner.container_manager import ContainerManager
from soj_runner.run_shellgei import ShellgeiDockerClient
from soj_shared.models.execution import ExecutionStatus
from tests.integration.test_full_problem_regression import PROBLEM_REPOSITORY


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="set SOJ_RUN_DOCKER_TESTS=1 for rootless sandbox tests",
    ),
]


@pytest.mark.parametrize(
    "command",
    [
        # 全問題のコマンドとrunnerの固定準備・取得コマンドが存在する。
        "for tool in bash cat seq awk bc cut tr sed sort factor rs find grep uniq wc "
        'xargs convert textimg base64 tar head sleep mkdir ln; do command -v "$tool" >/dev/null '
        '|| exit 1; done; test "$SHELL" = /bin/bash; test "$LANG" = ja_JP.UTF-8',
        # 非採用の言語・compiler、権限昇格・ネットワーク用toolを持ち込まない。
        "for tool in go gcc g++ make node npm python3 ruby pwsh clojure sudo ping "
        'curl wget ssh git; do if command -v "$tool" >/dev/null; then echo "$tool"; '
        'exit 1; fi; done; test -z "$(find /usr -xdev -type f -perm /6000 -print)"',
        # 旧来の3 directory以外も収録し、取得revisionを記録する。Git管理情報は実行時に不要。
        "test -s /ShellGeiData/LICENSE && test -s /ShellGeiData/README.md && "
        "test -d /ShellGeiData/docs && test -d /ShellGeiData/sd201606 && "
        "test -d /ShellGeiData/vol.75 && test ! -e /ShellGeiData/.git && "
        "grep -Eq '^[0-9a-f]{40}$' /usr/local/share/soj/shellgeidata-revision",
        # ホストへの接続は行わず、実network namespaceがloopbackだけであることを確認する。
        'test "$(ls /sys/class/net)" = lo',
        # 許可された画像形式とpipeでの受け渡しを維持する。
        "convert -size 2x2 xc:red png:- | convert - media/output.gif; "
        "test -s media/output.gif",
        # 日本語・ANSI色の文字画像を標準出力からpipeへ渡し、JPEG/GIF出力も確認する。
        "set -e; set -o pipefail; "
        "printf '\\033[31mシェル芸\\033[0m\\n' | textimg | convert - media/output.jpg; "
        "textimg 日本語 -o /tmp/text.jpg; textimg 日本語 -o /tmp/text.gif; "
        "test \"$(identify -format '%m' media/output.jpg)\" = JPEG; "
        "test \"$(identify -format '%m' /tmp/text.jpg)\" = JPEG; "
        "test \"$(identify -format '%m' /tmp/text.gif)\" = GIF",
        # 不要なPDF、URL、間接file参照を小さな入力で拒否する。
        "if convert -size 2x2 xc:red /tmp/output.pdf 2>/dev/null; then exit 1; fi; "
        "if convert https://example.invalid/a.png /tmp/a.png 2>/dev/null; then exit 1; fi; "
        "printf secret >/tmp/caption; "
        "if convert label:@/tmp/caption /tmp/a.png 2>/dev/null; then exit 1; fi",
        # 幅制限をわずかに超える小さな画像要求で、policyによる上限を確認する。
        "if convert -size 4097x1 xc:red /tmp/wide.png 2>/dev/null; then exit 1; fi",
    ],
)
def test_minimal_sandbox_commands_and_restrictions(command: str) -> None:
    # 各入力は専用ownerのsandboxで実行し、成功・失敗にかかわらずcontainerを回収する。
    manager = ContainerManager(pool_size=1, owner_id=f"tools-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, problem_repository=PROBLEM_REPOSITORY
    )
    manager.initialize_pool()
    try:
        result = asyncio.run(client.run_with_timeout(command, "STANDARD-00000001"))
        assert result.status is ExecutionStatus.COMPLETED, result
        assert result.exit_code == 0, (result.stdout, result.stderr)
    finally:
        manager.shutdown_pool()
        client.close()
