import hashlib
import json

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


def test_changed_sibling_fetches_the_published_revision(source_tree, monkeypatch):
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
            yield payload

    def download(url, **kwargs):
        requested.append(url)
        return Response()

    monkeypatch.setattr(sources.requests, "get", download)
    directory, revision = sources.resolve("provider")
    assert requested == [
        f"https://raw.githubusercontent.com/in-rolls/provider/{revision}/data/input.csv"
    ]
    assert (directory / "data/input.csv").read_bytes() == payload


def test_unpinned_siblings_keep_the_existing_resolution(source_tree):
    assert sources.resolve("unrelated_provider") is None
