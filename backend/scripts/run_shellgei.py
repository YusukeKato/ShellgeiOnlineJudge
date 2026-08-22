#!/usr/bin/env python3
import asyncio
import time
import yaml
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from scripts.container_manager import manager
from scripts.execution_archive import build_execution_archive


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
            # Build all request-specific files in memory. Host-side shared temporary
            # files would allow concurrent requests to overwrite each other's data.
            yaml_path = self.base_dir / "problems" / "yaml_data" / f"{problem_id}.yaml"
            input_str = ""
            if yaml_path.exists():
                with open(yaml_path, "r", encoding="utf-8") as yf:
                    p_data = yaml.safe_load(yf)
                input_str = p_data.get("input", "")
            execution_archive = build_execution_archive(shellgei, input_str)
            container.put_archive(path="/", data=execution_archive)
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
