from scripts.sandbox_limits import BoundedByteBuffer


def test_bounded_buffer_never_stores_more_than_limit() -> None:
    output = BoundedByteBuffer(8)

    assert output.append(b"1234") is True
    assert output.append(b"56789") is False

    assert output.to_bytes() == b"12345678"
    assert len(output) == 8
    assert output.truncated is True


def test_bounded_buffer_accepts_exact_limit() -> None:
    output = BoundedByteBuffer(4)

    assert output.append(b"1234") is True
    assert output.to_bytes() == b"1234"
    assert output.truncated is False
