import hashlib
import json
from types import SimpleNamespace

import pytest

from local_reservations.common import sources


@pytest.fixture
def source_tree(tmp_path, monkeypatch):
    root = tmp_path / "consumer"
    (root / "data").mkdir(parents=True)
    payload = b"id,name\n45,GP 45\n44,GP 44\n"
    specification = {
        "ref": "a" * 40,
        "files": {"data/input.csv": hashlib.sha256(payload).hexdigest()},
    }
    (root / "data/sources.json").write_text(json.dumps({"provider": specification}))
    sibling = tmp_path / "provider/data/input.csv"
    sibling.parent.mkdir(parents=True)
    sibling.write_bytes(payload)
    monkeypatch.setattr(sources, "ROOT", root)
    monkeypatch.setenv("INDIA_DATA_HOME", str(tmp_path / "cache"))
    return sibling, payload


def test_verified_sibling_and_cache_need_no_network(source_tree, monkeypatch):
    sibling, payload = source_tree

    def no_download(*args, **kwargs):
        pytest.fail("An intact local source should not need the network")

    monkeypatch.setattr(sources.requests, "get", no_download)
    directory, revision = sources.resolve("provider")
    assert revision == "a" * 40
    assert (directory / "data/input.csv").read_bytes() == payload
    sibling.write_bytes(b"changed source")
    assert sources.resolve("provider") == (directory, revision)


def test_corrupt_cache_is_rejected(source_tree):
    directory, _ = sources.resolve("provider")
    (directory / "data/input.csv").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Cached source checksum mismatch"):
        sources.resolve("provider")


@pytest.mark.parametrize("corrupt", [False, True])
def test_changed_sibling_fetches_the_published_revision(
    source_tree, monkeypatch, corrupt
):
    sibling, payload = source_tree
    sibling.write_bytes(b"different revision")
    requested = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"corrupt download" if corrupt else payload

    def download(url, **kwargs):
        requested.append(url)
        return Response()

    monkeypatch.setattr(sources.requests, "get", download)
    if corrupt:
        with pytest.raises(ValueError, match="Published source checksum mismatch"):
            sources.resolve("provider")
        assert not list((sibling.parents[2] / "cache").rglob("input.csv"))
        return
    directory, revision = sources.resolve("provider")
    assert requested == [
        f"https://raw.githubusercontent.com/in-rolls/provider/{revision}/data/input.csv"
    ]
    assert (directory / "data/input.csv").read_bytes() == payload


def test_unpinned_siblings_keep_the_existing_resolution(source_tree):
    assert sources.resolve("unrelated_provider") is None


def test_builder_passes_verified_directory_and_revision_to_adapters(
    source_tree, monkeypatch
):
    from local_reservations.tools import build_master

    _, payload = source_tree
    received = []

    def slices(directory):
        received.append(directory)
        assert (directory / "data/input.csv").read_bytes() == payload
        yield {"rows": [{"id": "45"}, {"id": "44"}]}

    def supplemental(directory):
        received.append(directory)
        return {"rows": [{"count": 2}]}

    adapter = SimpleNamespace(REPO="provider", slices=slices, supplemental=supplemental)
    monkeypatch.setattr(build_master.adapters, "REGISTRY", {"example": adapter})
    directory, revision = sources.resolve("provider")
    result = list(build_master.sibling_slices())
    assert result == [
        {
            "rows": [{"id": "45"}, {"id": "44"}],
            "source_repo": "provider",
            "source_commit": revision,
        }
    ]
    extra = list(build_master.sibling_supplemental())
    assert extra == [
        {"rows": [{"count": 2, "source_repo": "provider", "source_commit": revision}]}
    ]
    assert received == [directory, directory]
