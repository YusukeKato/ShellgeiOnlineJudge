from enum import Enum


class SubmissionStatus(str, Enum):
    """提出use caseの完了、問題未登録、runner混雑・停止を区別して表す。"""

    COMPLETED = "completed"
    PROBLEM_NOT_FOUND = "problem_not_found"
    RUNNER_BUSY = "runner_busy"
    RUNNER_UNAVAILABLE = "runner_unavailable"


class SubmissionPersistenceStatus(str, Enum):
    """実行ログが保存済み、保存不能、保存対象外のどれかを表す。"""

    SAVED = "saved"
    UNAVAILABLE = "unavailable"
    NOT_ATTEMPTED = "not_attempted"
