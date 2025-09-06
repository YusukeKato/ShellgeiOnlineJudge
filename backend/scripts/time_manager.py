#!/usr/bin/env python3
import time
from pathlib import Path


class TimeManager:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.unixtime_path = self.base_dir / "unixtime.txt"

    def read_unixtime_file(self) -> float:
        with open(self.unixtime_path, "r", encoding="utf-8") as file:
            return float(file.read().strip())

    def write_unixtime_file(self, unix_time: float) -> None:
        with open(self.unixtime_path, "w", encoding="utf-8") as file:
            file.write(str(unix_time))

    def is_time_exceeded(self, limit: float = 0.1) -> bool:
        current_time: float = time.time()
        last_time: float = self.read_unixtime_file()
        if (current_time - last_time) > limit:
            self.write_unixtime_file(current_time)
            return True
        else:
            return False
