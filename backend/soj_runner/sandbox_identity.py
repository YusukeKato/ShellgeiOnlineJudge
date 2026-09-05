"""runnerとホスト監視が共有する、sandbox識別情報と管理上限の正本。"""

import re


DEFAULT_POOL_SIZE = 3
MANAGED_LABEL = "com.shellgei-online-judge.sandbox"
OWNER_LABEL = "com.shellgei-online-judge.owner"
INSTANCE_LABEL = "com.shellgei-online-judge.runner-instance"
DEFAULT_SANDBOX_OWNER_ID = "shellgei-online-judge"
SANDBOX_OWNER_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}")
