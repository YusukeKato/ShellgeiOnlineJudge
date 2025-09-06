#!/usr/bin/env python3
from pathlib import Path


class LogManager:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.shellgei_id_path = self.base_dir / "shellgei_id.txt"

    def read_shellgei_id_file(self) -> int:
        with open(self.shellgei_id_path, "r", encoding="utf-8") as file:
            return int(file.read().strip())

    def write_shellgei_id_file(self, shellgei_id: int) -> None:
        with open(self.shellgei_id_path, "w", encoding="utf-8") as file:
            file.write(str(shellgei_id))

    def update_shellgei_id(self) -> str:
        current_id: int = self.read_shellgei_id_file()
        new_id: int = current_id + 1
        self.write_shellgei_id_file(new_id)
        return str(new_id)
