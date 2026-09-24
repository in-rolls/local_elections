"""Apply source-pinned GP fragment context without changing electoral readings."""

import gzip
import hashlib
import json
import re
import tarfile
from collections import Counter
from pathlib import Path

import pandas as pd

from local_elections.common.observations import digest, inside

ROOT = Path(__file__).resolve().parents[3]
RAW_FIELDS = (
    "body_raw",
    "category_raw",
    "office_raw",
    "relation_raw",
    "ward_raw",
    "winner_raw",
)
COLUMN_DICTIONARY = {
    "body_before_gp_fragment_context_review": (
        "Prior within-page body value; original body_raw is unchanged."
    ),
    "gp_fragment_context_body_source_raw": (
        "Body name read from the reviewed GP heading sequence."
    ),
    "gp_fragment_context_district_source_raw": (
        "Printed district name, not a certified administrative code."
    ),
    "gp_fragment_context_block_source_raw": (
        "Printed block name, not a certified administrative code."
    ),
    "gp_fragment_context_review_status": (
        "Applied only after raw-cell and evidence preconditions pass."
    ),
    "gp_fragment_context_review_file": (
        "Context packet path relative to the Haryana OCR output directory."
    ),
    "gp_fragment_context_review_sha256": "SHA256 of the compressed context packet.",
    "gp_fragment_context_evidence_json": (
        "Source-page chain and content-addressed image archive provenance."
    ),
    "gp_fragment_overlap_group_sha256": (
        "Shared identifier for copies of one printed publication entry; not a seat "
        "identifier."
    ),
    "gp_fragment_overlap_kind": (
        "same_publication; never independent accuracy evidence."
    ),
}


def row_key(row):
    return (
        row["source_sha256"],
        int(row["source_page"]),
        int(row["source_row_on_page"]),
    )


def matches(actual, expected):
    missing = bool(pd.isna(actual))
    return missing if expected is None else not missing and actual == expected


