class BoundedByteBuffer:
    """Store at most byte_limit bytes and report whether input was truncated."""

    def __init__(self, byte_limit: int) -> None:
        if byte_limit < 1:
            raise ValueError("byte_limit must be at least 1")
        self.byte_limit = byte_limit
        self._data = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> bool:
        remaining = self.byte_limit - len(self._data)
        if len(chunk) > remaining:
            self._data.extend(chunk[:remaining])
            self.truncated = True
            return False
        self._data.extend(chunk)
        return True

    def to_bytes(self) -> bytes:
        return bytes(self._data)

    def __len__(self) -> int:
        return len(self._data)
