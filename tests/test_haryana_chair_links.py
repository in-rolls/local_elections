import pytest

from local_reservations.tools.link_haryana_chairs import link_chairs


def chair(name, bbox="[0, 0, 10, 10]"):
    return {
        "body_raw": name,
        "source_sha256": "report-hash",
        "source_page": 22,
        "source_bbox": bbox,
    }


def test_barwala_reservations_remain_separate_and_unassigned():
    rows = link_chairs(
        [chair("Barwala"), chair("Barwala", "[20, 0, 30, 10]")],
        [
            {"label": "BARWALA", "heading": "HISAR", "url": "same.pdf"},
            {"label": "BARWALA", "heading": "PANCHKULA", "url": "same.pdf"},
        ],
        [],
    )
    assert len(rows) == 2
    assert all(r["district_candidate"] is None for r in rows)
    assert all(r["linkage_method"] == "ambiguous_name" for r in rows)
    assert rows[0]["report_source_bbox"] != rows[1]["report_source_bbox"]


def test_spelling_variants_require_explicit_review():
    source = [chair("Dadari-1")]
    directory = [{"label": "DADRI-I", "heading": "BHIWANI"}]
    assert link_chairs(source, directory, [])[0]["district_candidate"] is None
    review = [{"report_body_raw": "Dadari-1", "index_body_raw": "DADRI-I"}]
    assert link_chairs(source, directory, review)[0]["district_candidate"] == "BHIWANI"
    with pytest.raises(ValueError, match="Changed or duplicate"):
        link_chairs(source, directory, review + review)
    with pytest.raises(ValueError, match="Changed or duplicate"):
        link_chairs([chair("Dadari-I")], directory, review)


def test_duplicate_report_identity_is_rejected():
    with pytest.raises(ValueError, match="Duplicate report cell"):
        link_chairs([chair("A"), chair("B")], [], [])


def test_whitespace_normalization_preserves_original_body():
    raw = "Hansi-\nI"
    row = link_chairs([chair(raw)], [{"label": "HANSI-I", "heading": "HISAR"}], [])[0]
    assert row["report_body_raw"] == raw
    assert row["district_candidate"] == "HISAR"
    assert row["linkage_method"] == "normalized_name"