def load_packet(out, entry, checked_sources):
    path = inside(out, entry["path"])
    if digest(path) != entry["sha256"]:
        raise ValueError("GP context packet checksum mismatch")
    packet = json.loads(gzip.decompress(path.read_bytes()))
    if (
        packet["status"] != "rebased_raw_guards_passed_context_application_pending"
        or packet["assignment_usable"] is not False
    ):
        raise ValueError("GP context packet is not explicitly provisional and reviewed")
    archive_spec = packet["review_image_path_base"]
    if archive_spec["kind"] != "tar_gzip_member":
        raise ValueError("Unsupported GP context image storage")
    archive_path = inside(path.parent, archive_spec["archive_path"])
    if digest(archive_path) != archive_spec["archive_sha256"]:
        raise ValueError("GP context image archive checksum mismatch")
    image_pins = {}
    documents = {}
    for doc in packet["documents"]:
        if (
            doc["notification_context_review_status"]
            != "printed_heading_and_continuous_gp_table_reviewed"
            or doc["notification_block_and_district_not_yet_source_validated"]
            is not False
            or doc["overlap_is_same_publication_not_independent_ground_truth"]
            is not True
        ):
            raise ValueError("GP notification context has unresolved prerequisites")
        pages = [page["page"] for page in doc["page_chain"]]
        if pages != list(range(doc["notification_page"], doc["counterpart_page"] + 1)):
            raise ValueError("GP notification page chain is not contiguous")
        for prefix in ("fragment", "counterpart"):
            source = inside(ROOT, doc[prefix + "_source_path"])
            expected = doc[prefix + "_source_sha256"]
            if source not in checked_sources:
                checked_sources[source] = digest(source)
            if checked_sources[source] != expected:
                raise ValueError("GP context PDF checksum mismatch")
            if expected in documents:
                raise ValueError("Ambiguous GP context source document")
            documents[expected] = doc
        for prefix in ("fragment", "counterpart", "preceding"):
            image_pins[doc[prefix + "_image_path"]] = doc[prefix + "_image_sha256"]
        for page in doc["page_chain"]:
            image_pins[page["image_path"]] = page["image_sha256"]
    with tarfile.open(archive_path, "r:gz") as archive:
        for name, expected in image_pins.items():
            if not re.fullmatch(r"images/[0-9a-f]{64}\.png", name):
                raise ValueError("Unsafe GP review image member name")
            member = archive.getmember(name)
            if not member.isfile():
                raise ValueError("GP review image is not a regular archive member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("GP review image is missing")
            with stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected:
                raise ValueError("GP review image checksum mismatch")
    rows = {}
    for review in packet["context_rows"]:
        key = row_key(review)
        if key in rows or set(review["expected_raw"]) != set(RAW_FIELDS):
            raise ValueError("Duplicate GP review or incomplete raw-cell guards")
        doc = documents.get(key[0])
        if doc is None:
            raise ValueError("GP review refers to an unpinned document")
        expected_page = (
            doc["fragment_page"]
            if key[0] == doc["fragment_source_sha256"]
            else doc["counterpart_page"]
        )
        if (
            key[1] != expected_page
            or review["context_source_sha256"] != doc["counterpart_source_sha256"]
            or review["context_notification_page"] != doc["notification_page"]
            or review["context_target_page"] != doc["counterpart_page"]
            or review["context_body_page"]
            not in {page["page"] for page in doc["page_chain"]}
        ):
            raise ValueError("GP review page references disagree with its evidence")
        for field in ("body_source_raw", "block_source_raw", "district_source_raw"):
            if not isinstance(review[field], str) or not review[field].strip():
                raise ValueError("GP context reading is empty")
        if any(
            review[field] != doc[field]
            for field in ("block_source_raw", "district_source_raw")
        ):
            raise ValueError("GP row and notification jurisdiction disagree")
        if (
            review["category_and_identity_not_corrected_by_this_context_review"]
            is not True
        ):
            raise ValueError(
                "GP context packet attempts to change identity/category scope"
            )
        rows[key] = {"review": review, "document": doc}
    linked = set()
    for pair in packet["overlap_pairs"]:
        if (
            pair["same_printed_publication_observation"] is not True
            or pair["independent_accuracy_evidence"] is not False
        ):
            raise ValueError("GP overlap must remain same-publication evidence")
        pair_keys = (tuple(pair["fragment_key"]), tuple(pair["counterpart_key"]))
        group = hashlib.sha256(
            json.dumps(sorted(pair_keys), separators=(",", ":")).encode()
        ).hexdigest()
        for key in pair_keys:
            if key not in rows or key in linked:
                raise ValueError("GP overlap linkage is absent or repeated")
            if rows[key]["review"]["body_source_raw"] != pair["body_source_raw"]:
                raise ValueError("GP overlap body readings disagree")
            linked.add(key)
            rows[key]["overlap_group"] = group
    if linked != set(rows):
        raise ValueError("A GP context row lacks its same-publication linkage")
    for item in rows.values():
        item["packet_file"] = path.relative_to(out.resolve()).as_posix()
        item["packet_sha256"] = entry["sha256"]
        item["archive_file"] = archive_path.relative_to(out.resolve()).as_posix()
        item["archive_sha256"] = archive_spec["archive_sha256"]
    return rows


def apply_source_gp_fragment_context_reviews(records, out):
    out = Path(out).resolve()
    config_path = out / "gp_fragment_context_sources.json"
    if not config_path.exists():
        return {"applied": 0, "packets": 0}
    config = json.loads(config_path.read_bytes())
    if config["format_version"] != 1:
        raise ValueError("Unsupported GP context source configuration")
    reviews, checked_sources = {}, {}
    for entry in config["packets"]:
        loaded = load_packet(out, entry, checked_sources)
        if set(loaded).intersection(reviews):
            raise ValueError("Conflicting GP context packets")
        reviews.update(loaded)
    selected = {}
    for record in records:
        key = row_key(record)
        if key not in reviews:
            continue
        if key in selected:
            raise ValueError("Repeated target observation in GP context export")
        review = reviews[key]["review"]
        if record.get("office_normalized") not in {"PANCH", "SARPANCH"}:
            raise ValueError("GP context cannot be applied to another office")
        if any(
            field not in record
            or not matches(record[field], review["expected_raw"][field])
            for field in RAW_FIELDS
        ):
            raise ValueError(f"GP context raw-cell precondition failed: {key}")
        selected[key] = record
    if set(selected) != set(reviews):
        raise ValueError("A reviewed GP observation is absent from the export")
    counts = Counter()
    for key, record in selected.items():
        item = reviews[key]
        review, doc = item["review"], item["document"]
        old_body = record.get("body_within_page")
        flags = set((record.get("quality_flags") or "").split(";")) - {""}
        record["body_before_gp_fragment_context_review"] = (
            None if bool(pd.isna(old_body)) else old_body
        )
        if not matches(old_body, review["body_source_raw"]):
            counts["body_values_changed"] += 1
        if "incoming_body_context_unvalidated" in flags:
            counts["incoming_body_holds_resolved"] += 1
        record["body_within_page"] = review["body_source_raw"]
        for field in ("body_source_raw", "block_source_raw", "district_source_raw"):
            record["gp_fragment_context_" + field] = review[field]
        record["gp_fragment_context_review_status"] = "applied"
        record["gp_fragment_context_review_file"] = item["packet_file"]
        record["gp_fragment_context_review_sha256"] = item["packet_sha256"]
        record["gp_fragment_context_evidence_json"] = json.dumps(
            {
                "context_source_sha256": review["context_source_sha256"],
                "notification_page": review["context_notification_page"],
                "body_page": review["context_body_page"],
                "target_page": review["context_target_page"],
                "archive_file": item["archive_file"],
                "archive_sha256": item["archive_sha256"],
                "page_chain": doc["page_chain"],
                "fragment_image": doc["fragment_image_path"],
                "counterpart_image": doc["counterpart_image_path"],
                "assignment_usable": False,
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
        record["gp_fragment_overlap_group_sha256"] = item["overlap_group"]
        record["gp_fragment_overlap_kind"] = "same_publication"
        flags.discard("incoming_body_context_unvalidated")
        flags.update(
            {
                "gp_fragment_context_source_reviewed_raw_preserved",
                "overlapping_source_observation_reconciliation_pending",
            }
        )
        if any(page.get("limitation") for page in doc["page_chain"]):
            flags.add("gp_context_chain_cropped_page_margin")
        record["quality_flags"] = ";".join(sorted(flags))
        counts["applied"] += 1
    return {
        **dict(counts),
        "packets": len(config["packets"]),
        "pdf_sources_pinned": len(checked_sources),
        "config_sha256": digest(config_path),
        "column_dictionary": COLUMN_DICTIONARY,
        "raw_identity_category_fields_modified": False,
        "same_publication_links_are_independent_accuracy_evidence": False,
    }
