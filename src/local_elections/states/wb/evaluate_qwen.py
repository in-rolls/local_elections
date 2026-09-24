"""Compare frozen local vision readings with separately recorded visual references.

The references are source readings by visual agents, not human double entry.
Sampling weights describe only the acquired office-cell frame, not West Bengal.
Ambiguous references are excluded by field, never counted as model errors.
"""

import argparse
import hashlib
import io
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.wb_qwen_review import PROMPT, fingerprint

BASE = ROOT / "data/wb/derived/qwen_review/expanded"


def indexed(rows, label):
    """Reject duplicate IDs before constructing an index that could hide them."""
    if not isinstance(rows, list):
        raise ValueError(f"{label} must contain a list of rows")
    result = {}
    for row in rows:
        sid = row.get("sample_id")
        if type(sid) is not int or sid < 1 or sid in result:
            raise ValueError(f"Invalid or duplicate sample ID in {label}: {sid}")
        result[sid] = row
    return result


def validated_manifest(sample, inference, rendered, root=ROOT):
    """Link inference geometry to the sample and bytes to the rendered manifest."""
    if set(inference) != set(sample) or set(rendered) != set(sample):
        raise ValueError("Manifest IDs do not match the frozen sample")
    output = {}
    fields = ("row_id", "source_path", "source_sha256", "source_page", "axis", "tier")
    for sid, source in sample.items():
        entry, raster = inference[sid], rendered[sid]
        for field in fields:
            if entry.get(field) != source[field] or raster.get(field) != source[field]:
                raise ValueError(f"Manifest source mismatch for {sid}: {field}")
        if (
            entry.get("bbox") != source["bbox"]
            or entry.get("bbox_units") != source["bbox_units"]
        ):
            raise ValueError(f"Inference geometry differs from frozen sample: {sid}")
        image_hash = hashlib.sha256(
            (root / raster["image_path"]).read_bytes()
        ).hexdigest()
        if image_hash != raster.get("image_sha256"):
            raise ValueError(f"Frozen rendered crop changed: {sid}")
        if entry["image_path"] != raster["image_path"]:
            raise ValueError(f"Inference image path differs from rendered crop: {sid}")
        if entry.get("image_sha256", image_hash) != image_hash:
            raise ValueError(f"Inference image hash differs from rendered crop: {sid}")
        output[sid] = entry | {"image_sha256": image_hash}
    return output


def validate_weights(sample, design):
    strata = defaultdict(list)
    for row in sample.values():
        strata[row["stratum"]].append(row)
    population = 0
    for rows in strata.values():
        frame_n = rows[0]["frame_n"]
        if not isinstance(frame_n, int) or frame_n < len(rows):
            raise ValueError("Invalid stratum population")
        for row in rows:
            if (
                row["frame_n"] != frame_n
                or row["sample_n"] != len(rows)
                or not math.isclose(row["sampling_weight"], frame_n / len(rows))
            ):
                raise ValueError("Frozen stratum allocation/weight mismatch")
        population += frame_n
    if (
        len(sample) != design["sample_size"]
        or len(strata) != design["strata"]
        or population != design["eligible_frame_cells"]
    ):
        raise ValueError("Frozen sampling design totals disagree")


def reference_memberships(sample):
    ids = sorted(sample)
    return {
        "gold_a.json": set(ids[:100] + ids[100:110]),
        "gold_b.json": set(ids[100:] + ids[:10]),
    }


def validate_reference_image(row, manifest):
    sid = row["sample_id"]
    if row.get("image_sha256") != manifest[sid]["image_sha256"]:
        raise ValueError(f"Visual reference image hash missing or changed: {sid}")
    for field in ("axis", "source_sha256", "source_page"):
        if field in row and row[field] != manifest[sid][field]:
            raise ValueError(f"Visual reference provenance mismatch: {sid} {field}")
    reference = canonical_reference(row)
    allowed = (
        {None, "W"} if manifest[sid]["axis"] == "women" else {None, "SC", "ST", "BC"}
    )
    if reference["category"] not in allowed:
        raise ValueError(f"Visual reference category contradicts axis: {sid}")
    if reference["blank"] and (reference["name"] or reference["category"]):
        raise ValueError(f"Blank visual reference contains a named category: {sid}")


def normalized(value):
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def reading_fields(raw, axis):
    text = re.sub(r"\s+", " ", raw or "").strip()
    if not text or re.fullmatch(r"[-–—._|\s]+", text):
        return {"name": None, "category": None, "blank": True}
    match = re.search(r"(?:\s+|[-({\[]\s*)(SC|ST|BC|W)[)\]}\s.]*$", text, re.I)
    name = text[: match.start()].strip() if match else text
    marker = match[1].upper() if match else None
    return {
        "name": name,
        "category": "W" if axis == "women" else marker,
        "blank": False,
    }


