#!/usr/bin/env python3
import docker

class ShellgeiDockerClient:
    def __init__(self):
        self.client = docker.from_env()
        self.image_id = "theoldmoon0602/shellgeibot"

    def exec_shellgei(self, shellgei) -> str:
        container = None
        try:
            container = self.client.containers.run(
                self.image_id,
                detach=True,
                command='sleep infinity',
                ipc_mode='none',
                network_mode='none',
            )
        except Exception as e:
            return f"Error: create container: {e}"
        try:
            result = container.exec_run(
                shellgei,
                demux=False,
            )
            return result.output.decode('utf-8')
        except Exception as e:
            return f"Error: run shellgei: {e}"
        finally:
            if container:
                try:
                    container.stop()
                    container.remove(force=True)
                except Exception as e:
                    return f"Error: stop/remove container: {e}"

if __name__ == "__main__":
    docker_client = ShellgeiDockerClient()
    print(docker_client.exec_shellgei("echo hello"))
    print(docker_client.exec_shellgei("sleep 20"))
    print("end")