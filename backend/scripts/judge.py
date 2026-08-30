#!/usr/bin/env python3
import re

from scripts.input_validation import validate_problem_id
from scripts.problem_repository import ProblemRepository, get_problem_repository


class ShellgeiJudge:
    def __init__(self, problem_repository: ProblemRepository | None = None) -> None:
        """任意の検証済みrepositoryを受け取り、未指定ならprocess globalを遅延参照する。"""
        self.problem_repository = problem_repository

    def _repository(self) -> ProblemRepository:
        """注入済みrepositoryを返し、未指定なら起動時にloadしたrepositoryを返す。"""
        return self.problem_repository or get_problem_repository()

    def str_replace(self, s: str) -> str:
        """比較対象文字列の空白と記号を既存判定用tokenへ置換して返す。"""
        s = s.replace("\r", "")
        s = s.replace(" ", "SPACE")
        s = s.replace("\n", "NEWLINE")
        s = s.replace("\t", "TAB")
        s = s.replace("<", "LT")
        s = s.replace(">", "GT")
        return s

    def judge(self, output_str: str, output_image: str, problem_id: str) -> str:
        """出力文字列・画像を指定問題の正解と比較し、既存の判定codeを返す。"""
        try:
            validate_problem_id(problem_id)
        except ValueError:
            return "Error: invalid problem ID."
        record = self._repository().get(problem_id)
        if record is None:
            return "Error: answer yaml file not found."
        if len(output_str) == 0:
            output_str = "NULL"
        answer_str = record.expected_output or "NULL"
        answer_image = record.answer_image_base64

        output_str_replaced = self.str_replace(output_str)
        answer_str_replaced = self.str_replace(answer_str)
        while re.match(r".*NEWLINE$", output_str_replaced) is not None:
            output_str_replaced = re.sub(r"NEWLINE$", "", output_str_replaced)
        while re.match(r".*NEWLINE$", answer_str_replaced) is not None:
            answer_str_replaced = re.sub(r"NEWLINE$", "", answer_str_replaced)
        while re.match(r".*SPACE$", output_str_replaced) is not None:
            output_str_replaced = re.sub(r"SPACE$", "", output_str_replaced)
        while re.match(r".*SPACE$", answer_str_replaced) is not None:
            answer_str_replaced = re.sub(r"SPACE$", "", answer_str_replaced)
        output_image_sliced = output_image[28:]
        answer_image_sliced = answer_image[28:]

        judge = "9"
        if (
            output_str_replaced == answer_str_replaced
            and output_image_sliced == answer_image_sliced
        ):
            judge = "1"
        elif (
            output_str_replaced == answer_str_replaced
            and output_image_sliced != answer_image_sliced
        ):
            judge = "2"
        elif (
            output_str_replaced != answer_str_replaced
            and output_image_sliced == answer_image_sliced
        ):
            judge = "3"
        else:
            judge = "4"
        return judge
