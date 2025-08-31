#!/usr/bin/env python3
import docker
import time
import threading

class DockerClient:
    def __init__(self):
        self.client = docker.from_env()
        self.image_id = "theoldmoon0602/shellgeibot"

    def exec_shellgei_with_timeout(self, shellgei, timeout: int) -> str:
        container = None
        try:
            # Step 1: コンテナの作成と起動
            container = self.client.containers.run(
                self.image_id,
                command='sleep infinity',
                detach=True,
                ipc_mode='none',
                network_mode='none',
            )

            # Step 2: タイムアウト付きでコマンドを実行
            # exec_runをストリームモードで実行
            exec_stream = container.exec_run(shellgei, stream=True, demux=False)
            
            output = b''
            start_time = time.time()
            
            # ストリームから出力を読み取りながらタイムアウトをチェック
            while True:
                if time.time() - start_time > timeout:
                    # タイムアウトしたら例外を発生
                    raise TimeoutError(f"コマンド実行がタイムアウトしました (>{timeout}s)。")
                
                try:
                    chunk = next(exec_stream.output)
                    if chunk:
                        output += chunk
                except StopIteration:
                    # ストリームの終端に達したらループを終了
                    break

            # 正常終了した場合の処理
            return output.decode('utf-8')

        except TimeoutError as e:
            return f"Error: {e}"
        except Exception as e:
            # Docker API関連のエラーをキャッチ
            return f"Error: {e}"
        finally:
            # Step 3: コンテナのクリーンアップ
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                except Exception as e:
                    print(f"コンテナの削除中にエラー: {e}")

if __name__ == "__main__":
    client = DockerClient()
    print(client.exec_shellgei("sleep 20"))