def processed_image(entry, root=ROOT):
    image = (root / entry["image_path"]).read_bytes()
    if entry.get("image_sha256") and (
        hashlib.sha256(image).hexdigest() != entry["image_sha256"]
    ):
        raise ValueError("Frozen source crop changed")
    rotation = entry.get("image_rotation_clockwise", 0)
    if rotation not in {0, 90, 180, 270}:
        raise ValueError("Unsupported source orientation")
    if rotation:
        with Image.open(io.BytesIO(image)) as original:
            encoded = io.BytesIO()
            original.rotate(-rotation, expand=True).save(encoded, format="PNG")
            image = encoded.getvalue()
    return image


def find_reading(entry, directory, model_digest, root=ROOT):
    key = fingerprint(processed_image(entry, root), model_digest, PROMPT)
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
    path = directory / f"{digest}.json"
    if not path.exists():
        return None
    saved = json.loads(path.read_text())
    if saved["fingerprint"] != key:
        raise ValueError("Prediction fingerprint mismatch")
    payload = saved["response"]["response"]
    try:
        raw = json.loads(payload)
        if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
            raise ValueError("Model response lacks a text string")
    except (json.JSONDecodeError, ValueError) as error:
        return {"text": payload, "cache": str(path), "parse_error": str(error)}
    return {"text": raw["text"], "cache": str(path), "parse_error": None}


def canonical_reference(row):
    if "raw_transcription" in row:
        return {
            "name": row["name"],
            "category": "W" if row.get("women_reserved") else row.get("caste_code"),
            "blank": row["status"] in {"blank", "dash", "nondata"},
            "name_ambiguous": row["status"] == "ambiguous",
            "category_ambiguous": row.get(
                "category_ambiguous",
                row["status"] == "ambiguous"
                and not row.get("women_reserved")
                and row.get("caste_code") is None,
            ),
            "blank_ambiguous": row.get(
                "blank_ambiguous",
                row["status"] == "ambiguous"
                and row.get("name") is None
                and not row.get("women_reserved")
                and row.get("caste_code") is None,
            ),
        }
    return {
        "name": row.get("exact_printed_name"),
        "category": row.get("category_explicit"),
        "blank": row.get("blank", False) or row.get("nondata", False),
        "name_ambiguous": row.get("ambiguous", False),
        "category_ambiguous": row.get(
            "category_ambiguous",
            row.get("ambiguous", False) and row.get("category_explicit") is None,
        ),
        "blank_ambiguous": row.get(
            "blank_ambiguous",
            row.get("ambiguous", False)
            and row.get("exact_printed_name") is None
            and row.get("category_explicit") is None,
        ),
    }


def same_reference(a, b):
    return all(
        normalized(a[key]) == normalized(b[key]) if key == "name" else a[key] == b[key]
        for key in (
            "name",
            "category",
            "blank",
            "name_ambiguous",
            "category_ambiguous",
            "blank_ambiguous",
        )
    )


def compare(prediction, reference):
    name = (
        None
        if reference["blank"] or reference["name_ambiguous"]
        else normalized(prediction["name"]) == normalized(reference["name"])
    )
    category = (
        None
        if reference["category_ambiguous"]
        else prediction["category"] == reference["category"]
    )
    blank = (
        None
        if reference.get("blank_ambiguous")
        else prediction["blank"] == reference["blank"]
    )
    return {
        "name_correct": name,
        "category_correct": category,
        "positive_category_correct": category
        if not reference["blank"] and not reference.get("blank_ambiguous")
        else None,
        "blank_correct": blank,
        "false_positive_on_blank": not prediction["blank"]
        if reference["blank"] and not reference.get("blank_ambiguous")
        else None,
        "whole_cell_correct": (
            None
            if reference["name_ambiguous"]
            or reference["category_ambiguous"]
            or reference.get("blank_ambiguous")
            else blank and category and (name if not reference["blank"] else True)
        ),
    }


def summarize(rows):
    metrics = {}
    for field in (
        "name_correct",
        "category_correct",
        "positive_category_correct",
        "blank_correct",
        "false_positive_on_blank",
        "whole_cell_correct",
    ):
        eligible = [r for r in rows if r.get(field) is not None]
        weight = sum(r["sampling_weight"] for r in eligible)
        metrics[field] = {
            "numerator": sum(r[field] for r in eligible),
            "denominator": len(eligible),
            "excluded": len(rows) - len(eligible),
            "design_weighted_fraction": (
                sum(r["sampling_weight"] * r[field] for r in eligible) / weight
                if weight
                else None
            ),
        }
        if field == "false_positive_on_blank":
            metrics[field]["denominator_definition"] = (
                "Unambiguously blank references with valid model responses; "
                "invalid responses are excluded, not labelled hallucinations"
            )
    return metrics


