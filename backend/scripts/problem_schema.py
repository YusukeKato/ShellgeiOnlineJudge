from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from models.problem import ProblemDefinitionV3


MAX_PROBLEM_SCHEMA_FILE_BYTES = 2_000_000


class ProblemSchemaError(ValueError):
    """Raised when a v3 problem definition cannot be parsed or validated."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


class _ProblemDumper(yaml.SafeDumper):
    """Safe YAML dumper that keeps multiline problem text readable."""


def _represent_problem_string(
    dumper: _ProblemDumper,
    value: str,
) -> yaml.nodes.ScalarNode:
    """入力文字列をYAML nodeへ変換し、複数行なら読みやすいliteral形式で返す。"""
    style = "|" if "\n" in value else None
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str",
        value,
        style=style,
    )


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    """入力YAML mapping nodeをdictへ変換し、重複keyがあれば例外を送出する。"""
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)
_ProblemDumper.add_representer(str, _represent_problem_string)


def load_yaml_mapping(text: str, *, source: str) -> Mapping[str, Any]:
    """YAML文字列を重複keyのないmappingとして読み込む。

    入力はYAML本文と、エラー表示に使うsource名。出力は未検証のmappingで、
    YAML構文エラー、重複key、最上位がmappingでない場合はProblemSchemaErrorを送出する。
    """
    try:
        data = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ProblemSchemaError(f"failed to parse {source}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ProblemSchemaError(f"{source} must contain a YAML mapping")
    return data


def parse_problem_definition(
    text: str,
    *,
    source: str = "<memory>",
) -> ProblemDefinitionV3:
    """YAML文字列をschema v3として検証し、型付きproblem definitionを返す。

    入力はYAML本文と任意のsource名。file上限、YAML構造、全fieldを検証し、
    不正な場合はProblemSchemaErrorを送出する。
    """
    if len(text.encode("utf-8")) > MAX_PROBLEM_SCHEMA_FILE_BYTES:
        raise ProblemSchemaError(
            f"{source} exceeds the {MAX_PROBLEM_SCHEMA_FILE_BYTES}-byte file limit"
        )
    data = load_yaml_mapping(text, source=source)
    try:
        return ProblemDefinitionV3.model_validate(data)
    except ValidationError as exc:
        raise ProblemSchemaError(
            f"invalid problem definition in {source}: {exc}"
        ) from exc


def load_problem_definition(path: Path) -> ProblemDefinitionV3:
    """指定pathのv3 YAMLを読み、ファイル名とIDも検証して型付き定義を返す。

    読込、schema検証、またはファイル名との不一致があればProblemSchemaErrorを送出する。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ProblemSchemaError(f"failed to read {path}") from exc
    definition = parse_problem_definition(text, source=str(path))
    if definition.id != path.stem:
        raise ProblemSchemaError(f"problem ID must match the filename stem: {path}")
    return definition


def dump_problem_definition(definition: ProblemDefinitionV3) -> str:
    """入力された型付きproblem definitionを決定的で可読なYAML文字列として返す。"""
    data = definition.model_dump(mode="json")
    return yaml.dump(
        data,
        Dumper=_ProblemDumper,
        allow_unicode=True,
        sort_keys=False,
        width=1_000,
    )
