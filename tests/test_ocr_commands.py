from types import SimpleNamespace

from local_elections.states.jharkhand import ocr_seats
from local_elections.tools import compare_readers


def test_packaged_ocr_helpers_import() -> None:
    assert compare_readers.parse is ocr_seats.parse


def test_ocr_seats_uses_isolated_uv_group(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ocr_seats.subprocess, "run", fake_run)
    ocr_seats.ocr_all([tmp_path / "page.png"], tmp_path)

    command, kwargs = calls[0]
    assert command[:6] == [
        "uv",
        "run",
        "--no-default-groups",
        "--group",
        "ocr",
        "python",
    ]
    assert kwargs == {"cwd": ocr_seats.ROOT}
