import csv
import hashlib

import pytest

from local_elections.common import harvest


def document():
    return harvest.SourceDocument(
        source_id="example_series_2020",
        state="Gujarat",
        year="2020",
        government_level="district_panchayat",
        tier="zp_member",
        language="Gujarati",
        document_format="encoded-text",
        district="Ahmedabad",
        file="ahmedabad.pdf",
        url="https://example.gov.in/ahmedabad.pdf",
        landing_url="https://example.gov.in/reservations",
    )


def test_acquire_writes_standard_manifest_and_reuses_identical_bytes(
    tmp_path, monkeypatch
):
    payload = b"reviewed source bytes"
    calls = []

    def fetch(*args, **kwargs):
        calls.append((args, kwargs))
        return payload

    monkeypatch.setattr(harvest.fetch, "body", fetch)
    out = tmp_path / "sources"
    manifest = out / "manifest.csv"

    first = harvest.acquire([document()], out, manifest, tmp_path)
    second = harvest.acquire([document()], out, manifest, tmp_path)

    assert first[0]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert second[0]["retrieved_at"] == first[0]["retrieved_at"]
    assert len(calls) == 1
    with manifest.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0]) == harvest.MANIFEST_FIELDS
    assert rows[0]["source_id"] == "example_series_2020"
    assert rows[0]["government_level"] == "district_panchayat"
    assert (out / "ahmedabad.pdf").read_bytes() == payload
    verified = harvest.verify(manifest, out, {document().source_id: 1})
    assert verified[0]["file"] == "ahmedabad.pdf"


def test_acquire_refuses_to_overwrite_changed_held_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        harvest.fetch, "body", lambda *args, **kwargs: b"live source bytes"
    )
    out = tmp_path / "sources"
    out.mkdir()
    (out / document().file).write_bytes(b"different held bytes")

    with pytest.raises(RuntimeError, match="differs from the live source"):
        harvest.acquire([document()], out, out / "manifest.csv", tmp_path)


def test_source_series_count_is_an_executable_expectation():
    with pytest.raises(RuntimeError, match="expected 2 documents, found 1"):
        harvest.require_count([document()], 2, document().source_id)


def test_offline_verification_detects_changed_source_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        harvest.fetch, "body", lambda *args, **kwargs: b"reviewed source bytes"
    )
    out = tmp_path / "sources"
    manifest = out / "manifest.csv"
    harvest.acquire([document()], out, manifest, tmp_path)
    (out / document().file).write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="byte count differs"):
        harvest.verify(manifest, out, {document().source_id: 1})
