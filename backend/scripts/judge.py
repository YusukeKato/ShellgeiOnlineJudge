#!/usr/bin/env python3
import re
from pathlib import Path
import base64

class ShellgeiJudge:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent

    def str_replace(self, s: str) -> str:
        s = s.replace("\r", "")
        s = s.replace(" ", "SPACE")
        s = s.replace("\n", "NEWLINE")
        s = s.replace("\t", "TAB")
        s = s.replace("<", "LT")
        s = s.replace(">", "GT")
        return s

    def judge(self, output_str: str, output_image: str, problem_id: str) -> str:
        if len(output_str) == 0:
            output_str = "NULL"
        answer_str_path = self.base_dir / "problems" / "output" / problem_id
        answer_str_path_str = f"{answer_str_path}.txt"
        answer_image_path = self.base_dir / "problems" / "image" / problem_id
        answer_image_path_str = f"{answer_image_path}.jpg"
        # 答えの文字列の取得
        try:
            with open(answer_str_path_str, 'r', encoding='utf-8') as file:
                answer_str = file.read()
        except FileNotFoundError:
            return "Error: answer str file not found."
        except Exception as e:
            return f"Error: get answer str file: {e}"
        # 答えの画像の取得
        try:
            with open(answer_image_path_str, 'rb') as image_file:
                image_bytes = image_file.read()
                base64_bytes = base64.b64encode(image_bytes)
                answer_image = base64_bytes.decode('utf-8')
        except FileNotFoundError:
            return "Error: answer image file not found."
        except Exception as e:
            return f"Error: get answer image file: {e}"

        output_str_replaced = self.str_replace(output_str)
        answer_str_replaced = self.str_replace(answer_str)
        while re.match(r'.*NEWLINE$', output_str_replaced) != None:
            output_str_replaced = re.sub(r'NEWLINE$', '', output_str_replaced)
        while re.match(r'.*NEWLINE$', answer_str_replaced) != None:
            answer_str_replaced = re.sub(r'NEWLINE$', '', answer_str_replaced)
        while re.match(r'.*SPACE$', output_str_replaced) != None:
            output_str_replaced = re.sub(r'SPACE$', '', output_str_replaced)
        while re.match(r'.*SPACE$', answer_str_replaced) != None:
            answer_str_replaced = re.sub(r'SPACE$', '', answer_str_replaced)
        output_image_sliced = output_image[28:]
        answer_image_sliced = answer_image[28:]

        judge = "9"
        if (output_str_replaced == answer_str_replaced and output_image_sliced == answer_image_sliced):
            judge = "1"
        elif (output_str_replaced == answer_str_replaced and output_image_sliced != answer_image_sliced):
            judge = "2"
        elif (output_str_replaced != answer_str_replaced and output_image_sliced == answer_image_sliced):
            judge = "3"
        else:
            judge = "4"
        return judge