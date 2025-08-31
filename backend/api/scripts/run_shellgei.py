#!/usr/bin/env python3
import docker
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor


class ShellgeiDockerClient:
    def __init__(self):
        self.client = docker.from_env()
        self.image_id = "theoldmoon0602/shellgeibot"
        self.executor = ThreadPoolExecutor(max_workers=1)

    def exec_shellgei(self, shellgei: str, timeout: int) -> str:
        container = None
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
        finally:
            if container:
                try:
                    container.stop()
                    container.remove(force=True)
                except Exception as e:
                    return f"Error: stop/remove container: {e}"

    async def run_with_timeout(self, shellgei: str, timeout: int = 20) -> str:
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(self.executor, self.exec_shellgei, shellgei, timeout),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return "Error: asyncio: timed out."
        except Exception as e:
            return f"Error: {e}"

if __name__ == "__main__":
    docker_client = ShellgeiDockerClient()
    print(asyncio.run(docker_client.run_with_timeout("echo hello")))
    print(asyncio.run(docker_client.run_with_timeout("sleep 20")))
    print("end")