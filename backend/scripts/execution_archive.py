import io
import tarfile
from collections.abc import Iterable


def _add_text_file(archive: tarfile.TarFile, name: str, contents: str) -> None:
    """入力文字列を権限0600・固定mtimeのUTF-8 fileとしてtar archiveへ追加する。"""
    payload = contents.encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = 0o600
    info.mtime = 0
    archive.addfile(info, io.BytesIO(payload))


def build_execution_archive(
    shellgei: str,
    fixtures: Iterable[tuple[str, str]],
) -> io.BytesIO:
    """commandとfixture群から、1回のsandbox実行専用のmemory内tarを返す。"""
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for path, contents in fixtures:
            _add_text_file(archive, path, contents)
        _add_text_file(archive, "z.bash", shellgei)
    stream.seek(0)
    return stream
