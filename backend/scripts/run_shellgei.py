#!/usr/bin/env python3
import asyncio
import time
import tarfile
import io
import yaml
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from scripts.container_manager import manager


class ShellgeiDockerClient:
    def __init__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=5
        )  # 並列処理できるよう少し数を増やす
        self.base_dir = Path(__file__).resolve().parent.parent

    def exec_shellgei(
        self, shellgei: str, problem_id: str, timeout: int, limit_str: int
    ) -> list[str]:
        container = None
        # プールからコンテナを取得
        try:
            container = manager.get_container()
        except Exception as e:
            return [f"Error: failed to get container: {e}", ""]

        try:
            # === input.txt のコピー ===
            tar_stream = io.BytesIO()
            yaml_path = self.base_dir / "problems" / "yaml_data" / f"{problem_id}.yaml"
            # ファイルが存在するか確認
            if yaml_path.exists():
                with open(yaml_path, "r", encoding="utf-8") as yf:
                    p_data = yaml.safe_load(yf)
                input_str = p_data.get("input", "")
                if input_str:
                    input_tmp_path = self.base_dir / "input_tmp.txt"
                    with open(input_tmp_path, "w", encoding="utf-8") as f:
                        f.write(input_str)
                    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                        tar.add(input_tmp_path, arcname="input.txt")
                    tar_stream.seek(0)
                    container.put_archive(path="/", data=tar_stream)
            # === ユーザのシェル芸のbashファイルのコピー ===
            bash_file_path = self.base_dir / "z.bash"
            with open(bash_file_path, "w", encoding="utf-8") as file:
                file.write(shellgei)
            tar_stream_bash = io.BytesIO()
            with tarfile.open(fileobj=tar_stream_bash, mode="w") as tar:
                tar.add(bash_file_path, arcname="z.bash")
            tar_stream_bash.seek(0)
            container.put_archive(path="/", data=tar_stream_bash)
            # === サンプル画像作成 ===
            container.exec_run("convert -size 200x200 xc:white media/output.jpg")
            # === シェル芸を実行 ===
            output = b""
            exec_stream = container.exec_run(
                "bash z.bash",
                demux=False,
                stream=True,
            )
            # ストリーム読み込みとタイムアウト管理
            start_time = time.time()
            for chunk in exec_stream.output:
                if time.time() - start_time > timeout:
                    output += b"\n[Timed out]"
                    break
                if chunk:
                    output += chunk
            # === 画像取得 ===
            find_result = container.exec_run("find media -name output.gif")
            if "output.gif" in find_result.output.decode("utf-8", errors="ignore"):
                img_exec = container.exec_run("base64 -w 0 media/output.gif")
            else:
                img_exec = container.exec_run("base64 -w 0 media/output.jpg")
            image_str_utf8 = img_exec.output.decode("utf-8", errors="ignore")
            # === 結果整形 ===
            output_utf8 = output.decode("utf-8", errors="ignore")
            if not output_utf8:
                output_utf8 = "NULL"
            elif len(output_utf8) > limit_str:
                output_utf8 = output_utf8[:limit_str] + "..."
            if len(image_str_utf8) > 1_000_000:
                image_str_utf8 = image_str_utf8[:1_000_000]
            return [output_utf8, image_str_utf8]
        except Exception as e:
            return [f"Error during execution: {e}", ""]

        finally:
            # コンテナマネージャーにコンテナを管理してもらう
            if container:
                manager.release_container(container)

    async def run_with_timeout(
        self, shellgei: str, problem_id: str, timeout: int = 30, limit_str: int = 1000
    ) -> list[str]:
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self.executor,
                    self.exec_shellgei,
                    shellgei,
                    problem_id,
                    timeout,
                    limit_str,
                ),
                timeout=timeout + 2,  # スレッド処理自体の余裕を持たせる
            )
            return result
        except asyncio.TimeoutError:
            return ["Error: asyncio: timed out.", ""]
        except Exception as e:
            return [f"Error: run with timeout: {e}", ""]
