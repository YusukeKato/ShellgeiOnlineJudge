#!/usr/bin/env python3
import docker
import asyncio
import time
import tarfile
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class ShellgeiDockerClient:
    def __init__(self):
        self.client = docker.from_env()
        self.image_id = "theoldmoon0602/shellgeibot"
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.base_dir = Path(__file__).resolve().parent.parent

    def exec_shellgei(self, shellgei: str, problem_id: str, timeout: int) -> list[str, str]:
        container = None
        # コンテナ作成
        try:
            container = self.client.containers.run(
                self.image_id,
                detach=True,
                command='sleep 60',
                ipc_mode='none',
                network_mode='none',
            )
        except Exception as e:
            return [f"Error: create container: {e}", ""]

        # input.txtをコンテナ内へコピー
        try:
            tar_stream = io.BytesIO()
            input_path = self.base_dir / "problems" / "input" / problem_id
            input_path_str = f"{input_path}.txt"
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add(input_path_str, arcname="input.txt")
            tar_stream.seek(0)
            container.put_archive(path="/", data=tar_stream)
        except Exception as e:
            return [f"Error: copy input.txt: {e}", ""]

        # 実行するbashファイルをコピー
        try:
            bash_file_path = self.base_dir / "z.bash"
            with open(bash_file_path, "w", encoding="utf-8") as file:
                file.write(shellgei)
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add(bash_file_path, arcname="z.bash")
            tar_stream.seek(0)
            container.put_archive(path="/", data=tar_stream)
        except Exception as e:
            return [f"Error: copy bash file: {e}", ""]

        # サンプル像を作成しておく
        try:
            container.exec_run("convert -size 200x200 xc:white media/output.jpg")
        except Exception as e:
            return [f"Error: create sample image: {e}", ""]

        # シェル芸を実行
        output = b''
        try:
            exec_stream = container.exec_run(
                "bash z.bash",
                demux=False,
                stream=True,
            )
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    return ["Error: exec stream: timed out.", ""]
                try:
                    chunk = next(exec_stream.output, None)
                    if chunk is None:
                        break
                    output += chunk
                except StopIteration:
                    break
        except Exception as e:
            return [f"Error: run shellgei: {e}", ""]

        # 画像も取得して返す
        try:
            find_str = container.exec_run("find media -name output.gif")
            if "output.gif" in find_str.output.decode('utf-8'):
                image_str = container.exec_run("base64 -w 0 media/output.gif")
            else:
                image_str = container.exec_run("base64 -w 0 media/output.jpg")
            return [output.decode('utf-8'), image_str.output.decode('utf-8')]
        except Exception as e:
            return [f"Error: get image: {e}", ""]

        # 最後にコンテナを削除
        finally:
            if container:
                try:
                    container.stop()
                    container.remove(force=True)
                except Exception as e:
                    return [f"Error: stop/remove container: {e}", ""]

    async def run_with_timeout(self, shellgei: str, problem_id: str, timeout: int = 30) -> list[str, str]:
        loop = asyncio.get_running_loop()
        try:
            result: list[str, str] = await asyncio.wait_for(
                loop.run_in_executor(self.executor, self.exec_shellgei, shellgei, problem_id, timeout),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return ["Error: asyncio: timed out.", ""]
        except Exception as e:
            return [f"Error: run with timeout: {e}", ""]