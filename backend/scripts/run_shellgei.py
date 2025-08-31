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

    def exec_shellgei(self, shellgei: str, problem_id: str, timeout: int) -> str:
        container = None
        # コンテナ作成
        try:
            container = self.client.containers.run(
                self.image_id,
                detach=True,
                command='sleep 30',
                ipc_mode='none',
                network_mode='none',
            )
        except Exception as e:
            return f"Error: create container: {e}"

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
            return f"Error: copy input.txt: {e}"

        # シェル芸を実行
        try:
            exec_stream = container.exec_run(
                shellgei,
                demux=False,
                stream=True,
            )
            output = b''
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    return "Error: exec stream: timed out."
                try:
                    chunk = next(exec_stream.output, None)
                    if chunk is None:
                        break
                    output += chunk
                except StopIteration:
                    break
            return output.decode('utf-8')
        except Exception as e:
            return f"Error: run shellgei: {e}"

        # 最後にコンテナを削除
        finally:
            if container:
                try:
                    container.stop()
                    container.remove(force=True)
                except Exception as e:
                    return f"Error: stop/remove container: {e}"

    async def run_with_timeout(self, shellgei: str, problem_id: str, timeout: int = 20) -> str:
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(self.executor, self.exec_shellgei, shellgei, problem_id, timeout),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return "Error: asyncio: timed out."
        except Exception as e:
            return f"Error: {e}"