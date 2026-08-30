#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import Sequence

from scripts.problem_repository import (
    build_problem_manifest,
    collect_problem_records,
    render_problem_manifest,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """command line引数を解析し、対象directoryと出力方法をnamespaceで返す。"""
    parser = argparse.ArgumentParser(
        description="Generate the checked-in problem data manifest."
    )
    parser.add_argument("definition_directory", type=Path)
    parser.add_argument("image_directory", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the manifest to this path instead of standard output.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """問題dataを検証してmanifestを生成し、fileまたは標準出力へ書いて終了codeを返す。"""
    args = parse_args(argv)
    records = collect_problem_records(
        args.definition_directory,
        args.image_directory,
    )
    rendered = render_problem_manifest(build_problem_manifest(records))
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