@command("validate", state="West Bengal", source="frozen_qwen_sample")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=BASE)
    args = parser.parse_args()
    directory = args.directory
    design = json.loads((directory / "design.json").read_text())
    sample_path = directory / "sample.json"
    if hashlib.sha256(sample_path.read_bytes()).hexdigest() != design["sample_sha256"]:
        raise ValueError("Frozen sample changed")
    sample = indexed(json.loads(sample_path.read_text()), "sample")
    validate_weights(sample, design)
    manifest = validated_manifest(
        sample,
        indexed(
            json.loads((directory / "inference_manifest.json").read_text()),
            "inference manifest",
        ),
        indexed(
            json.loads((directory / "manifest.json").read_text()), "render manifest"
        ),
    )
    references = defaultdict(list)
    provenance = {}
    memberships = reference_memberships(sample)
    for filename in ("gold_a.json", "gold_b.json"):
        content = (directory / filename).read_bytes()
        provenance[filename] = hashlib.sha256(content).hexdigest()
        decoded = json.loads(content)
        rows = indexed(
            decoded.get("rows") if isinstance(decoded, dict) else decoded, filename
        )
        if set(rows) != memberships[filename]:
            raise ValueError(f"Visual reviewer membership mismatch: {filename}")
        for row in rows.values():
            sid = row["sample_id"]
            validate_reference_image(row, manifest)
            references[sid].append((filename, canonical_reference(row)))
    if set(references) != set(sample):
        raise ValueError("Visual references do not cover the frozen sample")
    adjudication_path = directory / "adjudications.json"
    adjudications = (
        indexed(json.loads(adjudication_path.read_text()), "adjudications")
        if adjudication_path.exists()
        else {}
    )
    if not set(adjudications) <= set(sample):
        raise ValueError("Adjudication IDs outside frozen sample")
    for row in adjudications.values():
        validate_reference_image(row, manifest)
    if adjudication_path.exists():
        provenance[adjudication_path.name] = hashlib.sha256(
            adjudication_path.read_bytes()
        ).hexdigest()
    caches = [
        json.loads(p.read_text()) for p in (directory / "readings").glob("*.json")
    ]
    digests = {c["fingerprint"]["model_digest"] for c in caches}
    if len(digests) != 1:
        raise ValueError("Expected a single frozen vision model digest")
    model_digest = digests.pop()
    results, overlap, missing = [], [], []
    for sid, source in sample.items():
        candidates = references[sid]
        reference = candidates[0][1]
        if len(candidates) == 2:
            agrees = same_reference(reference, candidates[1][1])
            overlap.append({"sample_id": sid, "agrees": agrees, "readings": candidates})
            if not agrees and sid not in adjudications:
                raise ValueError(
                    f"Unadjudicated independent visual disagreement: {sid}"
                )
        if sid in adjudications:
            reference = canonical_reference(adjudications[sid])
        prediction = find_reading(manifest[sid], directory / "readings", model_digest)
        if prediction is None:
            missing.append(sid)
            continue
        for engine, raw in (
            ("qwen", prediction["text"]),
            ("tesseract_baseline", source["baseline_reading"]),
        ):
            fields = reading_fields(raw, source["axis"])
            scores = compare(fields, reference)
            parse_error = prediction["parse_error"] if engine == "qwen" else None
            if parse_error:
                scores = {
                    key: None
                    if value is None or key == "false_positive_on_blank"
                    else False
                    for key, value in scores.items()
                }
            results.append(
                {
                    "sample_id": sid,
                    "row_id": source["row_id"],
                    "engine": engine,
                    "raw_text": raw,
                    "predicted": fields,
                    "reference": reference,
                    "sampling_weight": source["sampling_weight"],
                    "district": source["district"],
                    "year": source["year"],
                    "axis": source["axis"],
                    "source_path": source["source_path"],
                    "source_page": source["source_page"],
                    "cache": prediction["cache"] if engine == "qwen" else None,
                    "parse_error": parse_error,
                    **scores,
                }
            )
    report = {
        "complete": not missing,
        "sample_size": len(sample),
        "predictions_available": len(results) // 2,
        "missing_sample_ids": missing,
        "design": design,
        "independent_overlap": overlap,
        "reference_method": (
            f"Blinded visual agents; {len(overlap)} overlap cells; "
            "not human double entry"
        ),
        "reference_file_sha256": provenance,
        "adjudicated_sample_ids": sorted(adjudications),
        "model_digest": model_digest,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "invalid_model_responses": sum(bool(r["parse_error"]) for r in results),
        "invalid_on_blank": sum(
            bool(r["parse_error"])
            and r["reference"]["blank"]
            and not r["reference"].get("blank_ambiguous")
            for r in results
        ),
        "metric_scope": (
            "Complete frozen sample"
            if not missing
            else "Available paired predictions only; missingness can bias "
            "weighted fractions"
        ),
        "normalization": "Case and repeated whitespace only; Roman numerals preserved",
        "field_extraction": (
            "Terminal category markers and their separators are removed from names. "
            "After source review, separator parsing was fixed to accept whitespace "
            "after a hyphen (sample 194); internal name hyphens remain intact. "
            "Frozen references and raw model predictions were not changed."
        ),
        "caution": (
            "Equal allocation across 70 strata is not a self-weighting sample. "
            "Weighted fractions describe the acquired eligible cell frame only. "
            "These are comparisons with visual references, not certified accuracy."
        ),
        "metrics": {
            engine: summarize([r for r in results if r["engine"] == engine])
            for engine in ("qwen", "tesseract_baseline")
        },
    }
    for filename, data in (("evaluation.json", report), ("comparisons.json", results)):
        (directory / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        json.dumps(
            {k: report[k] for k in ("complete", "predictions_available", "metrics")}
        )
    )


if __name__ == "__main__":
    main()
