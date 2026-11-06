"""OpenTelemetry traceparentの短い境界入力と通常の伝播互換性を検査する。"""

import pytest
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

HEADER = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"


def test_traceparent_round_trip_preserves_trace_and_tracestate() -> None:
    """通常headerのID・flags・tracestateを抽出・再出力しても変えない。"""
    propagator = TraceContextTextMapPropagator()
    context = propagator.extract(
        {"traceparent": HEADER, "tracestate": "a=b,  c=d"}, context=Context()
    )
    span = trace.get_current_span(context).get_span_context()
    assert span.is_valid and span.is_remote
    output: dict[str, str] = {}
    propagator.inject(output, context=context)
    assert output == {"traceparent": HEADER, "tracestate": "a=b,c=d"}


@pytest.mark.parametrize("length,valid", [(512, True), (513, False)])
def test_traceparent_length_boundary_is_bounded_before_parsing(
    length: int, valid: bool
) -> None:
    """最大長以内の通常headerは許可し、1文字超過を拒否する。DoSサイズは生成しない。"""
    header = HEADER + " " * (length - len(HEADER))
    context = TraceContextTextMapPropagator().extract(
        {"traceparent": header}, context=Context()
    )
    assert trace.get_current_span(context).get_span_context().is_valid is valid


@pytest.mark.parametrize(
    "carrier",
    [
        {},
        {"traceparent": "\n" + HEADER},
        {"traceparent": HEADER + "\r"},
        {"traceparent": HEADER[:20] + "\n" + HEADER[20:]},
    ],
)
def test_small_malformed_traceparent_does_not_create_a_valid_span(
    carrier: dict[str, str],
) -> None:
    """欠落・短いCR/LF不正headerを受けても有効なtraceを作らない。"""
    context = TraceContextTextMapPropagator().extract(carrier, context=Context())
    assert not trace.get_current_span(context).get_span_context().is_valid
