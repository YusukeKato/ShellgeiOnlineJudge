import io
import tarfile
from concurrent.futures import ThreadPoolExecutor

from scripts.execution_archive import build_execution_archive


def read_archive(stream: io.BytesIO) -> dict[str, str]:
    files: dict[str, str] = {}
    with tarfile.open(fileobj=stream, mode="r:") as archive:
        for member in archive.getmembers():
            extracted = archive.extractfile(member)
            assert extracted is not None
            files[member.name] = extracted.read().decode("utf-8")
    return files


def test_execution_archive_preserves_command_and_input() -> None:
    archive = build_execution_archive("printf '日本語\\n'", "line 1\nline 2\n")

    assert read_archive(archive) == {
        "input.txt": "line 1\nline 2\n",
        "z.bash": "printf '日本語\\n'",
    }


def test_execution_archive_omits_empty_input_for_compatibility() -> None:
    archive = build_execution_archive("echo ok", "")

    assert read_archive(archive) == {"z.bash": "echo ok"}


def test_parallel_execution_archives_do_not_mix_request_data() -> None:
    def build_and_read(request_id: int) -> tuple[int, dict[str, str]]:
        files = read_archive(
            build_execution_archive(
                f"printf 'command-{request_id}'",
                f"input-{request_id}",
            )
        )
        return request_id, files

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(build_and_read, range(200)))

    for request_id, files in results:
        assert files == {
            "input.txt": f"input-{request_id}",
            "z.bash": f"printf 'command-{request_id}'",
        }
