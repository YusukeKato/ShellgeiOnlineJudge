import docker
import threading
from collections import deque


class ContainerManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ContainerManager, cls).__new__(cls)
            cls._instance.client = docker.from_env()
            cls._instance.image_id = "theoldmoon0602/shellgeibot"
            cls._instance.pool = deque()
            cls._instance.lock = threading.Lock()
            cls._instance.pool_size = 3  # 常時待機させるコンテナ数
        return cls._instance

    def initialize_pool(self):
        """起動時にプールを満たす"""
        print(f"Initializing container pool ({self.pool_size})...")
        # 初回は同期的に作成して準備完了を待つ
        for _ in range(self.pool_size):
            self._create_and_add()
        print("Container pool ready.")

    def _create_and_add(self):
        """新しいコンテナを作成してプールに追加する"""
        try:
            container = self.client.containers.run(
                self.image_id,
                detach=True,
                command="sleep infinity",  # 常駐させる
                ipc_mode="none",
                network_mode="none",
                mem_limit="512m",
                memswap_limit="512m",
                nano_cpus=500000000,
                pids_limit=50,
                cap_drop=["ALL"],
                tmpfs={"/media": "size=100M"},
                ulimits=[
                    docker.types.Ulimit(name="fsize", soft=50000000, hard=50000000)
                ],
            )
            with self.lock:
                self.pool.append(container)
        except Exception as e:
            print(f"Error creating container: {e}")

    def get_container(self):
        """プールからコンテナを取得。なければその場で作る"""
        with self.lock:
            if self.pool:
                return self.pool.popleft()
        # プールが空なら作成
        print("Pool empty! Creating emergency container...")
        # _create_and_add はプールに追加してしまうので、直接作成して返す
        return self.client.containers.run(
            self.image_id,
            detach=True,
            command="sleep infinity",  # 常駐させる
            ipc_mode="none",
            network_mode="none",
            mem_limit="512m",
            memswap_limit="512m",
            nano_cpus=500000000,
            pids_limit=50,
            cap_drop=["ALL"],
            tmpfs={"/media": "size=100M"},
            ulimits=[docker.types.Ulimit(name="fsize", soft=50000000, hard=50000000)],
        )

    def release_container(self, container):
        """使用済みコンテナを廃棄し、新しいコンテナを補充する"""
        # 使い終わったコンテナを非同期で削除
        threading.Thread(target=self._cleanup_old, args=(container,)).start()
        # 新しいコンテナを非同期で補充
        threading.Thread(target=self._create_and_add).start()

    def _cleanup_old(self, container):
        try:
            container.kill()
            container.remove(force=True)
        except Exception as e:
            print(f"Error cleaning up container: {e}")


# シングルトンインスタンス
manager = ContainerManager()
