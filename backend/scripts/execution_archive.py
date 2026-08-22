import io
import tarfile


def _add_text_file(archive: tarfile.TarFile, name: str, contents: str) -> None:
    payload = contents.encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = 0o600
    info.mtime = 0
    archive.addfile(info, io.BytesIO(payload))


def build_execution_archive(shellgei: str, input_data: str) -> io.BytesIO:
    """Build an isolated, in-memory archive for one sandbox execution."""
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        if input_data:
            _add_text_file(archive, "input.txt", input_data)
        _add_text_file(archive, "z.bash", shellgei)
    stream.seek(0)
    return stream
